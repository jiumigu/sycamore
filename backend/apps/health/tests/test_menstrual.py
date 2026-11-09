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


@pytest.mark.django_db
class TestMenstrualSaveErrorIsReadable:
    """保存失败的出口：必须是「哪一格、错在哪」的中文，不能是英文，也不能只是一句失败。

    2026-10-30 现场：新增记录只填开始日期 → 界面弹「保存失败」。
    真因是空字符串结束日期被 DRF 判格式错，而提示条把原因整个吞掉了。
    """

    URL = '/api/health/menstrual/'

    def _payload(self, **kw):
        data = {
            'user_id': 1, 'year': 2026, 'month': '10月',
            'start_date': '2026-10-30', 'end_date': None,
            'duration_days': None, 'offset': 1, 'cycle_days': 37, 'notes': '',
        }
        data.update(kw)
        return data

    def test_blank_end_date_reason_names_the_field(self):
        """空串结束日期：要说出「结束日期」和最省事的改法，不能回英文原文"""
        from rest_framework.test import APIClient
        r = APIClient().post(self.URL, self._payload(end_date=''), format='json')
        assert r.status_code == 400
        msg = r.data['end_date'][0]
        assert '结束日期' in msg
        assert '留空' in msg
        assert 'Date has wrong format' not in msg

    def test_null_end_date_saves(self):
        """不填结束日期是正常用法：传 null 必须存得进去"""
        from rest_framework.test import APIClient
        r = APIClient().post(self.URL, self._payload(), format='json')
        assert r.status_code == 201
        assert r.data['end_date'] is None
        assert r.data['duration_days'] is None

    def test_duplicate_day_says_same_day_only_once(self):
        """同一天重复记：不能说「The fields user_id, start_date must make a unique set.」"""
        from rest_framework.test import APIClient
        c = APIClient()
        assert c.post(self.URL, self._payload(), format='json').status_code == 201
        r = c.post(self.URL, self._payload(), format='json')
        assert r.status_code == 400
        msg = r.data['start_date'][0]
        assert '同一天只能记一次' in msg
        assert 'unique set' not in msg

    def test_update_own_day_is_not_blocked(self):
        """编辑自己、日期不变 —— 唯一约束不能把自己当成重复项"""
        from rest_framework.test import APIClient
        c = APIClient()
        created = c.post(self.URL, self._payload(), format='json').data
        r = c.put(f'{self.URL}{created["id"]}/', self._payload(), format='json')
        assert r.status_code == 200

    def test_update_to_other_occupied_day_blocked(self):
        """编辑时改到别人已占用的一天，仍然要拦住"""
        from rest_framework.test import APIClient
        c = APIClient()
        first = c.post(self.URL, self._payload(), format='json').data
        c.post(self.URL, self._payload(start_date='2026-10-01'), format='json')
        r = c.put(f'{self.URL}{first["id"]}/',
                  self._payload(start_date='2026-10-01'), format='json')
        assert r.status_code == 400
        assert '同一天只能记一次' in r.data['start_date'][0]
