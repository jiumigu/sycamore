"""综合进度看板 — 身心关联分析（由 services.py 拆分）"""

from __future__ import annotations

from datetime import datetime
from typing import Any

class BodyMindCorrelationService:
    """身体-状态关联分析 —— 睡眠、良品率、情绪的相关性"""

    @staticmethod
    def get_correlation_data(user_id: int = 1, weeks: int = 12) -> list[dict[str, Any]]:
        """获取近 N 周的睡眠-良品率-情绪关联数据"""
        from datetime import date, timedelta

        from django.db.models import Avg, Count

        from apps.goals.models import OutputRecord
        from apps.sugar.models import SugarRecord
        from apps.toolkit.models import HealthSelfCheck

        result: list[dict[str, Any]] = []

        for i in range(weeks):
            week_end = date.today() - timedelta(weeks=i)
            week_start = week_end - timedelta(days=6)

            # 睡眠数据（取每周平均）
            sleep_checks = HealthSelfCheck.objects.filter(
                user_id=user_id,
                check_date__gte=week_start,
                check_date__lte=week_end,
            )
            avg_sleep_latency = sleep_checks.aggregate(avg=Avg('sleep_latency'))['avg'] or 0
            avg_awakenings = sleep_checks.aggregate(avg=Avg('awakenings'))['avg'] or 0

            # 良品率
            outputs = OutputRecord.objects.filter(
                user_id=user_id,
                occurred_at__gte=week_start,
                occurred_at__lte=week_end,
            )
            total = outputs.count()
            good = outputs.filter(quality='good').count()
            output_rate = round(good / total * 100, 1) if total > 0 else None

            # 情绪（小确幸快乐程度均值作为情绪代理）
            sugar_mood = SugarRecord.objects.filter(
                time__gte=week_start,
                time__lte=week_end,
            ).aggregate(avg=Avg('level_of_happiness'))['avg'] or 0

            result.append({
                'week': week_end.isoformat(),
                'week_label': f'{week_start.month}/{week_start.day}-{week_end.month}/{week_end.day}',
                'sleep_score': round(100 - float(avg_sleep_latency) * 1.5 - float(avg_awakenings) * 15, 1),
                'output_rate': output_rate,
                'mood': round(float(sugar_mood), 1),
            })

        return list(reversed(result))
