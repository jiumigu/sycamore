"""小确幸奖励金额测试 — apps.sugar.views.SugarRecordViewSet.perform_create"""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.reward.models import RewardPool, RewardTransaction
from apps.sugar.models import SugarRecord

RECORDS_URL = '/api/sugar/records/'


def _create_sugar(level: int, reward_amount: float | None = None) -> dict:
    payload = {
        'title': f'今日小确幸 {level}',
        'time': '2025-01-07 12:00:00',
        'level_of_happiness': level,
    }
    if reward_amount is not None:
        payload['reward_amount'] = reward_amount
    resp = APIClient().post(RECORDS_URL, payload, format='json')
    return resp.data


def _balance() -> Decimal:
    return RewardPool.objects.first().balance if RewardPool.objects.exists() else Decimal('0')


@pytest.mark.django_db
def test_reward_equals_happiness_level_by_default() -> None:
    """核心：前端未传 reward_amount 时，奖励金额 = 快乐程度"""
    data = _create_sugar(level=12)
    record = SugarRecord.objects.get(s_id=data['s_id'])
    assert record.reward_amount == Decimal('12.00')
    assert _balance() == Decimal('12.00')
    tx = RewardTransaction.objects.get(source_type='sugar', source_id=record.s_id)
    assert tx.amount == Decimal('12.00')
    assert tx.transaction_type == 'sugar_create'


@pytest.mark.django_db
def test_frontend_reward_amount_takes_priority() -> None:
    """核心：前端显式传 >0 的 reward_amount 时优先使用"""
    _create_sugar(level=12, reward_amount=15)
    record = SugarRecord.objects.first()
    assert record.reward_amount == Decimal('15.00')
    assert _balance() == Decimal('15.00')


@pytest.mark.django_db
def test_frontend_reward_zero_falls_back_to_level() -> None:
    """边界：前端传 0 → 回退为快乐程度"""
    _create_sugar(level=12, reward_amount=0)
    record = SugarRecord.objects.first()
    assert record.reward_amount == Decimal('12.00')


@pytest.mark.django_db
def test_frontend_reward_negative_falls_back_to_level() -> None:
    """边界：前端传负数 → 回退为快乐程度"""
    _create_sugar(level=12, reward_amount=-5)
    record = SugarRecord.objects.first()
    assert record.reward_amount == Decimal('12.00')


@pytest.mark.django_db
def test_happiness_level_boundaries_5_and_20() -> None:
    """边界：快乐程度最小 5 / 最大 20 均可创建且奖励跟随"""
    _create_sugar(level=5)
    _create_sugar(level=20)
    records = list(SugarRecord.objects.order_by('s_id'))
    assert [r.reward_amount for r in records] == [Decimal('5.00'), Decimal('20.00')]
    assert _balance() == Decimal('25.00')


@pytest.mark.django_db
def test_happiness_level_below_minimum_rejected() -> None:
    """边界：快乐程度 <5 被校验拒绝"""
    resp = APIClient().post(
        RECORDS_URL,
        {'title': '无效', 'time': '2025-01-07 12:00:00', 'level_of_happiness': 4},
        format='json',
    )
    assert resp.status_code == 400
    assert SugarRecord.objects.count() == 0
