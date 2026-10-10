"""衣物口径（v3.59.8，P3-A 八期）

覆盖：
  ① 「穿」类的默认聚合口径是 **min 而不是 sum** —— 与「用」同一条判据：
     类内几件东西是**可替代**还是**并列缺一不可**。
       「米粉与面条都能当一顿饭」→ 可替代 → 求和；
       「袜子破了，大衣囤再多也解决不了穿什么出门」→ 并列 → 取最小。
     实测过 sum 的后果：三条睡衣记录（共 8 件 × 1095 天）相加 = 8760 天，
     四卡报「穿能撑 24.1 年」，而内裤、袜子、外衣、鞋**一件都没录** ——
     错误结果是静默的：那个数字看着完全合理。
  ② ⭐ 聚合口径存在**类别行上**（`aggregate_mode`），不是从常量现读的 ——
     所以改常量只影响新建的类别，**老库必须靠「覆盖类别口径」跟上**。
     这条同时解释了为什么 seed 的 overwrite 分支必须真的写这一列。
  ③ ⭐ 衣物可穿次数参考**只是录入锚点**，算法一个字段都不读它 ——
     尤其**不许**在用户没填口径时拿参考值兜底（那会给出一个「看着合理」的天数）。
  ④ 参考表自身的完整性：关键词唯一、区间有序、次数与轮次同生同灭、无 markdown 星号。
  ⑤ 接口：`/survival/meta/` 的 `wear_reference` 是**裸数组**（被全局分页包住会静默变空）。
"""

from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.wealth.constants import (
    SURVIVAL_CATEGORY_SEEDS,
    SURVIVAL_WEAR_REFERENCE,
)
from apps.wealth.models import (
    SurvivalCategory,
    SurvivalItem,
    SurvivalUnit,
)
from apps.wealth.services import survival_calc as calc
from apps.wealth.services import survival_service as svc

TODAY = date(2026, 9, 22)
META = '/api/wealth/survival/meta/'


# ──────────────────────────────────────────────────────────────
# 造数
# ──────────────────────────────────────────────────────────────

def _category(name='穿', mode='depreciation', aggregate='min'):
    return SurvivalCategory.objects.create(
        user_id=1, name=name, consume_mode=mode, aggregate_mode=aggregate,
    )


def _unit(category, name='件'):
    return SurvivalUnit.objects.create(
        user_id=1, category=category, name=name, base_unit='件',
        to_base_rate=1, is_serving_unit=False,
    )


def _item(category, name, quantity, unit, **extra):
    payload = {
        'user_id': 1, 'category': category, 'name': name,
        'quantity': quantity, 'unit': unit,
        'satiety': extra.pop('satiety', ''),
        'status': extra.pop('status', 'stocked'),
    }
    payload.update(extra)
    return SurvivalItem.objects.create(**payload)


def _run(category):
    """按服务层同样的方式算一遍（物品列表 + 无配方）"""
    return calc.compute_category(
        category, list(category.items.all().order_by('id')), [], TODAY,
    )


