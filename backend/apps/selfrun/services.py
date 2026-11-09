"""自我运转 · 服务层（**T1 制定 → T2 执行 → T3 复盘 → T4 回望**）

> 设计依据：`docs/自我运转-功能设计-v0.3-20261013.md` §3–§6。本文件是**全部业务口径**的落点。

🔴 五条贯穿性铁律：

1. **派生值不落库**；唯一例外是**快照**（`Period.readings` / `Stage.summary_snapshot`）。
   判据：「**以后重算得出同样结果吗？**」不能 ⇒ 才落。
2. **`GET` 一律不写库** —— 当前周期返回**虚拟对象**（`id=None`），首次写入才建行。
   （项目铁律：只读接口别 `get_or_create`。）
3. **撤销 ≠ 删除** —— 补一条负值流水，原记录保留（否则快照冻结后账实不符）。
4. **判定阈值只在 `constants.PERIOD_VERDICT_BANDS` 一份**，前端 0 个阈值数字。
5. **`None` ≠ `0`** —— 取不到返回 `None`（显示「—」+ 原因），真 0 返回 `0`（显示 `0h`）。
"""
import datetime as dt
import re
import uuid

from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from .constants import (
    BACKFILL_WARN_DAYS,
    MODULE_VALUE_WHITELIST,
    MONTHLY_QUESTION_COUNT,
    MONTHLY_QUESTION_KEYS,
    OPEN_STAGE_STATUSES,
    PERIOD_STATUS_CHOICES,
    PERIOD_VERDICT_BANDS,
    PLAN_SCOPE_CHOICES,
    READER_AGG,
    READER_KEYS,
    STALE_RULES,
    TARGET_SOURCE_FROM,
    TARGET_SOURCE_LABELS,
    TARGET_SOURCE_METRIC,
    TARGET_SOURCE_SINGLE,
)
from .models import (
    SelfRunCheckin, SelfRunMetric, SelfRunMetricLog, SelfRunMetricPlan,
    SelfRunPeriod, SelfRunPoolInject, SelfRunStage, SelfRunTemplate,
)
from .readers import (
    config_fingerprint, period_range, pool_inject_totals, run_reader, temporal_rows,
)
from .templates import TEMPLATE_COPY_FIELDS


# ══════════════════════════════════════════════════════════════
# 异常（视图层把它翻成 400 / 404 / 409）
# ══════════════════════════════════════════════════════════════

class SelfRunError(Exception):
    status_code = 400


class ConflictError(SelfRunError):
    status_code = 409


class NotFoundError(SelfRunError):
    status_code = 404


# ══════════════════════════════════════════════════════════════
# 小工具
# ══════════════════════════════════════════════════════════════

def _f(v):
    """Decimal/None → float/None。**`None` 必须原样保留**（不许兜成 0）。"""
    return None if v is None else float(v)


def _cmp(value, line, direction):
    """按方向比较。`at_least` = 「至少」；`at_most` = 「至多」。"""
    return value >= line if direction == 'at_least' else value <= line


def get_open_stage():
    """当前进行中的**叶子**阶段（= 那一个挂 KPI 的）。没有则 `None`。

    🔴 v3.65.0 起阶段可以分两层，所以「全局唯一 open」不成立了：
       长阶段与它的小阶段会**同时**处于 open。本函数只回答
       「**哪一层在跑 KPI**」—— 期判定、当期目标、心跳、归档全都只认这一层。

    🔴 用 `metrics__status='active'` 把长阶段排除，**不用** `parent__isnull`
       —— 后者会误伤「历史遗留的无父阶段」（那种阶段有 KPI、本该被选中）。

    ⚠️ 已知副作用：某阶段的 KPI **全部退役**时这里返回 `None`，
       页面会落到「还没有进行中的阶段」。语义上是对的（没 KPI 就没判定），
       但空态文案要说清「你有阶段，只是 KPI 全退役了」，否则看着像阶段丢了。
    """
    return (
        SelfRunStage.objects
        .filter(status__in=OPEN_STAGE_STATUSES, metrics__status='active')
        .distinct()
        .first()
    )


def get_open_long_stage():
    """当前进行中的**长阶段**（有子阶段、零 KPI 的那一个）。没有则 `None`。

    ⚠️ 判据是「零 KPI」而不是「有孩子」—— 长阶段可以先建、后挂小阶段，
       建完还没挂孩子的那段时间它同样是长阶段。
    """
    return (
        SelfRunStage.objects
        .filter(
            status__in=OPEN_STAGE_STATUSES,
            parent__isnull=True,
            metrics__isnull=True,
        )
        .first()
    )


def get_closed_stages():
    return SelfRunStage.objects.filter(status='closed')


def current_period_meta(period_type='weekly'):
    """`(key, start, end)` —— **当前周期是哪一期**，与有没有阶段**无关**。

    🔴 为什么要单独给出来：前端在「还没有进行中的阶段」时也要说清
       「本周指的是哪一周」/「本月指的是哪一月」——
       否则「本周状态」与「本月状态」两页长得一模一样（分不出自己在哪一页）。
    🔴 周期标识只许**后端一把尺子**：前端按 `Date` 自己算 ISO 周，
       在跨年边界（12-29 属于下一年 W01）会**静默差一周**，而且不报错。
    """
    start, end, key = period_range(period_type, timezone.localdate())
    return key, start, end


def parse_period_key(period_type, key):
    """`'2026-W42'` / `'2026-10'` → `(start, end)`（半开区间）。"""
    try:
        if period_type == 'weekly':
            y, w = str(key).split('-W')
            mon = dt.date.fromisocalendar(int(y), int(w), 1)
            return mon, mon + dt.timedelta(days=7)
        y, m = str(key).split('-')
        first = dt.date(int(y), int(m), 1)
        return first, (first + dt.timedelta(days=32)).replace(day=1)
    except (ValueError, TypeError) as exc:
        raise SelfRunError(f'周期标识 {key!r} 不合法（周应为 2026-W42，月应为 2026-10）') from exc


# ══════════════════════════════════════════════════════════════
# 按期目标解析（🔴 全模块**唯一**一处决定「这一期的目标是多少」）
# ══════════════════════════════════════════════════════════════

def _plans_by_metric(metric_ids):
    """一次取回这些 KPI 的全部按期设定。返回 `{metric_id: [plan, ...]}`。

    ⚠️ 用「一次查询 + Python 里挑」而不是每条 KPI 查两次 ——
       8 条 KPI × 2 次 = 16 次往返，而它**每次翻页**都要跑。
    """
    out = {}
    metric_ids = [i for i in (metric_ids or []) if i]
    if not metric_ids:
        return out
    for p in SelfRunMetricPlan.objects.filter(metric_id__in=metric_ids):
        out.setdefault(p.metric_id, []).append(p)
    return out


def pick_plan(plans, period_key):
    """从一堆设定里挑出**对这一期生效**的那条。返回 `(plan, source)`。

    🔴 优先序只有这一处实现（前端不重算、不兜底）：
       ① **`single` 且恰好是这一期** ⇒ 用它（**特例压过长期**）；
       ② `from` 里 `period_key <= 本期` 的**最晚**一条 ⇒ 用它；
       ③ 都没有 ⇒ `(None, 'metric')`，回落 `SelfRunMetric` 的默认值。

    ⚠️ `period_key` 的**字符串序即时间序**：`2026-W09 < 2026-W42 < 2026-W43`，
       跨年 `2025-W52 < 2026-W01` 也成立（零填充是前提，见 `readers.week_range`）。
    """
    if not period_key:
        return None, TARGET_SOURCE_METRIC
    single = next(
        (p for p in plans if p.scope == 'single' and p.period_key == period_key), None,
    )
    if single is not None:
        return single, TARGET_SOURCE_SINGLE
    froms = [p for p in plans if p.scope == 'from' and p.period_key <= period_key]
    if froms:
        return max(froms, key=lambda p: p.period_key), TARGET_SOURCE_FROM
    return None, TARGET_SOURCE_METRIC


def resolve_targets(metric, period_key=None, plans=None):
    """这一条 KPI 在 `period_key` 这一期的**生效目标**。

    返回 `(goal, floor, source, plan)`：
    - `source` ∈ `'metric'`（阶段默认）/ `'single'`（本期特例）/ `'from'`（按期设定）；
    - `plan` = 命中的那条设定（没命中为 `None`），界面用它回答「为什么是 10h」。

    🔴 没有 `period_key`（试算 / 未落库的对象）⇒ 一律用默认值，**不猜**。
    """
    if metric.pk is None or not period_key:
        return metric.goal_value, metric.floor_value, TARGET_SOURCE_METRIC, None
    if plans is None:
        plans = list(SelfRunMetricPlan.objects.filter(metric=metric))
    plan, source = pick_plan(plans, period_key)
    if plan is None:
        return metric.goal_value, metric.floor_value, TARGET_SOURCE_METRIC, None
    return plan.goal_value, plan.floor_value, source, plan


def resolve_map(metrics, period_key):
    """批量版：`{metric_id: (goal, floor, source, plan)}`（**一次**查询）。"""
    ids = [m.id for m in metrics if m.pk]
    plans_map = _plans_by_metric(ids)
    return {
        m.id: resolve_targets(m, period_key, plans_map.get(m.id) or [])
        for m in metrics
    }


# ══════════════════════════════════════════════════════════════
# 单条读数的计算（T2 与 T3 **共用**同一段口径 —— 不许写两份）
# ══════════════════════════════════════════════════════════════

def _manual_value(metric, start, end):
    """区间内手工登记的求和（`manual` / `auto_plus_manual` 型用）。

    ⚠️ **负数 = 冲销** ⇒ 直接求和，不过滤。
    ⚠️ 未落库的 metric（试算场景）没有 id ⇒ 返回 0 而不是崩。
    """
    if not metric.pk:
        return 0.0
    agg = metric.checkins.filter(
        checkin_date__gte=start, checkin_date__lt=end,
    ).aggregate(s=Sum('value'))
    return round(float(agg['s'] or 0), 2)


def _freshness_state(metric, reader_out, goal, floor):
    """按 `constants.STALE_RULES` 判数据源新鲜度。返回 `(state, freshness_dict)`。

    ⚠️ 「有没有设线」判的是**这一期生效的目标**（`goal` / `floor`），
       不是 `metric.goal_value` —— 否则「本期特例把两条都留空」会被算成「已配置」。
    """
    kind = (metric.source_config or {}).get('kind')
    rule = STALE_RULES.get(kind)
    at = reader_out.get('freshness_at')
    fresh = {'kind': kind, 'at': at.isoformat() if hasattr(at, 'isoformat') else None}

    if goal is None and floor is None:
        return 'unconfigured', fresh          # 没设线 ⇒ 只展示不判定

    if rule is None:
        return 'ok', fresh                    # 手工型没有新鲜度概念

    if at is None:
        # 源表**从来没有过数据** —— 这不是「过期」，是「确实没有」。
        # `stale` 的语义是「该更新却没更新」；空表是「就没开始过」⇒ 按 0 处理（判 empty）。
        return 'ok', fresh

    # 🔴 「哪一天」按**本地日**算：`Max('<datetime 列>')` 回来的是 aware datetime，
    #    直接 `.date()` 拿的是 **UTC 日** —— 本地 00:00–08:00 记的那条会被算成「昨天」，
    #    在 3 天 / 7 天这种紧阈值上刚好能把「昨天记的」判成 `stale`。
    if isinstance(at, dt.datetime):
        at_date = timezone.localtime(at).date() if timezone.is_aware(at) else at.date()
    else:
        at_date = at
    days = (timezone.localdate() - at_date).days
    fresh.update({'days': days, 'limit': rule['days'], 'hint': rule['hint']})
    if days > rule['days']:
        return 'stale', fresh
    return 'ok', fresh


def evaluate_verdict(final, state, source_count, goal, floor, direction):
    """单条 KPI 的本期判定（设计稿 §11.1）。

    🔴 分支顺序是**刻意的**：
       ① `unknown`（系统不知道）→ 不进分母；
       ② `empty`（系统正常、源里一条都没有）→ **进分母**（「真的没做」要算账）；
       ③ 有数 ⇒ 按 `goal` / `floor` 判。

    ⚠️ `goal` / `floor` 是**这一期生效的**目标（可能来自按期设定），
       不是 `metric.goal_value` —— 判定必须与读数里显示的那两个数**同一份**，
       否则会出现「显示的是一套、判的是另一套」。
    """
    if state in ('stale', 'unconfigured'):
        return 'unknown'
    if final is None:
        return 'unknown'
    if source_count == 0 and final == 0:
        return 'empty'

    goal, floor = _f(goal), _f(floor)
    if floor is not None:
        if not _cmp(final, floor, direction):
            return 'miss'
        if goal is not None and _cmp(final, goal, direction):
            return 'goal'
        return 'floor'
    if goal is not None:
        return 'goal' if _cmp(final, goal, direction) else 'miss'
    return 'unknown'


