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


@pytest.mark.django_db
def test_transaction_description_uses_reward_amount_not_level() -> None:
    """流水文案里的金额必须 = 实际入账金额，不能是 `level_of_happiness`。

    🔴 2026-10-26 实案：收件箱完成弹窗把「快乐程度」和「奖励金额」当同一个数，
       3 星 × 4 = 12 分给了程度、金额另填 5 ⇒ 流水描述写「获得 12.0 元奖励」，
       同一行右侧却是 `+¥5.00`。两个数字同屏、都像真的，用户没法判断哪个是真的。

    这里故意让两者**不相等**（level=12 / amount=5）：如果文案仍取 `level`，
    就会写出「获得12元」，用例立刻红。若只断言「文案里有金额」则两者都对，测不出问题。

    ⚠️ 标题里不能带数字：第一版用 `_create_sugar` 建的标题是「今日小确幸 12」，
       于是 `'12' not in description` 被标题误伤 —— 判据只该盯**金额那一句**。
    """
    APIClient().post(
        RECORDS_URL,
        {
            'title': '路口捡到一只小猫',
            'time': '2025-01-07 12:00:00',
            'level_of_happiness': 12,
            'reward_amount': 5,
        },
        format='json',
    )
    record = SugarRecord.objects.first()
    assert record.level_of_happiness == 12
    assert record.reward_amount == Decimal('5.00')

    tx = RewardTransaction.objects.get(source_type='sugar', source_id=record.s_id)
    assert tx.amount == Decimal('5.00')
    assert '获得5.00元奖励' in tx.description, tx.description
    assert '获得12' not in tx.description, f'文案里的金额是快乐程度分：{tx.description}'


def _patch(s_id: int, payload: dict):
    return APIClient().patch(f'{RECORDS_URL}{s_id}/', payload, format='json')


@pytest.mark.django_db
def test_update_keeps_amount_when_level_unchanged() -> None:
    """编辑标题时不能顺手把金额改成分数 —— 否则等于悄悄改写账本。

    历史记录里「程度 12 / 金额 5」是用户真填过的（旧弹窗允许两者不一致）。
    旧实现 `new_amount = validated_data.get('level_of_happiness', old_amount)`
    只看程度：只要请求带上 level（前端 PUT/PATCH 都会带），金额就被改成 12，
    还记一笔 +7 的调整流水 —— 用户只是想改个标题。
    """
    created = _create_sugar(level=12, reward_amount=5)
    tx_count_before = RewardTransaction.objects.count()

    resp = _patch(created['s_id'], {'title': '改个标题', 'level_of_happiness': 12})
    assert resp.status_code == 200, resp.data

    record = SugarRecord.objects.get(s_id=created['s_id'])
    assert record.level_of_happiness == 12
    assert record.reward_amount == Decimal('5.00')
    assert RewardTransaction.objects.count() == tx_count_before, '不该产生调整流水'
    assert _balance() == Decimal('5.00')


@pytest.mark.django_db
def test_update_recomputes_amount_when_level_changes() -> None:
    """程度真的变了 ⇒ 按现行口径「金额 = 分数」重算，并记一笔差额流水。"""
    created = _create_sugar(level=12, reward_amount=5)

    resp = _patch(created['s_id'], {'level_of_happiness': 15})
    assert resp.status_code == 200, resp.data

    record = SugarRecord.objects.get(s_id=created['s_id'])
    assert record.reward_amount == Decimal('15.00')
    assert _balance() == Decimal('15.00')
    tx = RewardTransaction.objects.get(
        source_type='sugar', source_id=record.s_id, transaction_type='sugar_update',
    )
    assert tx.amount == Decimal('10.00')


@pytest.mark.django_db
def test_update_explicit_amount_wins() -> None:
    """显式传金额 ⇒ 优先于程度（与创建时同一优先级）。"""
    created = _create_sugar(level=12)

    resp = _patch(created['s_id'], {'level_of_happiness': 15, 'reward_amount': 7})
    assert resp.status_code == 200, resp.data

    record = SugarRecord.objects.get(s_id=created['s_id'])
    assert record.reward_amount == Decimal('7.00')
    assert _balance() == Decimal('7.00')


@pytest.mark.django_db
def test_api_returns_reward_amount_as_number_not_string() -> None:
    """接口出口必须是 number，不能是 `"9.00"` 这种字符串。

    🔴 前端 `formatAmount` 第一句就是 `typeof value !== 'number' → 返回空占位`，
       所以字符串会让**有值**渲染成 `+¥--`（页面看起来像「没记金额」）。

    这个 bug 从上半年就在：DB 里的值是对的、序列化器也没少字段，
    只有比对**接口出参类型**才抓得到 —— 只断言 `SugarRecord.reward_amount`
    会一路绿灯（本文件上面几条全是那么写的，所以它没被拦住）。
    """
    created = _create_sugar(level=12)
    assert isinstance(created['reward_amount'], float), type(created['reward_amount'])

    listed = APIClient().get(RECORDS_URL).data['results'][0]
    assert isinstance(listed['reward_amount'], float), type(listed['reward_amount'])
    assert listed['reward_amount'] == 12.0