# ══════════════════════════════════════════════════════════════
# ① 「穿」不再累加
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestClothingAggregate:
    """衣物之间是并列的：一条腿断了，另一条再长也走不了"""

    def test_clothing_seed_uses_min(self):
        seed = next(s for s in SURVIVAL_CATEGORY_SEEDS if s['name'] == '穿')
        assert seed['aggregate_mode'] == 'min'
        # 类内几件是并列的 —— 与「用」「医药」同一条判据
        for name in ('用', '医药'):
            assert next(
                s for s in SURVIVAL_CATEGORY_SEEDS if s['name'] == name
            )['aggregate_mode'] == 'min'

    def test_min_reports_shortest_not_total(self):
        """三件衣物 → 取最先穿坏的那件，不是三件之和"""
        category = _category()
        piece = _unit(category)
        _item(category, '大衣', 1, piece, days_per_unit=3650)
        _item(category, 'T恤', 1, piece, days_per_unit=365)
        _item(category, '袜子', 1, piece, days_per_unit=90)

        result = _run(category)
        assert result['aggregate_mode_effective'] == 'min'
        assert result['days']['likely'] == 90.0
        # 对照：相加会得到 4105 天（11.2 年）—— 这正是被修掉的算法
        assert sum(
            r['days']['likely'] for r in result['items']
        ) == 4105.0

    def test_piling_up_the_strongest_slot_does_not_help(self):
        """给最宽裕的那件加库存，类别天数纹丝不动 —— 木桶只认短板"""
        category = _category()
        piece = _unit(category)
        _item(category, '袜子', 1, piece, days_per_unit=90)
        _item(category, '大衣', 1, piece, days_per_unit=3650)
        assert _run(category)['days']['likely'] == 90.0

        _item(category, '羽绒服', 20, piece, days_per_unit=3000)
        assert _run(category)['days']['likely'] == 90.0

        # 只有把短板自己抬上去、或者出现一件更短的，类别才跟着走
        _item(category, '内裤', 1, piece, days_per_unit=50)
        assert _run(category)['days']['likely'] == 50.0

    def test_more_of_the_weakest_item_is_not_summed_either(self):
        """同一件物品的数量仍然相乘（那是轮换，不是并列），件与件之间才取最小"""
        category = _category()
        piece = _unit(category)
        _item(category, '袜子', 4, piece, days_per_unit=90)
        _item(category, '大衣', 1, piece, days_per_unit=3650)
        # 4 双袜子轮换 = 360 天；仍比大衣短，故类别 = 360
        assert _run(category)['days']['likely'] == 360.0

    def test_aggregate_comes_from_the_row_not_the_constant(self):
        """⚠️ 口径是**数据**不是常量：改常量不会回头改已存在的类别行

        所以老库必须走一次「覆盖类别口径」才会从 sum 变成 min；
        这条测试同时钉住了「覆盖分支必须真的写 aggregate_mode」这个前提。
        """
        category = _category(aggregate='sum')
        piece = _unit(category)
        _item(category, '大衣', 1, piece, days_per_unit=3650)
        _item(category, '袜子', 1, piece, days_per_unit=90)
        assert _run(category)['days']['likely'] == 3740.0

    def test_seed_overwrite_switches_an_old_row_to_min(self):
        """老库跟上的唯一通道：seed(overwrite=True) 真的改那一列

        没有这条，界面上会写着「取最小」而算法仍按求和跑 —— 谎报。
        """
        svc.seed_survival_defaults()
        clothing = SurvivalCategory.objects.get(name='穿')
        # 模拟老库：先把它改回 sum
        clothing.aggregate_mode = 'sum'
        clothing.save(update_fields=['aggregate_mode'])

        svc.seed_survival_defaults(overwrite=True)
        assert SurvivalCategory.objects.get(name='穿').aggregate_mode == 'min'


# ══════════════════════════════════════════════════════════════
# ② 参考表自身的完整性
# ══════════════════════════════════════════════════════════════

class TestWearReferenceIntegrity:
    """参考表是一份**可以被匹配**的数据，所以它的形状本身要立得住"""

    def test_not_empty(self):
        assert len(SURVIVAL_WEAR_REFERENCE) >= 8

    def test_keywords_are_unique(self):
        keywords = [row['keyword'] for row in SURVIVAL_WEAR_REFERENCE]
        assert len(keywords) == len(set(keywords))

    def test_ranges_are_ordered(self):
        """按天一律给区间；按次允许**只给下限**（羊毛大衣是「1000 次以上」）"""
        for row in SURVIVAL_WEAR_REFERENCE:
            # 按天：没有「X 天以上」这种说法，两端都必须有
            assert row['days_low'] is not None and row['days_high'] is not None, row
            assert 0 < row['days_low'] <= row['days_high'], row
            # 按次：无下限 ⇒ 必须也无上限；有下限则上限可缺省（表示「以上」）
            if row['uses_low'] is None:
                assert row['uses_high'] is None, row
            else:
                assert row['uses_low'] > 0, row
                if row['uses_high'] is not None:
                    assert row['uses_low'] <= row['uses_high'], row

    def test_every_row_gives_at_least_one_way_to_fill_it(self):
        """每行至少要能支持一种填法，否则这行在界面上是废的"""
        for row in SURVIVAL_WEAR_REFERENCE:
            assert row['uses_low'] is not None or row['days_low'] is not None, row

    def test_uses_and_weekly_frequency_come_together(self):
        """有次数建议就必须有频次建议 —— 只有次数的话，默认「每天 1 次」会把
        T 恤的 150 次算成 150 天（实际应该按每周几次展开），给出一个错的天数。"""
        for row in SURVIVAL_WEAR_REFERENCE:
            assert (row['uses_low'] is None) == (row['wears_per_week'] is None), row
            if row['wears_per_week'] is not None:
                assert 1 <= row['wears_per_week'] <= 7, row

    def test_every_row_has_a_decay_signal(self):
        """「什么时候算该换了」比天数更能帮人下判断 —— 不许留空"""
        for row in SURVIVAL_WEAR_REFERENCE:
            assert row['signal'].strip(), row

    def test_no_markdown_asterisks(self):
        """这些文案会被原样渲染（同 METRIC_NOTES 那条规矩），星号会显示出来"""
        for row in SURVIVAL_WEAR_REFERENCE:
            assert '*' not in row['signal'], row
            assert '*' not in row['keyword'], row


