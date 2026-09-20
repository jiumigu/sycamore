import os
import re
import uuid

from datetime import date, datetime

from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from django.db.models import Count, DateField, Max, Sum
from django.db.models.functions import Cast

from .constants import ATTRIBUTION_ORDER
from .models import OneDayPage, TaskMeta, TemporalTask, WeeklyTimeCache
from .serializers import (
    OneDayPageSerializer,
    TaskMetaSerializer,
    TemporalTaskSerializer,
)
from .services import (
    CSVImportService,
    DailyLogAutoService,
    OneDayPageService,
    TemporalStatsService,
    _ensure_task_meta,
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
        self._ensure_meta_for(instance.task_name)

    def perform_update(self, serializer):
        old_name = serializer.instance.task_name
        instance = serializer.save()
        # 改名：新名字补建档；旧名字的 TaskMeta 不自动删（分类字典由用户在映射编辑器里维护）
        if instance.task_name and instance.task_name != old_name:
            self._ensure_meta_for(instance.task_name)

    @action(detail=False, methods=["get"])
    def daily_detail(self, request):
        # 每日明细：按日期查当日所有时间任务
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
        qs = TemporalTask.objects.filter(start_time__gte=ws, start_time__lte=we).order_by('start_time')
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

        dominant_attr（主导归因）：不按量值着色，而是给每天算五个 L1 归因的小时数，
        取最多者作为当天「主导归因」（并列按 ATTRIBUTION_ORDER 的价值序取靠前者）；
        五者全为 0 的日子 attr 返回 null，前端显示为「未归类」灰格。
        """
        metric = request.query_params.get('metric', 'hours')
        rows = list(
            TemporalTask.objects.exclude(start_time__isnull=True)
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

    @action(detail=False, methods=['post'])
    def import_csv(self, request):
        """CSV 导入任务记录（使用 Django 原生 multipart 解析，绕过 DRF 限制）"""
        file = request._request.FILES.get('file')
        if not file:
            print(f'[CSV 导入] request.FILES: {dict(request._request.FILES)}')
            return Response({'error': '请上传文件'}, status=status.HTTP_400_BAD_REQUEST)

        print(f'[CSV 导入] 文件: name={file.name}, size={file.size}, content_type={file.content_type}')

        batch_id = f'import_{uuid.uuid4().hex[:12]}'

        service = CSVImportService()
        try:
            result = service.import_from_csv(file, batch_id)
        except Exception as e:
            print(f'[CSV 导入] 处理异常: {type(e).__name__}: {e}')
            import traceback
            traceback.print_exc()
            return Response({'error': f'导入处理异常：{str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if 'error' in result:
            return Response({'error': result['error']}, status=status.HTTP_400_BAD_REQUEST)

        print(f'[CSV 导入] 完成: 新增 {result["inserted"]}, 更新 {result["updated"]}')
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
                # 命中规则时带上「是哪一条」：前端据此判断「撤销覆盖」能不能撤
                # （只有 task_name 维度的规则可撤；activity_type 规则覆盖多个任务、不归单行管）
                'rule_id': d.get('rule_id'),
                'rule_field': d.get('rule_field'),
                'rule_value': d.get('rule_value'),
                'is_unclassified': m.activity_type == '未归类',
                'is_system': m.is_system,
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

        items = rows
        if keyword:
            items = [r for r in items if keyword in r['task_name'].lower()]
        if activity_type:
            items = [r for r in items if r['activity_type'] == activity_type]
        if attribution:
            items = [r for r in items if r['effective_attribution'] == attribution]
        if unclassified_only:
            items = [r for r in items if r['is_unclassified']]
        items = sorted(items, key=lambda r: (-r['total_hours'], r['task_name']))

        return Response({'summary': summary, 'returned': len(items), 'items': items})

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
        """批量设 L3→L2(活动类型) + L1(归因)：写 temporal_task_meta；attribution 非空则额外写 redemption_attr_rule

        可选参数（台账单行编辑用，不传即保持旧行为）：
        - keep_default=True：只改活动类型，保留 default_attribution 原值（不写 None、不碰规则）
        - clear_rule=True（且未指定新 attribution）：软停用该 task_name 的赎回期归因规则
          （is_active=False，可追溯、不物理删除），即「撤销覆盖 → 回到类型默认」

        ⚠️ 撤销**只对 `match_field='task_name'` 的规则有效**。若撤销后该任务名的归因仍来自
        规则（命中 `activity_type`/`task_type` 维度 —— 这类规则同时覆盖同一类型下的其他任务名，
        不该由单行编辑顺手停掉），则计入响应 `blocked`，前端据此如实提示，**不得再报「已撤销」**。
        """
        task_names = request.data.get('task_names') or []
        activity_type = request.data.get('activity_type')
        attribution = request.data.get('attribution')
        keep_default = request.data.get('keep_default') in (True, '1', 'true', 'True')
        clear_rule = request.data.get('clear_rule') in (True, '1', 'true', 'True')
        if not task_names or not activity_type:
            return Response({'error': 'task_names 与 activity_type 必填'}, status=status.HTTP_400_BAD_REQUEST)

        from apps.redemption.models import RedemptionAttrRule

        updated = 0
        cleared = 0
        blocked = []
        for tn in task_names:
            defaults = {'activity_type': activity_type}
            if not keep_default:
                defaults['default_attribution'] = attribution or None
            TaskMeta.objects.update_or_create(task_name=tn, defaults=defaults)
            updated += 1
            if clear_rule and not attribution:
                n = RedemptionAttrRule.objects.filter(
                    match_field='task_name', match_value=tn, is_active=True,
                ).update(is_active=False)
                cleared += n
                # 撤销「之后」重新解析真实状态：同名规则撤掉了，也可能被 L2/L3 维度规则接管
                d = resolve_attribution_detail([tn]).get(tn) or {}
                if d.get('source') == 'rule':
                    blocked.append({
                        'task_name': tn,
                        'rule_field': d.get('rule_field'),
                        'rule_value': d.get('rule_value'),
                        'attribution': d.get('attribution'),
                        'cleared': n,
                    })
            if attribution:
                RedemptionAttrRule.objects.update_or_create(
                    match_field='task_name', match_value=tn,
                    defaults={'attribution': attribution, 'priority': 100, 'is_active': True,
                              'note': '时间重构批量设置'},
                )
        return Response({'updated': updated, 'cleared': cleared, 'blocked': blocked,
                         'activity_type': activity_type, 'attribution': attribution})

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
        start_year = int(request.GET.get('start_year', date.today().year - 5))
        end_year = int(request.GET.get('end_year', date.today().year + 4))
        benchmark = float(request.GET.get('benchmark', 30))

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
