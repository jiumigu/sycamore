"""赎回归属标记（period_tag）测试：筛选 / 批量（收入支出都生效）/ 收入不清空"""
import pytest
from datetime import datetime

from apps.wealth.models import WealthBillList


@pytest.mark.django_db
class TestPeriodTag:
    def _mk(self, ttype='支出', amount=100, period_tag=None, **kw):
        now = datetime.now()
        return WealthBillList.objects.create(
            transaction_type=ttype, date=datetime.fromisoformat('2026-10-15 10:00:00'),
            amount=amount, category='餐饮', merchant='店', notes='', user_id=1,
            created_at=now, updated_at=now, period_tag=period_tag, **kw,
        )

    def test_filter_and_unmarked(self):
        from rest_framework.test import APIClient
        c = APIClient()
        self._mk(period_tag='为自己')
        self._mk(period_tag='外部')
        b = self._mk()  # 未标记（None）
        b.period_tag = None
        b.save()

        r = c.get('/api/wealth/bills/?period_tag=为自己')
        assert r.status_code == 200
        assert r.data['count'] == 1

        r = c.get('/api/wealth/bills/?period_tag=unmarked')
        assert r.data['count'] == 1

    def test_batch_period_tag_both_sides(self):
        """批量标记时期收入与支出都生效（区别于 necessity 仅支出）"""
        from rest_framework.test import APIClient
        c = APIClient()
        exp = self._mk('支出', 100)
        inc = self._mk('收入', 5000)

        r = c.post('/api/wealth/bills/batch-period-tag/', {
            'ids': [exp.id, inc.id], 'period_tag': '为自己',
        }, format='json')
        assert r.status_code == 200
        assert r.data['updated'] == 2
        exp.refresh_from_db()
        inc.refresh_from_db()
        assert exp.period_tag == '为自己'
        assert inc.period_tag == '为自己'  # 收入也被标记

    def test_income_tag_not_cleared(self):
        """收入行 period_tag 保留（必要性对照用例会清空 income 的 necessity）"""
        from rest_framework.test import APIClient
        c = APIClient()
        inc = self._mk('收入', 8000, period_tag='为自己')
        r = c.patch(f'/api/wealth/bills/{inc.id}/', {'notes': '稿费'}, format='json')
        assert r.status_code == 200
        inc.refresh_from_db()
        assert inc.period_tag == '为自己'  # 未因更新被清空

    def test_period_tag_stats_both_sides(self):
        from rest_framework.test import APIClient
        c = APIClient()
        self._mk('支出', 100, period_tag='为自己')
        self._mk('收入', 5000, period_tag='为自己')
        self._mk('支出', 50, period_tag='过渡')
        r = c.get('/api/wealth/bills/period_tag_stats/')
        assert r.status_code == 200
        by_tag = {s['period_tag']: s for s in r.data['summary']}
        assert by_tag['为自己']['count'] == 2  # 含收入
        assert by_tag['为自己']['total'] == 5100.0
        assert by_tag['过渡']['count'] == 1
