"""自我运转 · 视图层（**按生命周期分组**：T1 配置 → T2 执行 → T3 复盘 → T4 回望）

🔴 两条贯穿性约定（设计稿 §10）：

1. **`GET` 一律不写库** —— 「本周状态」返回的是**虚拟对象**（`id=null`），
   直到你第一次写。项目铁律：只读接口别 `get_or_create`。
2. **每个 `POST`/`PATCH` 的返回里都带 `written`**（本次写了哪些表、几行）——
   这样「数据流转」在**运行时也是可见的**，出问题时一眼看出哪步没写。

🔴 列表端点一律 `pagination_class = None` 返回**裸数组**
（DRF 全局分页会把它包成 `{count, results}` ⇒ 前端按数组取用即「假 0」）。
"""
from django.db.utils import OperationalError, ProgrammingError
from django.shortcuts import get_object_or_404
from rest_framework import status as http
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import readers, services
from .constants import (
    DIRECTION_CHOICES, MONTHLY_QUESTION_COUNT, PERIOD_STATUS_CHOICES,
    PERIOD_STATUS_LABEL, PERIOD_TYPE_CHOICES, PERIOD_TYPE_PREFIX,
    PERIOD_VERDICT_BANDS, PLAN_SCOPE_CHOICES, SOURCE_KIND_CHOICES,
    VERDICT_COLORS, PERIOD_STATUS_COLORS, AGG_CHOICES,
    MODULE_VALUE_WHITELIST, READER_KEYS, READER_WHERE_KEYS, STALE_RULES,
    STAGE_KIND_CHOICES, STAGE_KIND_RECORD, STAGE_KIND_RUN,
)
from .models import (
    SelfRunCheckin, SelfRunMetric, SelfRunMetricLog, SelfRunMetricPlan,
    SelfRunPeriod, SelfRunStage, SelfRunTemplate,
)
from .serializers import (
    CheckinInputSerializer, FROZEN_PERIOD_FIELDS, HeartbeatSerializer,
    MetricPatchSerializer, MetricPreviewSerializer, PauseSerializer,
    PeriodCloseSerializer, PeriodReviewSerializer, PlanSetSerializer,
    ReasonSerializer, RecordStageInputSerializer, RecordStagePatchSerializer,
    ReopenSerializer, SelfRunCheckinSerializer,
    SelfRunMetricLogSerializer, SelfRunMetricPlanSerializer, SelfRunMetricSerializer,
    SelfRunPeriodSerializer, SelfRunStageSerializer, SelfRunTemplateSerializer,
    StageCopySerializer, StageCreateSerializer, StagePatchSerializer, SummarySerializer,
    TemplateInputSerializer, TemplatePatchSerializer,
)


class NoPagination(PageNumberPagination):
    """占位（列表端点用 `pagination_class = None`，见模块 docstring）。"""


class SelfRunBaseView(APIView):
    """统一权限 + 把服务层异常翻成正确的 HTTP 码。

    🔴 服务层抛 `SelfRunError`（含 `status_code`），这里统一转 ——
       不在每个接口里各写一遍 try/except（漏一个就变成 500 兜底）。
    """
    permission_classes = [AllowAny]

    def handle_exception(self, exc):
        if isinstance(exc, services.SelfRunError):
            return Response({'detail': str(exc)}, status=exc.status_code)
        return super().handle_exception(exc)


def _written(**kw):
    """`written` 只列**真的写了**的表（0 行不出现在里面）。"""
    return {k: v for k, v in kw.items() if v}


