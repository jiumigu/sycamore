"""资产口径与健康指标（v3.58.19 财务规划口径纠偏）

覆盖三件事：
  ① 净资产恒等式：净资产 = 活期 + 公积金 + 应收借出 − 负债
  ② 负债率分母纠偏：分母须含应收借出，无借出时新旧口径必须相等
  ③ 应急金月数：同一笔现金在不同支出水平下必须得到不同判定

wealth_cash_flow 是 managed=False 的外部遗留表，服务层只读不写，
故口径类测试用内存对象（SimpleNamespace）直接驱动 _build_overview，
不落库、也不依赖测试库中是否已有盘点记录。
"""
from datetime import datetime
from types import SimpleNamespace

import pytest

from apps.wealth.constants import EMERGENCY_MONTHS_TARGET
from apps.wealth.models import WealthBillList
from apps.wealth.serializers.wealth_serializers import CashFlowOverviewSerializer
from apps.wealth.services.cashflow_service import (
    _build_overview,
    get_recent_monthly_expense,
    sum_liquid_accounts,
)


def _cf(**kw) -> SimpleNamespace:
    """构造内存快照对象，字段与 wealth_cash_flow 对齐"""
    base = dict(
        yearmon='2026-09', btime=None, remarks='',
        zplay=0, wechat=0, cash=0,
        jianbank=0, gongbank=0, zhongbank=0, nongbank=0,
        accumulationfund=0, lend=0, borrow=0,
        flow_total=None, total=None, realnum=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _month_key(anchor: datetime, back: int) -> tuple[int, int]:
    """自 anchor 往前推 back 个自然月的 (年, 月)"""
    year, month = anchor.year, anchor.month
    for _ in range(back):
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return year, month


class TestNetWorthIdentity:
    """净资产口径：数字保持不变，只是首次被明确命名"""

    def test_net_worth_identity(self):
        cf = _cf(zplay=1000, wechat=2000, cash=500, jianbank=30000,
                 accumulationfund=50000, lend=8000, borrow=12000)
        s = _build_overview(cf)['summary']

        assert s['flow_total'] == 33500            # 活期类账户
        assert s['financial_assets'] == 83500      # 活期 + 公积金
        assert s['total_assets'] == 91500          # + 应收借出
        assert s['net_worth'] == 79500             # − 负债
        assert s['realnum'] == s['net_worth']      # 兼容别名同值
        assert s['total'] == s['financial_assets']  # 旧字段口径不变（仅前端标签归位）

    def test_net_worth_can_be_negative(self):
        """负债大于资产时净资产为负 —— 不得被取绝对值或截断为 0"""
        cf = _cf(cash=1000, borrow=5000)
        assert _build_overview(cf)['summary']['net_worth'] == -4000

    def test_liquid_accounts_exclude_provident_fund(self):
        cf = _cf(zplay=1, wechat=2, cash=3, jianbank=4,
                 gongbank=5, zhongbank=6, nongbank=7, accumulationfund=999)
        assert sum_liquid_accounts(cf) == 28


class TestDebtRatioDenominator:
    """负债率分母须含应收借出，否则被系统性高估"""

    def test_denominator_includes_receivable(self):
        cf = _cf(jianbank=200000, lend=30000, borrow=50000)
        h = _build_overview(cf)['health_metrics']

        assert h['debt_ratio'] == round(50000 / 230000 * 100, 1)     # 21.7
        assert h['debt_ratio_legacy'] == round(50000 / 200000 * 100, 1)  # 25.0
        assert h['debt_ratio'] < h['debt_ratio_legacy']

    def test_matches_legacy_when_no_receivable(self):
        """无应收借出时两口径必须相等 —— 保证修正不改变既有账目的结论"""
        h = _build_overview(_cf(jianbank=100000, borrow=10000))['health_metrics']
        assert h['debt_ratio'] == h['debt_ratio_legacy'] == 10.0

    def test_three_ratios_share_same_denominator(self):
        cf = _cf(jianbank=50000, accumulationfund=50000, lend=10000, borrow=5000)
        h = _build_overview(cf)['health_metrics']
        total = 110000

        assert h['liquidity_ratio'] == round(50000 / total * 100, 1)
        assert h['provident_fund_ratio'] == round(50000 / total * 100, 1)
        assert h['debt_ratio'] == round(5000 / total * 100, 1)

    def test_zero_assets_does_not_divide_by_zero(self):
        h = _build_overview(_cf())['health_metrics']
        assert h['debt_ratio'] == 0
        assert h['liquidity_ratio'] == 0


class TestEmergencyFundMonths:
    """应急金从绝对金额改为月数口径"""

    def test_months_and_target_gap(self):
        cf = _cf(zplay=10000, wechat=5000, cash=1000, jianbank=14000)
        h = _build_overview(cf, monthly_expense_avg=5000)['health_metrics']

        assert h['emergency_fund'] == 30000          # 含银行卡活期（原实现只算 16000）
        assert h['emergency_fund_months'] == 6.0
        assert h['emergency_months_target'] == EMERGENCY_MONTHS_TARGET
        assert h['emergency_target_amount'] == 30000
        assert h['emergency_gap'] == 0

    def test_same_cash_different_expense_level_differs(self):
        """同一笔 15000 现金：月支出 5000 属尚可，月支出 30000 属高危。

        原实现用绝对阈值 5000/10000 判定，两种情况都会显示为「好」。
        """
        cf = _cf(cash=15000)
        low = _build_overview(cf, monthly_expense_avg=5000)['health_metrics']
        high = _build_overview(cf, monthly_expense_avg=30000)['health_metrics']

        assert low['emergency_fund_months'] == 3.0
        assert high['emergency_fund_months'] == 0.5
        assert low['emergency_gap'] == 15000
        assert high['emergency_gap'] == 165000

    def test_no_expense_data_yields_null(self):
        """月均支出不可得时，派生指标置 null，不得退化成 0 或无穷大"""
        h = _build_overview(_cf(cash=1000))['health_metrics']

        assert h['emergency_fund'] == 1000
        assert h['emergency_fund_months'] is None
        assert h['emergency_gap'] is None
        assert h['emergency_target_amount'] is None


class TestSerializerFieldAlignment:
    """服务层字段与序列化器必须逐一对齐，防止改名后静默丢字段"""

    def test_overview_serializes_new_fields(self):
        data = _build_overview(_cf(jianbank=1000, lend=100, borrow=50),
                               monthly_expense_avg=100)
        out = CashFlowOverviewSerializer(data).data

        assert out['summary']['net_worth'] == 1050.0
        assert out['summary']['total_assets'] == 1100.0
        assert out['health_metrics']['emergency_fund_months'] == 10.0
        assert out['health_metrics']['debt_ratio_legacy'] == round(50 / 1000 * 100, 1)


@pytest.mark.django_db
class TestRecentMonthlyExpense:
    """月均支出取数：除以「有记录的月份数」，而非固定回看月数"""

    TEST_USER = 9999

    def _bill(self, year: int, month: int, amount: float) -> WealthBillList:
        now = datetime.now()
        return WealthBillList.objects.create(
            transaction_type='支出', date=datetime(year, month, 10, 10, 0),
            amount=amount, category='餐饮', merchant='口径测试', user_id=self.TEST_USER,
            year=year, month=month, day=10, created_at=now, updated_at=now,
        )

    def test_averages_only_months_with_records(self):
        """当月 1200、两月前 800、一月前无记录 → 均值取 1000，而非 2000/3"""
        anchor = datetime.now()
        y0, m0 = _month_key(anchor, 0)
        y2, m2 = _month_key(anchor, 2)
        self._bill(y0, m0, 1200)
        self._bill(y2, m2, 800)

        assert get_recent_monthly_expense(self.TEST_USER, months=3) == 1000.0

    def test_income_records_are_excluded(self):
        anchor = datetime.now()
        y0, m0 = _month_key(anchor, 0)
        now = datetime.now()
        WealthBillList.objects.create(
            transaction_type='收入', date=datetime(y0, m0, 5, 10, 0),
            amount=99999, category='工资', user_id=self.TEST_USER,
            year=y0, month=m0, day=5, created_at=now, updated_at=now,
        )
        self._bill(y0, m0, 600)

        assert get_recent_monthly_expense(self.TEST_USER, months=3) == 600.0
