"""账单清单「筛选结果总计」（v3.60.19）

核心判据：**总计与列表同源** —— 复用同一套 queryset（含 SearchFilter 的 search），
跨页全量聚合；不是「当前页 20 行的小计」。
"""
import pytest
from datetime import datetime

from apps.wealth.models import WealthBillList


@pytest.mark.django_db
class TestBillTotals:
    def _create_bill(self, dt='2026-08-10 10:00:00', transaction_type='支出', amount=100, **kw):
        now = datetime.now()
        return WealthBillList.objects.create(
            transaction_type=transaction_type, date=datetime.fromisoformat(dt), amount=amount,
            category='餐饮', merchant='测试店', notes='', user_id=1,
            created_at=now, updated_at=now, **kw,
        )

    # ─── 路由：静态路径不得被 `<pk>` 抢 ───

    def test_route_not_swallowed_by_pk(self):
        """`bills/totals/` 必须落在 totals action 上。

        若被 `bills/<pk>/` 抢先接走，`pk='totals'` 查不到 → 404，
        在界面上看着像「接口没注册」，而不会报出真正的原因。
        """
        from rest_framework.test import APIClient
        r = APIClient().get('/api/wealth/bills/totals/')
        assert r.status_code == 200
        assert set(r.data.keys()) == {'count', 'income', 'expense', 'net'}

    # ─── 口径正确性 ───

    def test_income_expense_net(self):
        from rest_framework.test import APIClient
        self._create_bill('2026-08-01 09:00:00', amount=30)
        self._create_bill('2026-08-02 09:00:00', amount=70)
        self._create_bill('2026-08-03 09:00:00', transaction_type='收入', amount=500)
        r = APIClient().get('/api/wealth/bills/totals/')
        assert r.data['count'] == 3
        assert r.data['expense'] == 100.0
        assert r.data['income'] == 500.0
        assert r.data['net'] == 400.0

    def test_ignores_pagination(self):
        """跨页全量：造 25 条、page_size=20。

        列表只回 20 行（但 count=25），总计必须是 **25 条的全量** ——
        这是本需求与「当前页小计」的分水岭。
        """
        from rest_framework.test import APIClient
        for i in range(25):
            self._create_bill(f'2026-08-{i + 1:02d} 09:00:00', amount=10)
        c = APIClient()
        lst = c.get('/api/wealth/bills/?page=1&page_size=20')
        assert len(lst.data['results']) == 20
        assert lst.data['count'] == 25
        tot = c.get('/api/wealth/bills/totals/')
        assert tot.data['count'] == 25
        assert tot.data['expense'] == 250.0  # 25 × 10，不是当前页的 200

    # ─── 同源判据：各筛选维度都要进汇总 ───

    def test_respects_search(self):
        """search 参与汇总 —— 最容易漏的一项。

        search 不是 `get_queryset()` 里的条件，而是 `SearchFilter` 在 queryset
        之后加的；若这里忘了 `filter_queryset()`，搜出来的条数会与总计对不上。
        """
        from rest_framework.test import APIClient
        self._create_bill('2026-08-01 09:00:00', amount=30, subcategory='早午晚餐')
        self._create_bill('2026-08-02 09:00:00', amount=70, subcategory='日常用品')
        r = APIClient().get('/api/wealth/bills/totals/?search=日常用品')
        assert r.data['count'] == 1
        assert r.data['expense'] == 70.0

    def test_respects_type_necessity_and_date(self):
        from rest_framework.test import APIClient
        self._create_bill('2026-08-01 09:00:00', amount=30, necessity='必要')
        self._create_bill('2026-08-02 09:00:00', amount=70, necessity='冲动')
        self._create_bill('2026-09-01 09:00:00', amount=999, necessity='必要')  # 落在范围外
        c = APIClient()
        r = c.get(
            '/api/wealth/bills/totals/'
            '?necessity=必要&date_from=2026-08-01&date_to=2026-08-31'
        )
        assert r.data['count'] == 1 and r.data['expense'] == 30.0
        # 类型筛选：无收入时应为 0，而不是把支出算进收入
        r2 = c.get('/api/wealth/bills/totals/?transaction_type=收入')
        assert r2.data['count'] == 0 and r2.data['income'] == 0.0

    def test_unmarked_necessity_bucket(self):
        """`necessity=unmarked`（NULL 或空串）也要能进汇总 —— 与列表同一套语义"""
        from rest_framework.test import APIClient
        self._create_bill('2026-08-01 09:00:00', amount=30)
        self._create_bill('2026-08-02 09:00:00', amount=70, necessity='必要')
        r = APIClient().get('/api/wealth/bills/totals/?necessity=unmarked')
        assert r.data['count'] == 1 and r.data['expense'] == 30.0

    def test_count_matches_list_count(self):
        """断言同源：同一组筛选参数下，totals.count == 列表的 count"""
        from rest_framework.test import APIClient
        self._create_bill('2026-08-01 09:00:00', amount=30, necessity='必要')
        self._create_bill('2026-08-02 09:00:00', amount=70)
        self._create_bill('2026-09-01 09:00:00', amount=10, necessity='必要')
        c = APIClient()
        q = '?necessity=必要&date_from=2026-08-01&date_to=2026-08-31'
        assert (
            c.get('/api/wealth/bills/totals/' + q).data['count']
            == c.get('/api/wealth/bills/' + q).data['count']
        )

    # ─── 空结果：0 而非 null ───

    def test_empty_returns_zeros_not_null(self):
        """空结果必须给 0。

        `Sum` 在空集上返回 None，若直接透传，前端 `Number(null) === 0` 会渲染成
        「0.00」——看起来像「合计真的是 0」，与「这个筛选下一条都没有」不分。
        """
        from rest_framework.test import APIClient
        r = APIClient().get('/api/wealth/bills/totals/?search=不存在关键词zzz')
        assert r.data == {'count': 0, 'income': 0.0, 'expense': 0.0, 'net': 0.0}