def _status_explain(stage, readings, period_type, answer_sheet=None, closed_status=None):
    """判定的**分子分母念出来**（Δ：不许只给一个状态词）。

    🔴 `unknown` / `skipped` **不进分母** —— 把它们算进去会得出「你这周不行」，
       而真相是「系统不知道」或「你说了这周不算」。

    🔴 月度**只有一把尺子**（v3.64.6）：三问。三问一个没答 ⇒ `value=''` +
       `basis='pending'` + 「待答三问」，**绝不拿 KPI 达标率顶上去**。
       旧行为下同一期会先后出现两个档位（归档前 4/4=100% ⇒ 我超棒，
       答完三问 2/3=67% ⇒ 合格），用户看到的就是「归档把我降档了」。

    🔴 已归档的期用**落库的 `status`**（`closed_status`），不用三问重算 ——
       归档即定格；归档后补答三问只留记录、不改档（要改走重开）。
    """
    counted = [r for r in readings if r['verdict'] != 'unknown' and not r.get('skipped')]
    ok = sum(1 for r in counted if r['verdict'] in ('goal', 'floor'))

    # ── 判定依据：周恒为 KPI；月只看三问（没答 = 未判定）──
    basis = 'kpi'
    yes = 0
    answered = 0
    live_status = ''
    if period_type == 'monthly':
        live_status = closed_status or services.compute_monthly_status(answer_sheet)
        yes, answered = services.monthly_answer_stats(answer_sheet)
        if live_status:
            basis = 'questions'
        else:
            basis = 'pending'
    else:
        live_status = services.compute_period_status(stage, readings)

    prefix = PERIOD_TYPE_PREFIX.get(period_type, '')
    # 整句在这里拼，不留给前端 —— 「几比几」「哪套尺子」只有后端知道
    if basis == 'questions':
        ratio = round(yes / MONTHLY_QUESTION_COUNT * 100)
        if period_type == 'monthly' and closed_status:
            # 已归档：说明是定格值，别让人以为还能靠改三问翻盘
            basis_text = (
                f'本月判定看三问：答「是」{yes}/{MONTHLY_QUESTION_COUNT}（{ratio}%）'
                f'⇒ {prefix}{PERIOD_STATUS_LABEL.get(live_status, live_status)}'
                '（归档时定格，补答三问不改档；要改请重开这一期）'
            )
        else:
            basis_text = (
                f'本月判定看三问：答「是」{yes}/{MONTHLY_QUESTION_COUNT}'
                f'（{ratio}%）⇒ {prefix}{PERIOD_STATUS_LABEL.get(live_status, live_status)}'
            )
    elif basis == 'pending':
        basis_text = (
            f'本月判定只看三问，现在还没答（0/{MONTHLY_QUESTION_COUNT}）—— 这一期还没有结论；'
            f'下面那条 {ok}/{len(counted)} 是 KPI 参考，不参与判定。'
        )
    else:
        basis_text = (
            '判定线：' + ' · '.join(
                f'≥{round(lower * 100)}% {PERIOD_TYPE_PREFIX.get(period_type, "")}'
                f'{PERIOD_STATUS_LABEL.get(k, k)}'
                for k, lower in sorted(PERIOD_VERDICT_BANDS, key=lambda x: -x[1])
            )
        )

    # 档位本名（含「本周 / 本月」前缀）也在这里拼：月度未判定时前端要显示
    # 「待答三问」—— 让前端自己写这个词，等于中文表又多一份。
    if live_status:
        label_text = f'{prefix}{PERIOD_STATUS_LABEL.get(live_status, live_status)}'
    else:
        label_text = '待答三问'

    return {
        'value': live_status,
        'label_text': label_text,
        'basis': basis,
        'basis_text': basis_text,
        'yes': yes,
        'answered': answered,
        'awaiting_answers': basis == 'pending',
        'ok': ok,
        'counted': len(counted),
        'total': len(readings),
        'skipped': sum(1 for r in readings if r.get('skipped')),
        'unknown': sum(1 for r in readings if r['verdict'] == 'unknown'),
        'empty': sum(1 for r in readings if r['verdict'] == 'empty'),
        # 🔴 阈值只在后端一份，前端只上色不判
        'thresholds': dict(PERIOD_VERDICT_BANDS),
        # 档位本名 + 本期前缀（前端拼 `本周合格` / `本月合格`，不再各写一份中文表）
        'labels': dict(PERIOD_STATUS_LABEL),
        'prefix': prefix,
        'monthly_question_count': MONTHLY_QUESTION_COUNT,
    }


# ══════════════════════════════════════════════════════════════
# T1 · 制定配置
# ══════════════════════════════════════════════════════════════

class TemplateListView(SelfRunBaseView):
    """模板库（**可自定义**）：`GET` 列全部；`POST` 新建一条。

    ⚠️ `GET` 返回 `{templates, enum}` 而**不是裸数组** ——
       枚举与列表同源下发，前端少一次请求，也不会两边各自漂移。
    """

    def get(self, request):
        # 延迟 import：`works` 与 `selfrun` 互相引用（作品的序列化要用 `period_range`），
        # 模块级 import 会把「先加载谁」变成一件必须小心的事。
        from apps.works.constants import WORK_KIND_CHOICES

        data = services.list_templates(request.query_params.get('period_type'))
        return Response({
            'templates': data,
            'enum': {
                'agg': [{'value': v, 'label': l} for v, l in AGG_CHOICES],
                'source_kind': [{'value': v, 'label': l} for v, l in SOURCE_KIND_CHOICES],
                'direction': [{'value': v, 'label': l} for v, l in DIRECTION_CHOICES],
                'period_type': [{'value': v, 'label': l} for v, l in PERIOD_TYPE_CHOICES],
                'plan_scope': [{'value': v, 'label': l} for v, l in PLAN_SCOPE_CHOICES],
                # 🔴 取数器枚举**随接口下发**，前端不抄第三份（抄了就会漏改、且静默）。
                #    `where_key` = 这个取数器还要在界面里补哪个字段（None = 不需要）。
                'readers': [
                    {
                        'value': k,
                        'hint': (STALE_RULES.get(k) or {}).get('hint', ''),
                        'where_key': READER_WHERE_KEYS.get(k),
                    }
                    for k in READER_KEYS
                ],
                # `module_value` 的白名单键（写错会直接报错，所以给你选、不给你填）
                'module_value_keys': list(MODULE_VALUE_WHITELIST),
                # `l2` 的候选值来自**库**（`temporal_task_meta.activity_type`），
                # 不是常量表 —— 常量表只是「出生证」，库里那行才是真源。
                'l2_options': services.list_l2_options(),
                # 作品类型：`works_count` 的 `work_kind` 候选值。
                # 🔴 从 `works.constants` 的唯一真源取，**不在这里抄一份** ——
                #    抄了以后加类型会漏，而漏的表现只是下拉里少一项（看着像没做）。
                'work_kind_options': [
                    {'value': v, 'label': l} for v, l in WORK_KIND_CHOICES
                ],
            },
        })

    def post(self, request):
        ser = TemplateInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        tpl = services.create_template(ser.validated_data)
        return Response({
            'template': SelfRunTemplateSerializer(tpl).data,
            'written': _written(selfrun_template=1),
        }, status=http.HTTP_201_CREATED)


