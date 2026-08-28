"""时间追踪任务 CRUD + 时间区间筛选（CONVERT_TZ 回归）+ oneday stats 列名回归"""
import pytest
from datetime import date, datetime

from apps.temporal.models import TemporalTask, OneDayPage


@pytest.mark.django_db
class TestTemporalTaskCrud:
    def _create_task(self, start='2026-08-10 10:00:00', name='任务A'):
        return TemporalTask.objects.create(
            task_name=name, start_time=datetime.fromisoformat(start),
            duration_hours=1.5, task_type='工作', notes='备注',
        )

    def test_api_create(self):
        from rest_framework.test import APIClient
        c = APIClient()
        r = c.post('/api/temporal/tasks/', {
            'task_name': '新任务', 'start_time': '2026-08-20 09:00:00',
            'duration_hours': 2, 'task_type': '学习', 'notes': '备注内容',
        }, format='json')
        assert r.status_code == 201
        assert r.data['notes'] == '备注内容'

    def test_api_update_notes(self):
        from rest_framework.test import APIClient
        c = APIClient()
        t = self._create_task()
        r = c.patch(f'/api/temporal/tasks/{t.id}/', {'notes': '改备注'}, format='json')
        assert r.status_code == 200 and r.data['notes'] == '改备注'

    def test_api_delete(self):
        from rest_framework.test import APIClient
        c = APIClient()
        t = self._create_task()
        assert c.delete(f'/api/temporal/tasks/{t.id}/').status_code == 204
        assert TemporalTask.objects.filter(id=t.id).count() == 0

    def test_date_range_filter(self):
        from rest_framework.test import APIClient
        self._create_task('2026-08-01 09:00:00')
        self._create_task('2026-08-20 09:00:00')
        self._create_task('2026-09-01 09:00:00')
        c = APIClient()
        r = c.get('/api/temporal/tasks/?date_from=2026-08-01&date_to=2026-08-31')
        assert r.data['count'] == 2


@pytest.mark.django_db
class TestOneDayStats:
    def test_stats_no_500_and_counts(self):
        """回归：beginDate 列重命名后 stats 不再 500"""
        from rest_framework.test import APIClient
        OneDayPage.objects.create(title='第一篇', begin_date=date(2026, 8, 1), oneday=100, page=50, total=150, years='2026')
        OneDayPage.objects.create(title='第二篇', begin_date=date(2026, 8, 2), oneday=200, page=100, total=300, years='2026')
        c = APIClient()
        r = c.get('/api/temporal/oneday/stats/')
        assert r.status_code == 200
        assert r.data['total_count'] == 2
        assert r.data['total_words'] == 450
        assert len(r.data['month_stats']) >= 1


@pytest.mark.django_db
class TestOneDayFlagFilter:
    def test_flag_substring_filter(self):
        """flag 多标签（逗号分隔）子串检索：flag=待回顾 应命中 '待回顾,美食'"""
        from datetime import date
        from rest_framework.test import APIClient
        OneDayPage.objects.create(title='需要回顾', begin_date=date(2026, 8, 22), flag='待回顾,美食')
        OneDayPage.objects.create(title='普通', begin_date=date(2026, 8, 23), flag=None)
        OneDayPage.objects.create(title='其他标签', begin_date=date(2026, 8, 24), flag='思考')
        c = APIClient()
        r = c.get('/api/temporal/oneday/?flag=待回顾')
        rows = r.data.get('results') or r.data
        titles = [x['title'] for x in rows]
        assert '需要回顾' in titles, titles
        assert '普通' not in titles and '其他标签' not in titles, titles

    def test_no_flag_param_returns_all(self):
        from datetime import date
        from rest_framework.test import APIClient
        OneDayPage.objects.create(title='A', begin_date=date(2026, 8, 22), flag='待回顾')
        OneDayPage.objects.create(title='B', begin_date=date(2026, 8, 23), flag=None)
        c = APIClient()
        rows = c.get('/api/temporal/oneday/').data.get('results') or []
        # list 会经 DailyLogAutoService 自动生成今日默认日记，因此 >= 2 且含 A/B
        titles = [x['title'] for x in rows]
        assert len(rows) >= 2
        assert 'A' in titles and 'B' in titles


@pytest.mark.django_db
class TestContribEndpoints:
    def test_task_contrib(self):
        from datetime import date
        from rest_framework.test import APIClient
        TemporalTask.objects.create(task_name='T1', start_time=datetime.fromisoformat('2026-08-01 09:00:00'), duration_hours=2.5)
        TemporalTask.objects.create(task_name='T2', start_time=datetime.fromisoformat('2026-08-01 14:00:00'), duration_hours=1.5)
        TemporalTask.objects.create(task_name='T3', start_time=datetime.fromisoformat('2026-08-02 09:00:00'), duration_hours=3)
        d = APIClient().get('/api/temporal/tasks/contrib/').data
        day1 = next(x for x in d['data'] if x['date'] == '2026-08-01')
        assert day1['value'] == 4.0
        assert d['min_year'] == 2026 and d['summary']['total_days'] == 2

    def test_oneday_contrib(self):
        from datetime import date
        from rest_framework.test import APIClient
        OneDayPage.objects.create(title='D1', begin_date=date(2026, 8, 1), oneday=100, page=50)
        OneDayPage.objects.create(title='D2', begin_date=date(2026, 8, 1), oneday=200, page=0)
        d = APIClient().get('/api/temporal/oneday/contrib/').data
        day1 = next(x for x in d['data'] if x['date'] == '2026-08-01')
        assert day1['value'] == 350.0  # total = oneday + page

    def test_bill_contrib_net_value(self):
        from datetime import datetime
        from rest_framework.test import APIClient
        from apps.wealth.models import WealthBillList
        now = datetime.now()
        WealthBillList.objects.create(transaction_type='收入', date=now, amount=1000, user_id=1, created_at=now, updated_at=now)
        WealthBillList.objects.create(transaction_type='支出', date=now, amount=300, user_id=1, created_at=now, updated_at=now)
        d = APIClient().get('/api/wealth/bills/contrib/').data
        day1 = next(x for x in d['data'] if x['date'] == now.strftime('%Y-%m-%d'))
        assert day1['value'] == 700.0  # 收入-支出净值

    def test_health_contrib(self):
        from datetime import datetime
        from rest_framework.test import APIClient
        from apps.health.models import HealthRecord
        HealthRecord.objects.create(time=datetime.now(), total=8000, htype=1)
        d = APIClient().get('/api/health/records/contrib/').data
        assert d['summary']['total_days'] >= 1
