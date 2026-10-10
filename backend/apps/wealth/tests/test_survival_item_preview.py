"""物品试算（v3.59.11）—— 保存前就把天数算出来

起因是一个真实数据：洗脸巾「数量 300 抽 + 一份能用几次 300 + 每 1 天用 2 次」，
四卡与明细表都报 **123.7 年**。算法没错 ——

    天数 = 数量 × 一份能用几次 × (周期天数 ÷ 每周期次数)
         = 300 × 300 × 0.5 = 45,000 天 ≈ 123.3 年（PERT 期望 123.7 年）

错在**同一个 300 被填了两遍**：一次是「我有 300 抽」，一次是「一份里有 300 抽」。
表单那一格的提示语「一包 10 片就填 10」把「一份」定义成了**包装**，
而用户的「数量」填的是**内容物**（抽/片）—— 两个口径一混，300 就出现两次。

而它之所以骗过了人：**表单从来没把这两个数乘出来给人看**。
中间量「一份可用 150 天」完全正常，错在最后一跳。

覆盖：
  ① ⭐ **试算的数 == 保存后的数**（两条路径必须是同一行代码算的）；
  ② 复现本案：300 × 300 → 45,144 天；改成 1 → 150 天；
  ③ 按天口径走同一个接口（衣物那边同样会踩「一件 × 300 天的量」）；
  ④ 试算**不写库**；
  ⑤ 校验与保存**一模一样**（试算放行、保存报错是最糟的组合）；
  ⑥ 配餐类拒绝试算（那时长由配方决定）；
  ⑦ 配置不全时返回 `None` + 原因，**不是 0 天**。
"""

from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.wealth.models import (
    SurvivalCategory,
    SurvivalItem,
    SurvivalUnit,
)

TODAY = date(2026, 9, 22)
ITEMS = '/api/wealth/survival/items/'
PREVIEW = '/api/wealth/survival/items/preview/'
ANALYSIS = '/api/wealth/survival/analysis/'


# ──────────────────────────────────────────────────────────────
# 造数
# ──────────────────────────────────────────────────────────────

def _category(name='用', mode='on_demand', aggregate='min'):
    return SurvivalCategory.objects.create(
        user_id=1, name=name, consume_mode=mode, aggregate_mode=aggregate,
    )


def _unit(category, name='抽'):
    return SurvivalUnit.objects.create(
        user_id=1, category=category, name=name, base_unit=name,
        to_base_rate=1, is_serving_unit=False,
    )


def _cycle_payload(category, unit, uses, times=2, quantity=300):
    """「按次」口径的完整表单负载 —— 与前端提交的字段一致"""
    return {
        'category_id': category.id,
        'name': '洗脸巾',
        'quantity': quantity,
        'unit_id': unit.id,
        'satiety': '',
        'status': 'stocked',
        'uses_per_unit': uses,
        'use_cycle_num': 1,
        'use_cycle_unit': 'day',
        'use_times': times,
    }


def _saved_expected(api, payload, name='洗脸巾'):
    """保存后，从**分析接口**里读回这件物品的期望天数

    刻意绕一圈走接口而不是直接调 `compute_item_life`：
    要验的是「用户保存前看到的数」与「保存后在页面上看到的数」一致，
    而不是「两个函数都调了同一个函数」。
    """
    api.post(ITEMS, payload, format='json')
    body = api.get(f'{ANALYSIS}?date={TODAY.isoformat()}').json()
    for category in body['categories']:
        for row in category['items']:
            if row['name'] == name:
                return row['expected']
    raise AssertionError(f'分析结果里没找到「{name}」')


# ══════════════════════════════════════════════════════════════
# ① 两条路径必须给出同一个数
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPreviewMatchesTheSavedNumber:
    """试算的存在理由就是「说对了」—— 说得不一样比没有更糟"""

    def test_cycle_preview_equals_saved(self):
        api = APIClient()
        category, unit = _category(), None
        unit = _unit(category)
        payload = _cycle_payload(category, unit, uses=300)
        preview = api.post(PREVIEW, payload, format='json').json()
        assert preview['expected'] == _saved_expected(api, payload)

    def test_day_preview_equals_saved(self):
        api = APIClient()
        category = _category(name='穿', mode='depreciation')
        unit = _unit(category, name='件')
        payload = {
            'category_id': category.id,
            'name': '大衣',
            'quantity': 3,
            'unit_id': unit.id,
            'satiety': '', 'status': 'stocked',
            'days_per_unit': 1095,
        }
        preview = api.post(PREVIEW, payload, format='json').json()
        assert preview['expected'] == _saved_expected(api, payload, name='大衣')

    def test_preview_serializer_is_the_same_shape(self):
        """形状同源：试算与列表行共用一份字段清单，不各写一份"""
        api = APIClient()
        category = _category()
        unit = _unit(category)
        row = api.post(PREVIEW, _cycle_payload(category, unit, uses=1), format='json').json()
        for field in (
            'expected', 'spread', 'days', 'days_per_unit_effective',
            'interval_days', 'life_mode', 'issues', 'item_id',
        ):
            assert field in row, f'试算结果缺字段 {field}'