class TemplateDetailView(SelfRunBaseView):
    """改 / 删一条模板。

    🔴 删模板**不影响任何已建阶段** —— `Metric.template_key` 是字符标记、不是 FK，
       所以不会触发 `PROTECT`，也不会连带删掉 KPI 或读数。
       返回里带上「曾被引用过的 KPI 条数」，让界面能说清影响面（其实只是来源失去指向）。
    """

    def patch(self, request, pk):
        tpl = get_object_or_404(SelfRunTemplate, pk=pk)
        ser = TemplatePatchSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        tpl, changed = services.update_template(tpl, ser.validated_data)
        return Response({
            'template': SelfRunTemplateSerializer(tpl).data,
            'changed': changed,
            'written': _written(selfrun_template=1 if changed else 0),
        })

    def delete(self, request, pk):
        tpl = get_object_or_404(SelfRunTemplate, pk=pk)
        # ⚠️ 先存下标：`delete()` 之后 `pk` 会变 `None`
        info = {'id': tpl.id, 'key': tpl.key, 'name': tpl.name}
        used = services.delete_template(tpl)
        return Response({
            'deleted': info,
            'used_by_metrics': used,
            'note': (
                f'这条模板曾被 {used} 条 KPI 引用过 —— 那些 KPI 与它们的读数**不受影响**，'
                f'只是「来源」不再指向任何模板。' if used else ''
            ),
            'written': _written(selfrun_template=1),
        })


class MetricPreviewView(SelfRunBaseView):
    """**纯试算，绝不落库**（你可以放心点一百次）。"""

    def post(self, request):
        ser = MetricPreviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        payload = dict(ser.validated_data)
        periods = int(payload.pop('periods', 11) or 11)
        result = services.preview_metric(payload, periods=periods)
        result['written'] = {}
        return Response(result)


# ══════════════════════════════════════════════════════════════
# T1b · 按期修订（「每周/每月修订下一周、月」）
# ══════════════════════════════════════════════════════════════

class PeriodOptionsView(SelfRunBaseView):
    """「哪几期可以修订」—— 上一期 + 本期 + 往后 N 期。

    🔴 周期标识**只许后端一把尺子**：前端拿 `Date` 自己算 ISO 周，
       在跨年边界（12-29 属于下一年 W01）会**静默差一周**，而且不报错。
    """

    def get(self, request):
        pt = request.query_params.get('period_type', 'weekly')
        try:
            count = min(max(int(request.query_params.get('count', 6)), 1), 24)
        except (TypeError, ValueError):
            count = 6
        return Response({
            'period_type': pt,
            'options': services.list_period_options(pt, count),
            'written': {},
        })


class TargetsView(SelfRunBaseView):
    """某一期的**生效目标**清单（修订界面用）。

    🔴 这里**不跑取数器** —— 修订目标不需要把 7 个 reader 跑一遍；
       与「本周状态」共用的是 `services.resolve_targets` 同一份口径。
    """

    def get(self, request):
        pt = request.query_params.get('period_type', 'weekly')
        key = request.query_params.get('period_key')
        stage = services.get_open_stage()
        if stage is None:
            return Response({
                'stage': None, 'targets': None,
                'hint': '还没有进行中的阶段 —— 先在下面开启一个。',
                'written': {},
            })
        if not key:
            key = services.current_period_meta(pt)[0]
        data = services.list_targets(pt, key, stage)
        return Response({
            'stage': SelfRunStageSerializer(data.pop('stage')).data,
            'targets': data,
            'written': {},
        })


class MetricPlanView(SelfRunBaseView):
    """某一条 KPI 的按期设定：`GET` 列它改过哪几期（**裸数组**）；`POST` 设/改某一期。"""

    pagination_class = None

    def get(self, request, pk):
        metric = get_object_or_404(SelfRunMetric, pk=pk)
        qs = SelfRunMetricPlan.objects.filter(metric=metric).order_by('period_key', 'scope')
        return Response(SelfRunMetricPlanSerializer(qs, many=True).data)

    def post(self, request, pk):
        metric = get_object_or_404(SelfRunMetric, pk=pk)
        ser = PlanSetSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        plan, log = services.set_plan(
            metric, d['period_key'], d.get('scope') or 'single',
            d['goal_value'], d['floor_value'],
            goal_why=d.get('goal_why') or '', floor_why=d.get('floor_why') or '',
            note=d.get('note') or '',
        )
        return Response({
            'plan': SelfRunMetricPlanSerializer(plan).data,
            'log': SelfRunMetricLogSerializer(log).data,
            'written': _written(selfrun_metric_plan=1, selfrun_metric_log=1),
        }, status=http.HTTP_201_CREATED)


class MetricPlanDetailView(SelfRunBaseView):
    """取消某一期的设定（回到上一层口径）。

    ⚠️ 这里**真的是删除**（配置不是流水，流水才适用「撤销 ≠ 删除」）；
       留痕交给 `MetricLog`。已归档的期另有闸门（409）。
    """

    def delete(self, request, pk, plan_id):
        plan = get_object_or_404(SelfRunMetricPlan, pk=plan_id, metric_id=pk)
        _metric, log = services.delete_plan(plan)
        return Response({
            'deleted': plan_id,
            'log': SelfRunMetricLogSerializer(log).data,
            'written': _written(selfrun_metric_plan=1, selfrun_metric_log=1),
        })


