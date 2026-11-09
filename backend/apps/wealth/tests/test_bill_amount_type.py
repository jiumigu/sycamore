"""账单金额口径 —— 出参必须是 **number**，不能是字符串。

`BillSerializer` 里 `amount` 原本没有显式声明，`ModelSerializer` 给 DecimalField
自动生成 `coerce_to_string=True` ⇒ 接口吐 `"12.64"`（字符串）。

为什么列表主行没坏、却仍然要修：
- 主行模板是 `formatSignedAmount(Number(row.amount), …)`，前端自己转了；
- 但删除确认弹窗 `formatAmount(row.amount, 0)` **没转** ⇒ 弹窗里会写
  「确认删除这笔账单（2026-10-15 ¥-）？」——金额位置是 `—`。
- 前端 `wealthTypes.ts` 里 `amount` 声明的是 `number`。补丁攒在调用点，
  漏一处就换一个地方显形；契约应当由后端保证。
"""
from datetime import datetime
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.wealth.models import WealthBillList

BILLS_URL = '/api/wealth/bills/'


@pytest.mark.django_db
def test_bill_amount_is_number_not_string() -> None:
    now = datetime.now()
    WealthBillList.objects.create(
        transaction_type='支出', date=datetime(2026, 10, 15, 10, 0, 0),
        amount=Decimal('12.64'), category='餐饮', merchant='测试店', notes='',
        user_id=1, created_at=now, updated_at=now,
    )

    body = APIClient().get(BILLS_URL).data
    rows = body.get('results') if isinstance(body, dict) else body

    assert isinstance(rows[0]['amount'], float), (
        f"amount 出参是 {type(rows[0]['amount']).__name__}，"
        '前端 formatAmount 只认 number ⇒ 会在没做 Number() 兜底的地方渲染成 ¥—'
    )
    assert rows[0]['amount'] == 12.64


@pytest.mark.django_db
def test_bill_amount_write_path_still_accepts_string_input() -> None:
    """写入方向不能退化：前端表单可能传字符串，落库仍要是 Decimal"""
    r = APIClient().post(BILLS_URL, {
        'transaction_type': '支出', 'date': '2026-10-15 10:00:00',
        'amount': '88.80', 'category': '餐饮', 'merchant': '店', 'notes': '',
    }, format='json')
    assert r.status_code == 201, r.data

    bill = WealthBillList.objects.get(id=r.data['id'])
    assert bill.amount == Decimal('88.80')
    assert isinstance(r.data['amount'], float)
