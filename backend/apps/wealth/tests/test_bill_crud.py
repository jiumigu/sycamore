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

    # ─── 必要性标签 ───

    def test_necessity_filter_and_unmarked(self):
        from rest_framework.test import APIClient
        self._create_bill('2026-08-01 09:00:00', amount=30, necessity='必要')
        self._create_bill('2026-08-02 09:00:00', amount=50, necessity='冲动')
        self._create_bill('2026-08-03 09:00:00', amount=20)  # 未标记
        c = APIClient()
        r = c.get('/api/wealth/bills/?necessity=冲动')
        assert r.data['count'] == 1 and r.data['results'][0]['necessity'] == '冲动'
        r2 = c.get('/api/wealth/bills/?necessity=unmarked')
        assert r2.data['count'] == 1

    def test_batch_necessity_only_expense(self):
        from rest_framework.test import APIClient
        e1 = self._create_bill('2026-08-01 09:00:00', amount=30)
        e2 = self._create_bill('2026-08-02 09:00:00', amount=50)
        inc = self._create_bill('2026-08-03 09:00:00', transaction_type='收入', amount=500)
        c = APIClient()
        r = c.post('/api/wealth/bills/batch-necessity/', {
            'ids': [e1.id, e2.id, inc.id], 'necessity': '必要',
        }, format='json')
        assert r.status_code == 200 and r.data['updated'] == 2
        e1.refresh_from_db(); e2.refresh_from_db(); inc.refresh_from_db()
        assert e1.necessity == '必要' and e2.necessity == '必要'
        assert inc.necessity is None  # 收入不受批量标记影响

    def test_necessity_stats(self):
        from rest_framework.test import APIClient
        self._create_bill('2026-08-01 09:00:00', amount=30, necessity='必要')
        self._create_bill('2026-08-02 09:00:00', amount=70, necessity='必要')
        self._create_bill('2026-08-03 09:00:00', amount=50, necessity='冲动')
        self._create_bill('2026-08-04 09:00:00', amount=20)  # 未标记
        self._create_bill('2026-08-05 09:00:00', transaction_type='收入', amount=500)
        c = APIClient()
        r = c.get('/api/wealth/bills/necessity_stats/?date_from=2026-08-01&date_to=2026-08-31')
        assert r.status_code == 200
        m = {x['necessity']: x for x in r.data['summary']}
        assert m['必要']['count'] == 2 and m['必要']['total'] == 100.0
        assert m['冲动']['count'] == 1
        assert m['unmarked']['count'] == 1
        assert r.data['grand_count'] == 4  # 收入不计入

    def test_income_necessity_force_blank(self):
        from rest_framework.test import APIClient
        c = APIClient()
        r = c.post('/api/wealth/bills/', {
            'transaction_type': '收入', 'date': '2026-08-10 10:00:00', 'amount': 500,
            'category': '工资', 'necessity': '必要',
        }, format='json')
        assert r.status_code == 201
        assert r.data['necessity'] in (None, '')

    # ─── 子分类：列表可读 + 可搜（v3.60.4） ───

    def test_list_exposes_subcategory(self):
        """列表返回体带 subcategory —— 表格新增「子分类」列的数据前提"""
        from rest_framework.test import APIClient
        self._create_bill('2026-08-01 09:00:00', subcategory='早午晚餐')
        c = APIClient()
        r = c.get('/api/wealth/bills/?date_from=2026-08-01&date_to=2026-08-31')
        assert r.data['results'][0]['subcategory'] == '早午晚餐'

    def test_search_hits_subcategory(self):
        """子分类可被搜索命中：该值只在 subcategory 上，漏搜就是「搜不到却不知道为什么」"""
        from rest_framework.test import APIClient
        self._create_bill('2026-08-01 09:00:00', subcategory='早午晚餐')
        self._create_bill('2026-08-02 09:00:00', subcategory='日常用品')
        c = APIClient()
        r = c.get('/api/wealth/bills/?search=日常用品')
        assert r.data['count'] == 1
        assert r.data['results'][0]['subcategory'] == '日常用品'

    def test_search_subcategory_does_not_leak_siblings(self):
        """同分类下两个子分类：搜其一不得连带命中另一个（证明按 subcategory 匹配）"""
        from rest_framework.test import APIClient
        self._create_bill('2026-08-01 09:00:00', subcategory='早午晚餐')
        self._create_bill('2026-08-02 09:00:00', subcategory='水果-牛奶')
        c = APIClient()
        r = c.get('/api/wealth/bills/?search=水果-牛奶')
        assert r.data['count'] == 1
        assert r.data['results'][0]['subcategory'] == '水果-牛奶'