class StageListCreateView(SelfRunBaseView):
    """`GET` 列阶段（裸数组）；`POST` 生效新阶段（**一个事务写 3 张表**）。

    🔴 `kind` **默认 `run`**（v3.64.56）：加「记录型阶段」这一维之后，
       这个接口的既有调用方（向导的上级阶段下拉、账本、时间统计、已收尾表）
       全都只该看到运转型。默认收紧 ⇒ 它们零改动即正确；
       要人生阶段档案请显式 `?kind=all`（只有总览页这么干）。
    """

    pagination_class = None

    def get(self, request):
        # 🔴 `shape`：分层之后 `status=active` **不止一行**（长阶段与它的小阶段同时 open），
        #    前端「取第一条」就会拿到长阶段 —— 页头于是显示「0 条 KPI」，
        #    周/月状态读一个永不判定的阶段，而且**不报错**。
        #    判据统一收敛到 `services.list_stages`（与 `get_open_stage()` 同一把尺子）。
        qs = services.list_stages(
            kind=request.query_params.get('kind') or 'run',
            status=request.query_params.get('status') or None,
            shape=request.query_params.get('shape') or None,
        )
        return Response(SelfRunStageSerializer(qs, many=True).data)

    def post(self, request):
        ser = StageCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        stage, metrics = services.create_stage(ser.validated_data)
        return Response({
            'stage': SelfRunStageSerializer(stage).data,
            'metrics': SelfRunMetricSerializer(metrics, many=True).data,
            'written': _written(
                selfrun_stage=1, selfrun_metric=len(metrics),
                selfrun_metric_log=len(metrics),
            ),
        }, status=http.HTTP_201_CREATED)


class StageDetailView(SelfRunBaseView):
    """阶段详情 / 改备注。

    🔴 `PUT` 一律 **405**（阶段不允许整体替换）；
       `PATCH` 只接受 `note` / `end_date` —— 送 `start_date` 直接 **400**，**不静默忽略**。
    """

    def get(self, request, pk):
        stage = get_object_or_404(SelfRunStage, pk=pk)
        return Response({
            'stage': SelfRunStageSerializer(stage).data,
            'metrics': SelfRunMetricSerializer(
                stage.metrics.all().order_by('sort_order', 'id'), many=True,
            ).data,
            'periods': SelfRunPeriodSerializer(
                stage.periods.filter(closed_at__isnull=False).order_by('-period_start'), many=True,
            ).data,
            'logs': SelfRunMetricLogSerializer(
                SelfRunMetricLog.objects.filter(metric__stage=stage).order_by('-at')[:50], many=True,
            ).data,
            'summary': services.compute_stage_summary(stage),
            # 模板 vs 库里的行：只读差异（§114.1）。空列表 = 两处口径一致。
            'template_drift': services.template_drift(stage),
            'written': {},
        })

    def patch(self, request, pk):
        stage = get_object_or_404(SelfRunStage, pk=pk)
        # 🔴 记录型走另一套校验：它没有 Period，`start_date` **可以**改
        #    （改它不会让任何已完成周期掉出阶段，而补录人生阶段写错年份是常态）。
        if stage.stage_kind == STAGE_KIND_RECORD:
            ser = RecordStagePatchSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            stage, touched = services.update_record_stage(stage, ser.validated_data)
            return Response({
                'stage': SelfRunStageSerializer(stage).data,
                'touched': touched,
                'written': _written(selfrun_stage=1 if touched else 0),
            })
        if 'start_date' in request.data:
            raise services.SelfRunError(
                '阶段的起点生效后不可修改（改它会让已完成周期掉出阶段）。要改请收尾后重开。'
            )
        ser = StagePatchSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        fields = []
        for k, v in ser.validated_data.items():
            setattr(stage, k, v)
            fields.append(k)
        if fields:
            stage.save(update_fields=fields + ['updated_at'])
        return Response({
            'stage': SelfRunStageSerializer(stage).data,
            'written': _written(selfrun_stage=1 if fields else 0),
        })

    def delete(self, request, pk):
        """删阶段 —— **只对记录型开放**。

        🔴 运转型一律 400：它有 KPI / Period / Checkin，删掉就是
           「历史判定与好几小时的记录凭空消失」且不报错。
           运转型的结束只有「收尾（归档）」一条路。
        """
        stage = get_object_or_404(SelfRunStage, pk=pk)
        if stage.stage_kind != STAGE_KIND_RECORD:
            raise services.SelfRunError(
                '运转型阶段不能删除（会带走 KPI 与已归档的周期）—— 请用「收尾阶段」。'
            )
        info = services.delete_record_stage(stage)
        return Response({
            'deleted': info,
            'written': _written(selfrun_stage=1),
        })


class RecordStageCreateView(SelfRunBaseView):
    """建一条**记录型**阶段（谋生期 / 小学期 / 中学期 / 大学期 …）。

    🔴 与 `POST /stages/` 分开：那条路是「开一段要跑 KPI 的阶段」，
       一个事务写 3 张表且强制至少一条 KPI。两类阶段的写入口混成一个，
       就只能靠「有没有 metrics」猜意图 —— 那正是本模块明令禁止的猜法。
    """

    def post(self, request):
        ser = RecordStageInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        stage = services.create_record_stage(ser.validated_data)
        return Response({
            'stage': SelfRunStageSerializer(stage).data,
            'written': _written(selfrun_stage=1),
        }, status=http.HTTP_201_CREATED)


