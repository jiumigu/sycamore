"""summary 维度换算的两条契约（§120）

1. 展示量级只由后端 `display_scale` 决定 —— 前端不再自己判「>=10000 就加万」
2. 净收入为负（亏损）不得被抹成 0；「取不到(None) / 0 / 负数」三件事必须分开
"""
import pytest

from apps.summary.constants import ZERO_REASON_NET_NEGATIVE, ZERO_REASON_NO_DATA
from apps.summary.services.progress_aggregator import ProgressAggregator
from apps.summary.services.quarterly_workbench_service import QuarterlyWorkbenchService
from apps.wealth.models import WealthBalanceList


def _balance(yearmon: str, wage: float = 0.0, other: float = 0.0, out: float = 0.0):
    return WealthBalanceList.objects.create(
        yearmon=yearmon, wageincome=wage, otherincome=other, outmoney=out,
    )


@pytest.mark.django_db
class TestWealthRawThreeStates:
    def test_no_rows_returns_none_not_zero(self):
        """没有任何月度收支行 = 取不到，不是「净收入 0 元」"""
        assert ProgressAggregator._wealth_raw(2099) is None

    def test_balanced_month_returns_zero(self):
        _balance('2026-01', wage=10000, out=10000)
        assert ProgressAggregator._wealth_raw(2026) == 0.0

    def test_net_loss_stays_negative(self):
        """回归：v3.62.39 之前这里是 max(net, 0.0)，2026 年 -16901.63 元被抹成 0"""
        _balance('2026-07', wage=12000, out=45514.1)
        assert ProgressAggregator._wealth_raw(2026) == pytest.approx(-33514.1)

    def test_month_filter_isolates_one_month(self):
        _balance('2026-01', wage=1000)
        _balance('2026-02', out=500)
        assert ProgressAggregator._wealth_raw(2026, 1) == pytest.approx(1000)
        assert ProgressAggregator._wealth_raw(2026, 2) == pytest.approx(-500)
        assert ProgressAggregator._wealth_raw(2026, 3) is None


@pytest.mark.django_db
class TestWealthEntryShape:
    def test_loss_year_points_floored_but_raw_visible(self):
        """亏损年：raw 如实为负，评分按 floor 记 0，且必须给出原因码"""
        _balance('2026-07', wage=12000, out=45514.1)
        entry = ProgressAggregator._module_entry('wealth', 2026)
        assert entry['raw_value'] == pytest.approx(-33514.1)
        assert entry['display_value'] == pytest.approx(-3.35)
        assert entry['points'] == 0.0
        assert entry['unit'] == '万元'
        assert entry['zero_reason'] == ZERO_REASON_NET_NEGATIVE

    def test_missing_year_is_null_not_zero(self):
        entry = ProgressAggregator._module_entry('wealth', 2099)
        assert entry['raw_value'] is None
        assert entry['display_value'] is None
        assert entry['points'] == 0.0
        assert entry['zero_reason'] == ZERO_REASON_NO_DATA

    def test_profit_year_has_no_reason_code(self):
        _balance('2025-12', wage=51923)
        entry = ProgressAggregator._module_entry('wealth', 2025)
        assert entry['raw_value'] == pytest.approx(51923)
        assert entry['display_value'] == pytest.approx(5.19)
        assert entry['points'] == pytest.approx(5.19)
        assert entry['zero_reason'] is None


class TestDisplayScale:
    """display_scale 与 divisor 不是同一个数：前者管显示，后者管计分"""

    def test_steps_are_scaled_to_wan(self):
        # 448067 步 → 44.81 万步（曾经前端再补一个「万」→ 44.81 万万步）
        assert ProgressAggregator._display_value('health', 448067) == pytest.approx(44.81)

    def test_hours_are_not_scaled(self):
        # 时间 divisor=30 是计分换算，与单位量级无关；2940 小时就该显示 2940
        assert ProgressAggregator._display_value('times', 2940) == 2940

    def test_words_scaled_but_sugar_not(self):
        assert ProgressAggregator._display_value('words', 237000) == pytest.approx(23.7)
        assert ProgressAggregator._display_value('sugar', 382) == 382

    def test_none_propagates(self):
        assert ProgressAggregator._display_value('wealth', None) is None


class TestRawToPointsWithNone:
    def test_none_is_zero_points(self):
        assert ProgressAggregator._raw_to_points('wealth', None) == 0.0

    def test_negative_is_floored(self):
        assert ProgressAggregator._raw_to_points('wealth', -16901.63) == 0.0


@pytest.mark.django_db
class TestQuarterRawNone:
    """季度聚合曾写 `total += _get_raw_value(...)`，遇到 None 直接 TypeError"""

    def test_quarter_without_rows_is_none(self):
        assert QuarterlyWorkbenchService._module_quarter_raw('wealth', 2099, 1) is None

    def test_quarter_sums_present_months(self):
        _balance('2026-01', wage=1000)
        _balance('2026-03', out=200)
        # 2 月无行：跳过缺失月，不当作 0 参与累加（None 不能进 +=）
        assert QuarterlyWorkbenchService._module_quarter_raw('wealth', 2026, 1) == pytest.approx(800)
