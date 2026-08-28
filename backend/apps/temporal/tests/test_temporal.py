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
