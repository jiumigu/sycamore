"""奖励池口径 —— 三个数必须与账本自洽（`services.py::get_pool`）。

钉住两件事。这两件以前都没有任何断言，所以烂了很久没人发现：

1. **余额 / 累计获得 / 累计提取全部从流水派生**：
   `累计获得 - 累计提取 == 余额` 恒成立，且「四源合计 == 累计获得」。
   2026-10-23 实查：池字段 22,092.00 / 21,395.90，流水实际 12,063.00 / 11,378.00，
   两个累计字段比账本虚高一万，页面上就是「流水明细和总数对不上」。

2. **删除负数流水不能让「累计获得」变大**。
   旧实现 `total_earned = total_earned - tx.amount` 对负数流水等于「加」——
   删掉一条 -11350.90 的礼物兑换，累计获得凭空涨一万多；
   而且 `total_withdrawn` 从头到尾没有回退（流水 id 1~379 只剩 360 条 ⇒ 删过 19 条）。
"""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.reward.models import RewardPool, RewardTransaction
from apps.reward.services import RewardPoolService

POOL_URL = '/api/reward/pool/'
STATS_URL = '/api/reward/stats/sources/'


def _tx(amount, source_type='sugar', transaction_type='sugar_create') -> RewardTransaction:
    return RewardTransaction.objects.create(
        source_id=1,
        source_type=source_type,
        amount=Decimal(str(amount)),
        transaction_type=transaction_type,
        balance_before=Decimal('0'),
        balance_after=Decimal('0'),
    )


@pytest.mark.django_db
def test_pool_three_numbers_are_derived_from_ledger() -> None:
    """三个数同源自洽：赚的正数、支出的负数、两者相加=余额"""
    _tx(100, 'milestone', 'milestone_complete')
    _tx(50, 'sugar', 'sugar_create')
    _tx(-30, 'gift', 'gift_exchange')
    _tx(-5, 'sugar', 'sugar_delete')

    pool = RewardPoolService.get_pool()

    assert pool['total_earned'] == 150.0
    assert pool['total_withdrawn'] == 35.0
    assert pool['balance'] == 115.0
    # 恒等式：这一条就是「对不上」的反面
    assert pool['total_earned'] - pool['total_withdrawn'] == pool['balance']


@pytest.mark.django_db
def test_source_stats_sum_equals_total_earned() -> None:
    """四源合计 == 累计获得；负数修正不算收入（否则必有缺口）"""
    _tx(100, 'milestone', 'milestone_complete')
    _tx(50, 'sugar', 'sugar_create')
    _tx(-20, 'sugar', 'sugar_delete')
    _tx(70, 'goal_complete', 'goal_complete')
    _tx(10, 'inbox_complete', 'inbox_complete')

    stats = RewardPoolService.get_stats_by_source()
    pool = RewardPoolService.get_pool()
    four = (
        stats['milestone'] + stats['sugar']
        + stats['goal_complete'] + stats['inbox_complete']
    )

    assert stats['sugar'] == 50.0, '负数修正不能混进「小确幸」这个来源'
    assert four == 230.0
    assert four == pool['total_earned']


@pytest.mark.django_db
def test_delete_expense_transaction_does_not_inflate_earned() -> None:
    """核心回归：删支出流水，累计获得不能变大"""
    RewardPool.objects.create(
        balance=Decimal('60'), total_earned=Decimal('100'), total_withdrawn=Decimal('40'),
    )
    _tx(100, 'milestone', 'milestone_complete')
    expense = _tx(-40, 'gift', 'gift_exchange')

    resp = APIClient().delete(f'/api/reward/transactions/{expense.id}/')
    assert resp.status_code == 204

    row = RewardPool.objects.first()
    row.refresh_from_db()
    assert row.total_earned == Decimal('100.00'), '删负数额流水不能让累计获得变大'
    assert row.total_withdrawn == Decimal('0.00'), '累计提取必须跟着回退'
    assert row.balance == Decimal('100.00')


@pytest.mark.django_db
def test_pool_api_and_source_api_share_one_ledger() -> None:
    """接口层同源：/pool/ 与 /stats/sources/ 不能各算各的"""
    _tx(80, 'milestone', 'milestone_complete')
    _tx(20, 'sugar', 'sugar_create')
    _tx(-20, 'gift', 'gift_exchange')

    client = APIClient()
    pool = client.get(POOL_URL).data
    stats = client.get(STATS_URL).data

    assert pool['balance'] == 80.0
    assert pool['total_earned'] == 100.0
    assert pool['total_withdrawn'] == 20.0
    assert stats['milestone'] + stats['sugar'] == pool['total_earned']
    assert stats['total'] == pool['total_earned']
