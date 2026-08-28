"""health 统计服务 ORM 化回归：步数统计（Cast 方案）"""
import pytest
from datetime import datetime

from apps.health.models import HealthRecord
from apps.health.services import HealthStatsService


@pytest.mark.django_db
class TestHealthStats:
    def _rec(self, dt, total, htype=1):
        return HealthRecord.objects.create(time=datetime.fromisoformat(dt), total=total, htype=htype, steps=int(total))

    def test_count_active_days(self):
        self._rec('2026-08-01 08:00:00', 5000)
        self._rec('2026-08-01 12:00:00', 3000)  # 同日
        self._rec('2026-08-02 08:00:00', 7000)
        assert HealthStatsService._count_active_days() == 2

    def test_month_steps_uses_date_range(self):
        self._rec('2026-08-01 08:00:00', 5000)
        self._rec('2026-08-15 08:00:00', 3000)
        self._rec('2026-07-31 08:00:00', 9999)  # 不应计入 8 月
        assert HealthStatsService._get_month_steps(2026, 8) == 8000.0

    def test_longest_streak(self):
        self._rec('2026-08-01 08:00:00', 1000)
        self._rec('2026-08-02 08:00:00', 1000)
        self._rec('2026-08-03 08:00:00', 1000)
        self._rec('2026-08-05 08:00:00', 1000)  # 断档
        self._rec('2026-08-06 08:00:00', 1000)
        assert HealthStatsService._calc_longest_streak() == 3

    def test_daily_trend(self):
        from datetime import date
        from django.utils import timezone
        today = timezone.localdate()
        self._rec(f'{today} 08:00:00', 6000)
        trend = HealthStatsService.get_daily_trend(days=1)
        assert len(trend) == 2
        assert any(d['date'] == today.isoformat() and d['total_steps'] == 6000 for d in trend)
