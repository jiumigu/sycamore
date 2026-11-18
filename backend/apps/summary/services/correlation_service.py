"""跨维度相关性「配对体检」—— 回答「我的这些量之间有没有关系」

与 `body_mind_correlation_service` 的分工：
- 那个是**周级**的身体-状态三联（睡眠 / 良品率 / 情绪），讲一个具体故事；
- 这个是**月级**的配对体检，一次列出若干组语义上说得通的配对，
  每组只回答三件事：有多少个共同月份、相关系数多少、去掉极端月还成不成立。

🔴 三条纪律：

1. **取数必须复用既有口径**，不另写 SQL。
   时间投入走 `ProgressAggregator._times_counted_year`（含 ATTRIBUTION_COUNTED
   与「未归类」排除）；财富走 `WealthBalanceList`（七维财富的同一个源）；
   健康走 `HealthRecord.total`。自己去 `SUM(duration_hours)` 会得到 19188 小时，
   而七维口径下远小于这个数 —— 两把尺子量同一件事，报表之间就会互相打脸。

2. **缺失的月份不进序列**，绝不补 0。
   某月没记账 ≠ 那月花了 0 元。补 0 会把「记不记账」的节奏当成「花不花钱」的
   波动，算出来的相关系数衡量的是记账习惯，不是生活。

3. **系数不给因果**。`CORRELATION_PAIRS` 里每条 `why` 都写成疑问句而不是断言，
   前端也必须显示「这是同期共变，不是因果」。
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..constants import (
    CORR_REASON_CONSTANT,
    CORR_REASON_NO_DATA,
    CORR_REASON_NOT_ENOUGH,
    CORRELATION_BANDS,
    CORRELATION_MIN_N,
    CORRELATION_PAIRS,
    CORRELATION_ROBUST_MIN,
    CORRELATION_ROBUST_MIN_N,
)


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    """秩相关（并列取平均秩）

    比 Pearson 更适合本项目：支出有「单月 4.5 万 vs 常态 5 千」这类极端值，
    Pearson 会被一两个点绑架，而秩相关只看顺序。
    """

    def ranks(v: list[float]) -> list[float]:
        order = sorted(range(len(v)), key=lambda i: v[i])
        out = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    n = len(xs)
    if n < 3:
        return None
    rx, ry = ranks(xs), ranks(ys)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    if dx == 0 or dy == 0:
        return None
    return round(num / (dx * dy), 3)


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = sum((a - mx) ** 2 for a in xs) ** 0.5
    dy = sum((b - my) ** 2 for b in ys) ** 0.5
    if dx == 0 or dy == 0:
        return None
    return round(num / (dx * dy), 3)


def _band(rho: float | None) -> tuple[str | None, str | None]:
    """|rho| → (档位 key, 档位文案)。阈值只在 constants 里定义"""
    if rho is None:
        return None, None
    for lower, key, label in CORRELATION_BANDS:
        if abs(rho) >= lower:
            return key, label
    return None, None


class CorrelationService:
    """跨维度配对体检"""

    # ── 各 metric 的月度序列 ──────────────────────────────
    # 返回 { 'YYYY-MM': 值 }；**只有该月确实有记录才进 dict**。

    @staticmethod
    def _metric_times(years: list[int]) -> dict[str, float]:
        """投入小时（计入行）—— 复用七维的口径，不另写过滤"""
        from .progress_aggregator import ProgressAggregator

        out: dict[str, float] = {}
        for year in years:
            for r in ProgressAggregator._times_counted_year(year):
                mon = r.get('mon')
                if not mon:
                    continue
                try:
                    key = f'{year}-{int(mon):02d}'
                except (TypeError, ValueError):
                    continue
                out[key] = out.get(key, 0.0) + float(r.get('h') or 0)
        return out

    @staticmethod
    def _metric_balance(years: list[int], field: str) -> dict[str, float]:
        """月度收支表取一列（七维财富的同一个源）

        `WealthBalanceList` 有该月一行即视为「记了账」，`outmoney=0` 是真实的
        0 元支出，与「没记」不同 —— 所以这里是 `is None` 才跳过。
        """
        from apps.wealth.models import WealthBalanceList

        wanted = {str(y) for y in years}
        rows = WealthBalanceList.objects.values('yearmon', 'wageincome', 'otherincome', 'outmoney')
        out: dict[str, float] = {}
        for r in rows:
            ym = r.get('yearmon') or ''
            if ym[:4] not in wanted:
                continue
            if field == 'expense':
                v = r.get('outmoney')
            elif field == 'income':
                wage, other = r.get('wageincome'), r.get('otherincome')
                if wage is None and other is None:
                    continue
                v = (wage or 0) + (other or 0)
            else:
                raise ValueError(f'未知的收支列: {field}')
            if v is None:
                continue
            out[ym] = float(v)
        return out

    @staticmethod
    def _metric_sugar_level(years: list[int]) -> dict[str, float]:
        """月度快乐程度**均值**

        刻意不用「次数」：记小确幸的次数会随记录习惯整体抬高（实测 2022–2025
        每月 1–3 条、2026 年 4–8 条），那个阶跃与生活无关，却足以把任何
        「次数 vs 某量」的相关系数带向它自己。
        """
        from django.db.models import Avg, Count
        from django.db.models.functions import TruncMonth

        from apps.sugar.models import SugarRecord

        rows = (
            SugarRecord.objects.filter(time__year__in=years)
            .annotate(k=TruncMonth('time'))
            .values('k')
            .annotate(avg=Avg('level_of_happiness'), c=Count('s_id'))
        )
        return {
            r['k'].strftime('%Y-%m'): float(r['avg'])
            for r in rows
            if r['k'] and r['avg'] is not None
        }

    @staticmethod
    def _metric_steps(years: list[int]) -> dict[str, float]:
        """月度步数合计 —— 与七维健康同源（`HealthRecord.total`）"""
        from django.db.models import Sum
        from django.db.models.functions import TruncMonth

        from apps.health.models import HealthRecord

        rows = (
            HealthRecord.objects.filter(time__year__in=years)
            .annotate(k=TruncMonth('time'))
            .values('k')
            .annotate(s=Sum('total'))
        )
        return {r['k'].strftime('%Y-%m'): float(r['s'] or 0) for r in rows if r['k']}

    # ── 组装 ────────────────────────────────────────────

    @classmethod
    def _all_metrics(cls, years: list[int]) -> dict[str, dict[str, float]]:
        return {
            'times': cls._metric_times(years),
            'expense': cls._metric_balance(years, 'expense'),
            'income': cls._metric_balance(years, 'income'),
            'sugar_level': cls._metric_sugar_level(years),
            'steps': cls._metric_steps(years),
        }

    @staticmethod
    def _years() -> list[int]:
        """覆盖到所有来源的年份跨度

        起点取「七维可观测起点」，与阶段对照同一把尺子（`get_available_years`
        的最早年），终点到今年 —— 少算年份会让老配对的 n 凭空变小。
        """
        from .progress_aggregator import ProgressAggregator

        today = date.today()
        avail = ProgressAggregator.get_available_years()
        start = min(avail) if avail else today.year
        return list(range(start, today.year + 1))

    @classmethod
    def _judge(cls, pair: dict, series: dict[str, dict[str, float]]) -> dict[str, Any]:
        """一组配对：取共同月份 → 算系数 → 判档 → 复核稳健性"""
        left = series.get(pair['left'], {})
        right = series.get(pair['right'], {})
        months = sorted(set(left) & set(right))

        base: dict[str, Any] = {
            'key': pair['key'],
            'left_label': pair['left_label'],
            'right_label': pair['right_label'],
            'unit_left': pair['unit_left'],
            'unit_right': pair['unit_right'],
            'why': pair['why'],
            'n': len(months),
        }

        if not months:
            return {**base, 'pearson': None, 'spearman': None, 'trimmed_spearman': None,
                    'level': None, 'level_label': None, 'robust': None,
                    'reason': CORR_REASON_NO_DATA, 'months': None, 'points': []}

        xs = [left[m] for m in months]
        ys = [right[m] for m in months]
        rho = _spearman(xs, ys)
        r = _pearson(xs, ys)

        if rho is None:
            # 某一侧常年不变（例如三个月支出全是同一个数）—— 相关系数无定义
            return {**base, 'pearson': r, 'spearman': None, 'trimmed_spearman': None,
                    'level': None, 'level_label': None, 'robust': None,
                    'reason': CORR_REASON_CONSTANT, 'months': None, 'points': []}

        if len(months) < CORRELATION_MIN_N:
            # 有数、能算，但样本太少 —— 照样给系数，只是不判档、不下结论
            return {**base, 'pearson': r, 'spearman': rho, 'trimmed_spearman': None,
                    'level': None, 'level_label': None, 'robust': None,
                    'reason': CORR_REASON_NOT_ENOUGH, 'months': None,
                    'points': [{'month': m, 'x': x, 'y': y} for m, x, y in zip(months, xs, ys)]}

        level, label = _band(rho)

        # 稳健性：按左侧量的顺序去掉最高、最低各一个月，看结论还在不在
        trimmed = None
        robust = None
        if len(months) >= CORRELATION_ROBUST_MIN_N:
            order = sorted(range(len(xs)), key=lambda i: xs[i])
            keep = order[1:-1]
            trimmed = _spearman([xs[i] for i in keep], [ys[i] for i in keep])
            if trimmed is not None:
                # 只有「原本过线」的结论才需要复核：
                # 本来就说「没关系」的，去掉极端月后更没关系，不值得标成不稳健
                robust = abs(trimmed) >= CORRELATION_ROBUST_MIN or abs(rho) < CORRELATION_ROBUST_MIN

        return {
            **base,
            'pearson': r,
            'spearman': rho,
            'trimmed_spearman': trimmed,
            'level': level,
            'level_label': label,
            'robust': robust,
            'reason': None,
            'months': {'from': months[0], 'to': months[-1]},
            'points': [{'month': m, 'x': x, 'y': y} for m, x, y in zip(months, xs, ys)],
        }

    @classmethod
    def pair_check(cls) -> dict[str, Any]:
        """配对体检：所有预置组合一次算完"""
        years = cls._years()
        series = cls._all_metrics(years)
        pairs = [cls._judge(p, series) for p in CORRELATION_PAIRS]

        return {
            'pairs': pairs,
            'min_n': CORRELATION_MIN_N,
            'bands': [
                {'lower': lower, 'key': key, 'label': label}
                for lower, key, label in CORRELATION_BANDS
            ],
            'robust_min': CORRELATION_ROBUST_MIN,
            # 覆盖面：让读者知道「不是只有这几组可比，而是只有这几组收进来了」
            'coverage': {
                'years': [years[0], years[-1]],
                'metrics': {
                    'times': len(series['times']),
                    'expense': len(series['expense']),
                    'income': len(series['income']),
                    'sugar_level': len(series['sugar_level']),
                    'steps': len(series['steps']),
                },
            },
        }