class StageTimelineView(SelfRunBaseView):
    """人生阶段时间轴：**全部**阶段（运转型 + 记录型）按起点正序 + 空档。

    🔴 为什么不能前端自己排：空档是派生值，而「两段之间的空白」最容易被写成
       「相邻两行相减」—— 一旦有嵌套（长阶段包小阶段）或重叠（两条并行的阶段），
       相减会算出负数天或不存在的空档，而列表看起来完全正常。
       口径统一在 `services.stage_timeline()`（顶层区间并集扫描）。
    ⚠️ 日期在这里格式化成字符串：`total.first_start` 为空是**合法的**（还没有任何阶段），
       前端据此显示空态，不需要再判一次类型。
    """

    def get(self, request):
        data = services.stage_timeline()

        def _d(v):
            return f'{v:%Y-%m-%d}' if v else None

        def _gap(g):
            return None if g is None else {**g, 'start': _d(g['start']), 'end': _d(g['end'])}

        roots = [
            {
                'stage': SelfRunStageSerializer(r['stage']).data,
                'children': [SelfRunStageSerializer(c).data for c in r['children']],
                # 🔴 空档**挂在节点上**（这一段之前空了多久），不另给平铺数组 ——
                #    让前端按日期自己去配对，起点相同或重叠时必然配错且不报错。
                'gap_before': _gap(r['gap_before']),
            }
            for r in data['roots']
        ]
        totals = data['totals']
        totals['first_start'] = _d(totals['first_start'])
        totals['last_end'] = _d(totals['last_end'])
        return Response({
            'roots': roots,
            'tail_gap': _gap(data['tail_gap']),
            'totals': totals,
            # 枚举随接口下发 —— 前端不抄第三份（抄了就会漏改，且静默）
            'enum': {
                'kind': [{'value': v, 'label': l} for v, l in STAGE_KIND_CHOICES],
            },
            'written': {},
        })


# ══════════════════════════════════════════════════════════════
# T2 · 执行
# ══════════════════════════════════════════════════════════════

class CurrentPeriodView(SelfRunBaseView):
    """「本周 / 本月状态」—— 🔴 **GET 不写库**（当期没有行就返回虚拟对象）。"""

    def get(self, request):
        period_type = request.query_params.get('period_type', 'weekly')
        period, meta = services.get_current_period(period_type)
        # 🔴 两个分支**必须同形**：`period_key` 与有没有阶段无关。
        #    少了它 ⇒ 前端 `undefined` ⇒ 页面静默不渲染（不报错），
        #    表现就是「本周状态」与「本月状态」两页长得一样。
        key, start, end = services.current_period_meta(period_type)
        if period is None:
            return Response({
                'stage': None, 'period': None, 'live': True,
                'period_key': key, 'period_start': start, 'period_end': end,
                'hint': '还没有进行中的阶段 —— 先去「制定配置」开启一个。',
                # 🔴 与下面那个分支**同形**：没有阶段时也要有这个键，否则前端
                #    `undefined` ⇒ 两块复盘内容静默消失（不报错）。
                'extras': None,
                'written': {},
            })
        readings = period.readings or []
        return Response({
            'stage': SelfRunStageSerializer(period.stage).data,
            'period': SelfRunPeriodSerializer(period).data,
            'live': meta['source'] == 'live',
            'period_key': meta['period_key'],
            'period_start': meta['start'],
            'period_end': meta['end'],
            'status_explain': _status_explain(
                period.stage, readings, period_type, period.answer_sheet,
                # 已归档 ⇒ 用落库的档位（定格），不拿三问重算
                closed_status=period.status if period.closed_at else None,
            ),
            'heartbeat': services.heartbeat_state(period.stage),
            # 复盘的两块补充：本期到期里程碑 + 本期时间流失（只读派生，不落库）
            'extras': services.compute_period_extras(
                period_type, meta['start'], meta['end'],
            ),
            'colors': {'verdict': VERDICT_COLORS, 'period': PERIOD_STATUS_COLORS},
            'written': {},      # 🔴 GET 从不写库
        })


class CheckinListCreateView(SelfRunBaseView):
    """手工登记（**每次都是一笔新流水**，不幂等）。"""

    pagination_class = None

    def get(self, request):
        qs = SelfRunCheckin.objects.all()
        metric_id = request.query_params.get('metric_id')
        if metric_id:
            qs = qs.filter(metric_id=metric_id)
        return Response(SelfRunCheckinSerializer(qs[:200], many=True).data)

    def post(self, request):
        ser = CheckinInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        ck = services.create_checkin(
            d['metric'], d.get('checkin_date'), d['value'], d.get('note') or '',
        )
        return Response({
            'checkin': SelfRunCheckinSerializer(ck).data,
            'written': _written(selfrun_checkin=1),
        }, status=http.HTTP_201_CREATED)


class CheckinDetailView(SelfRunBaseView):
    """🔴 `DELETE` **实为冲销** —— 补一条负值，**原记录保留**（撤销 ≠ 删除）。

    否则 `Period` 快照冻结之后，历史读数会与明细账实不符。
    """

    def delete(self, request, pk):
        ck = get_object_or_404(SelfRunCheckin, pk=pk)
        rev = services.reverse_checkin(ck)
        return Response({
            'reversal': SelfRunCheckinSerializer(rev).data,
            'original': SelfRunCheckinSerializer(ck).data,
            'note': '原记录已保留；本次冲销是一次**新增**流水。',
            'written': _written(selfrun_checkin=1),
        })


