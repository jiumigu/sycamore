"""成长记录金额口径 —— 出参必须是 **number**，不能是字符串。

2026-10-23 顺手修的一类静默故障：`ConflictEventSerializer` 里 `loss_amount`
没有显式声明，`ModelSerializer` 给 DecimalField 自动生成 `coerce_to_string=True`
⇒ 接口吐 `"150.00"`（字符串）。前端「成长记录」表格写的是

    ¥{{ formatAmount(row.loss_amount, 0) }}

而 `formatAmount` 第一句就是 `typeof value !== 'number' → '—'`
⇒ 一笔 150 元的损失渲染成 `¥—`，看着像**没填金额**。

同页「累计损失」卡不会坏：它读的是 `Sum` 聚合结果，直接进 `Response`，
由 JSON 层把 Decimal 编码成 number —— 同一页两个数字一个坏一个不坏，
最容易被误判成「数据没存进去」。
"""
from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.relation.models import ConflictEvent, Relationship

CONFLICTS_URL = '/api/relation/conflicts/'


def _conflict(loss) -> ConflictEvent:
    rel = Relationship.objects.create(
        user_id=1, name='朋友', current_quality='neutral', current_status='active', tags='',
    )
    return ConflictEvent.objects.create(
        user_id=1, contact=rel, title='测试事件', event_date=date(2026, 10, 20),
        loss_amount=None if loss is None else Decimal(loss),
    )


@pytest.mark.django_db
def test_loss_amount_is_number_not_string() -> None:
    _conflict('150.00')

    body = APIClient().get(CONFLICTS_URL).data
    rows = body.get('results') if isinstance(body, dict) else body

    assert isinstance(rows[0]['loss_amount'], float), (
        f"loss_amount 出参是 {type(rows[0]['loss_amount']).__name__}，"
        '前端 formatAmount 只认 number ⇒ 会渲染成 ¥—'
    )
    assert rows[0]['loss_amount'] == 150.0


@pytest.mark.django_db
def test_loss_amount_null_stays_null() -> None:
    """没填损失时是 null（不是 0.00、不是字符串）——「没填」与「损失 0 元」是两件事"""
    _conflict(None)

    body = APIClient().get(CONFLICTS_URL).data
    rows = body.get('results') if isinstance(body, dict) else body

    assert rows[0]['loss_amount'] is None
