"""综合进度看板 — 身心关联分析（周级）

与 `correlation_service` 的分工：这个是**周级三联的具体故事**
（睡眠 / 良品率 / 情绪按周对齐），那个是**月级配对体检**。

🔴 v3.64.62 修掉三处会静默给错数的写法：

1. `aggregate(...)['avg'] or 0` —— 无数据变 0。
   全库健康自检只有 4 条（2026-06→09），12 周窗口内 0 条，
   于是每周都算出「延迟 0 分钟、夜醒 0 次」。实测接口 12 周 `sleep_score`
   **全是 100.0**：一个满分假象，比空态危险得多（空态至少看得出没数据）。
2. 手算 `sleep_score = 100 - 延迟*1.5 - 夜醒*15` —— 系数没有出处、
   量纲是凑的、且可能为负（延迟 70 分钟就负数）。已删除，改下发**原始量**：
   平均入睡耗时、平均夜醒次数。这两个数有明确单位和出处，读者自己判断。
3. `WealthBillList` 那类 `DateTimeField` 上的 `__lte=date` 会漏掉当天 ——
   本模块的三个日期字段（`check_date` / `occurred_at` / `time`）都是 DateField，
   不踩这个坑；但区间仍统一用**闭区间 + 显式 days**，与项目「半开区间」约定区分开：
   这里是「按自然周分组」，不是「某时刻之后」。

输出每一周都带 `nights`（该周有几天自检）。前端据此判断「这条线能不能读」——
`nights=0` 时所有睡眠相关的量都是 `None`，不是 0。
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any


class BodyMindCorrelationService:
    """身体-状态关联 —— 睡眠原始量、良品率、情绪按周对齐"""

    @staticmethod
    def get_correlation_data(user_id: int = 1, weeks: int = 12) -> list[dict[str, Any]]:
        """近 N 周的三联数据

        每周一行，三组量的**缺失一律 `None`**：

        | 字段 | 含义 | 缺失时 |
        |---|---|---|
        | `sleep_latency` | 平均入睡耗时（分钟） | `None`（该周没有自检） |
        | `awakenings` | 平均夜醒次数 | `None` |
        | `nights` | 该周有几天做了自检 | 0 |
        | `output_rate` | 良品率（%） | `None`（该周没有产出记录） |
        | `mood` | 小确幸快乐程度均值（5–20） | `None`（该周没有小确幸） |

        🔴 `mood` 的量程是 **5–20**（`SugarRecord.level_of_happiness`，
        不是 1–10）。前端第二根 y 轴曾写死 `min:1,max:10`，导致所有点顶到天花板。
        """
        from django.db.models import Avg

        from apps.goals.models import OutputRecord
        from apps.sugar.models import SugarRecord
        from apps.toolkit.models import HealthSelfCheck

        today = date.today()
        result: list[dict[str, Any]] = []

        for i in range(weeks):
            week_end = today - timedelta(days=7 * i)
            week_start = week_end - timedelta(days=6)

            # ── 睡眠：逐项 avg，缺就是 None ──
            checks = HealthSelfCheck.objects.filter(
                user_id=user_id,
                check_date__gte=week_start,
                check_date__lte=week_end,
            )
            agg = checks.aggregate(
                latency=Avg('sleep_latency'),
                awake=Avg('awakenings'),
            )
            nights = checks.count()
            latency = float(agg['latency']) if agg['latency'] is not None else None
            awakenings = float(agg['awake']) if agg['awake'] is not None else None

            # ── 良品率：分母为 0 就是 None（不是 0%）──
            outputs = OutputRecord.objects.filter(
                user_id=user_id,
                occurred_at__gte=week_start,
                occurred_at__lte=week_end,
            )
            total = outputs.count()
            good = outputs.filter(quality='good').count()
            output_rate = round(good / total * 100, 1) if total else None

            # ── 情绪：均值，无记录就是 None ──
            mood_agg = SugarRecord.objects.filter(
                time__gte=week_start,
                time__lte=week_end,
            ).aggregate(avg=Avg('level_of_happiness'))
            mood = round(float(mood_agg['avg']), 1) if mood_agg['avg'] is not None else None

            result.append({
                'week': week_end.isoformat(),
                'week_label': f'{week_start.month}/{week_start.day}-{week_end.month}/{week_end.day}',
                'week_start': week_start.isoformat(),
                'sleep_latency': round(latency, 1) if latency is not None else None,
                'awakenings': round(awakenings, 2) if awakenings is not None else None,
                'nights': nights,
                'output_rate': output_rate,
                'output_count': total,
                'mood': mood,
            })

        return list(reversed(result))
