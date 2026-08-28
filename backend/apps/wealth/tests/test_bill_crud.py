"""账单清单 CRUD：创建自动填充 / 编辑备注 / 删除 / 时间区间筛选（CONVERT_TZ 回归）"""
import pytest
from datetime import datetime

from apps.wealth.models import WealthBillList


@pytest.mark.django_db
class TestBillCrud:
    def _create_bill(self, dt='2026-08-10 10:00:00', transaction_type='支出', amount=100, **kw):
        now = datetime.now()
        return WealthBillList.objects.create(
            transaction_type=transaction_type, date=datetime.fromisoformat(dt), amount=amount,
            category='餐饮', merchant='测试店', notes='', user_id=1,
            created_at=now, updated_at=now, **kw,
        )

    def test_api_create_fills_derived(self):
        from rest_framework.test import APIClient
        c = APIClient()
        r = c.post('/api/wealth/bills/', {
            'transaction_type': '支出', 'date': '2026-08-27 10:00:00', 'amount': 99.5,
            'category': '餐饮', 'merchant': '店', 'notes': '备注测试',
        }, format='json')
        assert r.status_code == 201
        assert r.data['notes'] == '备注测试'
        b = WealthBillList.objects.get(id=r.data['id'])
        assert b.year == 2026 and b.month == 8 and b.day == 27
        assert b.created_at is not None

    def test_api_update_notes(self):
        from rest_framework.test import APIClient
        c = APIClient()
        b = self._create_bill()
        r = c.patch(f'/api/wealth/bills/{b.id}/', {'notes': '更新备注'}, format='json')
        assert r.status_code == 200
        assert r.data['notes'] == '更新备注'

    def test_api_delete(self):
        from rest_framework.test import APIClient
        c = APIClient()
        b = self._create_bill()
        assert c.delete(f'/api/wealth/bills/{b.id}/').status_code == 204
        assert WealthBillList.objects.filter(id=b.id).count() == 0

    def test_date_range_filter(self):
        from rest_framework.test import APIClient
        self._create_bill('2026-08-01 09:00:00')
        self._create_bill('2026-08-15 09:00:00')
        self._create_bill('2026-09-01 09:00:00')
        c = APIClient()
        r = c.get('/api/wealth/bills/?date_from=2026-08-01&date_to=2026-08-31')
        assert r.data['count'] == 2
        # 单日边界
        r2 = c.get('/api/wealth/bills/?date_from=2026-08-15&date_to=2026-08-15')
        assert r2.data['count'] == 1

    def test_transaction_type_filter(self):
        from rest_framework.test import APIClient
        self._create_bill('2026-08-10 09:00:00', transaction_type='收入', amount=500)
        self._create_bill('2026-08-11 09:00:00')
        c = APIClient()
        r = c.get('/api/wealth/bills/?transaction_type=收入')
        rows = r.data['results'] or []
        assert len(rows) == 1 and rows[0]['transaction_type'] == '收入'