class MetricDetailView(SelfRunBaseView):
    """改 KPI 配置 —— **不新建行**（`metric_id` 必须稳定）+ 每次留痕。"""

    def patch(self, request, pk):
        metric = get_object_or_404(SelfRunMetric, pk=pk)
        ser = MetricPatchSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = dict(ser.validated_data)
        reason = d.pop('reason', None)
        reason_note = d.pop('reason_note', '')
        metric, logs = services.update_metric(
            metric, d, reason=reason or None, reason_note=reason_note,
        )
        return Response({
            'metric': SelfRunMetricSerializer(metric).data,
            'logs': SelfRunMetricLogSerializer(logs, many=True).data,
            'written': _written(
                selfrun_metric=1 if logs else 0, selfrun_metric_log=len(logs),
            ),
        })


class MetricRetireView(SelfRunBaseView):
    """退役（「这条我不要了」）—— 与两种「暂停」作用域不同（见 `constants` docstring）。"""

    def post(self, request, pk):
        metric = get_object_or_404(SelfRunMetric, pk=pk)
        ser = ReasonSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        metric, log = services.retire_metric(metric, ser.validated_data.get('reason') or '')
        return Response({
            'metric': SelfRunMetricSerializer(metric).data,
            'written': _written(selfrun_metric=1 if log else 0, selfrun_metric_log=1 if log else 0),
        })


class MetricReviveView(SelfRunBaseView):
    def post(self, request, pk):
        metric = get_object_or_404(SelfRunMetric, pk=pk)
        ser = ReasonSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        metric, log = services.revive_metric(metric, ser.validated_data.get('reason') or '')
        return Response({
            'metric': SelfRunMetricSerializer(metric).data,
            'written': _written(selfrun_metric=1 if log else 0, selfrun_metric_log=1 if log else 0),
        })


class StagePauseView(SelfRunBaseView):
    """整个阶段暂停（休耕）—— 周期照常流转，归档时判 `fallow`。"""

    def post(self, request, pk):
        stage = get_object_or_404(SelfRunStage, pk=pk)
        ser = PauseSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        stage = services.pause_stage(
            stage, reason=d.get('reason'), resume_at=d.get('resume_at'), note=d.get('note') or '',
        )
        return Response({
            'stage': SelfRunStageSerializer(stage).data,
            'written': _written(selfrun_stage=1),
        })


class StageResumeView(SelfRunBaseView):
    def post(self, request, pk):
        stage = get_object_or_404(SelfRunStage, pk=pk)
        stage = services.resume_stage(stage)
        return Response({
            'stage': SelfRunStageSerializer(stage).data,
            'written': _written(selfrun_stage=1),
        })


class HeartbeatView(SelfRunBaseView):
    """「回访即握手」—— 🔴 只 UPDATE `last_seen_at`，不判好坏、不改任何 KPI、不建记录。"""

    def post(self, request):
        ser = HeartbeatSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        stage, wrote = services.heartbeat(ser.validated_data.get('seen', True))
        if stage is None:
            return Response({'stage': None, 'written': {}})
        return Response({
            'stage': SelfRunStageSerializer(stage).data,
            'heartbeat': services.heartbeat_state(stage),
            'written': _written(selfrun_stage=1 if wrote else 0),
        })


# ══════════════════════════════════════════════════════════════
# T3 · 复盘
# ══════════════════════════════════════════════════════════════

class PeriodListView(SelfRunBaseView):
    """历史周期列表（裸数组）。**归档后读数取自快照，绝不重算。**"""

    pagination_class = None

    def get(self, request):
        qs = SelfRunPeriod.objects.filter(closed_at__isnull=False)
        pt = request.query_params.get('period_type')
        stage_id = request.query_params.get('stage_id')
        if pt:
            qs = qs.filter(period_type=pt)
        if stage_id:
            qs = qs.filter(stage_id=stage_id)
        limit = request.query_params.get('limit')
        if limit:
            try:
                qs = qs[: max(int(limit), 1)]
            except ValueError:
                pass
        return Response(SelfRunPeriodSerializer(qs, many=True).data)


class PeriodCloseView(SelfRunBaseView):
    """归档 = 定格。🔴 **系统不自动归档** —— 归不归档是你的动作（V3）。

    🔴 已归档的周期再次归档 ⇒ **409**（不静默覆盖）。
    """
    
    def post(self, request):
        ser = PeriodCloseSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        period, extra = services.close_period(
            d['period_type'], d['period_key'],
            skipped_metric_ids=d.get('skipped_metric_ids'),
            answer_sheet=d.get('answer_sheet'),
        )
        return Response({
            'period': SelfRunPeriodSerializer(period).data,
            'backfill_days': extra.get('backfill_days', 0),
            'note': (
                '本周期读数是**事后补算的** —— 与「当天归档」不等价。'
                if period.is_backfilled else ''
            ),
            'written': _written(selfrun_period=1),
        }, status=http.HTTP_201_CREATED)


class PeriodDetailView(SelfRunBaseView):
    """归档后**仍可写**的只有 `review_text` / `answer_sheet`（记忆型 ≠ 数据型）。

    🔴 试图写冻结字段 ⇒ **405**（**不静默忽略** —— 静默忽略会让你以为改成功了）。
    """

    def get(self, request, pk):
        period = get_object_or_404(SelfRunPeriod, pk=pk)
        return Response({
            'period': SelfRunPeriodSerializer(period).data,
            # 复盘两块补充（本期到期里程碑 + 本期时间流失）。
            # ⚠️ 这两块是**按窗口现算**的：窗口是死的（period_start/end），
            #    所以重算结果稳定；但它不属于 `readings` 那份冻结快照，
            #    补记数据后会有变化 —— 这是有意的（冻结的是 KPI 结论，不是时间轴）。
            'extras': services.compute_period_extras(
                period.period_type, period.period_start, period.period_end,
            ),
            'written': {},
        })

    def patch(self, request, pk):
        period = get_object_or_404(SelfRunPeriod, pk=pk)
        bad = [k for k in FROZEN_PERIOD_FIELDS if k in request.data]
        if bad:
            return Response(
                {'detail': f'这些字段归档后只读，不能修改：{"、".join(bad)}'},
                status=http.HTTP_405_METHOD_NOT_ALLOWED,
            )
        ser = PeriodReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        period, written = services.update_review(
            period,
            review_text=ser.validated_data.get('review_text'),
            answer_sheet=ser.validated_data.get('answer_sheet'),
        )
        return Response({
            'period': SelfRunPeriodSerializer(period).data,
            'written': _written(selfrun_period=1 if written else 0),
        })


