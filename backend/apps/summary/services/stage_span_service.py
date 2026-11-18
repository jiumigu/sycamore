"""综合进度看板 — 阶段分段（只读借用 selfrun 的人生阶段）

## 为什么 summary 可以 import selfrun，反过来不行

总览在上、明细在下，依赖只能向下。`summary` 已经单向依赖
temporal / sugar / book / toolkit / goals，再加一条不产生环；
而 `selfrun` 一旦反向依赖 `summary`，就成环了。

## 三条判据必须与 `selfrun.stage_timeline()` 逐字一致（同一把尺子）

1. 阶段区间是**闭区间** `[start_date, end_date]` —— 那边算空档时是从
   `end_date + 1` 起算的，若这里改成半开，同一天会同时属于「阶段内」
   和「空档」，两边各自都自洽、放在一起就自相矛盾。
2. 只取**顶层**（`parent IS NULL`）：小阶段是长阶段内部的细分
   （`离职适应期` 在 `三年赎回期` 里）。把两层摊平到七维上，
   同一个月会同时标两个阶段名，而曲线一个月只有一格。
3. `end_date` 为空 ⇒ 延伸到无限。

## 本文件不判断「阶段在不在运转」

`stage_kind`（run / record）只作为**标签**下发，不参与任何过滤 ——
`求学期` 是记录型、零 KPI，但它同样是一段人生，七维曲线上该标出来。
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from django.utils import timezone

from ..constants import COVERAGE_SPEC, MODULE_LIST, MODULE_META
from .progress_aggregator import ProgressAggregator

# 「这一段还没建阶段记录」—— 与「记了但一条没有」是两件事，原因码分开
REASON_NO_STAGE = 'no_stage'
# 整段都在系统有数据之前 ⇒ 分母不存在（不是 0%）
REASON_BEFORE_DATA = 'before_data'
# 这个维度从来没有任何记录 ⇒ 不可观测（不是 0%）
REASON_NO_RECORDS = 'no_records'
# 月粒度维度在不足一个完整月的阶段里算不出来（不是 0%）
REASON_NO_COMPLETE_PERIOD = 'no_complete_period'
# 可观测维度少于 2 个 ⇒ 不点名最短板（一个候选里挑最差，没有比较意义）
MIN_COMPARABLE = 2


class StageSpanService:
    """把人生阶段摊到「月」和「阶段」两个尺度上（只读）"""

    # ── 取阶段 ─────────────────────────────────────────────

    @staticmethod
    def _top_stages() -> list:
        """顶层阶段，按起点正序（人生顺序，不是列表的「新在前」）"""
        from apps.selfrun.models import SelfRunStage

        return list(
            SelfRunStage.objects.filter(parent__isnull=True).order_by('start_date', 'id')
        )

    # ── 月尺度：给七维曲线画阶段带 ─────────────────────────

    @classmethod
    def month_spans(cls, year: int) -> dict:
        """12 个月各属于哪个阶段

        🔴 一个月内可能**发生切换**（A 结束、B 开始）：返回 `segments`
           让前端按段铺带，并给 `is_mixed` 让它在格子上标「切换」。
           不要只给一个阶段名 —— 那会把「11 月还是谋生期、12 月已是赎回期」
           抹成整月同一个颜色。

        🔴 一个月可能**没有任何阶段**（`covered_days === 0`）：这是
           「还没建那段阶段记录」，`label` 给 None 并带原因码，
           不要回退成上一个阶段名 —— 那会凭空延长一段人生。
        """
        stages = cls._top_stages()
        months: list[dict] = []

        for m in range(1, 13):
            first = date(year, m, 1)
            last = date(year, m, calendar.monthrange(year, m)[1])
            days_in_month = (last - first).days + 1

            # 与本月有交集的顶层阶段（闭区间）
            hits = [
                s for s in stages
                if s.start_date <= last and (s.end_date is None or s.end_date >= first)
            ]

            segments: list[dict] = []
            covered_days = 0
            for s in hits:
                seg_start = max(s.start_date, first)
                seg_end = min(s.end_date or last, last)
                if seg_end < seg_start:
                    continue
                seg_days = (seg_end - seg_start).days + 1
                covered_days += seg_days
                segments.append({
                    'stage_id': s.id,
                    'name': s.name,
                    'kind': s.stage_kind,
                    'start': seg_start.isoformat(),
                    'end': seg_end.isoformat(),
                    'days': seg_days,
                })

            # 主段 = 覆盖天数最多的那一段（`max` 并列时返回先出现的 ⇒
            # 起点早的那段胜出，与人生顺序一致）
            main = max(segments, key=lambda x: x['days']) if segments else None

            months.append({
                'month': m,
                'label': main['name'] if main else None,
                'kind': main['kind'] if main else None,
                'stage_id': main['stage_id'] if main else None,
                'is_mixed': len(segments) > 1,
                'segments': segments,
                'covered_days': covered_days,
                'total_days': days_in_month,
                'reason': None if segments else REASON_NO_STAGE,
            })

        # 本年出现过的阶段（图例用，按起点正序、去重）
        seen: dict[int, dict] = {}
        for row in months:
            for seg in row['segments']:
                seen.setdefault(seg['stage_id'], {
                    'stage_id': seg['stage_id'],
                    'name': seg['name'],
                    'kind': seg['kind'],
                })

        return {
            'year': year,
            'stages': list(seen.values()),
            'months': months,
            # 让人一眼看出「这一年有几格其实没有阶段」—— 不静默留白
            'uncovered_months': [r['month'] for r in months if r['reason']],
        }

    # ── 阶段尺度：跨年对照 ─────────────────────────────────

    @classmethod
    def stage_compare(cls) -> dict:
        """各顶层阶段的七维**覆盖率**对照（跨年，不归到自然年）

        🔴 只比覆盖率，不比强度：覆盖率是「有记录期数 ÷ 该有的期数」，
           无量纲、两个阶段同尺；强度是绝对量（步/天 vs 元/月），
           并排一定会被读成「赎回期过得比谋生期好」—— 那是合成，不是测量。

        🔴 分母起点 = `max(阶段起点, 系统可观测起点)`，不是阶段起点。
           `求学期` 是 2001–2017，而系统最早的数据在 2019 —— 分母若从
           2001 算，这个阶段的七维覆盖率全是 0%，读起来就是
           「你那时候什么都没做」。分母被裁过就下发 `clipped=True`，
           整段都在数据之前则 `pct=None` 并给 `before_data`。

        🔴 **可观测起点是全局的、七个维度共用一个**（`min(avail_years)` 的
           1 月 1 日），不是「该维度最早一条记录」。
           用后者会把「阶段开头那几天没记」悄悄从分母里剔掉 ——
           覆盖率虚高，而页面上完全看不出来。虚高比虚低危险：
           虚低至少显示出 0% 让你去看，虚高会让断档直接消失。
        """
        stages = cls._top_stages()
        today = timezone.localdate()

        # 一次性把能观测到的年份取齐，阶段之间共用（否则每个阶段各查一遍）
        #
        # 🔴 这里必须按**记账年**遍历、不能只遍历阶段区间内的年份：
        #    `_covered_marks` 有些维度是按年字段过滤（旅行 `tyear`、财富
        #    `yearmon`），返回的却是**实际日期**（`ttime`）。旅行存在
        #    「2020 年补记 2016 年的行程」这种行 —— 只取 2016 年会把它们漏掉，
        #    只取 2020 年又会把它们算成 2020 有记录。取全部记账年再按实际
        #    日期分箱，两个问题同时消失。
        marks_cache: dict[tuple[str, int], set[date]] = {}
        avail_years = ProgressAggregator.get_available_years()
        if avail_years:
            years = list(range(min(avail_years), today.year + 1))
            system_start: date | None = date(min(avail_years), 1, 1)
        else:
            years = [today.year]
            system_start = None

        rows = []
        for s in stages:
            start = s.start_date
            # 未来的日子还没发生，不进分母
            end = min(s.end_date or today, today)
            if end < start:
                # 整段都在未来：不给数，但要说清为什么
                rows.append({
                    'stage_id': s.id, 'name': s.name, 'kind': s.stage_kind,
                    'start': s.start_date.isoformat(),
                    'end': s.end_date.isoformat() if s.end_date else None,
                    'end_effective': s.start_date.isoformat(),
                    'days': 0, 'in_future': True,
                    'coverage': {}, 'weakest': None,
                    'comparable_modules': 0,
                })
                continue

            coverage = {}
            for mod in MODULE_LIST:
                coverage[mod] = cls._span_coverage(
                    mod, start, end, years, marks_cache, system_start,
                )

            modules_for_weakest = [
                {'module': mod, 'label': MODULE_META[mod]['label'],
                 'color': MODULE_META[mod]['color'],
                 'coverage': coverage[mod]}
                for mod in MODULE_LIST
            ]
            # 🔴 「最短板」是**相对比较**：只有 1 个维度算得出来时不点名。
            #    求学期就是这种情形 —— 系统 2019 才起步，2001–2017 只有
            #    「旅行」偶尔有数（补记的旧行程），点它是「最短板」纯属误导。
            comparable = [m for m in MODULE_LIST if coverage[m]['pct'] is not None]
            rows.append({
                'stage_id': s.id,
                'name': s.name,
                'kind': s.stage_kind,
                'start': s.start_date.isoformat(),
                'end': s.end_date.isoformat() if s.end_date else None,
                # 实际算到哪天：阶段还没结束时 `end` 是计划终点，
                # 而 `days` / 分母都只算到**今天**。两者不分开，页面上
                # 「2029-09-30 结束，共 14 天」就自相矛盾。
                'end_effective': end.isoformat(),
                'days': (end - start).days + 1,
                'in_future': False,
                'coverage': coverage,
                'comparable_modules': len(comparable),
                # 与年度总览同一判据：只比覆盖率，不比点数
                'weakest': (
                    ProgressAggregator._weakest(modules_for_weakest)
                    if len(comparable) >= MIN_COMPARABLE else None
                ),
            })

        return {
            'as_of': today.isoformat(),
            'modules': [
                {
                    'module': mod,
                    'label': MODULE_META[mod]['label'],
                    'color': MODULE_META[mod]['color'],
                    'period_word': COVERAGE_SPEC[mod]['period_word'],
                    'label_text': COVERAGE_SPEC[mod]['label'],
                }
                for mod in MODULE_LIST
            ],
            # 正序 = 人生顺序（从早年走到现在），与 selfrun 时间轴一致
            'stages': rows,
            'note': '只比覆盖率（有记录的期数 ÷ 该有的期数）；强度是绝对量，不跨阶段比',
        }

    # ── 单维度在某个区间内的覆盖率 ─────────────────────────

    @classmethod
    def _span_coverage(
        cls,
        module: str,
        start: date,
        end: date,
        years: list[int],
        marks_cache: dict[tuple[str, int], set[date]],
        system_start: date | None,
    ) -> dict:
        spec = COVERAGE_SPEC[module]

        def row(pct, covered, periods, reason, clipped, visible_from):
            """统一形状：`ProgressAggregator._weakest` 直接吃这一份

            ⚠️ `recent_*` 三键必须留着（值恒 None）：`_weakest` 会读它们。
               跨阶段的「最近 30 天」没有意义（阶段可能早就结束了），
               但删掉键会让最短板算不出来 —— 那种 500 比缺三个键更糟。
            """
            return {
                'pct': pct,
                'covered': covered,
                'periods': periods,
                'period_word': spec['period_word'],
                'label': spec['label'],
                'reason': reason,
                'clipped': clipped,
                'visible_from': visible_from.isoformat() if visible_from else None,
                'recent_pct': None,
                'recent_covered': None,
                'recent_periods': None,
            }

        # 这个维度一条记录都没有 ⇒ 不可观测。与「这一段里没记」是两件事：
        # 前者是模组还没开始用，后者是用了没记 —— 后者才是 0%。
        marks = cls._marks_in(module, years, marks_cache)
        if not marks:
            return row(None, 0, 0, REASON_NO_RECORDS, False, None)

        if system_start is None or system_start > end:
            # 整段都在系统开始之前：分母不存在（不是 0%）
            return row(None, 0, 0, REASON_BEFORE_DATA, False, system_start)

        eff_start = max(start, system_start)
        clipped = eff_start > start

        if spec['period'] == 'day':
            periods = (end - eff_start).days + 1
            covered = len({d for d in marks if eff_start <= d <= end})
        else:
            # 月粒度：只数**完整落在区间内且已结完**的月份。
            # 边界月（阶段从月中开始 / 在月中结束）两不靠 —— 算进去会让
            # 分母多一期而分子拿不到那一期，覆盖率凭空变低。
            allowed: set[tuple[int, int]] = set()
            y, m = eff_start.year, eff_start.month
            while (y, m) <= (end.year, end.month):
                first = date(y, m, 1)
                last = date(y, m, calendar.monthrange(y, m)[1])
                if first >= eff_start and last <= end:
                    allowed.add((y, m))
                m += 1
                if m > 12:
                    m = 1
                    y += 1
            periods = len(allowed)
            covered = len({(d.year, d.month) for d in marks} & allowed)

        # 月粒度：阶段还不足一个完整月 ⇒ 分母为 0，给原因码而不是静默 `—`
        reason = None if periods else (
            REASON_NO_COMPLETE_PERIOD if spec['period'] == 'month' else None
        )
        return row(
            round(covered / periods * 100, 1) if periods else None,
            covered, periods, reason, clipped, system_start,
        )

    @staticmethod
    def _marks_in(
        module: str,
        years: list[int],
        cache: dict[tuple[str, int], set[date]],
    ) -> set[date]:
        """区间内该维度「有记录」的日期集合（按年取、请求内共用）

        ⚠️ 复用 `ProgressAggregator._covered_marks`，不另写取数 ——
           「哪一天算有记录」全站只此一份（空占位不算、归因剔除的不算）。
        """
        out: set[date] = set()
        for y in years:
            key = (module, y)
            if key not in cache:
                cache[key] = ProgressAggregator._covered_marks(module, y)
            out |= cache[key]
        return out
