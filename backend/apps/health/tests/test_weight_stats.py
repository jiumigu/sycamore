"""体重统计：`monthly_target_jin` 必须真的存在（v3.62.37）

🔴 之前 `get_stats()` 的返回字典里**只有 `monthly_target_kg`、没有 `monthly_target_jin`**，
   而前端 `WeightStats` 声明了后者、`MonthlyProgress` 也照着它渲染 ⇒
   「本月目标」恒显示 `--`（一个键缺失，表现成「这项目标没设置」）。

   这是「Serializer 少声明 = 静默丢键」的同族问题，只是这里没有 Serializer，
   而是一个手写 dict —— 没有东西替你检查键是否齐全，只能靠测试盯住。
"""
import datetime as dt
from decimal import Decimal

import pytest

from apps.health.models import UserBodyInfo, WeightGoal, WeightRecord
from apps.health.services import WeightService


def _goal(**kw):
    data = dict(
        user_id=1,
        start_weight_kg=Decimal('65.00'),
        target_weight_kg=Decimal('52.50'),
        monthly_target_kg=Decimal('1.50'),
        start_date=dt.date(2026, 6, 24),
        status='in_progress',
        is_active=True,
    )
    data.update(kw)
    return WeightGoal.objects.create(**data)


def _record(weight='63.00', day=dt.date(2026, 10, 18)):
    return WeightRecord.objects.create(
        user_id=1,
        record_date=day,
        weight_kg=Decimal(weight),
        measure_time='morning',
    )


@pytest.mark.django_db
def test_monthly_target_jin_present_and_doubled():
    _goal()
    _record()
    stats = WeightService.get_stats(user_id=1)
    assert 'monthly_target_jin' in stats, '少这个键 ⇒ 前端「本月目标」恒为 --'
    assert stats['monthly_target_jin'] == 3.0  # 1.5kg × 2
    assert stats['monthly_target_kg'] == 1.5


@pytest.mark.django_db
def test_monthly_target_jin_without_any_record():
    """目标本身是输入，不依赖「有没有称重记录」"""
    _goal()
    stats = WeightService.get_stats(user_id=1)
    assert stats['monthly_target_jin'] == 3.0
    # 没有记录 ⇒ 「本月已减」仍是「算不出」，不是 0
    assert stats['monthly_lost_jin'] is None


@pytest.mark.django_db
def test_no_goal_keeps_monthly_target_none():
    stats = WeightService.get_stats(user_id=1)
    assert stats['monthly_target_jin'] is None
    assert stats['monthly_target_kg'] is None


@pytest.mark.django_db
def test_bmi_from_body_info():
    UserBodyInfo.objects.create(user_id=1, height_cm=Decimal('163.0'), gender='female', age=32)
    _record('63.00')
    stats = WeightService.get_stats(user_id=1)
    assert stats['bmi'] == pytest.approx(63 / (1.63 ** 2), abs=0.01)
    assert stats['bmi_status'] == '正常'