def compute_metric_reading(metric, start, end, skipped=False, period_key=None, plans=None):
    """算一条 KPI 在 `[start, end)` 上的完整读数。

    返回的 dict **同时用于 T2 展示与 T3 冻结** —— 口径只有这一份实现。

    🔴 `period_key` 决定「这一期的目标」取自哪里（默认值 / 本期特例 / 按期设定）：
       - 传了 ⇒ 按 `resolve_targets` 解析，并在读数里带上 `target_source`；
       - 没传（试算等）⇒ 用 `metric` 的默认值。
       ⚠️ **冻结进 `Period.readings` 的是解析后的值** ⇒ 归档之后
          「这一期的目标是多少」**永远能回答**，不受此后任何修订影响。
    """
    out = run_reader(metric, start, end)
    goal, floor, target_source, plan = resolve_targets(metric, period_key, plans)
    state, fresh = _freshness_state(metric, out, goal, floor)
    reader_value = out['value']
    reader_count = out['count']

    # ── 三数合并（设计稿 §4.1 的表）──────────────────────────
    if metric.source_kind == 'manual':
        auto_value, manual_value = None, reader_value
        final_value = manual_value
        source_count = reader_count
    elif metric.source_kind == 'auto':
        auto_value, manual_value = reader_value, None
        final_value = auto_value
        source_count = reader_count
    else:  # auto_plus_manual：reader 给自动部分，另加手工补记
        auto_value = reader_value
        manual_value = _manual_value(metric, start, end)
        final_value = None if auto_value is None else round(auto_value + manual_value, 2)
        source_count = reader_count

    verdict = evaluate_verdict(final_value, state, source_count, goal, floor, metric.direction)

    return {
        'metric_id': metric.id,
        'name': metric.name,
        'unit': metric.unit,
        'direction': metric.direction,
        'period_type': metric.period_type,
        'agg': metric.agg,
        'source_kind': metric.source_kind,
        'goal_value': _f(goal),
        'floor_value': _f(floor),
        # 🔴 「为什么是这个数」也取**生效那一份**的依据：
        #    本期特例有自己写的依据就用它，没有才落回阶段默认的。
        'goal_why': (plan.goal_why if plan and plan.goal_why else metric.goal_why),
        'floor_why': (plan.floor_why if plan and plan.floor_why else metric.floor_why),
        # 🔴 目标来自哪：`metric` 默认 / `single` 本期特例 / `from` 按期设定。
        #    三者必须能分辨 —— 全都显示成同一个数的话，
        #    「我这周的目标怎么变了」就永远说不清（而界面两处都「看着正常」）。
        'target_source': target_source,
        'target_source_label': TARGET_SOURCE_LABELS.get(target_source, ''),
        'plan_id': plan.id if plan else None,
        'plan_scope': plan.scope if plan else None,
        'plan_note': (plan.note if plan else '') or '',
        # 🔴 三个数都要在：只存 final 的话，三个月后没法回答「这 1 天是自动取的还是你补的」
        'auto_value': auto_value,
        'manual_value': manual_value,
        'final_value': final_value,
        'verdict': verdict,
        'state': state,
        'skipped': skipped,
        # 溯源（V2：让你看见尺子）
        'breakdown': out['breakdown'][:50],
        'breakdown_total': len(out['breakdown']),
        'warnings': out['warnings'] + out.get('issues', []),
        'freshness': fresh,
    }


# ══════════════════════════════════════════════════════════════
# 判定引擎
# ══════════════════════════════════════════════════════════════

def compute_period_status(stage, readings):
    """周/月判定（设计稿 §5.4）。

    🔴 分母口径：
       - `unknown`（含 `stale` / `unconfigured`）**不进分母**（V1：「没记」不是「没做」）；
       - `skipped`（本周明确说不算）**不进分母**；
       - `empty`（系统正常、真的一条没有）**进分母** —— 它才是「真的没做」。
    🔴 分子 = `goal` 或 `floor`（**达底线即算达标**，与 §3.3 试算的「达标 7/11」同一把尺子）。
    """
    if stage.status == 'paused':
        return 'fallow'
    counted = [r for r in readings if r['verdict'] != 'unknown' and not r.get('skipped')]
    if not counted:
        return 'no_record'
    ok = sum(1 for r in counted if r['verdict'] in ('goal', 'floor'))
    return _ratio_band(ok / len(counted))


def _ratio_band(ratio):
    """比例 → 档位（**唯一一份**分档实现，周与月共用同一张表）"""
    for name, lower in PERIOD_VERDICT_BANDS:
        if ratio >= lower:
            return name
    return 'slid'


def monthly_answer_stats(answer_sheet):
    """数一次月度三问：`(答「是」个数, 已答个数)`。

    🔴 **唯一实现** —— 判定（`compute_monthly_status`）、判定说明
    （`views._status_explain`）、归档前置校验、阶段汇总的 `yes_count`
    都从这里取，别各写一份 `is True` 的循环（少一处就差一个口径）。

    🔴 `answer=None`（**还没答**）与 `answer=False`（**答了否**）必须分开：
       前者不计已答，后者计已答但不算「是」—— 又是一处 `null ≠ 0`。
    """
    yes = 0
    answered = 0
    for key in MONTHLY_QUESTION_KEYS:
        ans = ((answer_sheet or {}).get(key) or {}).get('answer')
        if ans is True:
            yes += 1
            answered += 1
        elif ans is False:
            answered += 1
    return yes, answered


def compute_monthly_status(answer_sheet):
    """月度判定：三问里答「是」的个数 ÷ 3。

    🔴 `answer=None`（**还没答**）与 `answer=False`（**答了否**）必须分开 ——
       又是一处 `null ≠ 0`。只数 `is True` 的。
    🔴 但分母**恒为 3**（`MONTHLY_QUESTION_COUNT`），不按已答数：
       答了 1 个「是」就是 1/3，不是 1/1 —— 否则「只答一个还答了是」会判成满分。
    🔴 一个都没答（全是 `None`）⇒ 返回 `''`：**未判定**，不是「活着」也不是
       「按 KPI 算」。调用方据此显示「待答三问」并给答题入口（v3.64.6）——
       旧实现让调用方落回 KPI 档位，于是「4/4=100% 我超棒」与「2/3=67% 合格」
       在同一期上先后出现，读起来就是「归档给我降了档」。
    """
    if not answer_sheet:
        return ''
    yes, answered = monthly_answer_stats(answer_sheet)
    if not answered:
        return ''
    return _ratio_band(yes / MONTHLY_QUESTION_COUNT)



# ══════════════════════════════════════════════════════════════
# T1 · 制定配置
# ══════════════════════════════════════════════════════════════

def _template_fields(tpl):
    """`SelfRunTemplate` → 建阶段时用来兜底的字段字典（与旧常量的键**同名**）。"""
    return {
        'name': tpl.name, 'period_type': tpl.period_type, 'unit': tpl.unit,
        'direction': tpl.direction, 'goal_value': tpl.goal_value,
        'floor_value': tpl.floor_value, 'goal_why': tpl.goal_why,
        'floor_why': tpl.floor_why, 'agg': tpl.agg,
        'source_kind': tpl.source_kind, 'source_config': tpl.source_config,
        'sort_order': tpl.sort_order,
    }


def find_template(key):
    """按 `key` 取一条模板。没有 ⇒ `None`（**不报错**：来源只是展示用的标记）。"""
    if not key:
        return None
    return SelfRunTemplate.objects.filter(key=key).first()


def list_l2_options():
    """可选的活动类型（= `temporal_task_meta.activity_type` 的去重值）。

    🔴 取自**库**不是常量表：常量表只是「出生证」，库里那行才是真源
       （`readers._temporal_filtered` 的口径也一样）。
    给模板编辑界面用 —— 让 `temporal_hours` 的 `l2` 过滤可以**选**而不是手打，
       手打的错字不报错、只会静默取到 0。
    """
    from apps.temporal.models import TaskMeta
    return sorted({
        v for v in TaskMeta.objects.values_list('activity_type', flat=True) if v
    })


def list_templates(period_type=None):
    """模板库 —— 🔴 读**表**（不再读 `templates.py` 常量）。

    常量只在迁移 `0002` 里被 seed 一次；此后模板的增删改一律落库
    ⇒ 你在界面上删掉的模板**不会**在下次启动时自己回来。
    """
    qs = SelfRunTemplate.objects.all()
    if period_type:
        qs = qs.filter(period_type=period_type)
    # 「被几个 KPI 引用过」一次聚合算完（模板与阶段只靠字符 key 关联，没法 annotate）
    used = dict(
        SelfRunMetric.objects.exclude(template_key='')
        .values_list('template_key').annotate(n=Count('id'))
    )
    out = []
    for t in qs:
        kind = (t.source_config or {}).get('kind')
        row = _template_fields(t)
        row.update({
            'id': t.id,
            'key': t.key,
            'reader_kind': kind,
            'reader_hint': (STALE_RULES.get(kind) or {}).get('hint', ''),
            'used_count': used.get(t.key, 0),
        })
        out.append(row)
    return out


def _validate_lines(goal, floor, direction, label):
    """目标与底线的方向性校验（**模板 / 按期设定共用**）。错就报，不静默纠正。"""
    if goal is not None and floor is not None:
        g, f = float(goal), float(floor)
        if direction == 'at_least' and g < f:
            raise SelfRunError(f'{label}：目标 {g} 低于底线 {f}，请确认。')
        if direction == 'at_most' and g > f:
            raise SelfRunError(f'{label}：目标 {g} 高于底线 {f}（方向为「至多」），请确认。')


def _validate_source_config(source_kind, source_config, label):
    """校验「取数方式 + 取数器」能不能真的跑起来，并**归一化** `kind`。

    🔴 为什么要在**建模板**的时候就报错：未知 `kind` 要到**取数那一刻**才炸
       （`run_reader` 直接抛 `ValueError`）⇒ 表现是「阶段建好了、某一页 500」。
       早报一格，错误就落在「你刚点的那个按钮」上，而不是三天后的某一页。
    🔴 `source_kind='manual'` 也**必须**有一个注册表内的 `kind`：手工项的取值走
       `run_reader`（只是结果被当作 `manual_value`）⇒ `kind` 空着照样会炸。
       没给就默认 `manual_sum`。
    """
    cfg = dict(source_config or {})
    kind = cfg.get('kind') or ('manual_sum' if source_kind == 'manual' else None)
    if kind not in READER_KEYS:
        raise SelfRunError(
            f'{label}：取数方式要配一个取数器，而 {kind!r} 不在允许清单里（{list(READER_KEYS)}）。'
        )
    if kind == 'module_value':
        key = (cfg.get('where') or {}).get('key')
        if key not in MODULE_VALUE_WHITELIST:
            raise SelfRunError(
                f'{label}：`module_value` 的键 {key!r} 不在白名单内'
                f'（{list(MODULE_VALUE_WHITELIST)}）。'
            )
    cfg['kind'] = kind
    return cfg


_TEMPLATE_EDITABLE = (
    'name', 'period_type', 'unit', 'direction', 'goal_value', 'floor_value',
    'goal_why', 'floor_why', 'agg', 'source_kind', 'source_config', 'sort_order',
)


@transaction.atomic
def create_template(payload):
    """新建一条自定义模板。

    🔴 `key` **由后端生成**（`custom_<8位>`），前端不许自己编 ——
       它是显示层与 seed 数据之间的稳定标识，撞了就是「来源指向别人的模板」。
    """
    name = (payload.get('name') or '').strip()
    if not name:
        raise SelfRunError('模板名称不能为空。')
    period_type = payload.get('period_type') or 'weekly'
    if period_type not in ('weekly', 'monthly'):
        raise SelfRunError(f'未知周期类型：{period_type!r}')
    direction = payload.get('direction') or 'at_least'
    _validate_lines(
        payload.get('goal_value'), payload.get('floor_value'), direction, f'模板「{name}」',
    )
    source_kind = payload.get('source_kind') or 'manual'
    source_config = _validate_source_config(
        source_kind, payload.get('source_config'), f'模板「{name}」',
    )

    key = ''
    for _ in range(5):
        candidate = 'custom_' + uuid.uuid4().hex[:8]
        if not SelfRunTemplate.objects.filter(key=candidate).exists():
            key = candidate
            break
    if not key:
        raise SelfRunError('生成模板标识失败，请重试。')

    sort_order = payload.get('sort_order')
    if sort_order is None:
        last = SelfRunTemplate.objects.order_by('-sort_order').first()
        sort_order = ((last.sort_order or 0) + 10) if last else 10

    return SelfRunTemplate.objects.create(
        key=key, name=name, period_type=period_type,
        unit=payload.get('unit') or '',
        direction=direction,
        goal_value=payload.get('goal_value'),
        floor_value=payload.get('floor_value'),
        goal_why=payload.get('goal_why') or '',
        floor_why=payload.get('floor_why') or '',
        agg=payload.get('agg') or 'manual_sum',
        source_kind=source_kind,
        source_config=source_config,
        sort_order=sort_order,
    )


@transaction.atomic
def update_template(tpl, payload):
    """改模板。**`key` 不可改**（它是 `SelfRunMetric.template_key` 的指向）。"""
    data = {k: v for k, v in (payload or {}).items() if k in _TEMPLATE_EDITABLE}
    if 'name' in data and not (data['name'] or '').strip():
        raise SelfRunError('模板名称不能为空。')
    label = f'模板「{data.get("name") or tpl.name}」'
    goal = data.get('goal_value', tpl.goal_value)
    floor = data.get('floor_value', tpl.floor_value)
    direction = data.get('direction') or tpl.direction
    _validate_lines(goal, floor, direction, label)
    # 只在**动过取数相关字段**时校验（否则每次改名都等于重跑一遍取数器校验，
    # 而老模板里可能正躺着一个当年合法、如今被移出白名单的 kind）
    if 'source_kind' in data or 'source_config' in data:
        data['source_config'] = _validate_source_config(
            data.get('source_kind') or tpl.source_kind,
            data.get('source_config', tpl.source_config),
            label,
        )

    changed = []
    for k, v in data.items():
        if getattr(tpl, k) == v:
            continue
        setattr(tpl, k, v)
        changed.append(k)
    if changed:
        tpl.save(update_fields=changed + ['updated_at'])
    return tpl, changed


