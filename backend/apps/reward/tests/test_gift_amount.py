"""礼物金额口径 —— 出参必须是 **number**，不能是字符串。

钉住两件事，都是 2026-10-23「礼物清单里价格全部显示成 `¥—`」的回归点：

1. **`expected_reward` / `actual_reward` 必须是 number**。
   之前这两个字段在 `GiftListSerializer` 里没有显式声明，`ModelSerializer`
   给 DecimalField 自动生成的是 `coerce_to_string=True` 的字段 ⇒ 接口吐
   `"800.00"`（JSON 里也是字符串）。前端 `GiftCard` 用
   `formatAmount(gift.expected_reward)` 渲染，而它第一句是
   `typeof value !== 'number' → EMPTY_AMOUNT` ⇒ **每张卡片的价格都画成 `¥—`**。

   同一张卡片上「还差 ¥115.00」是 `get_needed` 方法字段（真 number），
   所以只坏价格一处 —— 看着像「价格没填」，其实是类型不对。

   注意这是**类型声明抓不到**的一类 bug：前端 `GiftList` 里写的就是
   `expected_reward: number`，字符串照样过 `vue-tsc`，只在运行时炸。

2. **整页只读一次奖励池**。
   `get_pool()` 已改为从流水聚合派生（3 个 aggregate），而每张卡片要
   `progress` / `needed` / `can_redeem` 三个值。三个方法字段各查一次 ⇒
   N 条礼物 3N 次聚合（6 条时实测 21 次 SQL）。现在收口到一次。
"""
from decimal import Decimal
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.reward.models import GiftList
from apps.reward.services import RewardPoolService

GIFTS_URL = '/api/reward/gifts/'


def _gift(name: str, price: str, **kwargs) -> GiftList:
    return GiftList.objects.create(
        name=name, expected_reward=Decimal(price), **kwargs,
    )


@pytest.mark.django_db
def test_gift_amounts_are_numbers_not_strings() -> None:
    """核心回归：价格必须是 number，否则前端 formatAmount 一律给 `—`"""
    _gift('WEDGWOOD 咖啡杯', '230.00')

    row = APIClient().get(GIFTS_URL).data[0]

    assert isinstance(row['expected_reward'], float), (
        f"expected_reward 出参是 {type(row['expected_reward']).__name__}，"
        '前端 formatAmount 只认 number ⇒ 会渲染成 ¥—'
    )
    assert row['expected_reward'] == 230.0
    # progress / needed 同期必须是 number，三者共用同一个池快照
    assert isinstance(row['needed'], float)
    assert isinstance(row['progress'], float)


@pytest.mark.django_db
def test_gift_actual_reward_null_stays_null() -> None:
    """没兑换时 actual_reward 是 null（不是 0、不是字符串 'None'）

    前端凭这个区分「还没兑换」与「兑换价为 0」。
    """
    _gift('耳机', '800.00', status='waiting')

    row = APIClient().get(GIFTS_URL).data[0]

    assert row['actual_reward'] is None


@pytest.mark.django_db
def test_gift_actual_reward_is_number_after_redeem() -> None:
    """兑换后 actual_reward 也得是 number（同一条声明管两个方向）"""
    _gift('耳机', '800.00', status='redeemed', actual_reward=Decimal('799.00'))

    row = APIClient().get(GIFTS_URL).data[0]

    assert isinstance(row['actual_reward'], float)
    assert row['actual_reward'] == 799.0


@pytest.mark.django_db
def test_pool_is_read_once_for_the_whole_list() -> None:
    """列表只读一次池：条数增长不能让聚合查询跟着长"""
    for i in range(5):
        _gift(f'礼物{i}', '100.00')

    calls = {'n': 0}
    real = RewardPoolService.get_pool  # 先存原始引用（staticmethod 取出来就是普通函数）

    def counting(*args, **kwargs):
        calls['n'] += 1
        return real(*args, **kwargs)

    with patch.object(RewardPoolService, 'get_pool', staticmethod(counting)):
        rows = APIClient().get(GIFTS_URL).data

    assert len(rows) == 5
    assert calls['n'] == 1, f'池被读了 {calls["n"]} 次（应为 1）'
