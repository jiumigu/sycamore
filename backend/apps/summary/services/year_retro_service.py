"""年度回顾（叙事版）—— 把「这一年」讲成人话，每一句都指得到真实记录

判据来自审计报告 6.3 与用户裁定的三处口径：

1. **只讲有时间锚点的事**：第一条 / 最后一条记录、中间的空档、阶段切换、
   连续有记录的最长一段。「今年读了几本书」这类清点留给「年度明细」表格 ——
   塞进来就又变成一张表了。
2. **每段必须带 `evidence`**：至少一条真实记录（类型 + 日期 + 摘要）。
   取不到证据的段不生成，宁可少讲。
3. **只陈述事实**，不评价、不建议、不打分。

⚠️ **开头和结尾的空档不算断档**（这条是实测撞出来的）：
   - 结尾：本月记账还没到（`end` 是今天，而账通常月末才落）⇒ 会报成「断了 44 天」
   - 开头：上一年最后几天没记 ⇒ 那段空档去年已经算过一次
   两处都会变成假警报，而且「最后一条记录」那段已经说过了。
   所以只统计**两条记录之间**的空档。
"""

from __future__ import annotations

from datetime import date, datetime, time as dtime, timedelta

from django.utils import timezone

from ..constants import (
    BOOK,
    COVERAGE_SPEC,
    HEALTH,
    MODULE_LIST,
    MODULE_META,
    RETRO_DENSEST_MIN_DAYS,
    RETRO_FIRST,
    RETRO_GAP,
    RETRO_GAP_MIN_DAYS,
    RETRO_GAP_MIN_MONTHS,
    RETRO_LAST,
    RETRO_MAX_GAPS,
    RETRO_MAX_SEGMENTS,
    RETRO_MAX_STAGES,
    RETRO_STAGE,
    RETRO_THIN_SEGMENTS,
    SUGAR,
    TIMES,
    TRAVEL,
    WEALTH,
    WORDS,
)
from .progress_aggregator import ProgressAggregator
from .stage_span_service import StageSpanService

# 权重只用来在超限时决定「留哪几段」，不对外下发。
# first / last 是叙事的两头，永远必留。
_WEIGHT_MUST = 10 ** 6