# ══════════════════════════════════════════════════════════════
# ③ 参考表绝不参与计算
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestWearReferenceDoesNotFeedCalculation:
    """参考值是「别人一般填多少」，不是这件物品的参数。

    给它一个兜底的作用，就等于给所有衣物套一个统一寿命 ——
    那恰恰是本次要修的错（「还能穿多久」取决于接受标准，不是统一规定的数）。
    """

    def test_reference_never_fills_in_a_missing_value(self):
        """名字里带「T恤」也不会被参考表兜底：没填就是「算不出来」"""
        category = _category()
        piece = _unit(category)
        _item(category, 'T恤', 1, piece)          # 两条口径都没填

        result = _run(category)
        assert result['days']['likely'] is None
        assert result['items'][0]['issues']

    def test_swapping_the_table_does_not_change_days(self, monkeypatch):
        """把参考表清空，同一份库存算出来的天数一模一样"""
        category = _category()
        piece = _unit(category)
        _item(category, 'T恤', 3, piece, days_per_unit=365)
        before = _run(category)['days']['likely']

        monkeypatch.setattr(svc, 'SURVIVAL_WEAR_REFERENCE', ())
        assert _run(category)['days']['likely'] == before == 1095.0


# ══════════════════════════════════════════════════════════════
# ④ 接口：裸数组下发
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestWearReferenceApi:

    def test_meta_returns_bare_array(self):
        """⚠️ 被全局分页包成 {count, results} 时前端会按裸数组取用 → 静默变空列表"""
        resp = APIClient().get(META)
        assert resp.status_code == 200
        rows = resp.data['wear_reference']
        assert isinstance(rows, list)
        assert len(rows) == len(SURVIVAL_WEAR_REFERENCE)

    def test_meta_row_shape(self):
        """前端按这些键取值，少一个就渲染不出来"""
        rows = APIClient().get(META).data['wear_reference']
        row = next(r for r in rows if r['keyword'] == 'T恤')
        assert row['uses_low'] == 100
        assert row['uses_high'] == 200
        assert row['days_low'] == 365
        assert row['wears_per_week'] == 3
        assert row['signal']

    def test_meta_row_keeps_nulls_visible(self):
        """「这件不适合作按次估」必须以 null 下发，**不能**被序列化器悄悄补成 0"""
        rows = APIClient().get(META).data['wear_reference']
        row = next(r for r in rows if r['keyword'] == '袜子')
        assert row['uses_low'] is None
        assert row['uses_high'] is None
        assert row['wears_per_week'] is None
        assert row['days_low'] == 90

    def test_life_days_note_declares_the_standard(self):
        """口径说明必须说清「寿命取决于接受标准」—— 这是这次修正的语义核心"""
        notes = APIClient().get(META).data['metric_meta']
        note = next(n for n in notes if n['key'] == 'life_days')['note']
        joined = '\n'.join(note)
        assert '遮体保暖' in joined
        assert '体面' in joined
        # 旧口径那句「多件按接续方式相加」必须已被替换掉
        assert '接续方式相加' not in joined
        assert '取最先见底' in joined
