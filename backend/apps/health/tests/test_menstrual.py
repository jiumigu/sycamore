"""好朋友跟踪：end_date / duration_days 自动计算与 12 个月口径 stats"""
import pytest
from datetime import date, timedelta

from apps.health.models import MenstrualRecord


@pytest.mark.django_db
class TestMenstrualRecord:
    def _create(self, start, end=None, duration=None, **kw):
        data = {'year': start.year, 'month': f'{start.month:02d}', 'start_date': start,
                'offset': 0, 'cycle_days': 30, **kw}
        if end:
            data['end_date'] = end
        if duration is not None:
            data['duration_days'] = duration
        return MenstrualRecord.objects.create(user_id=1, **data)

    def test_auto_duration_from_end_date(self):
        # 自动计算在 serializer 层（ORM create 不触发）
        from rest_framework.test import APIClient
        c = APIClient()
        r = c.post('/api/health/menstrual/', {
            'year': 2026, 'month': '08', 'start_date': '2026-08-10',
            'end_date': '2026-08-15', 'offset': 0, 'cycle_days': 30,
        }, format='json')
        assert r.status_code == 201
        assert r.data['duration_days'] == 5

    def test_manual_duration_overrides(self):
        r = self._create(date(2026, 8, 20), end=date(2026, 8, 23), duration=2)
        assert r.duration_days == 2

    def test_no_end_date_no_duration(self):
        r = self._create(date(2026, 8, 1))
        assert r.duration_days is None

    def test_api_create_auto_duration(self):
        from rest_framework.test import APIClient
        c = APIClient()
        r = c.post('/api/health/menstrual/', {
            'year': 2026, 'month': '08', 'start_date': '2026-08-10',
            'end_date': '2026-08-15', 'offset': 0, 'cycle_days': 30,
        }, format='json')
        assert r.status_code == 201
        assert r.data['duration_days'] == 5

    def test_stats_only_last_12_months(self):
        today = date.today()
        # 13 个月前（应被排除）
        self._create(today - timedelta(days=400), cycle_days=90)
        # 近 12 个月（应计入）
        self._create(today - timedelta(days=30), cycle_days=30)
        self._create(today - timedelta(days=5), cycle_days=32)
        from rest_framework.test import APIClient
        c = APIClient()
        s = c.get('/api/health/menstrual/stats/').data
        assert s['total_records'] == 2
        assert s['avg_cycle'] == 31
        assert s['avg_duration'] is None  # 无结束日期

    def test_stats_avg_duration(self):
        today = date.today()
        self._create(today - timedelta(days=40), end=today - timedelta(days=34), duration=6)
        self._create(today - timedelta(days=10), end=today - timedelta(days=2), duration=8)
        from rest_framework.test import APIClient
        c = APIClient()
        s = c.get('/api/health/menstrual/stats/').data
        assert s['avg_duration'] == 7