class PeriodReopenView(SelfRunBaseView):
    """重开（改历史判定的**唯一出口**，且留痕 + 必须写原因）。"""

    def post(self, request, pk):
        period = get_object_or_404(SelfRunPeriod, pk=pk)
        ser = ReopenSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        period = services.reopen_period(period, ser.validated_data['reason'])
        return Response({
            'period': SelfRunPeriodSerializer(period).data,
            'written': _written(selfrun_period=1),
        })


# ══════════════════════════════════════════════════════════════
# T4 · 事后分析
# ══════════════════════════════════════════════════════════════

class StageSummaryView(SelfRunBaseView):
    """`GET` 看数字（实时算）；`POST` 写你那段话（**T4 唯一落库的分析**）。"""

    def get(self, request, pk):
        stage = get_object_or_404(SelfRunStage, pk=pk)
        return Response({
            'stage': SelfRunStageSerializer(stage).data,
            'summary': services.compute_stage_summary(stage),
            'summary_snapshot': stage.summary_snapshot,
            'summary_at': stage.summary_at,
            'written': {},
        })

    def post(self, request, pk):
        stage = get_object_or_404(SelfRunStage, pk=pk)
        ser = SummarySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        stage, snapshot = services.save_summary(stage, ser.validated_data.get('text') or '')
        return Response({
            'stage': SelfRunStageSerializer(stage).data,
            'summary_snapshot': snapshot,
            'written': _written(selfrun_stage=1),
        })


class StageLedgerView(SelfRunBaseView):
    """`GET` 阶段账本：区间 / 时间 / 钱 / 作品 / 子阶段。

    🔴 **只读现算，零写库** —— 数字全部由现有表推出来（不落任何快照），
       所以改口径后它立刻跟着变，不存在「页面上是旧数」的可能。
    ⚠️ 对叶子阶段同样可用（只看钱与时间两块），不设「只给长阶段」的闸门：
       闸门会让「这个阶段花了多少」变成一个只有长阶段才答得出的问题。
    """

    def get(self, request, pk):
        stage = get_object_or_404(SelfRunStage, pk=pk)
        try:
            ledger = services.stage_ledger(stage)
        except (OperationalError, ProgrammingError) as exc:
            # 🔴 「表不存在」只在**上线顺序**上出现：代码已经是新版，而 `migrate` 还没跑。
            #    不兜成「注入算 0」——那会让余额凭空少一块，而且静默；
            #    也不留一个 500 堆栈 —— 它长得和「代码坏了」一模一样。
            if 'selfrun_pool_inject' in str(exc):
                return Response(
                    {'detail': '阶段账本依赖 selfrun_pool_inject 表，请先执行数据库迁移（manage.py migrate）'},
                    status=http.HTTP_503_SERVICE_UNAVAILABLE,
                )
            raise
        return Response({
            'stage': SelfRunStageSerializer(stage).data,
            'ledger': ledger,
            'written': {},
        })


class StageLedgerConfigView(SelfRunBaseView):
    """`PATCH` 账本参数（目前只有 `pool_principal`）。

    🔴 单独一个端点，**不并进 `StagePatchSerializer`**：
       本金是「这段路带多少钱」的**输入**，改它不该牵连阶段身份与终点；
       混在一个 PATCH 里，一次「只改本金」的请求会顺带把没传的字段
       落回默认值（项目踩过的「没传 = 传默认」）。
    """

    ALLOWED = {'pool_principal'}

    def patch(self, request, pk):
        stage = get_object_or_404(SelfRunStage, pk=pk)
        extra = set(request.data.keys()) - self.ALLOWED
        if extra:
            return Response(
                {'detail': f'本端点只收 pool_principal，多了：{sorted(extra)}'},
                status=http.HTTP_400_BAD_REQUEST,
            )
        raw = request.data.get('pool_principal')
        if raw is None:
            return Response(
                {'detail': '要传 pool_principal（本金，可为 0）'},
                status=http.HTTP_400_BAD_REQUEST,
            )
        try:
            principal = float(raw)
        except (TypeError, ValueError):
            return Response(
                {'detail': '本金必须是数字'}, status=http.HTTP_400_BAD_REQUEST,
            )
        if principal < 0:
            return Response(
                {'detail': '本金不能为负'}, status=http.HTTP_400_BAD_REQUEST,
            )
        cfg = dict(stage.ledger_config or {})
        cfg['pool_principal'] = round(principal, 2)
        stage.ledger_config = cfg
        stage.save(update_fields=['ledger_config', 'updated_at'])
        return Response({
            'stage': SelfRunStageSerializer(stage).data,
            'ledger': services.stage_ledger(stage),
            'written': _written(selfrun_stage=1),
        })