# ══════════════════════════════════════════════════════════════
# ② 本案：同一个数字被填了两遍
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestTheDoubleCountCase:
    """300 抽 × 每抽 300 次 —— 试算要在**保存前**就把这个数摆出来"""

    def test_the_reported_case_comes_out_as_123_years(self):
        api = APIClient()
        category = _category()
        unit = _unit(category)
        row = api.post(PREVIEW, _cycle_payload(category, unit, uses=300), format='json').json()
        assert row['days']['likely'] == pytest.approx(45000.0)
        assert row['expected'] == pytest.approx(45144.2)
        # 一份 150 天这个**中间量**看着完全正常 —— 它正是骗过人的那一半
        assert row['days_per_unit_effective'] == pytest.approx(150.0)
        assert row['interval_days'] == pytest.approx(0.5)

    def test_one_use_per_unit_gives_the_expected_150_days(self):
        """一抽就是一次 → 300 ÷ 每天 2 次 = 150 天，正是用户预期"""
        api = APIClient()
        category = _category()
        unit = _unit(category)
        row = api.post(PREVIEW, _cycle_payload(category, unit, uses=1), format='json').json()
        assert row['days']['likely'] == pytest.approx(150.0)
        assert row['expected'] == pytest.approx(150.5)
        assert row['days_per_unit_effective'] == pytest.approx(0.5)

    def test_the_two_usages_differ_by_the_quantity_factor(self):
        """两版差的就是那个 300 —— 试算把「差在哪」摆到台面上"""
        api = APIClient()
        category = _category()
        unit = _unit(category)
        wrong = api.post(PREVIEW, _cycle_payload(category, unit, uses=300), format='json').json()
        right = api.post(PREVIEW, _cycle_payload(category, unit, uses=1), format='json').json()
        assert wrong['expected'] == pytest.approx(right['expected'] * 300, rel=1e-3)


# ══════════════════════════════════════════════════════════════
# ③ 试算不写库 / 不产生 id
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPreviewDoesNotWrite:
    def test_nothing_is_persisted(self):
        api = APIClient()
        category = _category()
        unit = _unit(category)
        before = SurvivalItem.objects.count()
        api.post(PREVIEW, _cycle_payload(category, unit, uses=300), format='json')
        assert SurvivalItem.objects.count() == before

    def test_item_id_is_null(self):
        api = APIClient()
        category = _category()
        unit = _unit(category)
        row = api.post(PREVIEW, _cycle_payload(category, unit, uses=1), format='json').json()
        assert row['item_id'] is None


# ══════════════════════════════════════════════════════════════
# ④ 校验与保存一模一样
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPreviewValidationMatchesCreate:
    """「试算放行、一保存报 400」是最糟的组合 —— 它先把人哄住了"""

    def test_bad_cycle_is_rejected_like_create(self):
        api = APIClient()
        category = _category()
        unit = _unit(category)
        payload = _cycle_payload(category, unit, uses=1)
        payload['use_times'] = 0
        assert api.post(PREVIEW, payload, format='json').status_code == 400
        assert api.post(ITEMS, payload, format='json').status_code == 400

    def test_foreign_unit_is_rejected_like_create(self):
        api = APIClient()
        category = _category()
        other = _category(name='穿', mode='depreciation')
        payload = _cycle_payload(category, _unit(other, name='件'), uses=1)
        assert api.post(PREVIEW, payload, format='json').status_code == 400
        assert api.post(ITEMS, payload, format='json').status_code == 400


# ══════════════════════════════════════════════════════════════
# ⑤ 算不出来就说算不出来
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPreviewSaysUnknownInsteadOfZero:
    def test_no_measure_returns_none_with_reason(self):
        api = APIClient()
        category = _category()
        unit = _unit(category)
        payload = {
            'category_id': category.id, 'name': '洗脸巾',
            'quantity': 300, 'unit_id': unit.id,
            'satiety': '', 'status': 'stocked',
        }
        row = api.post(PREVIEW, payload, format='json').json()
        assert row['expected'] is None
        assert 'no_days_per_unit' in [issue['code'] for issue in row['issues']]

    def test_meal_category_is_refused(self):
        """配餐类的时长由配方决定 —— 按单件口径算出来的是一个没人核对过的数"""
        api = APIClient()
        category = _category(name='吃', mode='meal', aggregate='min')
        unit = _unit(category, name='罐')
        payload = {
            'category_id': category.id, 'name': '八宝粥',
            'quantity': 12, 'unit_id': unit.id,
            'satiety': 'filling', 'status': 'stocked',
            'days_per_unit': 30,
        }
        response = api.post(PREVIEW, payload, format='json')
        assert response.status_code == 400
        assert '配方' in response.json()['detail']
