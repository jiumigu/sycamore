"""负债明细 / 应收账龄（v3.58.20，P1-A）

覆盖：
  ① 负债派生口径：已还本金、年利息成本、加权平均利率（权重是余额，不是笔数）
  ② 还款优先级：雪崩法（利率降序）/ 雪球法（余额升序）；已结清不参与编号
  ③ 应收账龄分桶边界（30/31/90/91/180/181/365/366）与「借出日为空不归桶」
  ④ 逾期判定：仅「在借」且约定期已过才计逾期
  ⑤ 汇总的零除保护，账龄份额合计恒为 100%
  ⑥ 与快照 borrow / lend 的对账差
  ⑦ 写接口校验：负金额 400、到期日早于起借日 400
  ⑧ 列表返回**裸数组** —— 防被全局分页包成 {count, results} 后前端静默显示为空

两张新表由 conftest 的 session 级 django_db_setup 镜像建表
（--no-migrations --reuse-db 下新表不会自动出现）。
对账用例写真实快照行：btime 取 2099 年末，保证它恒为「最新快照」，
不受测试库里既有行影响。
"""
from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient

from apps.wealth.constants import AGING_UNKNOWN_BUCKET
from apps.wealth.models import WealthCashFlow, WealthLiabilityDetail, WealthReceivableDetail
from apps.wealth.services.debt_service import (
    aging_bucket,
    get_liability_list, get_liability_summary,
    get_receivable_list, get_receivable_summary,
)

LIAB_URL = '/api/wealth/debt/liabilities/'
RECV_URL = '/api/wealth/debt/receivables/'
FUTURE_BTIME = date(2099, 12, 31)


def _liab(**kw) -> WealthLiabilityDetail:
    base = dict(
        name='测试负债', category='信用卡', principal=10000, outstanding=10000,
        annual_rate=7.2, monthly_payment=1000, status='在还', user_id=1,
    )
    base.update(kw)
    return WealthLiabilityDetail.objects.create(**base)


def _recv(**kw) -> WealthReceivableDetail:
    base = dict(
        counterparty='测试对象', principal=10000, received=0,
        status='在借', annual_rate=0, user_id=1,
    )
    base.update(kw)
    return WealthReceivableDetail.objects.create(**base)


def _snapshot(borrow=0, lend=0) -> WealthCashFlow:
    return WealthCashFlow.objects.create(
        yearmon='2099-12', btime=FUTURE_BTIME, borrow=borrow, lend=lend,
        zplay=0, wechat=0, cash=0, jianbank=0, gongbank=0,
        zhongbank=0, nongbank=0, accumulationfund=0,
    )


# ══════════════════════════════════════════════════════════════
# 账龄分桶
# ══════════════════════════════════════════════════════════════


class TestAgingBucket:
    """边界是闭区间：30 天算「30天内」，31 天才进下一桶"""

    @pytest.mark.parametrize('days,expected', [
        (0, '30天内'),
        (30, '30天内'),
        (31, '31-90天'),
        (90, '31-90天'),
        (91, '91-180天'),
        (180, '91-180天'),
        (181, '181-365天'),
        (365, '181-365天'),
        (366, '365天以上'),
        (3000, '365天以上'),
    ])
    def test_bucket_boundaries(self, days, expected):
        assert aging_bucket(days) == expected

    def test_missing_lend_date_is_not_zero_days(self):
        """借出日为空不得落进 0 天桶 —— 那是把「没数据」当成「刚借出」"""
        assert aging_bucket(None) == AGING_UNKNOWN_BUCKET
        assert aging_bucket(None) != aging_bucket(0)

    def test_future_lend_date_is_not_bucketed(self):
        """借出日晚于今天属录入错误，同样不归桶"""
        assert aging_bucket(-1) == AGING_UNKNOWN_BUCKET
        assert aging_bucket(-999) == AGING_UNKNOWN_BUCKET


