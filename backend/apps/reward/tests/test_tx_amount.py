"""奖励流水金额口径 —— 出参必须是 **number**，不能是字符串。

`RewardTransactionSerializer` 原先三个金额字段都没显式声明，`ModelSerializer`
给 DecimalField 自动生成 `coerce_to_string=True` 的字段 ⇒ 接口吐 `"5.00"`。
前端靠 `rewardStore.fetchTransactions` 里三行 `Number()` 兜住，所以界面看着正常，
但这是「补丁散在调用点」：换一个消费方（时间线组件、导出、新页面）就重新炸一次，
且炸出来的样子是 `formatSignedAmount` 的 `—`，看着像「没数据」。

🔴 同一类 bug 前端类型检查抓不到：`RewardTransaction.amount` 声明的就是 `number`，
字符串照样过 `vue-tsc`，只有接口真发了字符串才在界面显形。故断言必须写在后端出参。
"""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.reward.models import RewardTransaction

TX_URL = '/api/reward/transactions/'


def _tx(amount: str, before: str, after: str) -> RewardTransaction:
    return RewardTransaction.objects.create(
        source_id=1,
        source_type='sugar',
        amount=Decimal(amount),
        transaction_type='sugar_create',
        balance_before=Decimal(before),
        balance_after=Decimal(after),
        description='pytest 造数',
    )


@pytest.mark.django_db
def test_tx_amounts_are_numbers_not_strings() -> None:
    """三个金额都必须是 number，否则流水页渲染成 `—`"""
    _tx('5.00', '680.00', '685.00')

    row = APIClient().get(TX_URL).data['items'][0]

    for key in ('amount', 'balance_before', 'balance_after'):
        assert isinstance(row[key], float), (
            f'{key} 出参是 {type(row[key]).__name__}（{row[key]!r}），'
            '前端 formatSignedAmount 只认 number ⇒ 会渲染成 —'
        )
    assert row['amount'] == 5.0
    assert row['balance_before'] == 680.0
    assert row['balance_after'] == 685.0


@pytest.mark.django_db
def test_tx_negative_amount_keeps_sign() -> None:
    """负数流水必须保留负号 —— 支出方向不能被「做成绝对值」"""
    _tx('-11350.90', '11885.90', '535.00')

    row = APIClient().get(TX_URL).data['items'][0]

    assert row['amount'] == -11350.9
    assert row['amount'] < 0
