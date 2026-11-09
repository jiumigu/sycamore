"""综合进度看板 — 核心聚合器（由 services.py 拆分）"""

from __future__ import annotations

import calendar
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime, timedelta
from typing import Any

from django.db.models import Sum
from django.utils import timezone

from ..constants import (
    BOOK,
    CONVERSION_RULES,
    COVERAGE_SPEC,
    HEALTH,
    MODULE_LIST,
    MODULE_META,
    MONTHLY_TARGET_RATIO,
    RADAR_MAX,
    RECENT_DAYS,
    SUGAR,
    TIMES,
    TRAVEL,
    WEALTH,
    WORDS,
    YEARLY_TARGET,
    ZERO_REASON_NET_NEGATIVE,
    ZERO_REASON_NO_DATA,
)


# ── 一次请求内的取数记忆 ──────────────────────────────────────────────
# 为什么需要：同一个请求里「时间投入」这份事实会被反复取 —— 年视图要全年
# （算覆盖率）、月视图要单月（算总量）、强度还要再要一次原始值。实测一个
# `overview` 请求因此发了 35 条 SQL，其中 12 条是同一份数据被取了三遍。
#
# 🔴 只活在**一次请求**里（`request_scope()` 进作用域创建、出作用域销毁）：
#    绝不能做成模块级缓存 —— 归因规则是用户可改的，进程级缓存会让改完规则
#    的页面继续显示旧口径，而且界面上完全看不出来（静默失败）。
_TIMES_COUNTED: ContextVar[dict[int, list[dict]] | None] = ContextVar(
    'summary_times_counted', default=None,
)

# 「没有传」的哨兵。`None` 是合法值（财富净额算不出来就是 None），
# 不能拿 None 当「没传」用。
_UNSET = object()