# ══════════════════════════════════════════════════════════════
# 负债口径
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestLiabilityMetrics:
    def test_weighted_avg_rate_weights_by_balance(self):
        """加权平均利率按余额加权：小额高息债不得拉高整体成本

        9000 × 18% + 1000 × 0% = 1620 ÷ 10000 = 16.2%
        若误按笔数取算术平均会得到 9.0% —— 两者相差近一倍。
        """
        _liab(name='大额低息', principal=9000, outstanding=9000, annual_rate=18)
        _liab(name='小额免息', principal=1000, outstanding=1000, annual_rate=0)

        s = get_liability_summary()
        assert s['total_outstanding'] == 10000
        assert s['weighted_avg_rate'] == pytest.approx(16.2, abs=0.05)
        assert s['weighted_avg_rate'] != pytest.approx(9.0, abs=0.5)

    def test_interest_cost_and_repaid_amount(self):
        _liab(principal=10000, outstanding=4000, annual_rate=6, monthly_payment=500)
        item = get_liability_list()[0]

        assert item['repaid_amount'] == 6000
        assert item['repaid_ratio'] == 60.0
        assert item['annual_interest_cost'] == pytest.approx(240.0)  # 4000 × 6%
        assert item['remaining_months'] == 8  # ceil(4000 ÷ 500)

    def test_zero_monthly_payment_has_no_term_estimate(self):
        """月供为 0 时剩余期数无依据 —— 返回 None，不得臆造"""
        _liab(monthly_payment=0, outstanding=5000)
        assert get_liability_list()[0]['remaining_months'] is None

    def test_avalanche_and_snowball_give_different_first_pick(self):
        """先还哪一笔：利率最高的 ≠ 余额最小的

        大额高息信用卡（20000 @ 18.25%）vs 小额低息亲友借款（3000 @ 4%）。
        雪崩法先打信用卡（省息最优），雪球法先打亲友借款（先清掉一笔有心理收益）。
        """
        _liab(name='信用卡', principal=20000, outstanding=20000, annual_rate=18.25)
        _liab(name='亲友借款', principal=3000, outstanding=3000, annual_rate=4.0)

        items = {i['name']: i for i in get_liability_list()}
        assert items['信用卡']['priority_by_rate'] == 1        # 雪崩法先打它
        assert items['亲友借款']['priority_by_balance'] == 1   # 雪球法先打它
        assert items['亲友借款']['priority_by_rate'] == 2
        assert items['信用卡']['priority_by_balance'] == 2

        s = get_liability_summary()
        assert s['prepay_focus'] == {'by_rate': '信用卡', 'by_balance': '亲友借款'}
        assert s['highest_rate_item']['name'] == '信用卡'

    def test_settled_excluded_from_totals_and_priority(self):
        _liab(name='在还中', outstanding=2000, annual_rate=5, monthly_payment=200)
        _liab(name='已结清', outstanding=8000, annual_rate=24, status='已结清', monthly_payment=0)

        items = {i['name']: i for i in get_liability_list()}
        assert items['已结清']['priority_by_rate'] is None
        assert items['已结清']['priority_by_balance'] is None

        s = get_liability_summary()
        assert s['count'] == 2
        assert s['active_count'] == 1
        assert s['settled_count'] == 1
        assert s['total_outstanding'] == 2000          # 已结清不计入余额
        assert s['total_monthly_payment'] == 200
        assert s['weighted_avg_rate'] == 5.0

    def test_category_distribution_shares_sum_to_100(self):
        _liab(name='信用卡A', category='信用卡', outstanding=7500, annual_rate=18)
        _liab(name='房贷A', category='房贷', outstanding=2500, annual_rate=3.5)

        s = get_liability_summary()
        assert [b['category'] for b in s['by_category']] == ['信用卡', '房贷']  # 按金额降序
        assert s['by_category'][0]['share'] == 75.0
        assert s['by_category'][1]['share'] == 25.0

    def test_empty_ledger_has_no_division_error(self):
        s = get_liability_summary()
        assert s['count'] == 0
        assert s['total_outstanding'] == 0
        assert s['weighted_avg_rate'] == 0.0
        assert s['highest_rate_item'] is None
        assert s['by_category'] == []
        assert s['prepay_focus'] == {'by_rate': None, 'by_balance': None}
        assert s['borrow_diff'] is None  # 无快照时不给差额（0 会被误读成「已对平」）