@transaction.atomic
def delete_template(tpl):
    """删模板。

    🔴 **不影响任何已建阶段** —— `SelfRunMetric.template_key` 只是字符标记、不是 FK，
       所以不会触发 `PROTECT`，也不会连带删掉任何 KPI 或读数。
       代价只是那些 KPI 的「来源」失去指向（来源只用于展示，不参与取数）。
    返回**曾被引用过的 KPI 条数**，供界面在删除前告诉你影响面。
    """
    used = SelfRunMetric.objects.filter(template_key=tpl.key).count()
    tpl.delete()
    return used


def preview_metric(payload, periods: int = 11):
    """**纯试算，绝不落库**（你可以放心点一百次）。

    给定一份「还没建」的 KPI 配置，算出它在最近 N 个已过去周期上的读数分布，
    并给出「若底线设成 X，过去会有几期达标」。

    ⚠️ 这里构造的 `SelfRunMetric` **不 save** —— `manual_sum` reader 对无 pk 的对象
       返回 0（不崩），其余 reader 全部只读源表。
    """
    period_type = payload.get('period_type') or 'weekly'
    if period_type not in ('weekly', 'monthly'):
        raise SelfRunError(f'未知周期类型：{period_type!r}')

    probe = SelfRunMetric(
        stage_id=0,
        name=payload.get('name') or '试算',
        period_type=period_type,
        unit=payload.get('unit') or '',
        direction=payload.get('direction') or 'at_least',
        agg=payload.get('agg') or 'sum_hours',
        source_kind=payload.get('source_kind') or 'auto',
        source_config=payload.get('source_config') or {},
        goal_value=payload.get('goal_value'),
        floor_value=payload.get('floor_value'),
    )

    today = timezone.localdate()
    rows = []
    latest_warnings = []
    for i in range(1, periods + 1):
        if period_type == 'weekly':
            ref = today - dt.timedelta(days=7 * i)
        else:
            ref = (today.replace(day=1) - dt.timedelta(days=1))
            for _ in range(i):
                ref = (ref.replace(day=1) - dt.timedelta(days=1))
        start, end, key = period_range(period_type, ref)
        r = compute_metric_reading(probe, start, end)
        if i == 1:
            latest_warnings = r['warnings']      # 最近一期的告警（越界值 / 两把尺子…）
        rows.append({'key': key, 'start': str(start), 'end': str(end),
                     'value': r['final_value'], 'state': r['state'], 'verdict': r['verdict']})
    rows.reverse()

    values = [r['value'] for r in rows if r['value'] is not None]
    stats = {}
    if values:
        s = sorted(values)
        stats = {
            'count': len(values),
            'min': min(values), 'max': max(values),
            'median': s[len(s) // 2] if len(s) % 2 else round((s[len(s) // 2 - 1] + s[len(s) // 2]) / 2, 2),
            'mean': round(sum(values) / len(values), 2),
        }

    # 「底线设成 X 会有几期达标」—— 按达底线即算达标，与周期判定同一把尺子
    floor_options = payload.get('floor_options') or [3, 5, 9, 12]
    hit = [
        {
            'floor': opt,
            'hit': sum(1 for v in values if _cmp(v, opt, probe.direction)),
            'total': len(values),
        }
        for opt in floor_options
    ]

    return {
        'period_type': period_type,
        'rows': rows,
        'stats': stats,
        'floor_options': hit,
        'reader_kind': probe.source_config.get('kind'),
        'warnings': latest_warnings,
    }


def _validate_metric_payload(m, index, template):
    """校验一条 KPI 配置。**错就报，不静默纠正。**

    ⚠️ 校验的是**最终生效值**（不传 ⇒ 模板默认），而不是「这次请求里传了什么」——
       否则「模板 12/5 但请求里只传了 goal=3」这种情况会绕过校验。
    """
    goal = m.get('goal_value', template.get('goal_value'))
    floor = m.get('floor_value', template.get('floor_value'))
    direction = m.get('direction') or template.get('direction') or 'at_least'
    label = f'第 {index} 条「{m.get("name") or template.get("name") or "KPI"}」'
    _validate_lines(goal, floor, direction, label)
    return direction


@transaction.atomic
def create_stage(payload):
    """T1 唯一的写库动作（设计稿 §3.4）：**一个事务里写 3 张表**。

    ⇒ `Stage`（一步到位 `status='active'`，不留 draft 残留）
      + `Metric × N`
      + `MetricLog × N`（`created` —— 「创建」也是「一次配置变更」）

    v3.65.0 起两种形态，**必须由调用方显式声明**（见下方 `is_long_stage`）：

    | 形态 | `is_long_stage` | `parent` | `metrics` | 写几张表 |
    |---|---|---|---|---|
    | 叶子阶段（跑 KPI 的） | 否（默认） | 可空 | **≥ 1 条** | 3 |
    | 小阶段（挂在长阶段下） | 否（默认） | **必填** | **≥ 1 条** | 3 |
    | 长阶段（只汇总） | **是** | 必须为空 | **必须为空** | 1 |
    """
    metrics_in = payload.get('metrics') or []
    is_long = bool(payload.get('is_long_stage'))
    parent_id = payload.get('parent')

    parent = None
    if parent_id:
        parent = SelfRunStage.objects.filter(pk=parent_id).first()
        if parent is None:
            raise SelfRunError('上级阶段不存在。')
        # 🔴 两层封顶，服务层再判一次（`model.clean()` 挡不住 `objects.create()`）
        if parent.parent_id:
            raise SelfRunError('只支持两层：上级阶段不能再有上级。')
        if parent.status == 'closed':
            raise SelfRunError(f'上级阶段「{parent.name}」已收尾，不能再往下开小阶段。')

    if is_long:
        if parent is not None:
            raise SelfRunError('长阶段不能挂在别的阶段下 —— 它本身就是最上面那一层。')
        if metrics_in:
            raise SelfRunError('长阶段只汇总，不配 KPI —— 请把 KPI 挂到它下面的小阶段上。')
    elif not metrics_in:
        # 🔴 不静默把「忘填 KPI 的叶子」变成长阶段：两者行为完全不同，
        #    靠「有没有 metrics」猜意图就是让一个错配变成一个看起来正常的错。
        raise SelfRunError('至少要有一条 KPI 才能开始；若这是只做汇总的长阶段，请显式声明。')

    # 互斥按 `parent` 分组（不是全局唯一）—— 长阶段开着时，叶子必须挂在它下面。
    siblings = SelfRunStage.objects.filter(
        status__in=OPEN_STAGE_STATUSES, parent_id=parent_id,
    )
    existing = siblings.first()
    if existing is not None:
        if existing.metrics.exists():
            raise SelfRunError(
                f'已有进行中的阶段「{existing.name}」，请先收尾它再开启新的。'
            )
        raise SelfRunError(
            f'长阶段「{existing.name}」正在进行中 —— 新阶段请挂在它下面（parent 填 {existing.pk}），'
            '不要另起一个平行的顶级阶段。'
        )

    name = (payload.get('name') or '').strip()
    if not name:
        raise SelfRunError('阶段名称不能为空。')
    start_date = payload.get('start_date') or timezone.localdate()
    end_date = payload.get('end_date')
    if end_date and end_date < start_date:
        raise SelfRunError('终点不能早于起点。')

    # 🔴 小阶段的区间必须落在上级阶段区间内。
    #    长阶段的账本按**自己的起止**现算（`stage_ledger`），跑出父区间的那些天
    #    既进不了任何一个小阶段、也不会从长阶段的汇总里消失 ——
    #    「长阶段 = 各小阶段之和」这条恒等式就此破掉，而两边各自看着都合理。
    if parent is not None:
        if start_date < parent.start_date:
            raise SelfRunError(
                f'起点早于上级阶段「{parent.name}」的起点（{parent.start_date}）—— '
                '小阶段不能跑到上级阶段之外。'
            )
        if parent.end_date and end_date and end_date > parent.end_date:
            raise SelfRunError(
                f'终点晚于上级阶段「{parent.name}」的终点（{parent.end_date}）—— '
                '小阶段不能跑到上级阶段之外。'
            )

    stage = SelfRunStage.objects.create(
        name=name, start_date=start_date, end_date=end_date,
        status='active', note=payload.get('note') or '',
        parent=parent,
        ledger_config=payload.get('ledger_config') or {},
    )

    created = []
    for i, m in enumerate(metrics_in, start=1):
        # 🔴 模板现在读**表**（可自定义）。查不到就当作「没有模板」——
        #    不报错：请求里本来就可能带全字段（向导会把模板值抄进请求），
        #    而 `template_key` 只是「来源」标记，不参与取数。
        tpl = find_template(m.get('template_key') or '')
        template = _template_fields(tpl) if tpl else {}
        direction = _validate_metric_payload(m, i, template)
        metric = SelfRunMetric.objects.create(
            stage=stage,
            template_key=m.get('template_key') or '',
            name=m.get('name') or template.get('name') or f'KPI {i}',
            period_type=m.get('period_type') or template.get('period_type') or 'weekly',
            unit=m.get('unit') or template.get('unit') or '',
            direction=direction,
            # 🔴 数值字段必须用 `.get(k, default)` —— **不能用 `or`**：
            #    `0` 是合法的目标值（「本月 0 次」是真实诉求），`or` 会把它换成模板值。
            #    ⚠️ 且「不传」≠「传 null」：不传 ⇒ 取模板默认；传 null ⇒ 就是要「没有这一档」。
            goal_value=m.get('goal_value', template.get('goal_value')),
            floor_value=m.get('floor_value', template.get('floor_value')),
            goal_why=m.get('goal_why') or template.get('goal_why') or '',
            floor_why=m.get('floor_why') or template.get('floor_why') or '',
            agg=m.get('agg') or template.get('agg') or 'sum_hours',
            source_kind=m.get('source_kind') or template.get('source_kind') or 'auto',
            source_config=m.get('source_config') or template.get('source_config') or {},
            status='active',
            sort_order=m.get('sort_order', template.get('sort_order') or i * 10),
        )
        SelfRunMetricLog.objects.create(
            metric=metric, action='created', reason='template_use',
            to_value={
                'name': metric.name, 'period_type': metric.period_type,
                'unit': metric.unit, 'direction': metric.direction,
                'goal_value': _f(metric.goal_value), 'floor_value': _f(metric.floor_value),
                'agg': metric.agg, 'source_kind': metric.source_kind,
                'source_config': metric.source_config,
            },
        )
        created.append(metric)

    return stage, created


# ══════════════════════════════════════════════════════════════
# T1b · 按期修订（「每周/每月修订下一周、月」）
# ══════════════════════════════════════════════════════════════

def _shift_period(period_type, today, offset):
    """`today` 前/后挪 `offset` 期。

    ⚠️ 月要按**日历加法**（`2026-01-31` 的下一月是 `2026-02-01` 那一期），
       不能用「+30 天」—— 那会在 2 月与 12 月静默错位。
    """
    if period_type == 'weekly':
        return today + dt.timedelta(days=7 * offset)
    total = (today.year * 12 + today.month - 1) + offset
    return dt.date(total // 12, total % 12 + 1, 1)


def list_period_options(period_type, count=6):
    """「哪几期可以修订」—— 上一期 + 本期 + 未来 `count` 期。

    🔴 周期标识只许**后端一把尺子**：前端拿 `Date` 自己算 ISO 周，
       在跨年边界（12-29 属于下一年 W01）会**静默差一周**，而且不报错。
    """
    if period_type not in ('weekly', 'monthly'):
        raise SelfRunError(f'未知周期类型：{period_type!r}')
    today = timezone.localdate()
    out = []
    for offset in range(-1, count):
        start, end, key = period_range(period_type, _shift_period(period_type, today, offset))
        out.append({
            'key': key,
            'start': str(start),
            'end': str(end),
            'offset': offset,
            'label': '上一期' if offset < 0 else ('本期' if offset == 0 else f'往后第 {offset} 期'),
        })
    return out


def list_targets(period_type, period_key, stage=None):
    """某一期「全套 KPI 的**生效目标**」—— 修订界面念的就是它。

    🔴 与 `get_current_period` 的分工：那个要**跑 7 个取数器**算读数，
       这个只回答「这一期的目标是多少」—— 修订界面不该顺带把取数也跑一遍。
       两者共用**同一份** `resolve_targets`，不写第二份口径。
    """
    stage = stage or get_open_stage()
    if stage is None:
        return None
    start, end = parse_period_key(period_type, period_key)
    metrics = [m for m in stage.metrics.filter(status='active')
               if m.period_type == period_type]
    plans_map = _plans_by_metric([m.id for m in metrics])
    rows = []
    for m in metrics:
        plans = plans_map.get(m.id) or []
        goal, floor, source, plan = resolve_targets(m, period_key, plans)
        rows.append({
            'metric_id': m.id,
            'name': m.name,
            'unit': m.unit,
            'direction': m.direction,
            'base_goal': _f(m.goal_value),
            'base_floor': _f(m.floor_value),
            'goal_value': _f(goal),
            'floor_value': _f(floor),
            'target_source': source,
            'target_source_label': TARGET_SOURCE_LABELS.get(source, ''),
            'goal_why': (plan.goal_why if plan and plan.goal_why else m.goal_why),
            'floor_why': (plan.floor_why if plan and plan.floor_why else m.floor_why),
            'plan_id': plan.id if plan else None,
            'plan_scope': plan.scope if plan else None,
            'plan_note': (plan.note if plan else '') or '',
            'plan_count': len(plans),
        })
    cur_key = current_period_meta(period_type)[0]
    return {
        'stage': stage,
        'period_type': period_type,
        'period_key': period_key,
        'period_start': str(start),
        'period_end': str(end),
        'current_key': cur_key,
        'is_current': period_key == cur_key,
        # ⚠️ 过去的期**能改**（改的是「当时该拿什么尺子」，且留痕），
        #    但界面要说清它已经过去 —— 只有**已归档**的期才会被闸门拦住（409）。
        'is_past': period_key < cur_key,
        'rows': rows,
    }


@transaction.atomic
def set_plan(metric, period_key, scope, goal_value, floor_value,
             goal_why='', floor_why='', note=''):
    """设定某一条 KPI 在**某一期**的目标（「修订下一周/月」的唯一写口）。

    🔴 归档闸门：落在**已归档周期**里 ⇒ **409** —— 与「补记」同一条规则
       （归档 = 定格，之后改目标会让读数里显示的值与结论里判的值**无声分家**）。
    🔴 `scope='from'` 会**一直生效到出现更晚的 `from`** —— 这一点必须在界面上说清，
       否则你会以为它只是「把这一期改了」。
    🔴 每次设定都写 `MetricLog`（`action='plan_changed'`）⇒ T4 的时间轴上看得见
       「哪一期换过尺子」。
    """
    scope = scope or 'single'
    if scope not in ('single', 'from'):
        raise SelfRunError(f'未知的作用域 {scope!r}（只能是 single / from）。')
    if metric.status != 'active':
        raise SelfRunError(f'「{metric.name}」已退役，先恢复它再设定目标。')
    # 顺带校验格式**与周期类型是否匹配**（周 key 送给月度 KPI 会在这里报错）
    start, _end = parse_period_key(metric.period_type, period_key)
    _assert_period_open(metric, start)
    _validate_lines(goal_value, floor_value, metric.direction, f'「{metric.name}」{period_key}')

    before = SelfRunMetricPlan.objects.filter(
        metric=metric, period_key=period_key, scope=scope,
    ).first()
    plan, _created = SelfRunMetricPlan.objects.update_or_create(
        metric=metric, period_key=period_key, scope=scope,
        defaults={
            'goal_value': goal_value, 'floor_value': floor_value,
            'goal_why': goal_why or '', 'floor_why': floor_why or '', 'note': note or '',
        },
    )
    log = SelfRunMetricLog.objects.create(
        metric=metric, action='plan_changed',
        field_name=f'{scope}:{period_key}'[:30],
        from_value=(None if before is None else {
            'goal_value': _f(before.goal_value), 'floor_value': _f(before.floor_value),
        }),
        to_value={'goal_value': _f(plan.goal_value), 'floor_value': _f(plan.floor_value)},
        reason_note=note or '',
    )
    return plan, log


@transaction.atomic
def delete_plan(plan):
    """取消某一期的设定（回到上一层口径：`single` 删掉 ⇒ 落回 `from` 或默认值）。

    ⚠️ 这里**真的是删除**，不是「冲销」—— `Plan` 是**配置**不是流水
       （流水才适用项目铁律「撤销 ≠ 删除」）。留痕由 `MetricLog` 承担。
    ⚠️ 同样受归档闸门约束：已归档的期不许动。
    """
    metric = plan.metric
    start, _end = parse_period_key(metric.period_type, plan.period_key)
    _assert_period_open(metric, start)
    info = {
        'period_key': plan.period_key, 'scope': plan.scope,
        'goal_value': _f(plan.goal_value), 'floor_value': _f(plan.floor_value),
    }
    plan.delete()
    log = SelfRunMetricLog.objects.create(
        metric=metric, action='plan_changed',
        field_name=f'{info["scope"]}:{info["period_key"]}'[:30],
        from_value=info, to_value=None,
        reason_note='取消了这一期的设定',
    )
    return metric, log


# ══════════════════════════════════════════════════════════════
# T2 · 执行
# ══════════════════════════════════════════════════════════════

def _find_current_period(stage, period_type):
    """查当期 `Period` 行。**查不到返回 `None`（不建行）。**"""
    start, end, key = period_range(period_type, timezone.localdate())
    obj = SelfRunPeriod.objects.filter(
        stage=stage, period_type=period_type, period_key=key,
    ).first()
    return obj, start, end, key


def get_current_period(period_type='weekly'):
    """「本周/本月状态」。

    🔴 **GET 不写库**（设计稿 §2.3）：
       - 当期已有行 ⇒ 返回它（若已归档 ⇒ **直接读快照，绝不重算**）；
       - 当期没有行 ⇒ 返回**虚拟对象**（`id=None`），首次写入时才建行。

    为什么不能 `get_or_create`：GET 写库 = 你翻个页就产生一行数据，
    且并发下会撞 `unique_together`。
    """
    stage = get_open_stage()
    if stage is None:
        return None, None

    obj, start, end, key = _find_current_period(stage, period_type)

    if obj is not None and obj.closed_at is not None:
        # 🔴 已归档 ⇒ 读冻结快照。**不重算** —— 否则等于没归档。
        return obj, {'source': 'snapshot', 'period_key': key, 'start': start, 'end': end}

    skipped = list(obj.skipped_metric_ids or []) if obj else []
    metrics = [m for m in stage.metrics.filter(status='active')
               if m.period_type == period_type]
    # 🔴 按期设定**一次取回**（别在循环里逐条查），再由 `compute_metric_reading` 解析 ——
    #    「这一期的目标是多少」只有 `resolve_targets` 一处实现。
    plans_map = _plans_by_metric([m.id for m in metrics])
    readings = [
        compute_metric_reading(
            m, start, end, skipped=m.id in skipped,
            period_key=key, plans=plans_map.get(m.id) or [],
        )
        for m in metrics
    ]

    if obj is None:
        obj = SelfRunPeriod(
            stage=stage, period_type=period_type, period_key=key,
            period_start=start, period_end=end,
            is_partial=start < stage.start_date,
            status='',
        )
        obj.pk = None
    obj.readings = readings
    return obj, {'source': 'live', 'period_key': key, 'start': start, 'end': end}


def _assert_period_open(metric, day):
    """🔴 落在**已归档周期**里的登记一律拒绝（409），**不静默接受**。

    为什么必须拦住：归档 = 定格 —— `Period.readings` 是那一刻算出来冻住的，
    之后再补记**不会**、也不该回头改它。
    ⇒ 静默接受这笔登记 = 明细账里有一笔、结论里没有，两边**悄悄分家**，
      而界面上两处都「看着正常」。

    出口写在错误文案里：要么先「重开这一期」（留痕），要么记到当前周期。
    """
    _, _, key = period_range(metric.period_type, day)
    closed = SelfRunPeriod.objects.filter(
        stage_id=metric.stage_id, period_type=metric.period_type,
        period_key=key, closed_at__isnull=False,
    ).first()
    if closed is None:
        return
    raise ConflictError(
        f'{key} 已经归档定格了（{timezone.localtime(closed.closed_at):%Y-%m-%d}）—— '
        f'那一期的结论不会因为这笔登记而改变。'
        f'要么先「重开这一期」（会留痕），要么把这笔记到当前周期。'
    )


def create_checkin(metric, checkin_date, value, note=''):
    """手工登记。

    🔴 `source_kind='auto'` 的条目**没有补记入口** —— 自动取错了要去改源
       （「一个写口」原则），不是在这里覆盖。
    🔴 落在已归档周期里的登记 **409**（见 `_assert_period_open`）。
    """
    if metric.source_kind == 'auto':
        raise SelfRunError(f'「{metric.name}」是自动取数项，没有补记入口（自动取错了请去改数据源）。')
    v = float(value)
    if metric.source_kind == 'auto_plus_manual' and v < 0:
        raise SelfRunError('补记不能填负数 —— 要撤销请用「撤销这一笔」。')
    day = checkin_date or timezone.localdate()
    _assert_period_open(metric, day)
    return SelfRunCheckin.objects.create(
        metric=metric, checkin_date=day, value=v, note=note or '',
    )


def reverse_checkin(checkin):
    """撤销 = **补一条负值**（项目铁律：撤销 ≠ 删除）。

    一条记录**最多被冲销一次**（再冲销就重复扣了）。
    🔴 同样受归档闸门约束 —— 冲销也是一笔新流水，落在已归档周期里就 409。
    """
    if float(checkin.value) < 0:
        raise SelfRunError('这已经是一条冲销记录了。')
    exists = SelfRunCheckin.objects.filter(
        metric=checkin.metric, note=f'冲销 #{checkin.id}',
    ).exists()
    if exists:
        raise ConflictError('这一笔已经冲销过了，不能重复冲销。')
    _assert_period_open(checkin.metric, checkin.checkin_date)
    return SelfRunCheckin.objects.create(
        metric=checkin.metric, checkin_date=checkin.checkin_date,
        value=-float(checkin.value), note=f'冲销 #{checkin.id}',
    )


@transaction.atomic
def update_metric(metric, data, reason=None, reason_note=''):
    """改 KPI 配置（goal / floor / 取数方式 / …）。

    🔴 **不新建 Metric 行** —— `metric_id` 必须稳定，否则 `Period.readings` 里的引用会失效。
    🔴 **每次改都写 `MetricLog`**，且**必须问原因**（校准 or 状态）——
       系统不判断对错，只记录；三个月后你在时间轴上自己看得出来。

    🔴 v3.64.31 起**取数方式（`source_kind`）也在这里改** —— 以前只有「建 KPI 时
       从模板挑」一个入口，建完发现「这条该自动取数」就无路可走（只能退役重建，
       而退役会带走全部手工登记）。改口径 = 换尺子：校验与建模板同一套
       （`_validate_source_config`），`agg` 由取数器推导，不许两处各说一套。
    """
    data = dict(data or {})
    if 'source_kind' in data or 'source_config' in data:
        kind = data.get('source_kind') or metric.source_kind
        cfg = data.get('source_config', metric.source_config)
        if kind == 'manual':
            # 手工项的口径只有一种：把手记的加起来。别让「手工 + 作品库取数器」
            # 这种混血存在 —— 界面会写「手工」，数却来自另一个模块。
            cfg = {'kind': 'manual_sum'}
        data['source_config'] = _validate_source_config(
            kind, cfg, f'KPI「{data.get("name") or metric.name}」',
        )
        # 取数器 → 聚合方式跟着走；调用方显式给了 `agg` 就不覆盖（保留旧行为）
        if 'agg' not in data:
            data['agg'] = READER_AGG[data['source_config']['kind']]

    tracked = ('goal_value', 'floor_value', 'source_kind', 'source_config', 'agg',
               'direction', 'name', 'unit', 'sort_order')
    logs = []
    for field in tracked:
        if field not in data:
            continue
        old = getattr(metric, field)
        new = data[field]
        if field in ('goal_value', 'floor_value'):
            old, new = _f(old), _f(new)
        if old == new:
            continue
        action = {
            'goal_value': 'goal_changed',
            'floor_value': 'floor_changed',
        }.get(field, 'config_changed')
        setattr(metric, field, new)
        logs.append(SelfRunMetricLog(
            metric=metric, action=action, field_name=field,
            from_value=old, to_value=new,
            reason=reason, reason_note=reason_note or '',
        ))
    if not logs:
        return metric, []
    metric.save()
    # ⚠️ 逐个 `save()`，不用 `bulk_create` —— 后者**不会跑 `pre_save`**，
    #    `auto_now_add` 与 `JSONField` 的序列化都会缺，落库后 `from_value` 变 NULL。
    for log in logs:
        log.save()
    return metric, logs


def retire_metric(metric, reason_note=''):
    """退役（「这条我不要了」）。

    ⚠️ 与两种「暂停」**作用域不同**（设计稿 §2.3）：
       「这周这条先不算」→ `Period.skipped_metric_ids`；
       「整个阶段歇一阵」→ `Stage.status='paused'`。
    """
    if metric.status == 'retired':
        return metric, None
    metric.status = 'retired'
    metric.save(update_fields=['status', 'updated_at'])
    log = SelfRunMetricLog.objects.create(
        metric=metric, action='retired', field_name='status',
        from_value='active', to_value='retired', reason_note=reason_note or '',
    )
    return metric, log


def revive_metric(metric, reason_note=''):
    if metric.status == 'active':
        return metric, None
    metric.status = 'active'
    metric.save(update_fields=['status', 'updated_at'])
    log = SelfRunMetricLog.objects.create(
        metric=metric, action='revived', field_name='status',
        from_value='retired', to_value='active', reason_note=reason_note or '',
    )
    return metric, log


def pause_stage(stage, reason=None, resume_at=None, note=''):
    """整个阶段暂停（休耕）。字段命名对齐 `redemption.RedemptionPeriod` 的既有先例。"""
    if stage.status not in OPEN_STAGE_STATUSES:
        raise SelfRunError(f'阶段当前是「{stage.get_status_display()}」，不能暂停。')
    stage.status = 'paused'
    stage.pause_reason = reason or 'other'
    stage.paused_since = timezone.localdate()
    stage.resume_at = resume_at
    if note:
        stage.note = note
    stage.save(update_fields=[
        'status', 'pause_reason', 'paused_since', 'resume_at', 'note', 'updated_at',
    ])
    return stage


def resume_stage(stage):
    if stage.status != 'paused':
        raise SelfRunError('阶段当前不是暂停中。')
    stage.status = 'active'
    stage.pause_reason = None
    stage.paused_since = None
    stage.resume_at = None
    stage.save(update_fields=[
        'status', 'pause_reason', 'paused_since', 'resume_at', 'updated_at',
    ])
    return stage


def heartbeat(seen=True):
    """「回访即握手」（V3：不追着你跑）。

    🔴 **只 UPDATE `last_seen_at`** —— 不判好坏、不改任何 KPI、不建记录。
    🔴 同一天最多写一次。
    """
    stage = get_open_stage()
    if stage is None:
        return None, False
    today = timezone.localdate()
    if stage.last_seen_at and timezone.localtime(stage.last_seen_at).date() == today:
        return stage, False
    stage.last_seen_at = timezone.now()
    stage.save(update_fields=['last_seen_at', 'updated_at'])
    return stage, True


def heartbeat_state(stage):
    """算「已经 N 天没在这里见到你」—— 中性文案，不是红色告警。"""
    if stage is None or stage.last_seen_at is None:
        return {'last_seen_at': None, 'days': None, 'message': None}
    days = (timezone.localdate() - timezone.localtime(stage.last_seen_at).date()).days
    message = None
    if days >= 3:
        message = f'已经 {days} 天没在这里见到你了'
    return {
        'last_seen_at': stage.last_seen_at.isoformat(),
        'days': days,
        'message': message,
    }


# ══════════════════════════════════════════════════════════════
# T3 · 复盘（唯一大量写库的阶段，写完后只读）
# ══════════════════════════════════════════════════════════════

def _nearest_previous_period_key(stage, period_type):
    """给「补归档」用：返回 `stage` 下**最近一个还没归档**的周期 key（若在追补）。"""
    today = timezone.localdate()
    start, end, key = period_range(period_type, today)
    # 若当前周期还没结束（今天就在周期内），则上一个周期的 key 才算「该归档了」
    if period_type == 'weekly':
        prev_ref = start - dt.timedelta(days=1)
    else:
        prev_ref = start - dt.timedelta(days=1)
    _, _, prev_key = period_range(period_type, prev_ref)
    return prev_key


@transaction.atomic
def close_period(period_type, period_key, skipped_metric_ids=None, answer_sheet=None):
    """归档 = 定格（设计稿 §5.1 事务里的六件事）。

    🔴 **系统不自动归档** —— 归不归档、什么时候归档是**你的动作**（V3）。
    🔴 已归档的周期再次归档 ⇒ **409**（不静默覆盖）。
    """
    stage = get_open_stage()
    if stage is None:
        raise SelfRunError('当前没有进行中的阶段。')

    start, end = parse_period_key(period_type, period_key)
    obj = SelfRunPeriod.objects.filter(
        stage=stage, period_type=period_type, period_key=period_key,
    ).first()
    if obj is not None and obj.closed_at is not None:
        raise ConflictError(f'{period_key} 已经归档过了。')

    skipped = list(skipped_metric_ids or [])
    metrics = [m for m in stage.metrics.filter(status='active') if m.period_type == period_type]
    plans_map = _plans_by_metric([m.id for m in metrics])
    targets = {
        m.id: resolve_targets(m, period_key, plans_map.get(m.id) or [])
        for m in metrics
    }
    readings = [
        compute_metric_reading(
            m, start, end, skipped=m.id in skipped,
            period_key=period_key, plans=plans_map.get(m.id) or [],
        )
        for m in metrics
    ]

    now = timezone.now()
    # ── 判定 ──────────────────────────────────────────────────
    # 周按达标率；月**只按三问**（v3.64.6）。
    # 🔴 月度归档必须先答完三问：档位在归档这一刻定格，之后补答不改档
    #    （要改走「重开这一期」）。若允许「没答就归档」，这一期会落一个空档位，
    #    而补答又不许改档 ⇒ 这期永远没有结论 —— 所以在这里拦住，而不是事后补。
    if period_type == 'monthly':
        _, answered = monthly_answer_stats(answer_sheet)
        if answered < MONTHLY_QUESTION_COUNT:
            raise SelfRunError(
                f'月度的结论只来自三问，还有 {MONTHLY_QUESTION_COUNT - answered} 个没答 —— '
                '先答完这 3 个问题再归档（答「否」也算答过）。'
            )
        status = compute_monthly_status(answer_sheet)
    else:
        status = compute_period_status(stage, readings)

    # 补归档留痕：距周期结束超过 7 天 ⇒ 显式标注「此数事后补算」
    over = (now.date() - end).days
    is_backfilled = over > BACKFILL_WARN_DAYS

    if obj is None:
        obj = SelfRunPeriod(stage=stage, period_type=period_type, period_key=period_key)
    obj.period_start = start
    obj.period_end = end
    obj.is_partial = start < stage.start_date
    obj.status = status
    obj.readings = readings
    # 🔴 指纹算的是**这一期生效**的目标值（按期修订过 ⇒ 两期本来就不是同一把尺子）。
    #    仍用 Decimal 原值拼串（不用 float），否则「12.00」与「12.0」会把指纹改掉。
    obj.config_fingerprint = config_fingerprint(
        stage, resolved={mid: (t[0], t[1]) for mid, t in targets.items()},
    )
    obj.skipped_metric_ids = skipped
    if answer_sheet:
        obj.answer_sheet = answer_sheet
    obj.closed_at = now
    obj.is_backfilled = is_backfilled
    obj.backfilled_at = now if is_backfilled else None
    obj.save()
    return obj, {'backfill_days': over if is_backfilled else 0}


@transaction.atomic
def update_review(period, review_text=None, answer_sheet=None):
    """归档后**仍可写**的两项：你写的字（记忆型 ≠ 数据型）。

    🔴 每次补写留 `at` ⇒ 界面上标「补写于归档后 N 天」——
       「当时的想法」和「事后的解释」不能混在一起。

    🔴 v3.64.6：**补答三问不再重判档位**。归档 = 定格，档位要改必须走
       `reopen_period`（限最近一期 + 写原因 + 留痕）。旧实现在这里直接
       `period.status = new_status`，于是「归档后补答一句」就能把历史结论改掉，
       而历史复盘页还写着「归档那刻数字定格」—— 同一屏两套说法。
    """
    written = []
    if review_text is not None and review_text != period.review_text:
        edits = list(period.review_edits or [])
        if period.closed_at is not None:
            days = (timezone.localdate() - timezone.localtime(period.closed_at).date()).days
            edits.append({
                'text': period.review_text or '',
                'at': timezone.now().isoformat(),
                'days_after_close': days,
            })
        period.review_edits = edits
        period.review_text = review_text
        written.append('review_text')
    if answer_sheet is not None:
        period.answer_sheet = answer_sheet
        written.append('answer_sheet')
    if written:
        period.save()
    return period, written


def reopen_period(period, reason):
    """重开（改历史判定的**唯一出口**，且留痕）。

    ⚠️ 限**最近一期**，且要求阶段仍在进行中 —— 否则就是「改写历史」。
    """
    if period.closed_at is None:
        raise SelfRunError('这一期还没归档，不需要重开。')
    if not reason:
        raise SelfRunError('重开必须写原因。')
    stage = period.stage
    latest = stage.periods.filter(
        period_type=period.period_type, closed_at__isnull=False,
    ).order_by('-period_start').first()
    if latest is None or latest.id != period.id:
        raise SelfRunError('只允许重开最近一期（更早的属于「改写历史」）。')
    if stage.status not in OPEN_STAGE_STATUSES:
        raise SelfRunError('阶段已收尾，不能再重开周期。')
    period.closed_at = None
    period.reopen_count = (period.reopen_count or 0) + 1
    period.reopened_at = timezone.now()
    period.reopen_reason = reason
    period.save()
    return period


# ══════════════════════════════════════════════════════════════
# T4 · 事后分析（几乎不写库，唯一例外是阶段总结）
# ══════════════════════════════════════════════════════════════

def compute_stage_summary(stage):
    """阶段总结的**数字部分**（实时算，不落库）。

    🔴 只有「你写的那段话」落库（`save_summary`），数字永远现算 ——
       因为改口径后数字应该跟着变；而你写话时**看到的那个数**会另存进 `summary_snapshot`。
    """
    periods = list(stage.periods.filter(closed_at__isnull=False).order_by('period_start'))
    weekly = [p for p in periods if p.period_type == 'weekly']
    monthly = [p for p in periods if p.period_type == 'monthly']
    counted_weeks = [p for p in weekly if not p.is_partial]   # 残缺周不进阶段达标率

    metrics = list(stage.metrics.all())
    plans_map = _plans_by_metric([m.id for m in metrics])
    per_metric = []
    for m in metrics:
        pool = weekly if m.period_type == 'weekly' else monthly
        values, hits = [], 0
        best = None
        for p in pool:
            for r in (p.readings or []):
                if r.get('metric_id') != m.id or r.get('skipped'):
                    continue
                if r.get('verdict') == 'unknown':
                    continue
                v = r.get('final_value')
                if v is None:
                    continue
                values.append(v)
                if r.get('verdict') in ('goal', 'floor'):
                    hits += 1
                if best is None or v > best['value']:
                    best = {
                        'value': v,
                        'period_key': p.period_key,
                        # 周号 + 日期区间，前端零算（「W42」单独印出来读不出是哪几天）
                        'period_label': period_range_label(p),
                    }
        plans = plans_map.get(m.id) or []
        per_metric.append({
            'metric_id': m.id,
            'name': m.name,
            'unit': m.unit,
            'period_type': m.period_type,
            # ⚠️ 这里是**阶段默认**的双档（`Metric` 上的值）。
            #    按期改过的期，其真实目标在各自的 `readings` 里（冻结过）——
            #    `plan_periods` 用来提示「这条换过尺子，别拿默认值去读往期」。
            'goal_value': _f(m.goal_value),
            'floor_value': _f(m.floor_value),
            'plan_count': len(plans),
            'plan_periods': sorted({p.period_key for p in plans}),
            'avg': round(sum(values) / len(values), 2) if values else None,
            'hit': hits,
            'total': len(values),
            'best': best,
        })

    # 🔴 按**枚举**生成，不逐档手写 —— 加一档（v3.62.45 的 `great`）时
    #    手写版会静默漏掉它，分布图少一根柱、总数还对不上（最难发现的那种）。
    breakdown = {'period_type': 'weekly'}
    for key, _label in PERIOD_STATUS_CHOICES:
        breakdown[key] = sum(1 for p in counted_weeks if p.status == key)

    return {
        'stage_id': stage.id,
        'name': stage.name,
        'start_date': str(stage.start_date),
        'end_date': str(stage.end_date) if stage.end_date else None,
        'total_weeks': len(weekly),
        'counted_weeks': len(counted_weeks),
        'partial_weeks': len(weekly) - len(counted_weeks),
        'total_months': len(monthly),
        'metrics': per_metric,
        'weekly_breakdown': breakdown,
        'monthly_statuses': [
            {'period_key': p.period_key, 'status': p.status,
             'yes_count': _monthly_yes_count(p.answer_sheet)}
            for p in monthly
        ],
        # 指纹分组：这一阶段用过几把尺子（T4「尺子断点」的骨架）
        'fingerprints': _fingerprint_groups(periods),
    }


def _monthly_yes_count(answer_sheet):
    """阶段汇总里的「答『是』几问」—— 一个都没答返 `None`（**不是 0**）。"""
    if not answer_sheet:
        return None
    yes, answered = monthly_answer_stats(answer_sheet)
    return yes if answered else None


def _fingerprint_groups(periods):
    """按 `config_fingerprint` 把周期分组 —— 同组才可直接比（T4 指纹闸门）。"""
    groups = []
    for p in periods:
        fp = p.config_fingerprint or ''
        if groups and groups[-1]['fingerprint'] == fp:
            groups[-1]['periods'].append(p.period_key)
        else:
            groups.append({'fingerprint': fp, 'periods': [p.period_key]})
    return groups


@transaction.atomic
def save_summary(stage, text):
    """写阶段总结 —— **T4 唯一落库的分析**。

    🔴 同时冻结 `summary_snapshot`（**你写这段话时看到的数**）：
       将来口径变了重算会不同，而你当时是看着那个数写下这段话的；
       不冻结 ⇔ 你留下的文字会与旁边的数字对不上，且你不知道是哪个变了。
    """
    snapshot = compute_stage_summary(stage)
    stage.summary = text or ''
    stage.summary_snapshot = snapshot
    stage.summary_at = timezone.now()
    stage.save(update_fields=['summary', 'summary_snapshot', 'summary_at', 'updated_at'])
    return stage, snapshot


@transaction.atomic
def close_stage(stage, end_date=None):
    """收尾阶段：写 `end_date` + `status='closed'`。"""
    if stage.status == 'closed':
        raise SelfRunError('这个阶段已经收尾了。')
    if not (stage.summary or '').strip():
        raise SelfRunError('收尾前请先写下阶段总结（哪怕一句话）。')
    stage.end_date = end_date or timezone.localdate()
    stage.status = 'closed'
    stage.save(update_fields=['end_date', 'status', 'updated_at'])
    return stage


@transaction.atomic
def copy_stage(from_stage, name, start_date):
    """用这个配置开新阶段。

    | 复制 | 不复制 | 必然不同 |
    |---|---|---|
    | `active` 的 `Metric`（含 `source_config` / 双档 / `why`） | `Period`（历史结论**永远跟着原阶段**） | `config_fingerprint`（新 `stage.id`） |
    | `template_key`（来源可追溯） | `Checkin`（明细不跟） | 🔴 **目标值必须重设**（阶段变了，KPI 可能不同） |

    🔴 必须在界面上显式说「目标值仍是上一阶段的，请逐条重设」——
       否则改过目标值之后你会以为「我变差了」，**实际是尺子换了**（V2）。
    """
    if not name or not name.strip():
        raise SelfRunError('新阶段名称不能为空。')
    source_metrics = list(
        from_stage.metrics.filter(status='active').order_by('sort_order', 'id')
    )
    # 🔴 长阶段零 KPI，复制出来会变成一个「没有判定的阶段」—— 看着正常、实际空转。
    if not source_metrics:
        raise SelfRunError(
            f'「{from_stage.name}」没有 KPI（长阶段只汇总），不能复制成跑 KPI 的阶段。'
        )
    # 互斥按 parent 分组；复制**继承上级** —— 在长阶段下复制出来的仍是它的小阶段。
    siblings = SelfRunStage.objects.filter(
        status__in=OPEN_STAGE_STATUSES, parent_id=from_stage.parent_id,
    )
    if siblings.exists():
        raise SelfRunError('已有进行中的阶段，请先收尾它。')

    stage = SelfRunStage.objects.create(
        name=name.strip(), start_date=start_date or timezone.localdate(),
        status='active', note=f'复制自「{from_stage.name}」',
        parent=from_stage.parent,
    )
    created = []
    for m in source_metrics:
        new = SelfRunMetric.objects.create(
            stage=stage, template_key=m.template_key, name=m.name,
            period_type=m.period_type, unit=m.unit, direction=m.direction,
            goal_value=m.goal_value, floor_value=m.floor_value,
            goal_why=m.goal_why, floor_why=m.floor_why,
            agg=m.agg, source_kind=m.source_kind, source_config=m.source_config,
            status='active', sort_order=m.sort_order,
        )
        SelfRunMetricLog.objects.create(
            metric=new, action='created',
            reason_note=f'复制自阶段 #{from_stage.id}「{from_stage.name}」',
            to_value={'copied_from_metric_id': m.id},
        )
        created.append(new)
    return stage, created


# ══════════════════════════════════════════════════════════════
# 模板 vs 库里的行：差异只读出口（§114.1）
# ══════════════════════════════════════════════════════════════

# 构成「口径」的字段：改这些等于换了尺子，必须让人看见
DRIFT_FIELDS = (
    'name', 'unit', 'period_type', 'direction', 'agg',
    'source_config', 'goal_value', 'floor_value',
)

_FIELD_LABELS = {
    'name': '名称', 'unit': '单位', 'period_type': '周期类型',
    'direction': '方向', 'agg': '汇总方式', 'source_config': '取数口径',
    'goal_value': '目标值', 'floor_value': '底线值',
}


def _plain(value):
    """Decimal / None 统一成可 JSON 化的字面量，便于前端直接显示。"""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def template_drift(stage):
    """本阶段各 KPI 与**模板库**之间的口径差异（只读，不修数据）。

    🔴 为什么需要它：模板是「起点」、阶段是「拷贝」（`templates.py` 铁律 1）。
       模板改了不会回溯改已建阶段 —— 这条规则是对的（否则改模板会重写历史口径），
       但它带来一个副作用：**两处数字不一样，而没有任何地方会告诉你**。
       v3.62.0 那次「输出次数 → 留下件数」就静默漏掉了库里那两行。

    🔴 本函数**只报差异、绝不写库**。要不要追平、追哪几个字段，是用户的决定
       —— 尤其 `goal_value` / `floor_value` 属于「用户手调过的输入」，
       自动覆盖会把人的判断抹掉（§114.1）。

    返回结构：
        [{'metric_id', 'template_key', 'name', 'status',
          'diffs': [{'field', 'label', 'db', 'tpl'}]}, ...]
        只含有差异的条目；无差异返回 []。
    """
    metrics = list(stage.metrics.all().order_by('sort_order', 'id'))
    keys = [m.template_key for m in metrics if m.template_key]
    if not keys:
        return []
    tpl_map = {t.key: t for t in SelfRunTemplate.objects.filter(key__in=keys)}

    out = []
    for m in metrics:
        tpl = tpl_map.get(m.template_key) if m.template_key else None
        if tpl is None:
            # 模板被用户删了 —— 不是差异，是「来源已不在了」，单独标出
            if m.template_key and m.status == 'active':
                out.append({
                    'metric_id': m.id, 'template_key': m.template_key,
                    'name': m.name, 'status': m.status,
                    'diffs': [{'field': 'template', 'label': '来源模板',
                               'db': m.template_key, 'tpl': None}],
                })
            continue
        diffs = []
        for field in DRIFT_FIELDS:
            a, b = getattr(m, field, None), getattr(tpl, field, None)
            if field in ('goal_value', 'floor_value'):
                a, b = _plain(a), _plain(b)
            if a != b:
                diffs.append({
                    'field': field, 'label': _FIELD_LABELS.get(field, field),
                    'db': a, 'tpl': b,
                })
        if diffs:
            out.append({
                'metric_id': m.id, 'template_key': m.template_key,
                'name': m.name, 'status': m.status, 'diffs': diffs,
            })
    return out


# ══════════════════════════════════════════════════════════════
# 复盘补充：本周目标完成情况 + 时间流失（只读，不落库）
# ══════════════════════════════════════════════════════════════

LOSS_ATTRIBUTION = '流失'      # 六词归因里的那一档（真源 temporal/constants.py）

# 「这一周我做了什么」每天列几件 —— 这是**版面预算**，不是口径：
# 多列几件不改变任何数，只改变一屏里能看见几行。
WHAT_HAPPENED_PER_DAY = 3

# 时段轴一次最多画多少块。一周实测 47 条、一个月约 200 条，400 是防极端值。
# 🔴 真触发了必须**说出来**（`truncated` 随数下发）：图上少一块而没人知道，
#    比不画更糟 —— 用户会以为「那天就这些」。
WHAT_HAPPENED_BLOCK_LIMIT = 400

# 跨午夜被切成残片的门槛（分钟）：短于这个的 split 段不参与纵轴范围计算。
# 🔴 一条 `23:35 → 次日 00:37` 的记录会切成 25 分钟的头段和 37 分钟的尾段。
#    头段本来就把当天画到 24:00，尾段那 37 分钟却足以把纵轴从 07:00 拉到 00:00 ——
#    实测 W42 一周 51 分钟的残片换来 235px 空白，用户看到的是「凌晨 2 点 / 4 点 / 6 点」
#    三条毫无内容的刻度。⚠️ 残片**照样下发**，前端在列头标出来，
#    「按错位置画一个块」比「不画」更糟。
WHAT_HAPPENED_FRAGMENT_MIN = 60


def _day_segments(start_local, end_local):
    """把一段真实时间切成「每个本地日一段」，返回 `[(date, 起分钟, 止分钟)]`。

    🔴 为什么必须按天切：`23:00 → 次日 02:00` 那 3 小时跨两列。
       整块挪到第二天，「昨晚熬夜」就变成「今天凌晨」；不切而画在第一天，
       块会冲出 24:00 的底边。
    🔴 分钟**相对当天 00:00**（0–1440），不是绝对时间戳 —— 前端按比例摆位置即可，
       不必解析时间串、不必再碰一次时区（`USE_TZ` 下 `new Date()` 会差 8 小时）。
    """
    out = []
    cur = start_local
    while cur < end_local:
        midnight = dt.datetime.combine(
            cur.date() + dt.timedelta(days=1), dt.time.min,
        ).replace(tzinfo=cur.tzinfo)
        seg_end = min(end_local, midnight)
        frm = cur.hour * 60 + cur.minute + cur.second / 60
        to = 1440.0 if seg_end >= midnight else (
            seg_end.hour * 60 + seg_end.minute + seg_end.second / 60
        )
        if to > frm:
            out.append((cur.date(), round(frm, 1), round(to, 1)))
        cur = seg_end
    return out


def _span_of(blocks):
    """纵轴范围：**上边界只由主体块决定**，跨午夜的零碎残片不参与。

    🔴 为什么上边界要裁：一条 `23:35 → 次日 00:37` 的记录会切成 25 分钟的头段
       和 37 分钟的尾段。头段本来就把当天画到 24:00，尾段那 37 分钟却足以
       把纵轴从 07:00 拉回 00:00 —— 实测 W42 一周 51 分钟残片换来 235px 空白，
       用户看到的是「凌晨 2 点 / 4 点 / 6 点」三条什么都没记的刻度。
    🔴 为什么**下边界不裁**：只有 `23:35–24:00` 那种头段能顶到 24:00，
       而它离别的块通常只差几十分钟（几十像素）；裁掉它，一条真实的
       深夜活动就只剩列顶一个数字。宁可多 40px，不丢事。
    ⚠️ 被裁掉的残片**仍在 `blocks` 里**，前端在列顶标「＋37m」——
       它的头段就画在左边那一列，所以什么都没丢。
    ⚠️ 全是残片时（只记了一条 `23:50 → 00:30`）退回用全部块，
       否则纵轴会是一个没有意义的零长度区间。
    """
    core = [b for b in blocks
            if b['split'] is None or b['minutes'] >= WHAT_HAPPENED_FRAGMENT_MIN]
    basis = core or blocks
    return {
        'from': min(b['from'] for b in basis),
        'to': max(b['to'] for b in blocks),
    }


def _build_blocks(rows, attr):
    """时段轴的数据：**一条记录一块**，跨天切成多块。

    与 `days` 的差别是**不合并**：同一天「刷短视频」有 3 条就画 3 块，
    因为它们在一天里的位置不同 —— 合并了就没有「几点到几点」这回事了。
    `days` 那边合并是为了让文字列表回答「今天做了几件事」，两个用途各按各的来。

    ⚠️ 只给「画得出来」的字段，不给时间串：前端不解析日期、不碰时区。
    """
    blocks = []
    for r in rows:
        if r.start_time is None:
            continue
        s = timezone.localtime(r.start_time)
        if r.end_time is not None:
            e = timezone.localtime(r.end_time)
        else:
            # `end_time` 缺失时用时长兜 —— 时长是录入时给的那一个，
            # 比「不知道到几点」诚实，也不会在图上留一个空洞。
            e = s + dt.timedelta(hours=float(r.duration_hours or 0))
        if e <= s:
            continue    # 脏数据（终点早于起点）不画，也不报错 —— 它不影响别的块

        segs = _day_segments(s, e)
        for i, (day, frm, to) in enumerate(segs):
            blocks.append({
                'date': day.isoformat(),
                'from': frm,
                'to': to,
                'minutes': round(to - frm, 1),
                'task_name': r.task_name,
                'attribution': attr.get(r.task_name) or '',
                # None=完整；head=前一天那截；tail=次日那截；mid=中间整天
                'split': None if len(segs) == 1 else (
                    'head' if i == 0 else 'tail' if i == len(segs) - 1 else 'mid'
                ),
            })

    # 🔴 `span` 用**截断前**的全集算：截断是版面限制，
    #    不该顺手把纵轴范围也改小（那会让剩下的块换个比例尺）。
    span = _span_of(blocks) if blocks else None

    truncated = 0
    if len(blocks) > WHAT_HAPPENED_BLOCK_LIMIT:
        truncated = len(blocks) - WHAT_HAPPENED_BLOCK_LIMIT
        blocks.sort(key=lambda b: -b['minutes'])    # 先保时长长的（信息量大）
        blocks = blocks[:WHAT_HAPPENED_BLOCK_LIMIT]
    blocks.sort(key=lambda b: (b['date'], b['from']))
    return blocks, span, truncated


def _what_happened(rows, attr, excluded, start, end):
    """「这一周我做了什么」——按**本地日期**分组，每天取时长最长的几件。

    🔴 为什么按本地日期：`start_time` 存的是 UTC（`USE_TZ=True`），直接 `.date()`
       会把 0–8 点的记录算到前一天 —— 而「昨晚熬夜写代码」正好落在那个区间。
       错一天，回忆就对不上号。
    🔴 这里给的是**做过的事**（任务名），不是汇总数：复盘页要回答的是
       「我忘了这周干了什么」，「成长 15.4h」这种数勾不起任何回忆。
    🔴 排除**睡眠类**（`contrib_excluded_names()`，与贡献图同一份名单）：
       睡眠每天都有、时长最长，不排掉它「周一做了：休息睡眠 8h」就恒排第一，
       这一块等于白做。而且「睡了多久」在健康/护栏卡里已经有出口。

    🔴 同一个函数产出两套视图（v3.64.35）：
       · `days`  —— **合并后**的任务与小时（文字列表用，回答「今天做了几件事」）
       · `blocks` —— **不合并**的时段区间（时间轴用，回答「几点到几点」）
       两套都从这里出，不各写一份取数：一旦分成两个函数，「这周做了什么」
       就会在列表和图里给出两组不同的记录（铁律「同一事实一把尺子」）。
    """
    from apps.temporal.constants import ATTRIBUTION_ORDER, WEEKDAY_LABELS

    rows = [r for r in rows if r.task_name not in excluded]

    by_day = {}
    for r in rows:
        if r.start_time is None:
            continue
        by_day.setdefault(timezone.localtime(r.start_time).date(), []).append(r)

    days = []
    for d in sorted(by_day):
        # 先按任务名合并**再**排序：同一天「刷短视频」常有 3–4 条记录，
        # 不合并的话前 3 格里会有两格是同名任务，一天看起来只做了 2 件事。
        per = {}
        for r in by_day[d]:
            per[r.task_name] = per.get(r.task_name, 0.0) + float(r.duration_hours or 0)
        ranked = sorted(per.items(), key=lambda x: -x[1])
        days.append({
            'date': d.isoformat(),
            'md': f'{d.month}/{d.day}',
            'weekday': WEEKDAY_LABELS[d.weekday()],
            'total_hours': round(sum(per.values()), 1),
            'items': [
                {
                    'task_name': k,
                    'hours': round(v, 1),
                    'attribution': attr.get(k, ''),
                }
                for k, v in ranked[:WHAT_HAPPENED_PER_DAY]
            ],
            # 没列出来的还有几件 —— 让「3 件」看起来是节选，不像「这周只做了 3 件」
            'more': max(len(ranked) - WHAT_HAPPENED_PER_DAY, 0),
        })

    by_attr = {}
    for r in rows:
        k = attr.get(r.task_name) or '未归类'
        by_attr[k] = by_attr.get(k, 0.0) + float(r.duration_hours or 0)
    order = {k: i for i, k in enumerate(ATTRIBUTION_ORDER)}
    attr_totals = [
        {'label': k, 'hours': round(v, 1)}
        for k, v in sorted(by_attr.items(), key=lambda x: order.get(x[0], 99))
    ]

    blocks, span, truncated = _build_blocks(rows, attr)

    # 列 = 周期内的**每一天**，没记录的那天也占一列 ——
    # 否则「周三整天没记」和「周三窄一截」在图上看不出区别，而它们是两件事。
    columns = []
    d = start
    while d < end:
        columns.append({
            'date': d.isoformat(),
            'md': f'{d.month}/{d.day}',
            'weekday': WEEKDAY_LABELS[d.weekday()],
        })
        d += dt.timedelta(days=1)

    return {
        'days': days,
        'day_count': len(days),
        'attr_totals': attr_totals,
        'columns': columns,
        'blocks': blocks,
        'span': span,
        'truncated': truncated,
    }


# ══════════════════════════════════════════════════════════════
# 这一期干成了什么（v3.64.37 · 只读汇总，不落库）
# ══════════════════════════════════════════════════════════════
#
# 三栏：出了成品（作品）/ 完成了里程碑 / 办完的事（小确幸秩序型 + 收件箱 done）。
#
# 🔴 **不给跨源总数**：同一件事可能既是「作品」又在「小确幸」里记过
#    （10-18 那篇文章两处都有），合并成一个数就是重复计数，而且无法回头去重。
#    三栏各报各的数，是唯一诚实的做法。
#
# 🔴 **小确幸只收 `joy_type='秩序型'`**（用户 2026-11-07 定的判据：秩序型 = 掌控感）：
#    「吃了个大榴莲」「看电影」不该进「干成了什么」。代价是**未标类型的会漏**
#    （库里 71 条有 36 条空着）—— 所以同时下发 `untyped_count`，
#    让前端能说一句「另有 N 条没标类型」，而不是让它们静默消失。
#    （铁律：取数上限必须说明或给出路。）

_OUTCOME_LIMIT = {'works': 8, 'milestones': 8, 'finished': 20}

_COMPLETED_PREFIX = re.compile(r'^完成[：:\s]+')


def _norm_outcome_title(text):
    """把「完成：xxx」和「xxx」归一到同一个比较键，用于收件箱与小确幸去重。

    用户的真实用法是：收件箱里一件事做完标 `done`，觉得值得回味再手写一条
    小确幸（库里 43 条 done 有 8 条与小确幸标题逐字相同）。

    🔴 **只做精确相等，不做模糊匹配**：包含 / 相似度会把
       「发公众号关于一步的内容」和「发表了文章」判成同一件 —— 那是**猜**。
       猜错的后果是「干成的事少了一件」，而页面上看不出来（少一行不报错）。
       精确匹配的代价是漏掉措辞不同的重复 —— **宁可漏，不可错**。
    """
    return _COMPLETED_PREFIX.sub('', (text or '').strip())


def _md_weekday(day):
    """`{date, md, weekday}` —— 时间一律后端给，前端零算（禁 `new Date()`）。"""
    from apps.temporal.constants import WEEKDAY_LABELS

    return {
        'date': day.isoformat(),
        'md': f'{day.month}/{day.day}',
        'weekday': WEEKDAY_LABELS[day.weekday()],
    }


def _period_outcomes(start, end, done_milestones):
    """这一期「干成了什么」：三栏明细，每栏 `count` 与 `items` 出自同一次取数。

    区间一律**半开** `[start, end)`：
    - 作品 `created_at`（timestamptz）
    - 收件箱 `processed_at`（timestamptz）
    - 小确幸 `time`（DateField；`__lt=end` 即「到 end 前一天」，含当天）

    ⚠️ `done_milestones` 由调用方从**同一个** `due_rows` 筛出来传进来 ——
       不在这里重查。自己再查一次就是「同一件事两份取数」，一旦分叉
       就是「成果卡说 2 个、缺口卡说 3 个」，而两个数各自看着都合理。
    """
    from apps.inbox.models import InboxItem
    from apps.sugar.constants import resolve_happiness_band
    from apps.sugar.models import SugarRecord

    from . import readers

    # ① 出了成品 —— 复用 KPI「留下件数」的取数器（`works_count`），不另查一次。
    #    ⚠️ 不走 `_stage_works`：那个函数内部会 `end + 1 天`（它的调用方传的是
    #    「区间最后一天 inclusive」），而这里的 `end` 是半开上界，走它会**多吃一天**。
    works_out = readers.works_count(None, start, end)
    works_items = []
    for row in works_out['breakdown'][::-1]:  # 倒序 = 最近成形的排前面
        day = dt.date.fromisoformat(row['extra']['created_at'][:10])
        works_items.append({
            'id': row['extra']['id'],
            # 三栏统一叫 `title`（作品模型里字段名是 `name`）——
            # 前端一张卡一条时间线，不该为「这栏取哪个键」写分支
            'title': row['label'],
            'kind': row['l2'],
            'status': row['extra']['status'],
            **_md_weekday(day),
        })

    # ② 完成了里程碑（口径见 `compute_period_extras` docstring：本期该交且已交）
    milestone_items = [
        {
            'id': m.id,
            'title': m.title,
            'goal': m.goal.title if m.goal_id else '',
            **_md_weekday(m.target_date),
        }
        for m in reversed(done_milestones)
    ]

    # ③ 办完的事 = 小确幸（只秩序型）+ 收件箱 done，按标题归一后去重
    sugar_qs = SugarRecord.objects.filter(time__gte=start, time__lt=end)
    merged = {}
    for r in sugar_qs.filter(joy_type='秩序型').order_by('time', 's_id'):
        band = resolve_happiness_band(r.level_of_happiness)
        merged[_norm_outcome_title(r.title)] = {
            'id': r.s_id,
            'title': r.title,
            'source': 'sugar',
            'date': r.time,  # 先留 date 对象，排序要用
            'happiness_label': band['label'],
            'happiness_color': band['color'],
        }

    # ⚠️ 时间边界只在 `readers._aware` 一处实现（本地零点 → UTC aware）——
    #    这里不另写一份 `make_aware(combine(...))`：那会是第二把尺子，
    #    哪天它改了（比如换时区策略），这一处会静默错开 8 小时。
    inbox_qs = InboxItem.objects.filter(
        status='done',
        processed_at__gte=readers._aware(start),
        processed_at__lt=readers._aware(end),
    ).order_by('processed_at')
    for it in inbox_qs:
        key = _norm_outcome_title(it.content)
        if key in merged:
            # 同一件事两处都记过 —— 只出一行，来源标「两处」。
            # 不删除任何一边：小确幸那条带着快乐档位，是本行更好的载体。
            merged[key]['source'] = 'both'
            continue
        merged[key] = {
            'id': it.id,
            'title': it.content,
            'source': 'inbox',
            'date': timezone.localtime(it.processed_at).date(),
            'happiness_label': None,
            'happiness_color': None,
        }

    finished = sorted(
        merged.values(), key=lambda x: (x['date'], x['id']), reverse=True,
    )
    for item in finished:
        item.update(_md_weekday(item['date']))  # date 对象 → ISO 串 + md/weekday

    def _pack(items, limit):
        return {
            'count': len(items),
            'items': items[:limit],
            'limit': limit,
            # `count` 是全量、`items` 可能截断 —— 两个数都下发，前端才能说「还有 N 条」
            'truncated': len(items) > limit,
        }

    works = _pack(works_items, _OUTCOME_LIMIT['works'])
    milestones = _pack(milestone_items, _OUTCOME_LIMIT['milestones'])
    finished_pack = _pack(finished, _OUTCOME_LIMIT['finished'])
    # 未标类型 ≠ 没完成、也 ≠ 不是完成：是「没分类」，所以单列、不进 count。
    # 脏值（'社交' / '其他' / '创造' 等早期词表残留）也不算未标 —— 它们标过。
    finished_pack['untyped_count'] = sugar_qs.filter(joy_type='').count()

    return {
        'works': works,
        'milestones': milestones,
        'finished': finished_pack,
        'empty': not (works['count'] or milestones['count'] or finished_pack['count']),
    }


def compute_period_extras(period_type, start, end):
    """每周/每月复盘的三块补充。

    ① **这一周我做了什么**：按天分组的具体任务（勾回忆用）。
    ② **目标完成情况**：本期到期的里程碑、其中完成了几个、历史逾期还没清的几个。
    ③ **时间流失**：本期归因「流失」的小时、占全部记录小时的比例、TOP 明细。

    🔴 只读、不落库：这三块是**派生值**（以后能重算出同样结果 ⇒ 不落库），
       归档时它们会随 `readings` 一起冻进快照——但快照里存的是**结论**，
       这里算的是**当下**。所以归档后不要指望它跟快照一致，属于正常。

    ⚠️ 里程碑没有 `completed_at` 字段，「本期完成」只能用 `target_date` 落在
       本期 + `status='completed'` 判定，语义是「**本期该交、且已交**」，
       不是「本期交的」。两者在补记场景下会不同，这里刻意选前者——
       因为复盘问的是「这周该做的事做完了吗」。
    """
    from apps.goals.models import Milestone
    from apps.temporal.services import contrib_excluded_names, resolve_attribution

    # 一次取出本期到期的里程碑，`due` / `done` / 缺口卡的 `items` / 成果卡的
    # 「完成了里程碑」全都从**这一份**里取（v3.64.37）。
    # 🔴 原先 `due`/`done` 各一次 `count()`、`items` 再一次 `select_related`，
    #    三处口径虽然一致，但成果卡要的「已完成明细」被 `[:8]` 截掉了 ——
    #    共用这一份就不存在「缺口卡 8 条、成果卡另算」的分叉。
    due_rows = list(
        Milestone.objects.filter(target_date__gte=start, target_date__lt=end)
        .select_related('goal').order_by('target_date')
    )
    due = len(due_rows)
    done_milestones = [m for m in due_rows if m.status == 'completed']
    done = len(done_milestones)
    overdue_qs = Milestone.objects.filter(target_date__lt=start).exclude(status='completed')
    overdue = overdue_qs.count()

    items = [
        {
            'id': m.id,
            'title': m.title,
            'goal': m.goal.title if m.goal_id else '',
            'target_date': m.target_date.isoformat() if m.target_date else None,
            'status': m.status,
        }
        for m in due_rows[:8]
    ]

    all_rows = temporal_rows({}, start, end)
    # 🔴 归因走**同一个函数**（`resolve_attribution`，含赎回期规则覆盖）——
    #    时间统计页、仪表盘护栏卡都是它。旧实现用 `{'l1': ['流失']}` 过滤，
    #    而那条路读的是 `TaskMeta.default_attribution`：被规则覆盖成「流失」的任务
    #    在这里会**静默漏掉**，同一件事于是有两个数（铁律「一把尺子」）。
    names = sorted({r.task_name for r in all_rows})
    attr = resolve_attribution(names) if names else {}

    loss_rows = [r for r in all_rows if attr.get(r.task_name) == LOSS_ATTRIBUTION]
    loss = sum(float(r.duration_hours or 0) for r in loss_rows)
    total = sum(float(r.duration_hours or 0) for r in all_rows)

    per = {}
    for r in loss_rows:
        per[r.task_name] = per.get(r.task_name, 0.0) + float(r.duration_hours or 0)
    top = [
        {'task_name': k, 'hours': round(v, 1)}
        for k, v in sorted(per.items(), key=lambda x: -x[1])[:5]
    ]

    # 当期还没走完（比如周三）⇒ 按已过天数折算，别拿半周去比整周
    today = timezone.localdate()
    elapsed_days = max((min(end, today + dt.timedelta(days=1)) - start).days, 1)

    return {
        'period_type': period_type,
        'what_happened': _what_happened(all_rows, attr, contrib_excluded_names(), start, end),
        # 「这一期干成了什么」—— 投入（what_happened）之外的**产出**视角。
        # 三栏各报各的数，不给跨源总数（见 `_period_outcomes` 顶部注释）。
        'outcomes': _period_outcomes(start, end, done_milestones),
        'goals': {
            'due': due,
            'done': done,
            # 「本期新增逾期」= 该交没交的那部分（`due - done`）。
            # 累积的 `overdue` 保留在响应里给「目标」模块用，但**不再当本周的账**
            # —— 那个数跨周恒定，放在周复盘里每期都是同一个值，信息量为 0。
            'missed': max(due - done, 0),
            'overdue': overdue,
            'items': items,
        },
        'time_loss': {
            'loss_hours': round(loss, 1),
            'total_hours': round(total, 1),
            # ⚠️ `None` = 这一期没有任何时间记录（≠ 流失 0%）
            'ratio': round(loss / total, 4) if total else None,
            'per_day': round(loss / elapsed_days, 2),
            'days': elapsed_days,
            'top': top,
        },
    }


# ══════════════════════════════════════════════════════════════
# 阶段账本（长阶段的「钱 / 时间 / 作品 / 小阶段」，只读现算）
# ══════════════════════════════════════════════════════════════
#
# 🔴 四个展示函数（`stage_elapsed_days` / `stage_range_label` /
#    `stage_status_display` / `stage_days_label`）**从这里出发**，
#    `serializers.SelfRunStageSerializer` 的 `get_*` 只是委托。
#    替身理由（项目铁律五）：「唯一实现」的注释不值钱，值钱的是调用同一份代码 ——
#    账本的 `range` 与阶段页头必须印同一个「第 N 天 / 共 N 天」，
#    两处各写一个三元表达式，迟早在一个边界上分叉（已归档阶段、未开始阶段）。

def stage_elapsed_days(stage):
    """今天在阶段里是第几天。现算不落库（重算得出同样结果，所以不存）。

    🔴 取 `min(今天, 终点)`，**不是** `end_date or 今天`：
       后者会让「设了计划终点」的阶段直接显示**计划总长**（v3.63.13 前的 bug：
       离职适应期 11-01→12-31 显示「第 61 天」，而当天 10-22 还没开始）。
    """
    today = timezone.localdate()
    end = min(today, stage.end_date) if stage.end_date else today
    return max((end - stage.start_date).days + 1, 0)


def stage_range_label(stage):
    """阶段区间：**从哪天到哪天、一共多少天** —— 全站只在这里拼一份。

    ⚠️ 本来页头只印 `days_label`，而它的「未开始」分支带的是 `MM-DD 起`，
       于是整页**只有起点、没有终点**（2026-10-31 用户提出：
       「阶段总结、阶段 KPI 制定里都看不到这个阶段什么时候结束」）。
       区间是阶段第一性的信息，不该藏在「第 N 天」这种进度词里。
    """
    start = f'{stage.start_date:%Y-%m-%d}'
    if not stage.end_date:
        return f'{start} 起（不设终点，手动收尾）'
    total = (stage.end_date - stage.start_date).days + 1
    return f'{start} ~ {stage.end_date:%Y-%m-%d}（{total} 天）'


def period_range_label(period):
    """一期的**显示词**：「2026-W42（10-12 ~ 10-18）」—— 全站只在这里拼一份。

    🔴 光有 `period_key` 读不出「这一周到底是哪几天」。用户看「最好的一期
       2026-W42」得自己去数第 42 周是哪天 —— 而 ISO 周号本身还会跨年
       （12-29 可能属于下一年 W01），心算必错。所以周号后面必须跟日期。
    🔴 `period_end` 是**半开**的（`[start, end)`，见模型注释）⇒ 显示时要减一天。
       不减的话每周都会印成「10-12 ~ 10-19」，看着像 8 天，用户会以为自己记错。
    ⚠️ 用**库里存的** `period_start` / `period_end`，不用 `parse_period_key` 重算：
       残缺周期（阶段起于周中）的行存的是阶段真实起点，不是一个整周。
    """
    last = period.period_end - dt.timedelta(days=1)
    return f'{period.period_key}（{period.period_start:%m-%d} ~ {last:%m-%d}）'


def stage_status_display(stage):
    """阶段状态的**显示词**。

    🔴 `active` + 今天还没到起点 ⇒ 显示「未开始」。
       库里的 `status='active'` 说的是「这是当前在册的那一个阶段」，
       不是「已经在跑了」。两种情况都印「进行中」，页头就会写成
       「进行中 · 还有 1 天开始」。
    """
    if stage.status == 'active' and stage.start_date > timezone.localdate():
        return '未开始'
    return stage.get_status_display()


def stage_days_label(stage):
    """天数的**显示词**（三种态用三种词）。

    三种态必须用三种词，因为「第 61 天」印在已归档阶段上会被读成「还在跑」。

    🔴 这里**不回带起点日期**：区间交给 `stage_range_label`。
       两处都写，页头就会变成「2026-11-01 ~ 2026-12-31 · 未开始 · 11-01 起」
       —— 同一件事写两遍，看着像两个不同的值。
       未开始时说的是**还差几天**（进度），不是区间。
    """
    n = stage_elapsed_days(stage)
    if n <= 0:
        return f'还有 {(stage.start_date - timezone.localdate()).days} 天开始'
    if stage.status == 'closed':
        return f'共 {n} 天'
    return f'第 {n} 天'


def stage_ledger(stage):
    """阶段账本：`range` / `time` / `money` / `works` / `children`。**只读现算，不写库。**

    🔴 时间与钱两块**不自己算**，一律调 `apps.redemption.services` 那几个函数
       （2026-11-02 起它们吃显式区间 `(start, end)`）。同一件事两份实现 ⇒
       两个数迟早分叉，而分叉是静默的：页面上下两块各自看着都合理。
    🔴 **六类小时之和必须等于 `covered_hours`**（跨轮验收红线）：账本把**除睡眠外的**
       全部记录都摊进六类，没设默认归因的部分单列 `fallback_hours`，但**不从六类里排除**。
    🔴 **睡眠（夜间 + 午睡）两边都不计**（2026-11-02）：覆盖率分母是「每天可支配小时」
       （`rs.THEORETICAL_DAILY_HOURS`，2026-11-05 由 12h 调到 14h），本来就不含睡眠；
       分子再含睡眠 ⇒ 覆盖率必然冲破 100%（实测 141.5%）。
       剔除量单列 `excluded_sleep_hours`，且 `covered_hours + excluded_sleep_hours`
       == 区间内全部记录时长 —— 让页面能把「这块时间去哪了」交代清楚。
    🔴 长阶段**没有任何 period 读数** —— `children` 里的 `reach_rate` 是小阶段的，
       它由 `compute_stage_summary()`（阶段总结同一个函数）逐个子阶段现算得出，
       不是长阶段自己的判定结果。长阶段只汇总，不判定。
    """
    from apps.redemption import services as rs

    start = stage.start_date
    # 不设终点的阶段按「到今天」算 —— 与 `stage_elapsed_days` 同一取法
    end = stage.end_date or timezone.localdate()
    if end < start:
        end = start      # 脏数据（终点早于起点）不能让区间反向，否则天数算成负数

    today = min(timezone.localdate(), end)
    total_days = (end - start).days + 1
    elapsed_days = max((today - start).days + 1, 0)

    cfg = stage.ledger_config or {}
    principal = float(cfg.get('pool_principal') or 0)

    # 注入 = 区间内**被标为「中途注入」的收入**，金额从账单读、窗口与本金/消耗同一把尺子
    #（v3.64.26 起不再自己记金额，也不再按阶段总量取）。
    # 🔴 这些账单同时要从净消耗里排除，否则「加进注入 + 减少消耗」双算。
    injected, inject_ids = pool_inject_totals(start, end)

    pool = rs.compute_pool_balance(
        principal, start, end, injected, exclude_bill_ids=inject_ids,
    )
    avg = rs.compute_avg_daily_self_net_detail(start, end)
    avg_daily = avg['avg_daily']
    support_until, support_reason = rs.compute_support_until(
        pool['balance'], avg_daily, today,
    )

    # 🔴 2026-11-05 撤掉 ¥/h 那一对（原「单位赎回成本」÷ 已过小时、「理论下限」
    #    ÷ 全期小时）。它们分子分母都不同，并排放必然读出「28.56 高于 11.74 ⇒
    #    超标了」—— 而这个读法本身不成立（阶段才第 5 天，大额支出还没摊开）。
    #    判断「撑不撑得到终点」只需要一把尺子：**每天多少钱**。
    remaining_days = max(total_days - elapsed_days, 0)
    # 允许日均 = 剩余余额 ÷ 剩余天数；和「日均净消耗」同量纲，可直接比大小。
    # ⚠️ 没设本金 ⇒ `None` + 原因码，不是 0：允许值为 0 意味着「一花钱就超额」，
    #    那是个结论，不是默认值。
    if principal <= 0:
        daily_allowance, allowance_reason = None, 'no_principal'
    elif remaining_days <= 0:
        daily_allowance, allowance_reason = None, 'no_day_left'
    else:
        daily_allowance = round(pool['balance'] / remaining_days, 2)
        allowance_reason = None
    # 预算占用 = 日均 ÷ 允许日均。两种「算不出来」要分开说：
    #   `no_allowance` = 允许值缺失或 ≤0（没本金 / 已超支）
    #   `net_inflow`   = 日均是负的（钱在变多），比值没有意义 —— 拿它算会得出
    #                    「-295%」，看着像「省了一半」，实际是净流入（用户截图实证）
    if daily_allowance is None or daily_allowance <= 0:
        daily_use_rate, rate_reason = None, 'no_allowance'
    elif avg_daily < 0:
        daily_use_rate, rate_reason = None, 'net_inflow'
    else:
        daily_use_rate, rate_reason = round(avg_daily / daily_allowance, 4), None

    time_block = rs.compute_time_attribution(start, end)
    # ⚠️ 同一个量只留一个出处：区间天数在 `range` 里，`time` 块自带的那个删掉
    #    （两处各给一个 `days_elapsed`，改口径时必然只改一处）。
    time_block.pop('days_elapsed', None)

    children = []
    for child in stage.children.order_by('start_date', 'id'):
        summary = compute_stage_summary(child)
        hit = sum(m['hit'] for m in summary['metrics'])
        judged = sum(m['total'] for m in summary['metrics'])
        children.append({
            'id': child.id,
            'name': child.name,
            'range_label': stage_range_label(child),
            'status_display': stage_status_display(child),
            # 达标率 = 命中次数 / 有判定的次数。**复用阶段总结的逐 KPI hit/total**，
            # 不在这条链路上另算一遍。
            'hit': hit,
            'judged': judged,
            'reach_rate': round(hit / judged, 4) if judged else None,
        })

    return {
        'stage_id': stage.id,
        'range': {
            'start': start.isoformat(),
            'end': end.isoformat(),
            'total_days': total_days,
            'elapsed_days': elapsed_days,
            'remaining_days': remaining_days,
        },
        'time': time_block,
        'money': {
            'pool': {
                **pool,
                'avg_daily': avg_daily,
                'support_until': support_until,
                'support_zero_reason': support_reason,
            },
            'tier': rs.compute_tier_stats(start, end),
            'daily_allowance': daily_allowance,
            'daily_allowance_zero_reason': allowance_reason,
            'daily_use_rate': daily_use_rate,
            'daily_use_rate_zero_reason': rate_reason,
            # 日均的样本可信度：分母已是 `min(实际天数, 30)`，数值不再被稀释；
            # 但样本不足 30 天时速度可能还没经历月末大额 ⇒ 样本天数必须一起摆出来。
            'avg_daily_sample_days': avg['sample_days'],
            'avg_daily_sample_thin': avg['thin'],
        },
        'works': _stage_works(start, end),
        'children': children,
    }


# 账本明细弹窗最多列几条。一个走了大半年的长阶段可能成形几十件，
# 全塞进一个弹窗要滚很久；超出的部分给「去作品」出口。
# 🔴 上限**必须随数据下发**（`limit` / `truncated`）：只截断不说，
#    用户会拿弹窗里那几条当全集 —— 那又是一句「看着合理」的谎。
_STAGE_WORKS_LIMIT = 50


def _stage_works(start, end):
    """区间内**成形**的作品：件数 + 明细。**同一次取数**出两样。

    ⚠️ 「成形于」是合成那件作品的那一刻，不是「那件事发生的那一刻」——
       与 `WorkCapture.captured_at` 同一个取舍：算「这期间整理出了什么」。

    🔴 复用 `readers.works_count`（KPI「留下件数」用的那个函数），不自己再查一次。
       原先这里是独立实现 `_stage_work_count` —— 同一件事两份取数；加了明细之后
       一旦分叉，表现就是**「写着 2 件、点开 3 条」，而两个数各自看着都合理**。
    🔴 `count` 与 `items` 必须出自同一次取数：分别查两次，两次之间作品被改动，
       页面就会自相矛盾（而且无法复现）。
    ⚠️ 两侧 `end` 语义不同：`works_count` 收**半开上界** `[start, end)`，
       账本收**区间最后一天**（inclusive）⇒ 这里 +1 天再传。
    """
    from apps.selfrun import readers

    out = readers.works_count(None, start, end + dt.timedelta(days=1))
    # 倒序 = 最近的排前面。`works_count` 给的是**时间升序**（KPI breakdown 的读法），
    # 而点开弹窗问的是「最近成形了什么」—— 照原序列，上个月的会排在最后。
    rows = out['breakdown'][::-1]
    items = [
        {
            'id': r['extra']['id'],
            'name': r['label'],
            'kind': r['l2'],
            'status': r['extra']['status'],
            'summary': r['extra']['summary'],
            'channel': r['extra']['channel'],
            'created_at': r['extra']['created_at'],
        }
        for r in rows[:_STAGE_WORKS_LIMIT]
    ]
    return {
        'count': out['count'],
        'items': items,
        'limit': _STAGE_WORKS_LIMIT,
        'truncated': len(rows) > _STAGE_WORKS_LIMIT,
    }



# ══════════════════════════════════════════════════════════════
# 池注入标记（v3.64.26）
# ══════════════════════════════════════════════════════════════
def list_pool_inject_bill_ids():
    """已标记为「中途注入」的账单 id 列表（前端拿它给账单行打标）。"""
    return list(SelfRunPoolInject.objects.values_list('bill_id', flat=True))


def set_pool_inject(bill_id, marked):
    """标记 / 取消标记一笔账单 → 返回 `(bill_id, 当前是否已标记)`。

    🔴 **只允许收入**：注入是「钱进来」。支出被标了会让余额凭空变大
       （它既要被当作注入 +amount，又会正常减少余额），而且页面看着合理。
    🔴 **金额不落库**：标记表只存 `bill_id`，金额与日期一律从账单读
       （`readers.pool_inject_totals`）。存第二份 = 两把尺子。
    ⚠️ 两个方向都**幂等**：重复标记 / 重复取消都返回 200，不报 409 ——
       前端是开关，用户手快点两下不该看到红色报错。
    """
    from apps.wealth.models import WealthBillList

    try:
        bill_id = int(bill_id)
    except (TypeError, ValueError):
        raise SelfRunError('bill_id 必须是整数')

    bill = WealthBillList.objects.filter(id=bill_id, user_id=1).first()
    if bill is None:
        raise NotFoundError(f'账单 {bill_id} 不存在')
    if bill.transaction_type != '收入':
        raise SelfRunError(
            f'只有收入能标为中途注入（这笔是「{bill.transaction_type}」）—— '
            '注入是钱进来，支出标了会把余额算歪'
        )

    if marked:
        SelfRunPoolInject.objects.get_or_create(bill_id=bill_id)
    else:
        SelfRunPoolInject.objects.filter(bill_id=bill_id).delete()
    return bill_id, bool(marked)