class PoolInjectView(SelfRunBaseView):
    """池注入标记：`GET` 出已标记的账单 id；`POST {bill_id, marked}` 标记 / 取消。

    🔴 单独一个端点，**不并进账本 `GET`**：这个布尔值的消费者是**账单明细页**
       （在收入那笔账单上开关），不是账本页。混进账本能省一个请求，但会让
       账单页为了一个标记去拉整本账（时间块 + 六类归因 + 子阶段全算一遍）。
    🔴 业务规则（只允许收入、金额不落库、两个方向都幂等）全在
       `services.set_pool_inject` —— 视图只搬参数，不自己判。
    """

    def get(self, request):
        try:
            ids = services.list_pool_inject_bill_ids()
        except (OperationalError, ProgrammingError) as exc:
            # 「列不存在」只在**上线顺序**上出现：代码已是新版，而 `migrate` 还没跑。
            # 不兜成空列表 —— 那会让页面显示「一笔都没标」，用户以为自己标丢了。
            if 'selfrun_pool_inject' in str(exc):
                return Response(
                    {'detail': '池注入标记依赖 selfrun_pool_inject.bill_id，请先执行数据库迁移（manage.py migrate）'},
                    status=http.HTTP_503_SERVICE_UNAVAILABLE,
                )
            raise
        return Response({'bill_ids': ids})

    def post(self, request):
        if 'bill_id' not in request.data:
            return Response(
                {'detail': '要传 bill_id'}, status=http.HTTP_400_BAD_REQUEST,
            )
        marked = request.data.get('marked', True)
        bill_id, marked = services.set_pool_inject(
            request.data.get('bill_id'), bool(marked),
        )
        return Response({
            'bill_id': bill_id,
            'marked': marked,
            'written': _written(selfrun_pool_inject=1),
        })


class StageCloseView(SelfRunBaseView):
    """收尾阶段（写 `end_date` + `status='closed'`）。"""

    def post(self, request, pk):
        stage = get_object_or_404(SelfRunStage, pk=pk)
        ser = SummarySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        text = ser.validated_data.get('text')
        if text:
            services.save_summary(stage, text)
        stage = services.close_stage(stage, ser.validated_data.get('end_date'))
        return Response({
            'stage': SelfRunStageSerializer(stage).data,
            'written': _written(selfrun_stage=1),
        })


class StageCopyView(SelfRunBaseView):
    """用这个配置开新阶段（**不复制 Period / Checkin**；指纹必然不同）。"""

    def post(self, request):
        ser = StageCopySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        src = get_object_or_404(SelfRunStage, pk=d['from_stage_id'])
        # 🔴 记录型没有 KPI 可复制 —— 放行会建出一个「0 条 KPI 的运转型阶段」，
        #    而它一建出来就是 active：一个永不判定的幽灵阶段（页头写着「进行中 · 0 条 KPI」）。
        if src.stage_kind != STAGE_KIND_RUN:
            raise services.SelfRunError(
                f'「{src.name}」是记录型阶段，没有 KPI 可复制 —— 它只记一笔事实。'
            )
        stage, metrics = services.copy_stage(src, d['name'], d.get('start_date'))
        return Response({
            'stage': SelfRunStageSerializer(stage).data,
            'metrics': SelfRunMetricSerializer(metrics, many=True).data,
            'copied_from': {'id': src.id, 'name': src.name},
            'note': '以下 KPI 的目标值**仍是上一阶段的**，请逐条重设 —— '
                    '否则改过目标值之后你会以为「我变差了」，实际是尺子换了。',
            'written': _written(
                selfrun_stage=1, selfrun_metric=len(metrics),
                selfrun_metric_log=len(metrics),
            ),
        }, status=http.HTTP_201_CREATED)


# ══════════════════════════════════════════════════════════════
# 跨模块：/dashboard 第一屏小卡（**唯一的跨模块改动**）
# ══════════════════════════════════════════════════════════════

class RunwayView(SelfRunBaseView):
    """仪表盘「跑道」卡：还能撑几个月、撑到哪天、样本够不够。🔴 不写库。

    与 KPI 白名单 `redemption.runway` **同一个函数**（`readers.runway_reading()`）——
    同一件事两份实现，两张屏上的数迟早分叉，而分叉是静默的。

    🔴 算不出来时 `months=None` + `issue.code`，**不是 0**：
       `0` 是「余额确实归零」，与「还没有速度可外推」结论相反。
    """

    def get(self, request):
        return Response({**readers.runway_reading(), 'written': {}})


class OverviewView(SelfRunBaseView):
    """仪表盘小卡：当前状态 + 心跳。🔴 不写库。"""

    def get(self, request):
        stage = services.get_open_stage()
        if stage is None:
            return Response({'stage': None, 'card': None, 'written': {}})
        period, meta = services.get_current_period('weekly')
        readings = period.readings if period is not None else []
        explain = _status_explain(stage, readings, 'weekly')
        goal_hit = [r for r in readings if r['verdict'] == 'goal']
        return Response({
            'stage': SelfRunStageSerializer(stage).data,
            'card': {
                'status': explain['value'],
                'status_label': dict(PERIOD_STATUS_CHOICES).get(explain['value'], '—'),
                'ok': explain['ok'],
                'counted': explain['counted'],
                'goal_count': len(goal_hit),
                'period_key': meta['period_key'] if meta else None,
                'heartbeat': services.heartbeat_state(stage),
            },
            'written': {},
        })