# ══════════════════════════════════════════════════════════════
# 应收口径
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestReceivableMetrics:
    def test_outstanding_never_negative(self):
        """已收回多于本金（含息或录错）时未收余额按 0 截断"""
        _recv(principal=1000, received=1500)
        item = get_receivable_list()[0]
        assert item['outstanding'] == 0
        assert item['recovery_ratio'] == 150.0

    def test_aging_days_and_bucket_from_lend_date(self):
        today = date.today()
        _recv(lend_date=today - timedelta(days=100), received=4000, principal=10000)
        item = get_receivable_list()[0]
        assert item['aging_days'] == 100
        assert item['aging_bucket'] == '91-180天'
        assert item['outstanding'] == 6000

    def test_overdue_only_for_active(self):
        """已收回的笔即便约定期已过也不算逾期"""
        today = date.today()
        _recv(counterparty='在借逾期', lend_date=today - timedelta(days=60),
              due_date=today - timedelta(days=10), status='在借', principal=5000)
        _recv(counterparty='已收回', lend_date=today - timedelta(days=60),
              due_date=today - timedelta(days=10), status='已收回', principal=5000, received=5000)
        _recv(counterparty='无约定期', lend_date=today - timedelta(days=60),
              due_date=None, status='在借', principal=5000)

        items = {i['counterparty']: i for i in get_receivable_list()}
        assert items['在借逾期']['is_overdue'] is True
        assert items['在借逾期']['overdue_days'] == 10
        assert items['已收回']['is_overdue'] is False
        assert items['无约定期']['is_overdue'] is False   # 无约定期不做逾期判定

        s = get_receivable_summary()
        assert s['overdue_count'] == 1
        assert s['overdue_amount'] == 5000
        assert s['max_overdue_days'] == 10

    def test_long_aging_flag(self):
        today = date.today()
        _recv(counterparty='长期挂账', lend_date=today - timedelta(days=400), principal=3000)
        _recv(counterparty='近期', lend_date=today - timedelta(days=20), principal=3000)

        items = {i['counterparty']: i for i in get_receivable_list()}
        assert items['长期挂账']['is_long_aging'] is True
        assert items['长期挂账']['aging_bucket'] == '365天以上'
        assert items['近期']['is_long_aging'] is False
        assert get_receivable_summary()['long_aging_count'] == 1

    def test_aging_distribution_shape_and_shares(self):
        today = date.today()
        _recv(counterparty='A', lend_date=today - timedelta(days=10), principal=1000)
        _recv(counterparty='B', lend_date=today - timedelta(days=200), principal=3000)
        _recv(counterparty='C', lend_date=None, principal=6000)  # 未填借出日

        s = get_receivable_summary()
        aging = {b['bucket']: b for b in s['aging']}
        # 形状固定：5 段 + 未知，前端可无条件渲染
        assert list(aging) == ['30天内', '31-90天', '91-180天', '181-365天', '365天以上', AGING_UNKNOWN_BUCKET]
        assert aging['30天内']['amount'] == 1000
        assert aging['181-365天']['amount'] == 3000
        assert aging[AGING_UNKNOWN_BUCKET]['amount'] == 6000
        assert sum(b['share'] for b in s['aging']) == pytest.approx(100.0, abs=0.5)
        assert aging[AGING_UNKNOWN_BUCKET]['share'] == 60.0

    def test_interest_free_ratio_and_income(self):
        _recv(counterparty='无息', principal=6000, annual_rate=0)
        _recv(counterparty='有息', principal=4000, annual_rate=6)

        s = get_receivable_summary()
        assert s['active_outstanding'] == 10000
        assert s['interest_free_amount'] == 6000
        assert s['interest_free_ratio'] == 60.0
        assert s['interest_income_annual'] == pytest.approx(240.0)  # 4000 × 6%

    def test_bad_debt_counted_but_listed_separately(self):
        _recv(counterparty='呆账', principal=2000, status='呆账')
        _recv(counterparty='在借', principal=1000, status='在借')

        s = get_receivable_summary()
        assert s['bad_debt_count'] == 1
        assert s['bad_debt_amount'] == 2000
        assert s['active_outstanding'] == 1000
        assert s['total_outstanding'] == 3000   # 呆账也是没收回来
        assert s['active_count'] == 1

    def test_empty_ledger_has_no_division_error(self):
        s = get_receivable_summary()
        assert s['count'] == 0
        assert s['recovery_ratio'] == 0.0
        assert s['interest_free_ratio'] == 0.0
        assert len(s['aging']) == 6
        assert all(b['share'] == 0.0 for b in s['aging'])
        assert s['lend_diff'] is None


# ══════════════════════════════════════════════════════════════
# 与快照对账
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestSnapshotReconcile:
    def test_borrow_diff_is_ledger_minus_snapshot(self):
        _liab(name='A', outstanding=3000)
        _liab(name='B', outstanding=1000)
        _snapshot(borrow=5000, lend=0)

        s = get_liability_summary()
        assert s['snapshot_borrow'] == 5000
        assert s['borrow_diff'] == -1000   # 台账比快照少 1000

    def test_lend_diff_is_ledger_minus_snapshot(self):
        _recv(counterparty='A', principal=2000, received=500)
        _snapshot(borrow=0, lend=8000)

        s = get_receivable_summary()
        assert s['snapshot_lend'] == 8000
        assert s['lend_diff'] == -6500     # 台账未收 1500，比快照少 6500

    def test_diff_none_when_no_snapshot(self):
        """无快照时差额为 None —— 0 会被误读成「已对平」"""
        _liab()
        assert get_liability_summary()['borrow_diff'] is None


