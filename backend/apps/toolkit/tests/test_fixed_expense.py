"""固定开销计算测试 — apps.toolkit.views.FixedExpenseViewSet._compute_totals"""
from decimal import Decimal

from apps.toolkit.views import FixedExpenseViewSet


def _compute(items: list[dict]) -> dict:
    return FixedExpenseViewSet()._compute_totals(items)


def test_compute_totals_mixed_periods() -> None:
    """核心：日/月/年三周期统一折算为日额再汇总"""
    result = _compute([
        {'amount': 300, 'period': 'monthly'},   # 300/30 = 10/天
        {'amount': 30, 'period': 'daily'},      # 30/1 = 30/天
        {'amount': 3650, 'period': 'yearly'},   # 3650/365 = 10/天
    ])
    assert result == {
        'total_daily': Decimal('50.00'),
        'total_monthly': Decimal('1500.00'),
        'total_yearly': Decimal('18250.00'),
    }


def test_compute_totals_empty_items_all_zero() -> None:
    """边界：空 items → 三项全 0"""
    assert _compute([]) == {
        'total_daily': Decimal('0.00'),
        'total_monthly': Decimal('0.00'),
        'total_yearly': Decimal('0.00'),
    }


def test_compute_totals_zero_amounts() -> None:
    """边界：金额为 0 的项不贡献"""
    result = _compute([{'amount': 0, 'period': 'monthly'}, {'amount': '0.00', 'period': 'daily'}])
    assert result['total_daily'] == Decimal('0.00')


def test_compute_totals_invalid_period_defaults_to_30_days() -> None:
    """边界：非法周期（如 weekly）默认按 30 天折算"""
    result = _compute([{'amount': 300, 'period': 'weekly'}])
    assert result['total_daily'] == Decimal('10.00')
    assert result['total_monthly'] == Decimal('300.00')


def test_compute_totals_decimal_precision_rounding() -> None:
    """边界：除不尽时四舍五入到分（1/30 → 0.0333 → 0.03）"""
    result = _compute([{'amount': '1', 'period': 'monthly'}])
    assert result['total_daily'] == Decimal('0.03')
    assert result['total_monthly'] == Decimal('0.90')


def test_compute_totals_ignores_non_dict_items() -> None:
    """边界：非 dict 条目跳过"""
    result = _compute([{'amount': 300, 'period': 'monthly'}, 'junk', None])
    assert result['total_daily'] == Decimal('10.00')
