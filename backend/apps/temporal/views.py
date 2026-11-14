import json
import os
import re

from datetime import date, datetime

from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.fields import DateTimeField
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from django.db.models import Count, DateField, Max, Min, Q, Sum
from django.db.models.functions import Cast

from rest_framework.exceptions import ValidationError

from . import timer as timer_service
from .constants import ATTRIBUTION_ORDER, DAILY_ROLE_VALUES, SOURCE_KIND_VALUES
from .models import OneDayPage, TaskMeta, TemporalTask, WeeklyTimeCache
from .serializers import (
    OneDayPageSerializer,
    TaskMetaSerializer,
    TemporalTaskSerializer,
    TimerSessionSerializer,
)
from .services import (
    CSVImportService,
    DailyLogAutoService,
    OneDayPageService,
    TaskNameError,
    TemporalStatsService,
    _ensure_task_meta,
    batches_of_kind,
    compute_daily_guards,
    contrib_excluded_names,
    delete_task_name,
    find_overlaps,
    list_record_sources,
    make_batch_id,
    rename_task_name,
    resolve_attribution,
    resolve_attribution_detail,
    resolve_task_meta,
)


def _build_contrib_response(rows):
    """rows: [(date, value), ...] → 贡献图统一响应"""
    data = [{'date': d.isoformat(), 'value': round(float(v), 2)} for d, v in rows]
    min_year = min((d.year for d, _ in rows), default=datetime.now().year)
    max_year = max((d.year for d, _ in rows), default=datetime.now().year)
    summary = {
        'total_days': len(data),
        'max_date': max(data, key=lambda x: x['value'])['date'] if data else None,
        'max_value': max((x['value'] for x in data), default=0),
    }
    return {'min_year': min_year, 'max_year': max_year, 'data': data, 'summary': summary}


def _build_dominant_attr_response(day_map: dict) -> dict:
    """主导归因模式：每天取时长最多的 L1 归因作为该日颜色

    - value 仍是当天总时长（供「峰值」展示与排序用），着色不用它
    - attr 为 null 表示当天无任何已归因时长（未归类日），前端画灰格
    - 并列最多时按 ATTRIBUTION_ORDER（价值序，见 constants.py）取靠前者
    """
    data = []
    for d in sorted(day_map):
        v = day_map[d]
        # 先四舍五入到 2 位小数再比较：保证「格子颜色」与悬浮提示里展示的 breakdown 完全一致，
        # 不会出现提示里两值看着并列、颜色却按浮点尾数分了个胜负的情况
        ah = {k: round(v['attr_hours'][k], 2) for k in ATTRIBUTION_ORDER}
        best_key, best_val = None, 0.0
        for k in ATTRIBUTION_ORDER:      # 严格大于 → 并列时保留价值序靠前者
            if ah[k] > best_val:
                best_key, best_val = k, ah[k]
        breakdown = dict(ah)
        if v['unclassified'] > 0:
            breakdown['未归类'] = round(v['unclassified'], 2)
        data.append({
            'date': d.isoformat(),
            'value': round(float(v['hours']), 2),
            'attr': best_key,
            'breakdown': breakdown,
        })
    attr_days = {k: sum(1 for x in data if x['attr'] == k) for k in ATTRIBUTION_ORDER}
    unclassified_days = sum(1 for x in data if x['attr'] is None)
    min_year = min((d.year for d in day_map), default=datetime.now().year)
    max_year = max((d.year for d in day_map), default=datetime.now().year)
    return {
        'min_year': min_year, 'max_year': max_year,
        'metric': 'dominant_attr', 'mode': 'attribution', 'data': data,
        'summary': {
            'total_days': len(data),
            'max_date': max(data, key=lambda x: x['value'])['date'] if data else None,
            'max_value': max((x['value'] for x in data), default=0),
            'attr_days': attr_days,
            'unclassified_days': unclassified_days,
        },
    }