class YearRetroService:
    """把一年的记录讲成一篇有前后顺序的事实流（只读）"""

    # ── 入口 ───────────────────────────────────────────────

    @classmethod
    def build(cls, year: int) -> dict:
        today = timezone.localdate()
        start = date(year, 1, 1)

        if year > today.year:
            return cls._empty(year, 'future', today)

        end = date(year, 12, 31) if year < today.year else today
        is_partial = year == today.year
        elapsed = (end - start).days + 1

        marks: dict[str, set[date]] = {}
        for module in MODULE_LIST:
            marks[module] = {
                d for d in ProgressAggregator._covered_marks(module, year)
                if start <= d <= end
            }

        union: set[date] = set().union(*marks.values()) if marks else set()
        if not union:
            return cls._empty(year, 'no_data', end, is_partial)

        segments: list[dict] = []
        segments += cls._first_and_last(marks, start, end)
        segments += cls._gaps(marks, start, end)
        segments += cls._stage_events(start, end)

        densest = cls._densest(union, start, end, elapsed)
        if densest:
            segments.append(densest)

        segments.sort(key=lambda s: s['sort_date'])
        segments = cls._cap(segments)

        absences = [MODULE_META[m]['label'] for m in MODULE_LIST if not marks[m]]

        return {
            'year': year,
            'as_of': end.isoformat(),
            'is_partial': is_partial,
            'summary': cls._summary(start, end, elapsed, len(union)),
            'segments': [cls._public(s) for s in segments],
            'absences': absences,
            'thin': len(segments) < RETRO_THIN_SEGMENTS,
            'thin_reason': cls._thin_reason(len(union), len(segments)),
            'empty_reason': None,
        }

    @staticmethod
    def _public(seg: dict) -> dict:
        """出口只留前端要用的键：内部排序/权重/质量标记都不对外"""
        out = {k: v for k, v in seg.items() if k not in ('sort_date', 'weight', 'span_days')}
        out['evidence'] = [{k: v for k, v in e.items() if k != 'weak'} for e in out['evidence']]
        return out

    # ── 汇总句 ─────────────────────────────────────────────

    @staticmethod
    def _summary(start: date, end: date, elapsed: int, covered: int) -> dict:
        """开头那一句。数字由后端算好，前端零算（同一事实一把尺子）"""
        every_day = covered >= elapsed
        if every_day:
            text = f'{YearRetroService._md(start)}到 {YearRetroService._md(end)}，{elapsed} 天里每一天都至少留下一项记录。'
        else:
            text = f'{YearRetroService._md(start)}到 {YearRetroService._md(end)}，{elapsed} 天里有 {covered} 天留下记录。'
        return {
            'span_start': start.isoformat(),
            'span_end': end.isoformat(),
            'elapsed_days': elapsed,
            'coverage_days': covered,
            'every_day': every_day,
            'text': text,
        }

    @staticmethod
    def _md(d: date) -> str:
        """「3 月 8 日」。年份在这一页是固定的，不重复写"""
        return f'{d.month} 月 {d.day} 日'

    # ── 第一条 / 最后一条 ──────────────────────────────────

    @classmethod
    def _first_and_last(cls, marks: dict[str, set[date]], start: date, end: date) -> list[dict]:
        days = sorted(set().union(*marks.values()))
        if not days:
            return []
        out = []
        for kind, day in ((RETRO_FIRST, days[0]), (RETRO_LAST, days[-1])):
            ev = cls._pick_evidence(marks, day)
            if not ev:
                # 这一天有记录，却取不到任何一条可引用的 —— 说明取数口径和
                # `_covered_marks` 不同步。宁可不讲，也不讲一句没有出处的话。
                continue
            prefix = '第一条' if kind == RETRO_FIRST else '最后一条'
            out.append(cls._seg(
                kind=kind,
                sort_date=day,
                date=day,
                text=f'{cls._md(day)}，今年{prefix}记录是{ev["label"]}：{ev["text"]}。',
                evidence=[ev],
                weight=_WEIGHT_MUST,
            ))
        return out

    @classmethod
    def _pick_evidence(cls, marks: dict[str, set[date]], day: date) -> dict | None:
        """这一天的代表记录

        顺序即口径：财富 → 健康 → 时间 → 文字 → 小确幸 → 旅行 → 阅读。
        同一天有多个维度时靠前的更「重」（钱和身体先于心情）。

        ⚠️ 但**没有实质内容的优先让位**：「当月记了一笔账（没有写备注）」这种
           是兜底话，拿它当「今年第一条记录」等于什么都没说，而那天明明
           还写了日记。所以有实质内容的一律排在前面。
        """
        cands = []
        for module in MODULE_LIST:
            if day not in marks[module]:
                continue
            ev = cls._evidence(module, day)
            if ev:
                cands.append(ev)
        if not cands:
            return None
        solid = [e for e in cands if not e.get('weak')]
        return (solid or cands)[0]

    # ── 空档 ───────────────────────────────────────────────

    @classmethod
    def _gaps(cls, marks: dict[str, set[date]], start: date, end: date) -> list[dict]:
        """两条记录之间的空档，每个维度最多一条，全局再取前 N

        🔴 只看「记录与记录之间」，不看两头 —— 见模块 docstring。
        🔴 每个维度只留最长的那一条：同一个小确幸空档 154 天、再空 87 天，
           两条都进榜就变成「同一件事抱怨两遍」，而真正长的别处反而挤不进来。
        """
        candidates: list[dict] = []

        for module in MODULE_LIST:
            days = sorted(marks[module])
            label = MODULE_META[module]['label']
            grain = COVERAGE_SPEC[module]['period']

            if grain == 'month':
                best = cls._longest(cls._month_gaps(module, label, days))
            else:
                best = None
                for a, b in zip(days, days[1:]):
                    empty = (b - a).days - 1
                    if empty < RETRO_GAP_MIN_DAYS:
                        continue
                    ev = [e for e in (cls._evidence(module, a), cls._evidence(module, b)) if e]
                    if not ev:
                        # 没有任何一条能引用的记录 ⇒ 这句话没有出处，不讲
                        continue
                    seg = cls._seg(
                        kind=RETRO_GAP,
                        sort_date=a,
                        date=a,
                        date_end=b,
                        module=module,
                        text=f'{cls._md(a)}到 {cls._md(b)}，{label}一条都没记，隔了 {empty} 天。',
                        evidence=ev,
                        weight=empty,
                        span_days=empty,
                    )
                    best = seg if best is None or empty > best['span_days'] else best

            if best:
                candidates.append(best)

        candidates.sort(key=lambda s: s['span_days'], reverse=True)
        return candidates[:RETRO_MAX_GAPS]

    @staticmethod
    def _longest(candidates: list[dict]) -> dict | None:
        return max(candidates, key=lambda s: s['span_days']) if candidates else None

    @classmethod
    def _month_gaps(cls, module: str, label: str, days: list[date]) -> list[dict]:
        """月粒度维度按「月」算空档 —— 拿天算会把它自己的记账节奏误报成断档

        记账按月落、读完一本书按月落，本来就不是天天有。
        """
        first_in_month: dict[tuple[int, int], date] = {}
        for d in days:
            first_in_month.setdefault((d.year, d.month), d)

        months = sorted(first_in_month)
        out = []
        for (y1, m1), (y2, m2) in zip(months, months[1:]):
            empty = (y2 * 12 + m2) - (y1 * 12 + m1) - 1
            if empty < RETRO_GAP_MIN_MONTHS:
                continue
            a, b = first_in_month[(y1, m1)], first_in_month[(y2, m2)]
            ev = [e for e in (cls._evidence(module, a), cls._evidence(module, b)) if e]
            if not ev:
                continue
            out.append(cls._seg(
                kind=RETRO_GAP,
                sort_date=a,
                date=a,
                date_end=b,
                module=module,
                text=f'{m1} 月到 {m2} 月之间，{label}空了 {empty} 个月。',
                evidence=ev,
                weight=empty * 30,
                span_days=empty * 30,
                facts={'empty_months': empty},
            ))
        return out

    # ── 阶段切换 ───────────────────────────────────────────

    @classmethod
    def _stage_events(cls, start: date, end: date) -> list[dict]:
        """人生阶段在这一年里开始 / 结束 / 换段的位置

        判据与 `StageSpanService` 逐字对齐：闭区间、只取顶层、`end_date=None` 无限延伸。
        """
        stages = StageSpanService._top_stages()
        events: list[dict] = []

        for s in stages:
            if not (start <= s.start_date <= end):
                continue
            prev = next(
                (p for p in stages
                 if p.id != s.id and p.end_date and p.end_date + timedelta(days=1) == s.start_date),
                None,
            )
            if prev:
                text = f'{cls._md(s.start_date)}，「{prev.name}」结束，第二天进入「{s.name}」。'
            else:
                text = f'{cls._md(s.start_date)}，阶段进入「{s.name}」。'
            events.append(cls._seg(
                kind=RETRO_STAGE,
                sort_date=s.start_date,
                date=s.start_date,
                text=text,
                evidence=[{
                    'type': 'stage', 'label': '人生阶段',
                    'date': s.start_date.isoformat(), 'text': s.name,
                    'id': s.id,
                }],
                weight=_WEIGHT_MUST // 10,
            ))

        # 年内结束、且没有下一段接上（`end_date=None` 的不算结束）
        for s in stages:
            if not s.end_date or not (start <= s.end_date <= end) or s.end_date >= end:
                continue
            if any(p.id != s.id and p.start_date == s.end_date + timedelta(days=1) for p in stages):
                continue
            events.append(cls._seg(
                kind=RETRO_STAGE,
                sort_date=s.end_date,
                date=s.end_date,
                text=f'{cls._md(s.end_date)}，「{s.name}」结束。',
                evidence=[{
                    'type': 'stage', 'label': '人生阶段',
                    'date': s.end_date.isoformat(), 'text': s.name,
                    'id': s.id,
                }],
                weight=_WEIGHT_MUST // 10,
            ))

        events.sort(key=lambda s: s['sort_date'])
        return events[:RETRO_MAX_STAGES]

    # ── 最密的一段 ─────────────────────────────────────────

    @classmethod
    def _densest(cls, union: set[date], start: date, end: date, elapsed: int) -> dict | None:
        """连续有记录的最长一段

        🔴 若是**整段区间**都连续，那它不是「一段」，是「全程」——
           已经在汇总句里说了，再单列一段就是同一句话讲两遍。
        """
        days = sorted(union)
        best_len, best_a, best_b = 0, days[0], days[0]
        run_a = prev = days[0]
        for d in days:
            if d != prev and (d - prev).days == 1:
                prev = d
            else:
                run_a = prev = d
            run_len = (d - run_a).days + 1
            if run_len > best_len:
                best_len, best_a, best_b = run_len, run_a, d

        if best_len >= elapsed or best_len < RETRO_DENSEST_MIN_DAYS:
            return None

        # 证据取**这一段的第一天**：句子说的是「从这天起连续」，
        # 引中间某天的一条记录，读者还得自己算它在不在段里。
        ev = [e for e in (cls._evidence_any(best_a), cls._evidence_any(best_b)) if e][:1]

        return cls._seg(
            kind='densest',
            sort_date=best_a,
            date=best_a,
            date_end=best_b,
            text=f'{cls._md(best_a)}到 {cls._md(best_b)}，连续 {best_len} 天都有记录。',
            evidence=ev,
            weight=best_len,
            span_days=best_len,
        )

    # ── 截断 ───────────────────────────────────────────────

    @classmethod
    def _cap(cls, segments: list[dict]) -> list[dict]:
        """超限时按权重留，但 first / last 必留，最后仍按时间排"""
        if len(segments) <= RETRO_MAX_SEGMENTS:
            return segments

        must = [s for s in segments if s['kind'] in (RETRO_FIRST, RETRO_LAST)]
        rest = [s for s in segments if s['kind'] not in (RETRO_FIRST, RETRO_LAST)]
        rest.sort(key=lambda s: s['weight'], reverse=True)
        kept = must + rest[: max(0, RETRO_MAX_SEGMENTS - len(must))]
        kept.sort(key=lambda s: s['sort_date'])
        return kept

    # ── 组装一段 ───────────────────────────────────────────

    @classmethod
    def _seg(cls, *, kind: str, sort_date: date, date: date, text: str,
             evidence: list[dict], weight: int,
             date_end: date | None = None, module: str | None = None,
             span_days: int = 0, facts: dict | None = None) -> dict:
        return {
            'kind': kind,
            'module': module,
            'date': date.isoformat(),
            'date_end': date_end.isoformat() if date_end else None,
            'text': text,
            'evidence': evidence,
            'facts': facts or {},
            # 内部字段，出口前删掉
            'sort_date': sort_date,
            'weight': weight,
            'span_days': span_days,
        }

    # ── 证据：真去取那一条 ─────────────────────────────────

    @classmethod
    def _evidence_any(cls, day: date) -> dict | None:
        """不知道是哪一维时，按 MODULE_LIST 顺序逐个试"""
        for module in MODULE_LIST:
            ev = cls._evidence(module, day)
            if ev:
                return ev
        return None

    @staticmethod
    def _day_bounds(day: date) -> tuple[datetime, datetime]:
        """本地一天 → 半开区间 [00:00, 次日 00:00)

        🔴 不用 `time__date=day`：`USE_TZ=True` 下它会走 `CONVERT_TZ`，
           跨时区时把凌晨的记录算到前一天。
        """
        tz = timezone.get_current_timezone()
        lo = timezone.make_aware(datetime.combine(day, dtime.min), tz)
        return lo, lo + timedelta(days=1)

    @classmethod
    def _evidence(cls, module: str, day: date) -> dict | None:
        """该维度在这一天的**一条真实记录**；取不到就 None，绝不编"""
        label = MODULE_META[module]['label']
        rec_id, text = None, None
        weak = False   # 「有这条记录，但引出来等于没引」

        if module == WEALTH:
            from apps.wealth.models import WealthBalanceList
            row = (WealthBalanceList.objects
                   .filter(yearmon__startswith=f'{day.year}-{day.month:02d}')
                   .order_by('yearmon')
                   .values('yearmon', 'remarks', 'balance')
                   .first())
            if row:
                remarks = (row['remarks'] or '').strip()
                # 🔴 兜底文案**不带金额**：叙事里出现的钱要么是你自己写的备注，
                #    要么没有。系统自己拼一个「净增 ¥2,361」就和隐私脱敏口径打架了。
                text = remarks or '当月记了一笔账（没有写备注）'
                weak = not remarks
                rec_id = None  # 这张表没有单列主键

        elif module == HEALTH:
            from apps.health.models import HealthRecord
            lo, hi = cls._day_bounds(day)
            row = (HealthRecord.objects.filter(time__gte=lo, time__lt=hi)
                   .order_by('-total').values('hid', 'steps', 'total').first())
            if row:
                steps = int(row['total'] or row['steps'] or 0)
                text = f'{steps} 步'
                rec_id = row['hid']

        elif module == TIMES:
            from apps.temporal.models import TemporalTask
            row = (TemporalTask.objects
                   .filter(year=day.year, mon=f'{day.month:02d}', day=day.day)
                   .order_by('-duration_hours')
                   .values('id', 'task_name', 'duration_hours').first())
            if row:
                hours = row['duration_hours'] or 0
                text = f'最长的一项是「{row['task_name']}」，{hours:.1f} 小时'
                rec_id = row['id']

        elif module == WORDS:
            from apps.temporal.models import OneDayPage
            row = (OneDayPage.objects.filter(begin_date=day, total__gt=0)
                   .order_by('-total').values('oid', 'title').first())
            if row:
                text = f'《{row['title'][:40]}》'
                rec_id = row['oid']

        elif module == SUGAR:
            from apps.sugar.models import SugarRecord
            row = (SugarRecord.objects.filter(time=day)
                   .order_by('-level_of_happiness')
                   .values('s_id', 'title', 'level_of_happiness').first())
            if row:
                text = f'{row['title']}（{row['level_of_happiness']} 级）'
                rec_id = row['s_id']

        elif module == TRAVEL:
            from apps.travel.models import TravelRecord
            row = (TravelRecord.objects.filter(ttime=day)
                   .order_by('tid').values('tid', 'tname').first())
            if row:
                text = f'去了{row['tname']}'
                rec_id = row['tid']

        elif module == BOOK:
            from apps.book.models import Book
            row = (Book.objects.filter(readDate=day, status=Book.STATUS_FINISHED)
                   .order_by('bid').values('bid', 'btitle').first())
            if row:
                text = f'读完《{row['btitle']}》'
                rec_id = row['bid']

        if text is None:
            return None
        return {
            'type': module,
            'label': label,
            'date': day.isoformat(),
            'text': text,
            'id': rec_id,
            'weak': weak,
        }

    # ── 空 ─────────────────────────────────────────────────

    @classmethod
    def _empty(cls, year: int, reason: str, as_of: date,
               is_partial: bool = False) -> dict:
        """讲不出东西的年份也要把「为什么」发下去

        `future` / `no_data` 都不是「这一年很平淡」—— 前者是还没到，
        后者是一条记录都没有。前端只查表，不自己拼文案。
        """
        return {
            'year': year,
            'as_of': as_of.isoformat(),
            'is_partial': is_partial,
            'summary': None,
            'segments': [],
            'absences': [],
            'thin': True,
            'thin_reason': reason,
            'empty_reason': reason,
        }

    @classmethod
    def _thin_reason(cls, covered: int, n_segments: int) -> str | None:
        if covered < 30:
            return 'sparse_data'   # 记录太少，讲不出什么
        if n_segments < RETRO_THIN_SEGMENTS:
            return 'few_events'    # 记录够多，但这一年确实平顺
        return None