# ══════════════════════════════════════════════════════════════
# 接口层
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestDebtApi:
    def test_lists_return_bare_arrays(self):
        """硬坑③：列表必须是数组，被包成 {count, results} 前端会静默显示为空"""
        _liab()
        _recv()
        for url in (LIAB_URL, RECV_URL):
            r = APIClient().get(url)
            assert r.status_code == 200
            assert isinstance(r.data, list), f'{url} 返回的不是裸数组'
            assert len(r.data) == 1

    def test_create_liability_returns_derived_fields(self):
        r = APIClient().post(LIAB_URL, {
            'name': '招行信用卡', 'category': '信用卡', 'principal': 20000,
            'outstanding': 8000, 'annual_rate': 18.25, 'monthly_payment': 1000,
            'start_date': '2026-01-10', 'due_date': '2027-01-10',
        }, format='json')
        assert r.status_code == 201
        assert r.data['annual_interest_cost'] == pytest.approx(1460.0)
        assert r.data['repaid_amount'] == 12000
        assert r.data['status'] == '在还'          # 默认值由模型给
        assert r.data['priority_by_rate'] == 1

    def test_create_rejects_negative_amount(self):
        r = APIClient().post(LIAB_URL, {'name': '负数', 'outstanding': -1}, format='json')
        assert r.status_code == 400
        assert 'outstanding' in r.data

    def test_create_rejects_rate_above_100(self):
        r = APIClient().post(RECV_URL, {'counterparty': '年化超标', 'annual_rate': 120}, format='json')
        assert r.status_code == 400
        assert 'annual_rate' in r.data

    def test_create_rejects_due_before_start(self):
        r = APIClient().post(LIAB_URL, {
            'name': '日期倒挂', 'start_date': '2026-06-01', 'due_date': '2026-01-01',
        }, format='json')
        assert r.status_code == 400
        assert 'due_date' in r.data

    def test_create_rejects_blank_name(self):
        r = APIClient().post(LIAB_URL, {'name': '', 'outstanding': 100}, format='json')
        assert r.status_code == 400
        assert 'name' in r.data

    def test_patch_updates_outstanding_and_priority(self):
        _liab(name='低息', outstanding=9000, annual_rate=3)
        b = _liab(name='高息', outstanding=1000, annual_rate=20)
        c = APIClient()

        # 高息那笔还清后：优先级交给低息那笔，且不再计入余额
        r = c.patch(f'{LIAB_URL}{b.id}/', {'status': '已结清', 'outstanding': 0}, format='json')
        assert r.status_code == 200
        assert r.data['priority_by_rate'] is None

        items = {i['name']: i for i in c.get(LIAB_URL).data}
        assert items['低息']['priority_by_rate'] == 1
        assert c.get(f'{LIAB_URL}summary/').data['total_outstanding'] == 9000

    def test_summary_endpoints(self):
        _liab(outstanding=4000, annual_rate=6, monthly_payment=500)
        _recv(principal=3000, received=1000)

        ls = APIClient().get(f'{LIAB_URL}summary/')
        assert ls.status_code == 200
        assert ls.data['total_outstanding'] == 4000
        assert ls.data['weighted_avg_rate'] == 6.0

        rs = APIClient().get(f'{RECV_URL}summary/')
        assert rs.status_code == 200
        assert rs.data['total_outstanding'] == 2000
        assert len(rs.data['aging']) == 6

    def test_list_filters(self):
        _liab(name='信用卡A', category='信用卡')
        _liab(name='房贷A', category='房贷')
        c = APIClient()
        assert len(c.get(f'{LIAB_URL}?category=房贷').data) == 1
        assert len(c.get(f'{LIAB_URL}?status=已结清').data) == 0

    def test_delete_removes_row(self):
        obj = _liab()
        r = APIClient().delete(f'{LIAB_URL}{obj.id}/')
        assert r.status_code == 200
        assert r.data['deleted'] == obj.id
        assert not WealthLiabilityDetail.objects.filter(id=obj.id).exists()

    def test_other_user_rows_are_isolated(self):
        _liab(name='他人负债', user_id=2)
        _recv(counterparty='他人借出', user_id=2)
        assert APIClient().get(LIAB_URL).data == []
        assert APIClient().get(RECV_URL).data == []