class ProgressAggregator:
    """核心聚合器 —— 从各模块读取原始数据，换算为统一进度点"""

    # ── 私有: 单模块年度聚合 ──────────────────────────────

    @staticmethod
    def _wealth_raw(year: int, month: int | None = None) -> float | None:
        """净收入 = wageincome + otherincome - outmoney

        返回值三态必须分开（§120.3）：
        - None：该区间没有任何月度收支行 —— 「取不到」，不是 0
        - 0.0 ：有数据且恰好收支平衡
        - 负数：有数据且净流出（亏损）—— 不再被 max(net, 0) 抹成 0

        亏损年份曾被 max(net, 0.0) 抹平：2026 年真实净额 -16901.63 元，
        界面上却显示「0 分」，与「今年没记过收支」完全无法区分。
        """
        from apps.wealth.models import WealthBalanceList

        qs = WealthBalanceList.objects.filter(yearmon__startswith=str(year))
        if month:
            qs = qs.filter(yearmon__endswith=f'-{str(month).zfill(2)}')

        if not qs.exists():
            return None

        agg = qs.aggregate(
            wage=Sum('wageincome'),
            other=Sum('otherincome'),
            out=Sum('outmoney'),
        )
        net = (agg['wage'] or 0) + (agg['other'] or 0) - (agg['out'] or 0)
        return float(net)

    @staticmethod
    def _health_raw(year: int, month: int | None = None) -> float:
        from apps.health.models import HealthRecord

        qs = HealthRecord.objects.filter(time__year=year)
        if month:
            from datetime import date
            start = date(year, month, 1)
            if month == 12:
                end = date(year + 1, 1, 1)
            else:
                end = date(year, month + 1, 1)
            qs = qs.filter(time__range=(start, end))
        return qs.aggregate(s=Sum('total'))['s'] or 0

    @classmethod
    @contextmanager
    def request_scope(cls):
        """一次请求的取数作用域 —— 进作用域才记忆，出作用域即失效

        ⚠️ 必须在**请求边界**（`SummaryViewSet.dispatch`）开，不要开在单个
        聚合方法里：那会出现「外层开一次、内层又开一次」的嵌套作用域，
        内层那份记不住外层刚取到的数据，等于没开。
        """
        token = _TIMES_COUNTED.set({})
        try:
            yield
        finally:
            _TIMES_COUNTED.reset(token)

    @staticmethod
    def _times_counted_year(year: int) -> list[dict]:
        """整年**计入行**的原始聚合（含 mon/day，未拼日期）—— 每请求只取一次

        「计入」的判据与 `_times_raw` 完全同源：排除未归类、只留
        `ATTRIBUTION_COUNTED` 里的归因 —— 覆盖率需要「哪几天有记录」，
        若另写一段过滤就成了第二把尺子（改归因规则时一处改了、另一处没改，
        覆盖率与总量对不上）。
        """
        from apps.temporal.constants import DEFAULT_FALLBACK_ATTR, ATTRIBUTION_COUNTED
        from apps.temporal.models import TaskMeta, TemporalTask
        from apps.temporal.services import resolve_attribution

        cache = _TIMES_COUNTED.get()
        if cache is not None and year in cache:
            return cache[year]

        rows = list(
            TemporalTask.objects.filter(year=year)
            .values('task_name', 'mon', 'day')
            .annotate(h=Sum('duration_hours'))
        )
        # 未归类（activity_type='未归类'）明确排除，不参与 30h=1 点换算
        unclassified_names = set(
            TaskMeta.objects.filter(activity_type='未归类').values_list('task_name', flat=True)
        )
        attr_map = resolve_attribution([r['task_name'] for r in rows])
        counted = [
            r for r in rows
            if r['task_name'] not in unclassified_names
            and attr_map.get(r['task_name'], DEFAULT_FALLBACK_ATTR) in ATTRIBUTION_COUNTED
        ]
        if cache is not None:
            cache[year] = counted
        return counted

    @staticmethod
    def _times_rows(year: int, month: int | None = None) -> list[tuple[date, float]]:
        """时间投入的**计入行**：[(日期, 小时), …]

        口径（v0.3 不变）：仅汇总 resolve_attribution 落入 ATTRIBUTION_COUNTED 的小时；
        流失与未归类明确排除。

        🔴 v3.62.43 把「聚合小时」与「有记录的天数」拆到同一个取数上：
        覆盖率需要「哪几天有记录」，若另写一段过滤就会变成第二把尺子
        （改归因规则时一处改了、另一处没改，覆盖率与总量对不上）。

        🔴 月度不再另发 SQL：整年取一次、按 `mon` 字符串过滤即可。
           过滤条件与原来的 `filter(mon='08')` **逐字同义** —— 别改成比较
           `date.month`，那会把 `mon` 没补零的历史行也放进来（静默多算）。
        """
        rows = ProgressAggregator._times_counted_year(year)
        if month:
            want = str(month).zfill(2)
            rows = [r for r in rows if r['mon'] == want]
        out: list[tuple[date, float]] = []
        for r in rows:
            # mon 是 CharField('08')、day 是 IntegerField —— 任一缺失/非法就跳过
            try:
                d = date(year, int(r['mon']), int(r['day']))
            except (TypeError, ValueError):
                continue
            out.append((d, float(r['h'] or 0)))
        return out

    @staticmethod
    def _times_raw(year: int, month: int | None = None) -> float:
        """时间投入原始小时（v0.3）—— 计入行的小时合计

        ⚠️ 必须是 staticmethod：它被收进 `_RAW_GETTERS` 字典按函数调用，
        classmethod 对象不可直接 call（`_get_raw_value` 会抛
        `TypeError: 'classmethod' object is not callable`）。
        """
        return sum(h for _, h in ProgressAggregator._times_rows(year, month))

    @staticmethod
    def _words_raw(year: int, month: int | None = None) -> float:
        from apps.temporal.models import OneDayPage

        qs = OneDayPage.objects.filter(begin_date__year=year)
        if month:
            qs = qs.filter(begin_date__month=month)
        return qs.aggregate(t=Sum('total'))['t'] or 0

    @staticmethod
    def _sugar_raw(year: int, month: int | None = None) -> float:
        from apps.sugar.models import SugarRecord

        qs = SugarRecord.objects.filter(time__year=year)
        if month:
            qs = qs.filter(time__month=month)
        return float(qs.aggregate(h=Sum('level_of_happiness'))['h'] or 0)

    @staticmethod
    def _travel_raw(year: int, month: int | None = None) -> int:
        from apps.travel.models import TravelRecord

        qs = TravelRecord.objects.filter(tyear=year)
        if month:
            qs = qs.filter(ttime__month=month)
        return qs.count()

    @staticmethod
    def _book_raw(year: int, month: int | None = None) -> int:
        from apps.book.models import Book

        qs = Book.objects.filter(
            status__in=['已完成', '通读', '精读'],
            readDate__year=year,
        )
        if month:
            qs = qs.filter(readDate__month=month)
        return qs.count()

    # ── 原始值获取路由 ─────────────────────────────────────

    _RAW_GETTERS: dict[str, callable] = {
        WEALTH: _wealth_raw,
        HEALTH: _health_raw,
        TIMES: _times_raw,
        WORDS: _words_raw,
        SUGAR: _sugar_raw,
        TRAVEL: _travel_raw,
        BOOK: _book_raw,
    }

    @classmethod
    def _get_raw_value(cls, module: str, year: int, month: int | None = None) -> float:
        return cls._RAW_GETTERS[module](year, month)

    # ── 原始值 → 进度点 ───────────────────────────────────

    @classmethod
    def _raw_to_points_raw(cls, module: str, raw_value: float | None) -> float:
        """raw → 进度点，**不套 floor**

        `_raw_to_points` 会把负值抬到 `points_floor`（财富 0），那是**总分时代**
        的规则：总分不能倒扣。总分已拆，达成率要如实反映「亏了多少」，
        所以这里保留负号 —— 净流出年份的达成率是负数，而不是 0%。
        """
        if raw_value is None:
            return 0.0
        rule = CONVERSION_RULES[module]
        rtype = rule.get('type', 'aggregate')
        if rtype in ('count', 'count_completed'):
            return float(raw_value)
        return float(raw_value) / rule['divisor']

    @classmethod
    def _raw_to_points(cls, module: str, raw_value: float | None) -> float:
        """raw → 进度点（带 floor）。仅用于内部评分，界面不展示。"""
        points = cls._raw_to_points_raw(module, raw_value)
        if raw_value is None:
            return 0.0
        floor = CONVERSION_RULES[module].get('points_floor')
        if floor is not None and points < floor:
            return float(floor)
        return points

    @staticmethod
    def _display_value(module: str, raw_value: float | None) -> float | None:
        """raw → 展示值（已按 unit 的量级前缀归一，如 448067 步 → 44.81 万步）。

        量级只在这里定义一次；前端拿到 display_value 直接拼 unit，
        不再自己判「>= 10000 就加万」（那会把「万步」拼成「万万步」）。
        """
        if raw_value is None:
            return None
        scale = CONVERSION_RULES[module].get('display_scale', 1)
        return round(raw_value / scale, 2)

    @classmethod
    def _zero_reason(cls, module: str, raw_value: float | None) -> str | None:
        """解释「为什么这个维度是 0」，前端只查表不自己编。"""
        if raw_value is None:
            return ZERO_REASON_NO_DATA
        rule = CONVERSION_RULES[module]
        floor = rule.get('points_floor')
        if floor is None:
            return None
        # 这里必须用「未 clamp 的点」判断，否则负值已被抬到 floor，永远判不出来
        rtype = rule.get('type', 'aggregate')
        raw_points = float(raw_value) if rtype in ('count', 'count_completed') else raw_value / rule['divisor']
        return ZERO_REASON_NET_NEGATIVE if raw_points < floor else None

    # ── 覆盖率（v3.62.43）：有记录的期数 ÷ 该有的期数 ─────────

    @classmethod
    def _covered_marks(cls, module: str, year: int) -> set[date]:
        """有内容的日期集合（月粒度维度只用到其中的年月）

        🔴 「有内容」≠「有行」：日记页每天会自动建一条空占位
        （`total=0`、标题是固定文案），把它算成「有记录」会让文字维度的
        覆盖率凭空变成 100% —— 那正是这次要消灭的假象。
        """
        spec = COVERAGE_SPEC[module]

        if module == WEALTH:
            from apps.wealth.models import WealthBalanceList
            out: set[date] = set()
            rows = WealthBalanceList.objects.filter(
                yearmon__startswith=str(year)
            ).values_list('yearmon', flat=True)
            for ym in rows:
                try:
                    y, m = str(ym).split('-')[:2]
                    out.add(date(int(y), int(m), 1))
                except (TypeError, ValueError):
                    continue
            return out

        if module == HEALTH:
            from apps.health.models import HealthRecord
            out = set()
            for stamp in HealthRecord.objects.filter(time__year=year).values_list('time', flat=True):
                if stamp is None:
                    continue
                out.add(timezone.localtime(stamp).date() if timezone.is_aware(stamp) else stamp.date())
            return out

        if module == TIMES:
            # 与 `_times_raw` 同源：归因不计入的那些天不算「有记录」
            return {d for d, _ in cls._times_rows(year)}

        if module == WORDS:
            from apps.temporal.models import OneDayPage
            qs = OneDayPage.objects.filter(begin_date__year=year)
            if spec.get('counts_empty', True) is False:
                qs = qs.filter(total__gt=0)
            return {d for d in qs.values_list('begin_date', flat=True) if d}

        if module == SUGAR:
            from apps.sugar.models import SugarRecord
            return {
                d for d in SugarRecord.objects.filter(time__year=year).values_list('time', flat=True) if d
            }

        if module == TRAVEL:
            from apps.travel.models import TravelRecord
            return {
                d for d in TravelRecord.objects.filter(tyear=year).values_list('ttime', flat=True) if d
            }

        if module == BOOK:
            from apps.book.models import Book
            qs = Book.objects.filter(
                status__in=['已完成', '通读', '精读'], readDate__year=year,
            )
            return {d for d in qs.values_list('readDate', flat=True) if d}

        return set()

    @staticmethod
    def _elapsed_span(year: int, month: int | None = None) -> tuple[date, date] | None:
        """该区间「该有的日子」的上界 → (起, 止)。未到则 None（算不出来，不是 0）"""
        today = timezone.localdate()
        if month:
            first = date(year, month, 1)
            last = date(year, month, calendar.monthrange(year, month)[1])
            if (year, month) > (today.year, today.month):
                return None
            if (year, month) == (today.year, today.month):
                return first, today
            return first, last
        if year > today.year:
            return None
        if year == today.year:
            return date(year, 1, 1), today
        return date(year, 1, 1), date(year, 12, 31)

    @staticmethod
    def _elapsed_months(year: int, month: int | None = None) -> int:
        """已「结完」的月数

        🔴 月度记录是**月结动作**，当前月还没过完就不该算成缺失 ——
        否则每月初打开页面，财富覆盖率都会无故掉一档。
        """
        today = timezone.localdate()
        if month:
            return 1 if (year, month) < (today.year, today.month) else 0
        if year < today.year:
            return 12
        if year > today.year:
            return 0
        return today.month - 1

    @classmethod
    def _coverage(
        cls,
        module: str,
        year: int,
        month: int | None = None,
        covered_marks: set[date] | None = None,
        with_intensity: bool = True,
        raw_value: Any = _UNSET,
    ) -> dict:
        """覆盖率 + 强度 —— 两个分母刻意不同：

        - 覆盖率分母 = **该有的期数**（回答「有没有断」）
        - 强度分母   = **实际有记录的期数**（回答「记的时候做了多少」）

        ⚠️ `with_intensity=False` 给趋势图用：那里只要覆盖率，
        强度要多做一次全量聚合，12 个月白白多跑 84 次。
        """
        spec = COVERAGE_SPEC[module]
        marks = covered_marks if covered_marks is not None else cls._covered_marks(module, year)
        today = timezone.localdate()

        if spec['period'] == 'day':
            span = cls._elapsed_span(year, month)
            window = {d for d in marks if span[0] <= d <= span[1]} if span else set()
            periods = (span[1] - span[0]).days + 1 if span else 0
            covered = len(window)
            recorded = len(window)
            recent = sum(
                1 for d in marks if today - timedelta(days=RECENT_DAYS - 1) <= d <= today
            )
        else:
            periods = cls._elapsed_months(year, month)
            if month:
                allowed = {(year, month)}
            elif periods:
                allowed = {(year, m) for m in range(1, periods + 1)}
            else:
                allowed = set()
            month_marks = {(d.year, d.month) for d in marks}
            covered = len(month_marks & allowed)
            if month:
                # 🔴 单月视角：分子是「这个月」的总量，分母就必须是「这个月有没有记」（0/1）。
                #    用全年有记录的月数当分母，会把本月总量除以 9 —— 强度凭空小 9 倍。
                recorded = 1 if (year, month) in month_marks else 0
            else:
                # 全年视角：强度的分母用**全部有记录的月**（含当前月）：
                # 总量里已经算进了本月那笔，分母再把它剔掉就会「总量含当月、期数不含当月」，
                # 两个数不同源 ⇒ 强度偏高/偏低而看不出原因。
                recorded = len(month_marks)
            recent = None

        return {
            'period_kind': spec['period'],
            'period_word': spec['period_word'],
            'label': spec['label'],
            'covered': covered,
            'periods': periods,
            # 算不出来就给 None —— 不是 0%（§null/0/取不到是三件事）
            'pct': round(covered / periods * 100, 1) if periods else None,
            'intensity': (
                cls._intensity(module, year, month, recorded, raw_value)
                if with_intensity else None
            ),
            'intensity_label': spec['intensity_label'],
            'intensity_unit': spec['intensity_unit'],
            'recent_covered': recent,
            'recent_periods': RECENT_DAYS if spec['period'] == 'day' else None,
            'recent_pct': round(recent / RECENT_DAYS * 100, 1) if recent is not None else None,
        }

    @classmethod
    def _intensity(
        cls,
        module: str,
        year: int,
        month: int | None,
        recorded: int,
        raw_value: Any = _UNSET,
    ) -> float | None:
        """总量 ÷ 有记录的期数；没有记录时返回 None（不是 0）

        ⚠️ `raw_value` 由调用方传入时**直接复用**，不再回库查一次 ——
           同一个请求里 `_module_entry` 刚查过同一个值，再查一遍就是
           35 条 SQL 里那 7 条纯重复的来源。
        """
        if not recorded:
            return None
        raw = cls._get_raw_value(module, year, month) if raw_value is _UNSET else raw_value
        if raw is None:
            return None
        return round(float(raw) / recorded, 2 if module == WEALTH else 1)

    @staticmethod
    def _axis_max_map() -> dict[str, float]:
        """雷达每根轴的满格刻度（点）—— 来自配置，未配置回退 RADAR_MAX"""
        from apps.summary.models import SevenDimConfig
        cfg = SevenDimConfig.get_active()
        out: dict[str, float] = {}
        for mod in MODULE_LIST:
            out[mod] = getattr(cfg, f'{mod}_max', None) or RADAR_MAX.get(mod, 100)
        return out

    # ── 单模块总览条目 ─────────────────────────────────────

    @classmethod
    def _module_entry(
        cls,
        module: str,
        year: int,
        month: int | None = None,
        axis_max: float | None = None,
        covered_marks: set[date] | None = None,
    ) -> dict:
        raw = cls._get_raw_value(module, year, month)
        points = cls._raw_to_points(module, raw)
        # 达成率用**未 floor** 的原始点：净流出就是负数，不能被抬成 0
        raw_points = cls._raw_to_points_raw(module, raw)
        meta = MODULE_META[module]
        rule = CONVERSION_RULES[module]
        # ⚠️ `count` / `count_completed` 两类没有 `divisor`（1 点 = 1 个物理单位），
        #    直接 `rule['divisor']` 会 KeyError —— 五个维度同时挂掉。
        target_amount = axis_max * rule.get('divisor', 1) if axis_max else None
        return {
            'module': module,
            'label': meta['label'],
            'color': meta['color'],
            # `points` 是内部评分单位，界面不再展示 —— 仅用于「对目标达成率」
            'points': round(points, 2),
            'raw_value': round(raw, 2) if raw is not None else None,
            'display_value': cls._display_value(module, raw),
            'unit': rule['unit'],
            'zero_reason': cls._zero_reason(module, raw),
            # 强度要用同一个 raw：再查一次库就是纯粹的重复（见 `_intensity`）
            'coverage': cls._coverage(module, year, month, covered_marks, raw_value=raw),
            'axis_max': axis_max,
            # 目标换算回物理量：axis_max 是「点」，1 点 = divisor 个物理单位
            'achievement_target': round(target_amount, 2) if target_amount else None,
            'achievement_pct': (
                round(raw_points / axis_max * 100, 1) if axis_max else None
            ),
        }

    # ── 公开: 可用年份 ─────────────────────────────────────

    @classmethod
    def get_available_years(cls) -> list[int]:
        """从所有模块收集有数据的年份"""
        from apps.wealth.models import WealthBalanceList
        from apps.health.models import HealthRecord
        from apps.temporal.models import OneDayPage, TemporalTask
        from apps.sugar.models import SugarRecord
        from apps.travel.models import TravelRecord
        from apps.book.models import Book

        year_sets = [
            set(WealthBalanceList.objects.values_list('yearmon', flat=True)),
            set(HealthRecord.objects.values_list('time__year', flat=True)),
            set(TemporalTask.objects.values_list('year', flat=True)),
            set(OneDayPage.objects.values_list('begin_date__year', flat=True)),
            set(SugarRecord.objects.values_list('time__year', flat=True)),
            set(TravelRecord.objects.values_list('tyear', flat=True)),
            set(Book.objects.filter(status='已完成').values_list('readDate__year', flat=True)),
        ]
        all_years: set[int] = set()
        for s in year_sets:
            for y in s:
                if y is not None:
                    if isinstance(y, str):
                        all_years.add(int(y[:4]))
                    else:
                        all_years.add(int(y))
        return sorted(all_years, reverse=True)

    # ── 公开: 年度总览 ─────────────────────────────────────

    @classmethod
    def get_yearly_overview(cls, year: int | None = None) -> dict:
        """年度总览：七维「覆盖率 + 强度」+ 最短板

        🔴 v3.62.43 起**不再返回总分**：`total_points` / `yearly_target` /
        `progress_percent` / `remaining_points` / `monthly_target` 全部移除。
        理由：七个不同量纲直接相加没有意义（1 本书 = 1 次旅行 = 1 万字 = 1 万步），
        而且七轴封顶之和 315 < 400，那个百分比既不可解释也不可达。
        """
        if year is None:
            year = datetime.now().year

        axis_max = cls._axis_max_map()
        modules = [
            cls._module_entry(m, year, axis_max=axis_max.get(m)) for m in MODULE_LIST
        ]
        span = cls._elapsed_span(year)
        return {
            'year': str(year),
            'as_of': timezone.localdate().isoformat(),
            'window': {
                'elapsed_days': (span[1] - span[0]).days + 1 if span else 0,
                'elapsed_months': cls._elapsed_months(year),
                'is_current_year': year == timezone.localdate().year,
            },
            'modules': modules,
            'weakest': cls._weakest(modules),
        }

    @staticmethod
    def _weakest(modules: list[dict]) -> dict | None:
        """最短板 = **覆盖率最低**的那根轴

        只比覆盖率，不比点数 / 达成率：达成率依赖每轴的封顶（那是拍出来的数），
        覆盖率是客观的「我记了多少」，用它点名才站得住。
        """
        ranked = [m for m in modules if m['coverage']['pct'] is not None]
        if not ranked:
            return None
        worst = min(ranked, key=lambda m: (m['coverage']['pct'], m['coverage']['covered']))
        cov = worst['coverage']
        return {
            'module': worst['module'],
            'label': worst['label'],
            'color': worst['color'],
            'coverage_pct': cov['pct'],
            'covered': cov['covered'],
            'periods': cov['periods'],
            'period_word': cov['period_word'],
            'recent_pct': cov['recent_pct'],
            'recent_covered': cov['recent_covered'],
            'recent_periods': cov['recent_periods'],
        }

    # ── 公开: 月度详情 ─────────────────────────────────────

    @classmethod
    def get_monthly_detail(cls, year: int | None = None, month: int | None = None) -> dict:
        """月度详情：同样只给「覆盖率 + 强度」，不给总分"""
        if year is None:
            year = datetime.now().year
        if month is None:
            month = datetime.now().month

        axis_max = cls._axis_max_map()
        modules = [
            cls._module_entry(m, year, month, axis_max=axis_max.get(m))
            for m in MODULE_LIST
        ]
        span = cls._elapsed_span(year, month)
        return {
            'year': str(year),
            'month': month,
            'window': {
                'elapsed_days': (span[1] - span[0]).days + 1 if span else 0,
                'elapsed_months': cls._elapsed_months(year, month),
            },
            'modules': modules,
            'weakest': cls._weakest(modules),
        }

    # ── 公开: 月度趋势 ─────────────────────────────────────

    @classmethod
    def get_trend(cls, year: int | None = None) -> dict:
        """12 个月的**覆盖率 + 强度**（v3.62.44）

        为什么两样都要给：只画覆盖率时，「记了 2 天走了 3 万步」和
        「记了 2 天走了 3 千步」是同一个颜色 —— 强度在月度尺度上完全不可见，
        而「记了但记得很差」恰恰是最需要看见的那一类。

        结构（前端按 `modules` 拿单位与颜色，按 `months` 取两套值）::

            {
              'year': 2026,
              'unit_note': '…',
              'modules': [{module,label,color,intensity_label,intensity_unit,period_word}],
              'months':  [{month,is_future,coverage:{mod:pct|None},
                           covered:{mod:int}, periods:{mod:int},
                           intensity:{mod:val|None}}],
            }

        🔴 `coverage` 与 `intensity` 都是 `None`-able：
           「还没到」与「记了但一条没有」必须能分开，不能都画成 0。

        ⚠️ 强度每月每维度都要一次聚合（7×12 = 84 次真实取数 —— 不同月份
           本来就是不同的数据，这部分**不该**合并）。2026-10-28 实测 66 条
           SQL / 约 42ms；改之前是 106 条 / 约 106ms，差的那 40 条全在
           「时间投入」被按月重复取整年这件事上（现已整年取一次）。
           仍然不做跨请求缓存：样本会变，缓存口径就会和详情页打架。
        """
        if year is None:
            year = datetime.now().year

        marks = {mod: cls._covered_marks(mod, year) for mod in MODULE_LIST}
        months: list[dict[str, Any]] = []
        # 每个维度的年内最高月强度 —— 前端用它把「柱高」归一（量纲不同，无法共用一个刻度）
        row_max: dict[str, float] = {mod: 0.0 for mod in MODULE_LIST}

        for m in range(1, 13):
            span = cls._elapsed_span(year, m)
            entry: dict[str, Any] = {
                'month': m,
                'is_future': span is None,
                'coverage': {},
                'covered': {},
                'periods': {},
                'intensity': {},
            }
            for mod in MODULE_LIST:
                cov = cls._coverage(mod, year, m, marks[mod])
                entry['coverage'][mod] = cov['pct']
                entry['covered'][mod] = cov['covered']
                entry['periods'][mod] = cov['periods']
                # 🔴 覆盖率为 None（该月还没结）时强度也给 None：
                #    否则会出现「覆盖率 —、但柱子有高度」的自相矛盾格子。
                iv = cov['intensity'] if cov['pct'] is not None else None
                entry['intensity'][mod] = iv
                # 归一用的最高月只取**正**强度：财富可能整月净流出（负数），
                # 拿负数当分母会让柱高反向、看起来像 bug。
                if iv is not None and iv > row_max[mod]:
                    row_max[mod] = iv
            months.append(entry)

        return {
            'year': year,
            'unit_note': '柱高 = 强度（相对该维度年内最高月）；颜色 = 覆盖率',
            'modules': [
                {
                    'module': mod,
                    'label': MODULE_META[mod]['label'],
                    'color': MODULE_META[mod]['color'],
                    'period_word': COVERAGE_SPEC[mod]['period_word'],
                    'intensity_label': COVERAGE_SPEC[mod]['intensity_label'],
                    'intensity_unit': COVERAGE_SPEC[mod]['intensity_unit'],
                }
                for mod in MODULE_LIST
            ],
            'months': months,
            'intensity_max': {mod: round(v, 2) for mod, v in row_max.items()},
        }

    # ── 公开: 雷达图 ───────────────────────────────────────

    @classmethod
    def _get_radar_config(cls):
        from apps.summary.models import SevenDimConfig
        return SevenDimConfig.get_active()

    @classmethod
    def get_radar(cls, year: int | None = None) -> dict:
        """七维雷达：同时给「覆盖率」与「对目标达成率」两套值

        默认画覆盖率 —— 它无量纲、不依赖任何拍出来的封顶，形状塌了就是
        「这个维度我断了记录」，看得很准。

        ⚠️ 仍保留 `achievement`：否则「七维封顶配置」就成了**没人读的死开关**
        （配置能改、雷达不认）。前端给一个切换，两种镜片各有各的用途。
        """
        if year is None:
            year = datetime.now().year

        axis_max = cls._axis_max_map()
        axes: list[dict] = []
        for mod in MODULE_LIST:
            entry = cls._module_entry(mod, year, axis_max=axis_max.get(mod))
            cov = entry['coverage']
            axes.append({
                'module': mod,
                'name': entry['label'],
                'color': entry['color'],
                # 覆盖率：None = 算不出来（该年还没开始），前端显示「—」
                'coverage': cov['pct'],
                'achievement': entry['achievement_pct'],
                'axis_max': entry['axis_max'],
                'achievement_target': entry['achievement_target'],
                # 净额/目标：财富这类「可正可负」的量，达成率可以是负数 ——
                # 负数不是 0%，它是「亏了多少」的唯一出口（见 §123.10）
                'achievement_negative': (
                    entry['achievement_pct'] is not None and entry['achievement_pct'] < 0
                ),
                'net_amount': entry['raw_value'] if mod == WEALTH else None,
                'covered': cov['covered'],
                'periods': cov['periods'],
                'period_word': cov['period_word'],
                'coverage_label': cov['label'],
                'intensity': cov['intensity'],
                'intensity_label': cov['intensity_label'],
                'intensity_unit': cov['intensity_unit'],
                'total_display': entry['display_value'],
                'total_unit': entry['unit'],
                'zero_reason': entry['zero_reason'],
            })

        return {
            'year': year,
            'basis_default': 'coverage',
            'axes': axes,
        }

    # ── 公开: 模块详情钻取 ─────────────────────────────────

    @classmethod
    def get_module_detail(cls, module: str, year: int | None = None, month: int | None = None) -> dict:
        if module not in MODULE_LIST:
            return {'error': f'未知模块: {module}'}

        raw = cls._get_raw_value(module, year, month)
        points = cls._raw_to_points(module, raw)
        meta = MODULE_META[module]
        rule = CONVERSION_RULES[module]

        # 获取原始记录（最多 50 条）
        records = cls._get_raw_records(module, year, month)

        return {
            'module': module,
            'label': meta['label'],
            'color': meta['color'],
            'raw_value': round(raw, 2) if raw is not None else None,
            'display_value': cls._display_value(module, raw),
            'points': round(points, 2),
            'unit': rule['unit'],
            'zero_reason': cls._zero_reason(module, raw),
            'record_count': len(records),
            'records': records[:50],
        }

    @classmethod
    def _get_raw_records(cls, module: str, year: int | None, month: int | None) -> list[dict]:
        """获取指定模块的原始记录摘要"""
        from datetime import datetime

        year = year or datetime.now().year

        if module == WEALTH:
            from apps.wealth.models import WealthBalanceList
            qs = WealthBalanceList.objects.filter(yearmon__startswith=str(year))
            if month:
                qs = qs.filter(yearmon__endswith=f'-{str(month).zfill(2)}')
            return [
                {'yearmon': r.yearmon, 'income': (r.wageincome or 0) + (r.otherincome or 0),
                 'expense': r.outmoney or 0, 'net': (r.wageincome or 0) + (r.otherincome or 0) - (r.outmoney or 0)}
                for r in qs.order_by('-yearmon')[:50]
            ]

        if module == HEALTH:
            from apps.health.models import HealthRecord
            qs = HealthRecord.objects.filter(time__year=year)
            if month:
                qs = qs.filter(time__month=month)
            return [
                {'date': r.time.isoformat() if r.time else '', 'steps': r.total or 0}
                for r in qs.order_by('-time')[:50]
            ]

        if module == TIMES:
            from apps.temporal.models import TemporalTask
            qs = TemporalTask.objects.filter(year=year)
            if month:
                qs = qs.filter(mon=str(month).zfill(2))
            return [
                {'task': r.task_name, 'hours': r.duration_hours or 0,
                 'date': r.start_time.isoformat() if r.start_time else ''}
                for r in qs.order_by('-start_time')[:50]
            ]

        if module == WORDS:
            from apps.temporal.models import OneDayPage
            qs = OneDayPage.objects.filter(begin_date__year=year)
            if month:
                qs = qs.filter(begin_date__month=month)
            return [
                {'date': r.begin_date.isoformat() if r.begin_date else '',
                 'title': r.title, 'words': r.total or 0}
                for r in qs.order_by('-begin_date')[:50]
            ]

        if module == SUGAR:
            from apps.sugar.models import SugarRecord
            qs = SugarRecord.objects.filter(time__year=year)
            if month:
                qs = qs.filter(time__month=month)
            return [
                {'title': r.title, 'happiness': float(r.level_of_happiness),
                 'date': r.time.isoformat() if r.time else ''}
                for r in qs.order_by('-time')[:50]
            ]

        if module == TRAVEL:
            from apps.travel.models import TravelRecord
            qs = TravelRecord.objects.filter(tyear=year)
            if month:
                qs = qs.filter(ttime__month=month)
            return [
                {'place': r.tname, 'cost': r.tcost or 0, 'date': r.ttime.isoformat() if r.ttime else ''}
                for r in qs.order_by('-ttime')[:50]
            ]

        if module == BOOK:
            from apps.book.models import Book
            qs = Book.objects.filter(status='已完成', readDate__year=year)
            if month:
                qs = qs.filter(readDate__month=month)
            return [
                {'title': r.btitle, 'author': r.author, 'date': r.readDate.isoformat() if r.readDate else ''}
                for r in qs.order_by('-readDate')[:50]
            ]

        return []