class TemporalTaskViewSet(viewsets.ModelViewSet):
    """任务时间记录视图集（清单 CRUD：列表/新增/编辑/删除，备注 notes 可编辑）"""

    queryset = TemporalTask.objects.all()
    permission_classes = [AllowAny]
    serializer_class = TemporalTaskSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['task_name', 'task_description', 'notes']
    ordering_fields = ['start_time', 'duration_hours', 'year', 'mon']
    ordering = ['-start_time']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        year = params.get('year')
        if year:
            qs = qs.filter(year=int(year))

        month = params.get('month')
        if month:
            qs = qs.filter(mon=month)

        # 三层过滤：L1 归因(attribution) / L2 活动类型(activity_type) / L3 task_name
        activity_type = params.get('activity_type')
        if activity_type:
            names = list(TaskMeta.objects.filter(activity_type=activity_type).values_list('task_name', flat=True))
            qs = qs.filter(task_name__in=names)

        attribution = params.get('attribution')
        if attribution:
            # order_by() 清序：避免 Django 把 start_time 注入 DISTINCT 列致去重失效
            all_names = list(qs.order_by().values_list('task_name', flat=True).distinct())
            names = [tn for tn, a in resolve_attribution(all_names).items() if a == attribution]
            qs = qs.filter(task_name__in=names)

        unclassified = params.get('unclassified')
        if unclassified in ('1', 'true', 'True'):
            names = list(TaskMeta.objects.filter(activity_type='未归类').values_list('task_name', flat=True))
            qs = qs.filter(task_name__in=names)

        task_name = params.get('task_name')
        if task_name:
            qs = qs.filter(task_name=task_name)

        # v3.64.33 来源筛选：表里没有 kind 列（外部表加不了列），
        # 只能把 kind 翻回批次号再筛 —— 唯一实现是 `services.batches_of_kind`。
        source = params.get('source')
        if source:
            if source not in SOURCE_KIND_VALUES:
                # 🔴 认不出的来源值**必须报错**，不能返回空列表：
                #    空列表会被读成「这个来源一条都没有」，而真相是「这个词拼错了」。
                raise ValidationError({'source': f'未知来源：{source}'})
            if source == 'unlabeled':
                # `import_batch__in=[None]` 生成 `IN (NULL)`，**永远不匹配** ——
                # 本库里「未标注」同时有 NULL 与空串两种存法，一并算进来。
                qs = qs.filter(Q(import_batch__isnull=True) | Q(import_batch=''))
            else:
                batches = [b for b in batches_of_kind(source) if b]
                # 该来源名下确实一条都没有时，`__in=[]` 是正确的空结果（不是拼写问题）
                qs = qs.filter(import_batch__in=batches)

        # 批次级钻取（来源批次弹窗里「看这 N 条」）：与 source 是**交集**，
        # 同时传 = 「该来源下的这一批」。空串视为未选择（前端 clearable 时会传空）。
        batch = params.get('import_batch')
        if batch:
            qs = qs.filter(import_batch=batch)

        date_from = params.get('date_from')
        if date_from:
            # datetime 区间直接比较（规避 __date 触发 CONVERT_TZ 时区转换返回 NULL）
            # make_aware：历史数据为本地时间，避免 naive datetime 警告
            qs = qs.filter(start_time__gte=timezone.make_aware(
                datetime.combine(datetime.strptime(date_from, '%Y-%m-%d').date(), datetime.min.time())))

        date_to = params.get('date_to')
        if date_to:
            qs = qs.filter(start_time__lte=timezone.make_aware(
                datetime.combine(datetime.strptime(date_to, '%Y-%m-%d').date(), datetime.max.time())))

        return qs

    # ─── 手工新增 / 编辑（v3.58.6）───────────────────────────────────────────
    # 时长与日历字段由 TemporalTaskSerializer.validate 从起止时间派生；
    # 这里只补一件事：新出现的 task_name 要进 TaskMeta，否则分类台账 / 映射编辑器看不到它。

    @staticmethod
    def _ensure_meta_for(task_name: str | None):
        """为新 task_name 补 TaskMeta（未命中映射表则进「未归类」桶）。幂等。"""
        if task_name:
            _ensure_task_meta([task_name])

    def perform_create(self, serializer):
        instance = serializer.save()
        # v3.64.33：手工新增要**自报家门**。`import_batch` 是 read_only（防前端伪造来源），
        # 所以只能在保存后补写。不写的话手工记录会和「早期来源不明」混成同一个空值桶，
        # 以后再想分清「这条是我敲的、还是老数据」就只能靠猜。
        if not instance.import_batch:
            TemporalTask.objects.filter(id=instance.id).update(import_batch='manual')
            instance.import_batch = 'manual'
        self._ensure_meta_for(instance.task_name)

    def perform_update(self, serializer):
        old_name = serializer.instance.task_name
        instance = serializer.save()
        # 改名：新名字补建档；旧名字的 TaskMeta 不自动删（分类字典由用户在映射编辑器里维护）
        if instance.task_name and instance.task_name != old_name:
            self._ensure_meta_for(instance.task_name)

    @action(detail=False, methods=['get'])
    def sources(self, request):
        """来源总览：全库按批次 + 按来源类型汇总（「来源可见」弹窗唯一取数口）。

        读的是 `import_batch` 一列（外部表没有 kind 列），分类在
        `services.classify_source`。**只读、不写库**。

        为什么单独给一个接口而不是让前端从任务列表自己数：
        列表是分页的，数出来的「41 条未标注」只是当前页 —— 而用户要的正是全库口径。
        """
        return Response(list_record_sources())

    @action(detail=False, methods=["get"])
    def daily_detail(self, request):
        """每日明细：按日期查当日的**全部**时间任务。

        `?scope=contrib`（v3.60.27）：改用**贡献图口径** —— 排除不计入贡献图的睡眠类
        任务（`services.contrib_excluded_names()`，常量名单 ∪ 角色为睡眠类的任务）。
        贡献图点格子弹的明细走这个。

        ⚠️ 默认不传 = 当天全部任务，行为与从前一致。这是**故意的**：本接口语义是
        「那天我记了什么」，将来别处（任务清单等）复用时不该莫名其妙少几行 ——
        而「少行且不报错」正是本项目反复防的那类静默失败。
        """
        from datetime import datetime
        from django.utils import timezone

        date_str = request.query_params.get('date')
        if not date_str:
            return Response({'error': 'date 参数必填'}, status=400)
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'date 格式 YYYY-MM-DD'}, status=400)
        ws = timezone.make_aware(datetime.combine(d, datetime.min.time()))
        we = timezone.make_aware(datetime.combine(d, datetime.max.time()))
        qs = TemporalTask.objects.filter(start_time__gte=ws, start_time__lte=we)
        if request.query_params.get('scope') == 'contrib':
            qs = qs.exclude(task_name__in=contrib_excluded_names())
        qs = qs.order_by('start_time')
        meta = resolve_task_meta([t.task_name for t in qs])
        attr = resolve_attribution([t.task_name for t in qs])
        items = [{
            'id': t.id,
            'start_time': t.start_time.isoformat() if t.start_time else None,
            'end_time': t.end_time.isoformat() if t.end_time else None,
            'task_name': t.task_name,
            'category_level1': t.category_level1,
            'category_level2': t.category_level2 or '',
            'activity_type': (meta.get(t.task_name) or {}).get('activity_type'),
            'attribution': attr.get(t.task_name),
            'duration_hours': round(t.duration_hours or 0, 2),
            'notes': t.notes or '',
        } for t in qs]
        return Response({
            'date': date_str,
            'total': round(sum(x['duration_hours'] for x in items), 2),
            'items': items,
        })

    @action(detail=False, methods=["get"])
    def contrib(self, request):
        """贡献图：单日聚合，支持 ?metric=hours|record_count|toward|deepwork|work|dominant_attr（默认 hours）

        work（牛马工作）：按 L3 任务名「牛马工作」聚合单日小时数（v3.58.14 替换原 sleep 指标；
        改走 task_name 而非 L2 类型，故与 attr_hours['谋生'] 不等价——后者含其他谋生类任务）。

        dominant_attr（主导归因）：不按量值着色，而是给每天算六个 L1 归因的小时数，
        取最多者作为当天「主导归因」（并列按 ATTRIBUTION_ORDER 的价值序取靠前者）；
        六者全为 0 的日子 attr 返回 null，前端显示为「未归类」灰格。

        🔴 v3.60.27：睡眠类任务**不计入本图**（`services.contrib_excluded_names()`）。
        它们的 L2 = 主动休息 ⇒ 归因 = 维持，每天 8h 会让热力图几乎天天是「维持」色，
        把真正想看的结构压掉。**六个口径一律排除**（同一处 queryset，不会只改一半）。
        ⚠️ 只剔本图：时间统计页的总时长 / 完整度 / 旭日图 / 趋势 / 168h 结构仍含睡眠。
        """
        metric = request.query_params.get('metric', 'hours')
        rows = list(
            TemporalTask.objects.exclude(start_time__isnull=True)
            # 睡眠类不计入贡献图 —— 单一真源在 services.contrib_excluded_names()
            .exclude(task_name__in=contrib_excluded_names())
            .annotate(d=Cast('start_time', DateField()))
            .values('d', 'task_name', 'duration_hours')
            .order_by('d')
        )
        meta = resolve_task_meta([r['task_name'] for r in rows])
        attr = resolve_attribution([r['task_name'] for r in rows])
        day_map: dict = {}
        for r in rows:
            d = r['d']
            h = float(r['duration_hours'] or 0)
            tn = r['task_name']
            at = (meta.get(tn) or {}).get('activity_type')
            a = attr.get(tn)
            bucket = day_map.setdefault(d, {
                'hours': 0.0, 'count': 0, 'toward': 0.0, 'deepwork': 0.0, 'work': 0.0,
                'attr_hours': {k: 0.0 for k in ATTRIBUTION_ORDER},
                'unclassified': 0.0,
            })
            bucket['hours'] += h
            bucket['count'] += 1
            # 响应字段名沿用 toward（英文标识），语义即「成长」
            if a == '成长':
                bucket['toward'] += h
            if at == '深度工作':
                bucket['deepwork'] += h
            # 牛马工作：L3 任务名精确匹配（v3.58.14 起替代原「睡眠」指标）
            if tn == '牛马工作':
                bucket['work'] += h
            # 主导归因：L2 类型为「未归类」或无 TaskMeta 的归因视为未定，不参与归因桶
            if at and at != '未归类' and a in bucket['attr_hours']:
                bucket['attr_hours'][a] += h
            else:
                bucket['unclassified'] += h

        if metric == 'dominant_attr':
            return Response(_build_dominant_attr_response(day_map))

        metric_key = {
            'hours': 'hours', 'record_count': 'count', 'toward': 'toward',
            'deepwork': 'deepwork', 'work': 'work',
        }.get(metric, 'hours')
        # 未知/已下线的 metric（含旧的 sleep）一律回落到 hours 取值口径，不报错
        data = [{'date': d.isoformat(), 'value': round(float(v[metric_key]), 2)} for d, v in day_map.items()]
        min_year = min((d.year for d in day_map), default=datetime.now().year)
        max_year = max((d.year for d in day_map), default=datetime.now().year)
        return Response({
            'min_year': min_year, 'max_year': max_year, 'metric': metric, 'mode': 'value', 'data': data,
            'summary': {
                'total_days': len(data),
                'max_date': max(data, key=lambda x: x['value'])['date'] if data else None,
                'max_value': max((x['value'] for x in data), default=0),
            },
        })

    @action(detail=False, methods=['get'])
    def task_names(self, request):
        """获取所有不重复的任务名称"""
        names = TemporalTask.objects.values_list('task_name', flat=True).distinct().order_by('task_name')
        return Response(list(names))

    @action(detail=False, methods=['get'])
    def frequent_names(self, request):
        """最近 N 个月最频繁的任务名 —— 手工新增弹窗的快捷单选候选

        `?months=3&limit=10`（均可选）。排序与窗口口径在
        `TemporalStatsService.get_frequent_names`，本视图只做参数校验。

        ⚠️ 参数写错必须返 400、不能静默回退默认值：否则「写错了」看起来就是
        「这段时间没有常用任务」，用户会以为候选功能坏了。
        """
        raw_months = request.query_params.get('months', '3')
        raw_limit = request.query_params.get('limit', '10')
        try:
            months = int(raw_months)
            limit = int(raw_limit)
        except (TypeError, ValueError):
            return Response(
                {'detail': 'months / limit 必须是整数'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not 1 <= months <= 24 or not 1 <= limit <= 30:
            return Response(
                {'detail': 'months 取 1~24、limit 取 1~30'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(TemporalStatsService.get_frequent_names(months, limit))

    @action(detail=False, methods=['get'])
    def check_overlap(self, request):
        """新增/编辑前查「这段时间有没有别的记录」—— **只读**，不写库、不阻断保存。

        `?start_time=2026-10-21 09:50:00&end_time=2026-10-21 10:50:00
          &exclude_id=12&task_name=看小说`（后两个可选）

        响应：`{has_overlap, conflicts:[{id,task_name,start_time,end_time,
        overlap_minutes,same_name}], same_name_count}`

        🔴 为什么放在**写入之前查**、而不是在 create 里 409 硬拦：
        本库真实数据里重叠是**合法形态**（「牛马工作 07:46-18:00」之内再细分
        「代码编程」），且 CSV 导入 / 计时器入账 / 加班重构走的是同一张表 ——
        在写入路径上设闸门，等于把用户补记细分记录的路一起堵死。
        所以这里只回答「重叠了哪些」，由前端把选择权交回用户。
        口径在 `services.find_overlaps`（单一真源），本视图只做参数校验。
        """
        params = request.query_params
        raw_start = (params.get('start_time') or '').strip()
        raw_end = (params.get('end_time') or '').strip()
        if not raw_start or not raw_end:
            return Response(
                {'detail': 'start_time / end_time 必填'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        fmt = DateTimeField()
        try:
            start = fmt.run_validation(raw_start)
            end = fmt.run_validation(raw_end)
        except Exception:
            return Response(
                {'detail': '时间格式应为 YYYY-MM-DD HH:MM:SS'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if end <= start:
            return Response(
                {'detail': '结束时间必须晚于开始时间'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_exclude = params.get('exclude_id')
        exclude_id = None
        if raw_exclude:
            try:
                exclude_id = int(raw_exclude)
            except (TypeError, ValueError):
                return Response(
                    {'detail': 'exclude_id 必须是整数'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        conflicts = find_overlaps(
            start, end,
            exclude_id=exclude_id,
            task_name=(params.get('task_name') or '').strip() or None,
        )
        return Response({
            'has_overlap': bool(conflicts),
            'conflicts': conflicts,
            'same_name_count': sum(1 for c in conflicts if c['same_name']),
        })

    @action(detail=False, methods=['post'])
    def preview_import(self, request):
        """CSV 导入**预演**（只读）：先看这份文件会撞上什么，再决定要不要落。

        multipart：`file`（必填）。**不接受** `skip_rows` —— 这一层不写库。

        响应分三个维度：
        - `summary`：`total = already_exists + clean + contained + edge + review + likely_dup`
        - `rows`：**只含需要人看/需要知道的行**（clean 与 already_exists 只有计数）
        - `inner_duplicate`：同一份 CSV 内部重复的条数（落库时会丢弃）

        🔴 为什么不在这一层「自动选好跳过哪些」：跳过等于**不要这份数据**，
           是价值判断。预演只做分拣与排序，勾选留给人。
        """
        file = request._request.FILES.get('file')
        if not file:
            return Response(
                {'error': '请上传文件'}, status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = CSVImportService().preview_from_csv(file)
        except Exception as e:                      # noqa: BLE001 —— 兜住解析层的任何意外
            print(f'[CSV 预演] 处理异常: {type(e).__name__}: {e}')
            return Response(
                {'error': f'预演失败：{str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        if result.get('error'):
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)

    @action(detail=False, methods=['post'])
    def import_csv(self, request):
        """CSV 导入任务记录（使用 Django 原生 multipart 解析，绕过 DRF 限制）

        multipart：`file`（必填）、`skip_rows`（可选，JSON 数组 / 逗号分隔的行号）。
        `skip_rows` 里的行号必须属于本次解析结果，否则 400 —— 见 service 里的注释。
        """
        file = request._request.FILES.get('file')
        if not file:
            print(f'[CSV 导入] request.FILES: {dict(request._request.FILES)}')
            return Response({'error': '请上传文件'}, status=status.HTTP_400_BAD_REQUEST)

        print(f'[CSV 导入] 文件: name={file.name}, size={file.size}, content_type={file.content_type}')

        raw_skip = (request._request.POST.get('skip_rows') or '').strip()
        skip_rows = []
        if raw_skip:
            try:
                parsed = json.loads(raw_skip)
                skip_rows = parsed if isinstance(parsed, list) else [parsed]
            except json.JSONDecodeError:
                # 退一步认逗号分隔（前端 / curl 手敲都可能走这条）
                skip_rows = [s for s in raw_skip.split(',') if s.strip()]

        # v3.64.33：批次号带日期（`import_20261107_1832_ab12`），批次清单里能按时间对上；
        # 前缀仍是 `import_`，按前缀分类与按批次回滚都不受影响。
        batch_id = make_batch_id()

        service = CSVImportService()
        try:
            result = service.import_from_csv(file, batch_id, skip_rows=skip_rows)
        except Exception as e:
            print(f'[CSV 导入] 处理异常: {type(e).__name__}: {e}')
            import traceback
            traceback.print_exc()
            return Response({'error': f'导入处理异常：{str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if 'error' in result:
            return Response({'error': result['error']}, status=status.HTTP_400_BAD_REQUEST)

        print(f'[CSV 导入] 完成: 新增 {result["inserted"]}, 更新 {result["updated"]}')
        # 把批次号回给前端：导入成功提示里直接写「本批 import_20261107_1832_ab12」，
        # 事后在「来源批次」弹窗里能按号找到它（否则用户只能凭日期猜是哪一批）。
        result['batch'] = batch_id
        return Response(result, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """统计总览"""
        year = request.query_params.get('year')
        if year:
            year = int(year)
        data = TemporalStatsService.get_overview(year)
        return Response(data)

    @action(detail=False, methods=['get'])
    def trend(self, request):
        """趋势数据，支持 ?level=l1|l2（默认 l1 按 L1 分组堆叠）"""
        year = request.query_params.get('year')
        group = request.query_params.get('group', 'month')
        level = request.query_params.get('level', 'l1')
        if year:
            year = int(year)
        data = TemporalStatsService.get_trend(year, group, level)
        return Response(data)

    @action(detail=False, methods=['get'])
    def balance(self, request):
        """平衡轮数据"""
        year = request.query_params.get('year')
        if year:
            year = int(year)
        data = TemporalStatsService.get_balance(year)
        return Response(data)

    @action(detail=False, methods=['get'])
    def ranking(self, request):
        """任务排行"""
        year = request.query_params.get('year')
        limit = request.query_params.get('limit', 10)
        if year:
            year = int(year)
        data = TemporalStatsService.get_ranking(year, int(limit))
        return Response(data)

    @action(detail=False, methods=['get'])
    def distribution(self, request):
        """时段分布"""
        year = request.query_params.get('year')
        if year:
            year = int(year)
        data = TemporalStatsService.get_distribution(year)
        return Response(data)

    @action(detail=False, methods=['get'])
    def calendar(self, request):
        """日历热力图"""
        year = request.query_params.get('year')
        if year:
            year = int(year)
        data = TemporalStatsService.get_calendar(year)
        return Response(data)

    @action(detail=False, methods=['get'])
    def meta(self, request):
        """L2 活动类型映射清单（分页）"""
        qs = TaskMeta.objects.all()
        name = request.query_params.get('name')
        if name:
            qs = qs.filter(task_name__icontains=name)
        unclassified_only = request.query_params.get('unclassified_only')
        if unclassified_only in ('1', 'true', 'True'):
            qs = qs.filter(activity_type='未归类')
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(TaskMetaSerializer(page, many=True).data)
        return Response(TaskMetaSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'])
    def meta_ledger(self, request):
        """分类台账：全量 task_name → L1 归因 / L2 类型 + 真实使用量

        与 /meta/（纯字典分页）的区别：带上累计时长·记录次数·单次均时·最近使用，
        以及「有效归因 + 来源（赎回期规则/类型默认/兜底）」；「未归类」只是其中一个筛选态。
        概要（summary）恒为全量口径，不受筛选影响，供页面筛选条与占比展示。
        """
        metas = list(TaskMeta.objects.all())
        names = [m.task_name for m in metas]
        # ⚠️ 显式 order_by() 清序：外部表 Meta.ordering = ['-start_time']，聚合查询须固定排序口径
        agg = {
            r['task_name']: r for r in TemporalTask.objects.filter(task_name__in=names)
            .values('task_name')
            .annotate(total_hours=Sum('duration_hours'), record_count=Count('id'), last_used=Max('start_time'))
            .order_by()
        }
        detail = resolve_attribution_detail(names)

        rows = []
        for m in metas:
            a = agg.get(m.task_name) or {}
            hours = round(float(a.get('total_hours') or 0), 2)
            cnt = int(a.get('record_count') or 0)
            last = a.get('last_used')
            d = detail.get(m.task_name) or {}
            rows.append({
                'task_name': m.task_name,
                'activity_type': m.activity_type,
                'default_attribution': m.default_attribution,
                'effective_attribution': d.get('attribution'),
                'attribution_source': d.get('source'),
                # 🔴 「没配归因」必须是一个**独立可筛的状态**（v3.64.28）。
                #    从前界面只下发 effective_attribution，于是兜底值和真配的值
                #    长得一模一样：用户点「去归好」进来，看到 L1 那格明明白白写着
                #    「成长」，以为早就配好了 —— 而库里是 NULL。同一屏上账本说
                #    「没设默认归因」、编辑器说「已配」，两个都对不上。
                'is_attr_unset': d.get('source') == 'fallback',
                'is_unclassified': m.activity_type == '未归类',
                'is_system': m.is_system,
                # 🔴 「成长计时」= 每周状态里「成长小时数」的**唯一依据**（v3.64.11）。
                #    以前这条口径是隐式的「L2 = 深度工作」，界面上看不见
                #    ⇒ 想拉一个新分类进来，只能把它塞进「深度工作」桶。
                'counts_growth': m.counts_growth,
                # 🔴 「今天的三条线」的角色（v3.64.12）：空白 = 不参与护栏。
                #    阈值不在这里、也不下发给前端 —— 角色只管「进哪条线」。
                'daily_role': m.daily_role,
                'total_hours': hours,
                'record_count': cnt,
                'avg_minutes': round(hours * 60 / cnt, 1) if cnt else 0.0,
                'last_used': last.date().isoformat() if last else None,
            })

        summary = {
            'total': len(rows),
            'classified': sum(1 for r in rows if not r['is_unclassified']),
            'unclassified': sum(1 for r in rows if r['is_unclassified']),
            'total_hours': round(float(sum(r['total_hours'] for r in rows)), 2),
            'unclassified_hours': round(float(sum(r['total_hours'] for r in rows if r['is_unclassified'])), 2),
            # 成长计时的口径小计：用户改开关时，能立刻看到「这一下动了多少量」
            'growth_count': sum(1 for r in rows if r['counts_growth']),
            'growth_hours': round(float(sum(r['total_hours'] for r in rows if r['counts_growth'])), 2),
            # 没配 L1 归因的任务名：行数 + 小时。与「未归类」并列 —— 一个是 L2 没配、
            # 一个是 L1 没配，都该在人能看见的地方计数，否则只能等账本报「兜底 Xh」。
            'unset_attr_count': sum(1 for r in rows if r['is_attr_unset']),
            'unset_attr_hours': round(float(sum(r['total_hours'] for r in rows if r['is_attr_unset'])), 2),
            # 三条线的「标了几条」：都标了才发现某条一直显示未记录 = 真的没做，
            # 而不是「忘了标」。没标的任务名不进任何一条线。
            'role_count': sum(1 for r in rows if r['daily_role']),
            'by_attribution': {
                a: round(float(sum(r['total_hours'] for r in rows if r['effective_attribution'] == a)), 2)
                for a in ATTRIBUTION_ORDER
            },
        }

        # ── 筛选（全部在内存做，与 summary 口径一致；TaskMeta 量级为几十条）──
        keyword = (request.query_params.get('search') or '').strip().lower()
        activity_type = request.query_params.get('activity_type')
        attribution = request.query_params.get('attribution')
        unclassified_only = request.query_params.get('unclassified_only') in ('1', 'true', 'True')
        growth_only = request.query_params.get('growth_only') in ('1', 'true', 'True')
        # 只看「参与日常护栏」的任务名（三条线标错了在这找得到）
        role_only = request.query_params.get('role_only') in ('1', 'true', 'True')
        # 只看「没配 L1 归因」的任务名（按兜底计入的那些）
        unset_attr_only = request.query_params.get('unset_attr_only') in ('1', 'true', 'True')

        items = rows
        if keyword:
            items = [r for r in items if keyword in r['task_name'].lower()]
        if activity_type:
            items = [r for r in items if r['activity_type'] == activity_type]
        if attribution:
            items = [r for r in items if r['effective_attribution'] == attribution]
        if unclassified_only:
            items = [r for r in items if r['is_unclassified']]
        if growth_only:
            items = [r for r in items if r['counts_growth']]
        if role_only:
            items = [r for r in items if r['daily_role']]
        if unset_attr_only:
            items = [r for r in items if r['is_attr_unset']]
        items = sorted(items, key=lambda r: (-r['total_hours'], r['task_name']))

        return Response({'summary': summary, 'returned': len(items), 'items': items})

    @action(detail=False, methods=['get'])
    def daily_guards(self, request):
        """今天的三条线：睡眠 / 午睡 / 流失（v3.64.13）

        `?date=YYYY-MM-DD` 可回看某一天，不传 = 本地今天。

        🔴 三条线的角色、阈值、状态词全在 `constants.DAILY_GUARD_LINES` /
           `DAILY_GUARD_STATUS_TEXT`，本接口只做取数与判定。
        🔴 「流失」不看角色：直接读 L1 归因（玩游戏 / 刷短视频 / 看小说 都归流失），
           与贡献图、时间统计页同一把尺子。
        🔴 `unrecorded` **永远不等于达标**：当天没记就照实说没记，
           不拿 0 小时冒充「没流失」（`null` 与 `0` 是两件事）。
        """
        date_str = request.query_params.get('date')
        target = timezone.localdate()
        if date_str:
            try:
                target = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({'error': 'date 格式 YYYY-MM-DD'}, status=400)
        return Response(compute_daily_guards(target))

    @action(detail=False, methods=['get'])
    def unclassified(self, request):
        """未归类任务池：活动类型='未归类' 的 task_name 汇总（按真实时长）"""
        names = list(TaskMeta.objects.filter(activity_type='未归类').values_list('task_name', flat=True))
        agg = TemporalTask.objects.filter(task_name__in=names).values('task_name').annotate(
            total_hours=Sum('duration_hours'), record_count=Count('id'),
        ).order_by('-total_hours')
        data = [
            {'task_name': r['task_name'], 'total_hours': round(float(r['total_hours'] or 0), 2),
             'record_count': r['record_count']}
            for r in agg
        ]
        return Response({'count': len(data), 'items': data})

    @action(detail=False, methods=['post'])
    def batch_set_meta(self, request):
        """批量设 L3→L2(活动类型) + L1(归因)：只写 temporal_task_meta

        可选参数（台账单行编辑用，不传即保持旧行为）：
        - keep_default=True：只改活动类型，保留 default_attribution 原值（不写 None）
        - counts_growth=True/False：**只**改「成长计时」开关，可单独发（不带 activity_type）。
          不传 = 不动 —— 批量改 L2 时不会顺手把成长计时清零（`None ≠ False`）。
        - daily_role=''|'sleep_night'|'nap'：改「日常护栏角色」，同样可单独发、
          不传 = 不动。空串表示退出护栏（是**有效值**，不是「没传」）。

        🔴 v3.64.16：不再顺带往 `redemption_attr_rule` 写一条 priority=100 的规则。
           那套「外挂规则」已整体退役（见 `redemption/services.compute_time_attribution`
           的说明）—— 它是本接口写下的影子副本，却只覆盖被改过的少数任务名，
           让赎回期页面的六类小时静默漏数。归因现在只有 `default_attribution` 一处。
        """
        task_names = request.data.get('task_names') or []
        activity_type = request.data.get('activity_type')
        attribution = request.data.get('attribution')
        keep_default = request.data.get('keep_default') in (True, '1', 'true', 'True')
        # ── 成长计时开关（v3.64.11）──
        # 🔴 用 `None` 表示「这次不动」、`False` 表示「关掉」：
        #    又是 `null ≠ 0`。写成 `bool(data.get(...))` 会让「不传」变成「全部关掉」，
        #    一次批量改 L2 就顺手把成长计时清零 —— 且不报错。
        growth_raw = request.data.get('counts_growth', None)
        has_growth = growth_raw is not None
        growth_value = growth_raw in (True, '1', 'true', 'True', 1) if has_growth else None
        # ── 日常护栏角色（v3.64.12）──
        # 🔴 与上面同理用 `None` 表「不动」：`''` 是**合法值**（退出护栏），
        #    写成 `if not role:` 会让「退出护栏」变成「什么都没发生」。
        role_raw = request.data.get('daily_role', None)
        has_role = role_raw is not None
        role_value = (role_raw or '').strip() if has_role else None
        if has_role and role_value and role_value not in DAILY_ROLE_VALUES:
            return Response(
                {'error': f'daily_role 只能是：{"、".join(sorted(DAILY_ROLE_VALUES))} 之一（空串表示不参与）'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not task_names:
            return Response({'error': 'task_names 必填'}, status=status.HTTP_400_BAD_REQUEST)
        if not activity_type and not has_growth and not has_role:
            return Response(
                {'error': '至少要给 activity_type / counts_growth / daily_role 之一'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # 🔴 归因只在「改 L2 的同一请求」里写：脱离 activity_type 单发会被下面
        #    的「只改开关」分支吃掉，表现为接口 200、值没变 —— 宁可 400 说清。
        if attribution and not activity_type:
            return Response(
                {'error': '改归因必须同时带 activity_type（该任务名当前的 L2 类型）'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated = 0
        missing = []
        for tn in task_names:
            if activity_type:
                defaults = {'activity_type': activity_type}
                if not keep_default:
                    defaults['default_attribution'] = attribution or None
                if has_growth:
                    defaults['counts_growth'] = growth_value
                if has_role:
                    defaults['daily_role'] = role_value
                TaskMeta.objects.update_or_create(task_name=tn, defaults=defaults)
            else:
                # 只改开关：台账里每一行都已存在，**不新建**（否则会凭空多出「未归类」行）
                rows = list(TaskMeta.objects.filter(task_name=tn))
                if not rows:
                    missing.append(tn)
                    continue
                for row in rows:
                    # 逐个字段比对：只把**真的变了**的列写进 update_fields，
                    # 两个开关同时发也不会互相覆盖（早退会在第一处改动后跳过第二处）
                    changed = []
                    if has_growth and row.counts_growth != growth_value:
                        row.counts_growth = growth_value
                        changed.append('counts_growth')
                    if has_role and row.daily_role != role_value:
                        row.daily_role = role_value
                        changed.append('daily_role')
                    if changed:
                        # auto_now 字段必须写进 update_fields，否则时间戳不落库
                        row.save(update_fields=[*changed, 'updated_at'])
            updated += 1
        if missing and not updated:
            # 一条都没改成 ⇒ 如实报错，不返回「已更新 0 个」让人以为生效了
            return Response(
                {'error': f'这些任务名不在映射表里：{"、".join(missing[:5])}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({'updated': updated, 'missing': missing,
                         'activity_type': activity_type, 'attribution': attribution,
                         'counts_growth': growth_value, 'daily_role': role_value})

    @action(detail=False, methods=['post'])
    def rename_task_name(self, request):
        """改名 / 合并：把一个任务名变成另一个（v3.64.55）

        `{task_name, new_name, dry_run?}` —— 新名已存在时就是**合并**（记录并过去、源行删掉）。

        `dry_run=1` 只算不写：弹窗的「影响预览」和真执行走**同一份判据**，
        否则前端自己拿台账行去猜「这个名字有没有人用过」，一旦列表被筛选过就会猜错
        （猜「改名」而实际执行了「合并」，用户点确定前看到的是一回事，做完是另一回事）。

        `TemporalTask` 是外部表（`managed=False`）但可以写：这里只改 `task_name` 一列。
        """
        task_name = (request.data.get('task_name') or '').strip()
        new_name = request.data.get('new_name') or ''
        if not task_name:
            return Response({'error': 'task_name 必填'}, status=status.HTTP_400_BAD_REQUEST)
        dry_run = request.data.get('dry_run') in (True, '1', 'true', 'True', 1)
        try:
            return Response(rename_task_name(task_name, new_name, dry_run=dry_run))
        except TaskNameError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def delete_task_name(self, request):
        """删一行台账 —— 只有名下 **0 条记录**时才允许（理由见 `services.delete_task_name`）"""
        task_name = (request.data.get('task_name') or '').strip()
        if not task_name:
            return Response({'error': 'task_name 必填'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            return Response(delete_task_name(task_name))
        except TaskNameError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def sunburst(self, request):
        """旭日/嵌套饼图数据：内圈 L1，外圈 L2"""
        year = request.query_params.get('year')
        if year:
            year = int(year)
        return Response(TemporalStatsService.get_sunburst(year))

    @action(detail=False, methods=['get'])
    def completeness(self, request):
        """记录完整度"""
        year = request.query_params.get('year')
        if year:
            year = int(year)
        return Response(TemporalStatsService.get_completeness(year))


class WeeklyStructureView(APIView):
    """168h 周结构（替代 weekly-tracking 的达标表，v0.2 决策 4 移除 30h benchmark）"""

    permission_classes = [AllowAny]

    def get(self, request):
        year = request.GET.get('year')
        if year:
            year = int(year)
        weeks = int(request.GET.get('weeks', 12))
        data = TemporalStatsService.get_168h_structure(year, weeks)
        return Response(data)


class WeeklyTimeTrackingView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        """获取多年周度时间追踪数据（从固化表读取）"""
        # ⚠️ 默认年份范围**由固化表数据决定**，不用「今年 − 5」：
        #    滚动下界会把最早几年静默挡掉（2020 的 40 周就是这么消失的）。
        bounds = WeeklyTimeCache.objects.aggregate(lo=Min('year'), hi=Max('year'))
        default_start = bounds['lo'] if bounds['lo'] is not None else date.today().year - 5
        default_end = bounds['hi'] if bounds['hi'] is not None else date.today().year + 4

        raw_start = request.GET.get('start_year')
        raw_end = request.GET.get('end_year')
        raw_benchmark = request.GET.get('benchmark')
        try:
            start_year = int(raw_start) if raw_start not in (None, '') else default_start
            end_year = int(raw_end) if raw_end not in (None, '') else default_end
            benchmark = float(raw_benchmark) if raw_benchmark not in (None, '') else 30.0
        except (TypeError, ValueError):
            # ⚠️ 参数写错**必须说出来**，静默回退默认值会让「写错了」看起来像「这段时间没数据」
            return Response(
                {'detail': 'start_year / end_year 必须是整数、benchmark 必须是数字'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cache_data = WeeklyTimeCache.objects.filter(
            year__gte=start_year,
            year__lte=end_year,
        )

        result = {}
        for item in cache_data:
            if item.year not in result:
                result[item.year] = {}
            result[item.year][item.week] = {
                'hours': item.total_hours,
                'percentage': round(item.total_hours / benchmark * 100, 1) if benchmark > 0 else 0,
                'task_count': item.task_count,
            }

        return Response({
            'start_year': start_year,
            'end_year': end_year,
            'benchmark': benchmark,
            'data': result,
            'weeks_per_year': {year: len(result[year]) for year in result},
            # 固化表里**真实存在**的年份范围 —— 让调用方能区分
            # 「这段时间确实没数据」与「被请求区间挡掉了」
            'data_range': {'start_year': bounds['lo'], 'end_year': bounds['hi']},
        })


class RefreshWeeklyCacheView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        """手动刷新周度缓存"""
        from apps.temporal.management.commands.refresh_weekly_cache import Command
        cmd = Command()
        cmd.handle()
        return Response({'success': True})


class OneDayPageViewSet(viewsets.ModelViewSet):
    """每日记录视图集"""

    queryset = OneDayPage.objects.all()
    permission_classes = [AllowAny]
    serializer_class = OneDayPageSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'remark']
    ordering_fields = ['begin_date', 'update_date', 'total', 'oneday', 'page', 'title']
    ordering = ['-begin_date']

    def list(self, request, *args, **kwargs):
        """列表加载时自动为今天生成默认日记（兜底）"""
        DailyLogAutoService.generate_default_log()
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        otype = params.get('otype')
        if otype:
            qs = qs.filter(otype=otype)

        flag = params.get('flag')
        if flag:
            # 子串匹配（flag 为逗号分隔多标签，如"待回顾,美食"）
            qs = qs.filter(flag__icontains=flag)

        years = params.get('years')
        if years:
            qs = qs.filter(years=years)

        year_from = params.get('year_from')
        if year_from:
            qs = qs.filter(years__gte=year_from)

        year_to = params.get('year_to')
        if year_to:
            qs = qs.filter(years__lte=year_to)

        date_from = params.get('date_from')
        if date_from:
            qs = qs.filter(begin_date__gte=date_from)

        date_to = params.get('date_to')
        if date_to:
            qs = qs.filter(begin_date__lte=date_to)

        total_min = params.get('total_min')
        if total_min:
            try:
                qs = qs.filter(total__gte=int(total_min))
            except ValueError:
                pass

        total_max = params.get('total_max')
        if total_max:
            try:
                qs = qs.filter(total__lte=int(total_max))
            except ValueError:
                pass

        return qs

    @action(detail=False, methods=['get'])
    def daily_detail(self, request):
        # 每日明细：按日期查当日日记
        date_str = request.query_params.get('date')
        if not date_str:
            return Response({'error': 'date 参数必填'}, status=400)
        try:
            from datetime import datetime
            d = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'date 格式 YYYY-MM-DD'}, status=400)
        qs = OneDayPage.objects.filter(begin_date=d).order_by('begin_date')
        items = [{
            'oid': p.oid,
            'title': p.title or '',
            'otype': p.otype,
            'total': p.total or 0,
            'flag': p.flag or '',
            'remark': p.remark or '',
        } for p in qs]
        return Response({'date': date_str, 'items': items})

    @action(detail=False, methods=["get"])
    def contrib(self, request):
        """贡献图：当日总字数聚合"""
        rows = list(
            OneDayPage.objects.values('begin_date')
            .annotate(v=Sum('total'))
            .order_by('begin_date')
            .values_list('begin_date', 'v')
        )
        return Response(_build_contrib_response(rows))

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """获取统计信息"""
        data = OneDayPageService.get_stats()
        return Response(data)

    @action(detail=False, methods=['delete'])
    def bulk_delete(self, request):
        """批量删除"""
        oid_list = request.data.get('oids', [])
        if not oid_list:
            return Response({'error': '请提供要删除的ID列表'}, status=status.HTTP_400_BAD_REQUEST)

        deleted_count, _ = OneDayPage.objects.filter(oid__in=oid_list).delete()
        return Response({'message': f'成功删除 {deleted_count} 条记录', 'deleted_count': deleted_count})

    @action(detail=False, methods=['get'])
    def yearly_heatmap(self, request):
        """获取指定年份的日记热力图数据"""
        year = request.query_params.get('year', '')
        try:
            year = int(year)
        except (ValueError, TypeError):
            year = timezone.now().year

        logs = OneDayPage.objects.filter(
            begin_date__year=year,
        ).values('begin_date', 'total', 'title')

        return Response({
            'year': year,
            'data': [
                {
                    'date': log['begin_date'].isoformat(),
                    'count': log['total'] or 0,
                    'title': log['title'],
                }
                for log in logs
            ],
        })

    @action(detail=False, methods=['get'])
    def week_count(self, request):
        """获取本周日记篇数"""
        from datetime import timedelta

        today = date.today()
        week_start = today - timedelta(days=today.weekday())

        count = OneDayPage.objects.filter(
            begin_date__gte=week_start,
            begin_date__lte=today,
        ).count()

        return Response({'count': count})

    @action(detail=False, methods=['get'])
    def week_stats(self, request):
        """仪表盘周统计：本周日记数 / 步数 / 支出"""
        from datetime import timedelta

        from django.db.models import Sum

        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        # 时间字段为本地 naive 存储（Asia/Shanghai），用 aware 边界过滤
        ws = timezone.make_aware(datetime.combine(week_start, datetime.min.time()))
        we = timezone.make_aware(datetime.combine(today, datetime.max.time()))

        diary = OneDayPage.objects.filter(
            begin_date__gte=week_start, begin_date__lte=today
        ).count()

        steps = 0
        expense = 0.0
        try:
            from apps.health.models import HealthRecord
            steps = HealthRecord.objects.filter(
                time__gte=ws, time__lte=we
            ).aggregate(s=Sum('total'))['s'] or 0
        except Exception:
            pass
        try:
            from apps.wealth.models import WealthBillList
            exp = WealthBillList.objects.filter(
                transaction_type='支出', date__gte=ws, date__lte=we
            ).aggregate(s=Sum('amount'))['s']
            expense = round(float(exp or 0), 2)
        except Exception:
            pass

        return Response({
            'count': diary,
            'step_count': round(steps),
            'weekly_expense': expense,
        })


class OpenLogseqView(APIView):
    """打开 Logseq 日记文件，返回 Markdown 内容"""

    permission_classes = [AllowAny]

    def get(self, request):
        filepath = request.GET.get('path', '')

        if not filepath or not os.path.exists(filepath):
            return Response({'error': '文件不存在'}, status=404)

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        content = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL)
        content = re.sub(r'collapsed::\s*true', '', content)

        return Response({
            'filename': os.path.basename(filepath),
            'content': content,
        })


class TimerViewSet(viewsets.ViewSet):
    """实时计时：开始 / 停止 / 丢弃 / 查运行中。

    🔴 所有写库动作都在 `apps.temporal.timer` 里，本层只做参数校验与错误码转换 ——
       避免「视图里也能写一条记录」，那样迟早会出现第二条写入路径、口径分叉。
    """

    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'])
    def running(self, request):
        """当前运行中的会话（含后端算好的已流逝秒数）。"""
        session = timer_service.get_running()
        return Response({
            'session': TimerSessionSerializer(session).data if session else None,
            'elapsed_seconds': timer_service.elapsed_of(session),
            'min_seconds': timer_service.MIN_SECONDS,
            'long_seconds': timer_service.LONG_SECONDS,
        })

    @action(detail=False, methods=['post'])
    def start(self, request):
        try:
            session, prev = timer_service.start(request.data.get('task_name', ''))
        except timer_service.TimerError as e:
            return Response({'code': e.code, 'error': e.message}, status=e.status_code)
        return Response({
            'session': TimerSessionSerializer(session).data,
            'elapsed_seconds': timer_service.elapsed_of(session),
            'prev': prev,
            'min_seconds': timer_service.MIN_SECONDS,
            'long_seconds': timer_service.LONG_SECONDS,
        })

    @action(detail=False, methods=['post'])
    def stop(self, request):
        session_id = request.data.get('session_id')
        if not session_id:
            return Response({'code': 'invalid', 'error': '缺少 session_id'}, status=400)
        try:
            session, result = timer_service.stop(
                int(session_id),
                notes=request.data.get('notes') or '',
                allow_long=bool(request.data.get('allow_long')),
            )
        except timer_service.TimerError as e:
            return Response(
                {'code': e.code, 'error': e.message, **e.extra},
                status=e.status_code,
            )
        except (TypeError, ValueError):
            return Response({'code': 'invalid', 'error': 'session_id 非法'}, status=400)

        return Response({
            'session': TimerSessionSerializer(session).data,
            'result': result,
        })

    @action(detail=False, methods=['post'])
    def discard(self, request):
        session_id = request.data.get('session_id')
        if not session_id:
            return Response({'code': 'invalid', 'error': '缺少 session_id'}, status=400)
        try:
            session, result = timer_service.discard(int(session_id))
        except timer_service.TimerError as e:
            return Response({'code': e.code, 'error': e.message}, status=e.status_code)
        except (TypeError, ValueError):
            return Response({'code': 'invalid', 'error': 'session_id 非法'}, status=400)

        return Response({
            'session': TimerSessionSerializer(session).data,
            'result': result,
        })
