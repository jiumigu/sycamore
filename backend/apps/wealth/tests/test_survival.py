"""生存资源盘点（v3.59.0，P3-A 一期）

覆盖：
  ① 单位换算：跨单位求和的前提是折到同一基准；不可比时**报错而非硬算**
  ② 配餐核心：同餐位可替代 → 求和；跨餐位必配 → 取最小（木桶只在这里成立）
     —— 特意用「八宝粥 20 顿 + 米粉 30 顿 + 面条 25 顿 = 75 顿」这一组数字，
        因为把它取最小会得出「只能吃 20 顿」这种一眼错的结论
  ③ 类别聚合**没有算术平均**：sum 与 min 两种口径给出不同答案，且都不是平均
  ④ PERT 三档由**每日餐数**派生（省 2 / 常 3 / 放 4）：O ≥ P、离散度 ≥ 0
  ⑤ 保质期是硬上限：库存能撑 200 天但最早那批 10 天后过期 → 封顶 10 天
  ⑥ 算不出来就返回 None + 原因，**绝不返回 0**；配方缺件判「不可信」不静默跳过
  ⑦ 零食不参与「能撑多少顿」，单独统计
  ⑧ 分派只看 consume_mode，**不看类别名**（把「吃」改名成「口粮」仍然算得对）
  ⑨ 删除一律先问再删：类别里有东西、单位被引用、物品被配方引用 → 400 可照做
  ⑩ 接口：四个列表端点与口径元信息都是**裸数组**（被全局分页包住会静默变空）

新表由 conftest 的 session 级 django_db_setup 镜像建表 ——
--no-migrations --reuse-db 下新 managed 表不会自动出现。
"""

from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient

from apps.wealth.constants import (
    SURVIVAL_CATEGORY_SEEDS,
    SURVIVAL_MEAL_SCENARIOS,
    SURVIVAL_METRIC_NOTES,
    SURVIVAL_RATE_SCENARIOS,
)
from apps.wealth.models import (
    SurvivalCategory,
    SurvivalItem,
    SurvivalRecipe,
    SurvivalRecipeLine,
    SurvivalUnit,
)
from apps.wealth.services import survival_calc as calc
from apps.wealth.services import survival_service as svc

TODAY = date(2026, 9, 21)


def _category(name='吃', mode='meal', aggregate='min'):
    return SurvivalCategory.objects.create(
        user_id=1, name=name, consume_mode=mode, aggregate_mode=aggregate,
    )


def _unit(category, name, base_unit, rate=1, serving=False):
    return SurvivalUnit.objects.create(
        user_id=1, category=category, name=name, base_unit=base_unit,
        to_base_rate=rate, is_serving_unit=serving,
    )


def _item(category, name, quantity, unit, **extra):
    payload = {
        'user_id': 1, 'category': category, 'name': name,
        'quantity': quantity, 'unit': unit,
        'satiety': extra.pop('satiety', 'filling'),
        'status': extra.pop('status', 'stocked'),
    }
    payload.update(extra)
    return SurvivalItem.objects.create(**payload)


def _line(recipe, item, quantity, role='staple', unit=None):
    return SurvivalRecipeLine.objects.create(
        recipe=recipe, item=item, role=role,
        quantity_per_serving=quantity, unit=unit,
    )


# ══════════════════════════════════════════════════════════════
# ① 单位换算
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestUnitConversion:
    """单位必须能折到同一基准，否则跨单位求和是错的 —— 而且错得静默"""

    def test_same_unit_is_comparable(self):
        category = _category()
        gram = _unit(category, '克', '克')
        assert calc.units_comparable(gram, gram) is True

    def test_different_base_is_not_comparable(self):
        """库存按「袋」（自成一系）、用量按「克」→ 不可比，不许猜换算率"""
        category = _category()
        bag = _unit(category, '袋', '袋')
        gram = _unit(category, '克', '克')
        assert calc.units_comparable(bag, gram) is False

    def test_shared_base_is_comparable(self):
        """同一基准下的两个单位可比（千克 ↔ 克）"""
        category = _category()
        gram = _unit(category, '克', '克', 1)
        kg = _unit(category, '千克', '克', 1000)
        assert calc.units_comparable(kg, gram) is True

    def test_stock_in_bag_consumed_in_gram(self):
        """1 袋 = 5000 克，每餐 100 克 → 50 餐（换算真的参与了计算）"""
        category = _category()
        bag = _unit(category, '袋', '克', 5000)
        gram = _unit(category, '克', '克', 1)
        rice = _item(category, '米', 1, bag)
        recipe = SurvivalRecipe.objects.create(
            user_id=1, category=category, name='一餐', meals_per_day=3,
        )
        _line(recipe, rice, 100, unit=gram)

        row = calc.compute_recipe(recipe, TODAY)
        assert row['meals'] == 50
        assert row['trustworthy'] is True

    def test_unit_mismatch_reports_instead_of_guessing(self):
        """不可比时给问题、不给数字 —— 猜一个换算率会静默产出错天数"""
        category = _category()
        bag = _unit(category, '袋', '袋')
        gram = _unit(category, '克', '克')
        rice = _item(category, '米', 1, bag)
        recipe = SurvivalRecipe.objects.create(
            user_id=1, category=category, name='一餐', meals_per_day=3,
        )
        _line(recipe, rice, 100, unit=gram)

        row = calc.compute_recipe(recipe, TODAY)
        assert row['meals'] is None
        assert row['trustworthy'] is False
        codes = [issue['code'] for issue in row['issues']]
        assert calc.ISSUE_UNIT_MISMATCH in codes


# ══════════════════════════════════════════════════════════════
# ② 配餐核心：主食位求和 + 必配位取最小
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMealCombo:
    """一顿饭不是一种东西，但也不是「必须凑齐」"""

    def _build(self):
        category = _category()
        can = _unit(category, '罐', '罐')
        gram = _unit(category, '克', '克')
        ml = _unit(category, '毫升', '毫升')
        congee = _item(category, '八宝粥', 20, can)          # 1 罐/餐 → 20 餐
        rice = _item(category, '米粉', 3000, gram)           # 100 克/餐 → 30 餐
        noodle = _item(category, '面条', 2500, gram)         # 100 克/餐 → 25 餐
        water = _item(category, '饮用水', 30000, ml, satiety='water')  # 500ml/餐 → 60 餐
        recipe = SurvivalRecipe.objects.create(
            user_id=1, category=category, name='一餐', meals_per_day=3,
        )
        _line(recipe, congee, 1)
        _line(recipe, rice, 100)
        _line(recipe, noodle, 100)
        _line(recipe, water, 500, role='required')
        return category, recipe

    def test_staples_are_summed_not_minimised(self):
        """主食相互替代 → 求和 75 餐；取最小会错成 20 餐"""
        _, recipe = self._build()
        row = calc.compute_recipe(recipe, TODAY)
        assert row['staple_servings'] == 75
        assert row['required_servings'] == 60
        assert row['meals'] == 60  # min(75, 60)：必配位才是木桶

    def test_documented_meal_combo_numbers(self):
        """设计文档里的验收数字：60 餐 → 省2/常3/放4 餐/天 = 30/20/15 天，E=20.8"""
        _, recipe = self._build()
        row = calc.compute_recipe(recipe, TODAY)
        assert row['days'] == {
            'optimistic': 30.0, 'likely': 20.0, 'pessimistic': 15.0,
        }
        assert row['expected'] == 20.8
        assert row['spread'] == 2.5

    def test_bottleneck_points_to_the_required_slot(self):
        """短板指向必配位 —— 要补的是水，不是那罐八宝粥"""
        _, recipe = self._build()
        row = calc.compute_recipe(recipe, TODAY)
        assert row['bottleneck_role'] == 'required'
        assert row['bottleneck_item'] == '饮用水'

    def test_zero_quantity_per_serving_is_rejected(self):
        category = _category()
        gram = _unit(category, '克', '克')
        rice = _item(category, '米', 1000, gram)
        recipe = SurvivalRecipe.objects.create(
            user_id=1, category=category, name='一餐', meals_per_day=3,
        )
        _line(recipe, rice, 0)
        row = calc.compute_recipe(recipe, TODAY)
        assert row['meals'] is None
        assert calc.ISSUE_BAD_QUANTITY in [i['code'] for i in row['issues']]

    def test_empty_recipe_reports_not_zero(self):
        category = _category()
        recipe = SurvivalRecipe.objects.create(
            user_id=1, category=category, name='空配方', meals_per_day=3,
        )
        row = calc.compute_recipe(recipe, TODAY)
        assert row['meals'] is None
        assert row['expected'] is None            # 不是 0
        assert calc.ISSUE_EMPTY_RECIPE in [i['code'] for i in row['issues']]

    def test_no_required_line_is_not_the_same_as_uncomputable(self):
        """「一行必配都没配」≠「配了但算不出来」—— 两者 required_servings 都是 None

        前者是**无约束、不影响结论**（正常配置），后者才是**配置有问题**。
        界面只能靠 `required_line_count` 分开说。合并成同一句话会造出自相矛盾：
        旁边「配方可支撑」算得好好的，这一格却说「算不出来」，使用者会以为
        自己配错了 —— 而其实什么都没错。
        """
        category = _category(name='吃-必配对比')
        gram = _unit(category, '克', '克')
        rice = _item(category, '米粉', 1000, gram)

        # ① 没配必配位：正常配置，餐数只由主食位决定
        plain = SurvivalRecipe.objects.create(
            user_id=1, category=category, name='只配主食', meals_per_day=1,
        )
        _line(plain, rice, 100)
        row = calc.compute_recipe(plain, TODAY)
        assert row['required_servings'] is None
        assert row['required_line_count'] == 0
        assert row['meals'] == 10          # 主食位 10 餐照常算得出
        assert row['issues'] == []         # 无必配项**不是**问题
        assert row['trustworthy'] is True

        # ② 配了必配位、但那一行算不出来：这才是真问题
        broken = SurvivalRecipe.objects.create(
            user_id=1, category=category, name='必配算不出', meals_per_day=1,
        )
        _line(broken, rice, 100)
        _line(broken, rice, 0, role='required')   # 每餐用量 0 → 该行算不出
        row2 = calc.compute_recipe(broken, TODAY)
        assert row2['required_servings'] is None
        assert row2['required_line_count'] == 1
        assert calc.ISSUE_BAD_QUANTITY in [i['code'] for i in row2['issues']]
        assert row2['trustworthy'] is False

    def test_required_line_count_counts_only_the_required_slot(self):
        """只数必配位 —— 主食位配多少行都不该影响这个判断"""
        _, recipe = self._build()          # 3 行主食 + 1 行必配
        row = calc.compute_recipe(recipe, TODAY)
        assert row['required_line_count'] == 1
        assert row['required_servings'] == 60

    def test_recipes_do_not_share_a_stock_budget(self):
        """⚠️ 特征化用例：**配方之间不共享库存**（已知局限，不是设计目标）

        `compute_recipe` 逐配方独立按 `item.quantity` **全额**算，配方之间没有任何分摊。
        所以同一件食材配在两个配方里时，两边都会按「全部库存都给我这一顿用」算出餐数，
        各自的数都偏大 —— 类别层取最小能让**综合结论**不至于虚高，但**单个配方的餐数会误导**。

        这条**刻意钉住现状**而不是钉住期望：
        将来若真做「配方间库存分摊」（三期），这条用例必须**改成断言分摊后的值**，
        而不是被悄悄删掉。使用者侧的规避办法是**分账记物品**（早餐米粉 / 午餐米粉分开）。
        """
        category = _category(name='吃-库存不共享')
        gram = _unit(category, '克', '克')
        # 一件共享食材：1000 克，一顿 100 克 → 单独用能撑 10 餐
        rice = _item(category, '米粉', 1000, gram)

        breakfast = SurvivalRecipe.objects.create(
            user_id=1, category=category, name='早餐拌米粉', meals_per_day=1,
        )
        lunch = SurvivalRecipe.objects.create(
            user_id=1, category=category, name='午餐米粉', meals_per_day=1,
        )
        _line(breakfast, rice, 100)
        _line(lunch, rice, 100)

        row_b = calc.compute_recipe(breakfast, TODAY)
        row_l = calc.compute_recipe(lunch, TODAY)
        # 两个配方各自都拿到「全部 1000 克」⇒ 都是 10 餐，而不是各 5 餐
        assert row_b['meals'] == 10
        assert row_l['meals'] == 10
        # 加起来是 20，超过这件库存真实能供的 10 餐 —— 所以**不能相加**
        assert row_b['meals'] + row_l['meals'] == 20

    def test_meal_category_uses_min_across_recipes(self):
        """早/正餐每天都在吃 → 跨配方取最小（有一个凑不齐今天就不成）"""
        category, _ = self._build()
        # 第二个配方只有 2 餐的存量 → 天数应被它拖到 2/3
        gram = SurvivalUnit.objects.get(category=category, name='克')
        small = _item(category, '仅够两餐', 200, gram)
        recipe2 = SurvivalRecipe.objects.create(
            user_id=1, category=category, name='加餐', meals_per_day=1,
        )
        _line(recipe2, small, 100)  # 2 餐 ÷ 1 餐/天 = 2 天

        result = calc.compute_category(
            category, list(category.items.all()), list(category.recipes.all()), TODAY,
        )
        assert result['days']['likely'] == 2.0
        assert result['aggregate_mode_effective'] == 'min'


# ══════════════════════════════════════════════════════════════
# ③ 类别聚合：只有求和与取最小，没有平均
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestCategoryAggregate:

    def _build(self, mode, aggregate):
        category = _category(name=f'用-{aggregate}', mode=mode, aggregate=aggregate)
        piece = _unit(category, '件', '件')
        _item(category, 'A', 1, piece, days_per_unit=100)   # 100 天
        _item(category, 'B', 1, piece, days_per_unit=200)   # 200 天
        return category

    def test_sum_mode_adds_up(self):
        category = self._build('on_demand', 'sum')
        result = calc.compute_category(category, list(category.items.all()), [], TODAY)
        assert result['days']['likely'] == 300.0

    def test_min_mode_takes_shortest(self):
        category = self._build('on_demand', 'min')
        result = calc.compute_category(category, list(category.items.all()), [], TODAY)
        assert result['days']['likely'] == 100.0

    def test_never_averages(self):
        """两种口径都不是「平均 150 天」—— 平均出来的数没有任何语义"""
        for aggregate, expected in (('sum', 300.0), ('min', 100.0)):
            category = self._build('on_demand', aggregate)
            result = calc.compute_category(category, list(category.items.all()), [], TODAY)
            assert result['days']['likely'] == expected
            assert result['days']['likely'] != 150.0


# ══════════════════════════════════════════════════════════════
# ④ PERT
# ══════════════════════════════════════════════════════════════

class TestPert:
    """PERT 的输入是消耗速率，不是手填天数；乐观一定撑得更久"""

    def test_formula(self):
        row = calc.pert_triple({'optimistic': 30.0, 'likely': 20.0, 'pessimistic': 15.0})
        assert row['expected'] == 20.8
        assert row['spread'] == 2.5

    def test_missing_scenario_yields_none(self):
        row = calc.pert_triple({'optimistic': 30.0, 'likely': None, 'pessimistic': 15.0})
        assert row['expected'] is None
        assert row['spread'] is None

    def test_optimistic_is_the_slowest_consumption(self):
        """语义铁律：乐观 = 吃得省 = 撑得久"""
        assert SURVIVAL_MEAL_SCENARIOS['optimistic'] < SURVIVAL_MEAL_SCENARIOS['pessimistic']
        assert SURVIVAL_RATE_SCENARIOS['optimistic'] < SURVIVAL_RATE_SCENARIOS['pessimistic']

    @pytest.mark.django_db
    def test_item_scenarios_are_ordered(self):
        category = _category(name='穿', mode='depreciation', aggregate='min')
        piece = _unit(category, '件', '件')
        _item(category, '大衣', 1, piece, days_per_unit=365)
        result = calc.compute_category(category, list(category.items.all()), [], TODAY)
        days = result['days']
        assert days['optimistic'] > days['likely'] > days['pessimistic']
        assert result['spread'] > 0


# ══════════════════════════════════════════════════════════════
# ④.5 按次计量（v3.59.3）
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestItemLifeByCycle:
    """不是每天都用的东西：问「一份能用几次 + 多久用一次」

    这条口径是为「一包 10 片卫生巾」这类物品开的 —— 问它「一包能用多少天」
    是问不出来的，答案只会是硬猜；而「一包 10 片」与「3 天用一片」两句人都答得出。
    与一期「把问题换成可观测的量」是同一条判据，不是新增一套哲学。
    """

    def _by_cycle(self, **kwargs):
        category = _category('用', mode='on_demand', aggregate='sum')
        unit = _unit(category, '件', '件')
        payload = {'uses_per_unit': 10}
        payload.update(kwargs)
        return _item(category, '卫生巾', 1, unit, **payload)

    def test_interval_days_from_cycle(self):
        """每 N 个周期用 M 次 → 间隔 = N × 周期天数 ÷ M

        四组覆盖三个周期单位，以及「一天用多次」这种小数间隔。
        """
        item = self._by_cycle(use_cycle_num=3, use_cycle_unit='day', use_times=1)
        assert calc.use_interval_days(item) == 3          # 卫生巾：3 天一片
        item.use_cycle_num, item.use_cycle_unit, item.use_times = 1, 'day', 2
        assert calc.use_interval_days(item) == 0.5        # 牙膏：每天早晚各一次
        item.use_cycle_num, item.use_cycle_unit, item.use_times = 1, 'week', 2
        assert calc.use_interval_days(item) == 3.5        # 洗衣液：一周洗两次
        item.use_cycle_num, item.use_cycle_unit, item.use_times = 1, 'month', 1
        assert calc.use_interval_days(item) == 30         # 驱虫药：每月一次

    def test_one_pack_of_pads_lasts_30_days(self):
        """1 包 ×（一份 10 次 × 每 3 天一次）= 30 天"""
        item = self._by_cycle(use_cycle_num=3, use_cycle_unit='day', use_times=1)
        row = calc.compute_item_life(item, TODAY)
        assert row['life_mode'] == 'cycle'
        assert row['days_per_unit_effective'] == 30.0
        assert row['interval_days'] == 3.0
        # 断言基准档而不是 expected：expected 是三档加权（约 30.1），
        # 拿它验「一份 10 次 × 3 天 = 30 天」会把换算和 PERT 混在一句里。
        assert row['days']['likely'] == 30.0

    def test_three_packs_lasts_three_times_longer(self):
        """按次口径同样乘数量：3 包 → 90 天（数量仍是第一位的乘数）"""
        category = _category('用', mode='on_demand', aggregate='sum')
        unit = _unit(category, '件', '件')
        item = _item(
            category, '卫生巾', 3, unit,
            uses_per_unit=10, use_cycle_num=3, use_cycle_unit='day', use_times=1,
        )
        assert calc.compute_item_life(item, TODAY)['days']['likely'] == 90.0

    def test_cycle_wins_when_both_filled(self):
        """⚠️ 两条都填时**按次优先**

        按次填的是原始量（次数 × 频次），按天填的是折算结果；
        而且用户改过次数之后，按天那个值往往就是**忘了同步的旧数**。
        """
        item = self._by_cycle(
            days_per_unit=99, use_cycle_num=3, use_cycle_unit='day', use_times=1,
        )
        row = calc.compute_item_life(item, TODAY)
        assert row['life_mode'] == 'cycle'
        assert row['days']['likely'] == 30.0               # 不是 99

    def test_broken_cycle_does_not_fall_back_to_days(self):
        """⚠️ 频次填坏时**绝不退回按天**（这条是本次最容易写错的地方）

        若退回按天，界面会拿一个旧的按天值当结果，而用户以为系统用的是
        他刚填的次数 —— 这种错比直接报错难查得多：数字看着很正常。
        """
        item = self._by_cycle(
            days_per_unit=99, use_cycle_num=3, use_cycle_unit='day', use_times=0,
        )
        row = calc.compute_item_life(item, TODAY)
        assert row['life_mode'] == 'cycle'
        assert row['days']['likely'] is None               # 不是 99
        assert row['expected'] is None
        assert calc.ISSUE_BAD_CYCLE in [i['code'] for i in row['issues']]

    def test_unknown_cycle_unit_is_rejected(self):
        """周期单位不认识 → 算不出来，不悄悄按「天」处理"""
        item = self._by_cycle(use_cycle_num=1, use_cycle_unit='fortnight', use_times=1)
        row = calc.compute_item_life(item, TODAY)
        assert row['expected'] is None
        assert calc.ISSUE_BAD_CYCLE in [i['code'] for i in row['issues']]

    def test_neither_filled_reports_missing_not_zero(self):
        """两条都没填 → 报「没填」，**不是 0 天**"""
        category = _category('用', mode='on_demand', aggregate='sum')
        unit = _unit(category, '件', '件')
        item = _item(category, '大衣', 3, unit)
        row = calc.compute_item_life(item, TODAY)
        assert row['life_mode'] is None
        assert row['expected'] is None
        assert calc.ISSUE_NO_DAYS_PER_UNIT in [i['code'] for i in row['issues']]

    def test_days_mode_is_untouched(self):
        """按天口径没被动过：一份 10 天 × 10 件 = 100 天"""
        category = _category('用', mode='on_demand', aggregate='sum')
        unit = _unit(category, '件', '件')
        item = _item(category, '纸巾', 10, unit, days_per_unit=10)
        row = calc.compute_item_life(item, TODAY)
        assert row['life_mode'] == 'day'
        assert row['days']['likely'] == 100.0
        assert row['days_per_unit_effective'] == 10.0

    def test_cycle_item_joins_category_aggregate(self):
        """按次物品与按天物品在类别层同一口径相加（30 + 70 = 100）"""
        category = _category('用', mode='on_demand', aggregate='sum')
        unit = _unit(category, '件', '件')
        _item(
            category, '卫生巾', 1, unit,
            uses_per_unit=10, use_cycle_num=3, use_cycle_unit='day', use_times=1,
        )
        _item(category, '纸巾', 10, unit, days_per_unit=7)
        items = list(SurvivalItem.objects.filter(category=category))
        result = calc.compute_category(category, items, [], TODAY)
        assert result['days']['likely'] == 100.0

    def test_form_rejects_zero_times(self):
        """入参层就把半个配置拦下 —— 别让它到计算层才变成一个旧数"""
        category = _category('用', mode='on_demand', aggregate='sum')
        unit = _unit(category, '件', '件')
        client = APIClient()
        resp = client.post('/api/wealth/survival/items/', {
            'category_id': category.id, 'name': '卫生巾', 'quantity': '1',
            'unit_id': unit.id, 'uses_per_unit': '10',
            'use_cycle_num': '3', 'use_cycle_unit': 'day', 'use_times': '0',
        }, format='json')
        assert resp.status_code == 400
        assert 'use_times' in resp.data

    def test_item_list_exposes_effective_days(self):
        """清单里必须拿得到**折算后**的一份可用天数

        ⚠️ 界面若直接读 `days_per_unit`，按次计量的物品会显示成「未填」——
           而它其实填得好好的，只是填在另一条口径上。
        """
        self._by_cycle(use_cycle_num=3, use_cycle_unit='day', use_times=1)
        client = APIClient()
        resp = client.get('/api/wealth/survival/items/')
        assert resp.status_code == 200
        assert isinstance(resp.data, list)          # 裸数组，不是 {count, results}
        row = next(r for r in resp.data if r['name'] == '卫生巾')
        assert row['days_per_unit'] is None
        assert row['days_per_unit_effective'] == 30.0
        assert row['life_mode'] == 'cycle'
        assert row['use_cycle_unit_label'] == '天'


# ══════════════════════════════════════════════════════════════
# ④-b 按天口径把「频次三兄弟」清成 NULL（v3.59.6）
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestItemSaveClearsCycleFields:
    """按天口径下，三个频次字段必须落成 NULL

    增/改物品时的「切口径显式送 null」是 v3.59.3 就定下的约定，可当时这三列
    还带着 `NOT NULL DEFAULT 1` / `NOT NULL DEFAULT 'day'` —— 序列化器放行 null、
    数据库拒收，于是**保存一律 500**，界面上只剩一句兜底的「保存失败」，
    连是哪个字段错了都看不出来。

    更要紧的是它长得不像配置错：`use_cycle_num=1, use_cycle_unit='day',
    use_times=1` 读起来是「每天用 1 次」，对一件羽绒服来说是句假话 ——
    「按天口径」在库里不该有这种写法。
    """

    def _payload(self, category, unit, **over):
        """前端在「按天」模式下真实发出来的那一份

        ⚠️ 注意 `use_cycle_unit` 送的是 'day' 而不是 null —— 前端当时是**迁就**
           这一列 NOT NULL 才这么写的，另外两个（num / times）则按约定送 null。
           一列迁就、两列不迁就，正是这处设计不一致把 bug 留了下来。
        """
        data = {
            'category_id': category.id, 'name': '羽绒服', 'quantity': 2,
            'unit_id': unit.id, 'satiety': '', 'grade': 'first',
            'status': 'stocked', 'priority': '', 'days_per_unit': 1095,
            'uses_per_unit': None, 'use_cycle_num': None,
            'use_cycle_unit': 'day', 'use_times': None,
            'stocktake_cycle_days': None, 'restock_threshold': None,
            'hours_per_unit': None, 'expire_date': None, 'notes': '',
        }
        data.update(over)
        return data

    def test_day_mode_with_explicit_nulls_saves(self):
        """回归：按天口径下带 null 的保存（这条曾经是 500）"""
        category = _category('穿', mode='depreciation', aggregate='min')
        unit = _unit(category, '件', '件')
        resp = APIClient().post(
            '/api/wealth/survival/items/', self._payload(category, unit), format='json',
        )
        assert resp.status_code == 201, resp.data
        assert resp.data['life_mode'] == 'day'
        assert resp.data['days_per_unit_effective'] == 1095.0
        item = SurvivalItem.objects.get(id=resp.data['id'])
        assert item.use_cycle_num is None
        assert item.use_cycle_unit is None
        assert item.use_times is None

    def test_day_mode_with_null_unit_saves(self):
        """三个频次字段全送 null 也要存得下（前端对齐后的写法）"""
        category = _category('穿', mode='depreciation', aggregate='min')
        unit = _unit(category, '件', '件')
        resp = APIClient().post(
            '/api/wealth/survival/items/',
            self._payload(category, unit, use_cycle_unit=None),
            format='json',
        )
        assert resp.status_code == 201, resp.data
        item = SurvivalItem.objects.get(id=resp.data['id'])
        assert item.use_cycle_unit is None

    def test_switch_back_to_day_clears_old_cycle_values(self):
        """按次改按天：旧频次不许留在库里

        留着会得到一个「界面显示按天、库里写着每 3 天一次」的物品 ——
        不是算法错，是账错，而且没人会去翻。
        """
        category = _category('用', mode='on_demand', aggregate='sum')
        unit = _unit(category, '件', '件')
        item = _item(
            category, '卫生巾', 1, unit, uses_per_unit=10,
            use_cycle_num=3, use_cycle_unit='day', use_times=1,
        )
        resp = APIClient().patch(
            f'/api/wealth/survival/items/{item.id}/',
            {'uses_per_unit': None, 'days_per_unit': 30,
             'use_cycle_num': None, 'use_cycle_unit': None, 'use_times': None},
            format='json',
        )
        assert resp.status_code == 200, resp.data
        item.refresh_from_db()
        assert item.use_cycle_num is None
        assert item.use_cycle_unit is None
        assert item.use_times is None
        assert item.days_per_unit == 30

    def test_server_nulls_leftover_cycle_values(self):
        """服务端自己兜底：没有「一份能用几次」，三个频次字段一律置空

        ⚠️ 不能只靠前端送 null。送不送是客户端的自由，而「按天口径下这三个字段
           没有含义」是**口径本身**的规定 —— 属于服务端该守住的不变量。
           这里刻意只送 `uses_per_unit=null`，模拟一个没同步更新的旧客户端：
           它的 use_cycle_num/use_times 还停在 3 / 1。
        """
        category = _category('用', mode='on_demand', aggregate='sum')
        unit = _unit(category, '件', '件')
        resp = APIClient().post(
            '/api/wealth/survival/items/',
            self._payload(category, unit, uses_per_unit=None,
                          use_cycle_num=3, use_times=1),
            format='json',
        )
        assert resp.status_code == 201, resp.data
        item = SurvivalItem.objects.get(id=resp.data['id'])
        assert item.use_cycle_num is None
        assert item.use_cycle_unit is None
        assert item.use_times is None

    def test_cycle_mode_save_keeps_values(self):
        """按次口径照旧存得下 —— 别为了修 null 把真值也一起丢了"""
        category = _category('用', mode='on_demand', aggregate='sum')
        unit = _unit(category, '件', '件')
        resp = APIClient().post(
            '/api/wealth/survival/items/',
            self._payload(
                category, unit, name='卫生巾', days_per_unit=None,
                uses_per_unit=10, use_cycle_num=3, use_cycle_unit='day',
                use_times=1,
            ),
            format='json',
        )
        assert resp.status_code == 201, resp.data
        assert resp.data['life_mode'] == 'cycle'
        assert resp.data['days_per_unit_effective'] == 30.0
        item = SurvivalItem.objects.get(id=resp.data['id'])
        assert float(item.use_cycle_num) == 3.0
        assert item.use_cycle_unit == 'day'
        assert float(item.use_times) == 1.0


# ══════════════════════════════════════════════════════════════
# ⑤ 保质期
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestExpiry:

    def test_expiry_caps_recipe_days(self):
        """库存能撑 200 天，但最早一批 10 天后过期 → 实际封顶 10 天"""
        category = _category()
        gram = _unit(category, '克', '克')
        rice = _item(category, '米', 20000, gram, expire_date=TODAY + timedelta(days=10))
        recipe = SurvivalRecipe.objects.create(
            user_id=1, category=category, name='一餐', meals_per_day=1,
        )
        _line(recipe, rice, 100)  # 200 餐 ÷ 1 餐/天 = 200 天（未封顶时）

        row = calc.compute_recipe(recipe, TODAY)
        assert row['expiry_cap_days'] == 10
        assert row['capped_by_expiry'] is True
        assert row['days']['likely'] == 10.0

    def test_no_expiry_means_no_cap(self):
        category = _category(name='穿', mode='depreciation', aggregate='min')
        piece = _unit(category, '件', '件')
        _item(category, '大衣', 1, piece, days_per_unit=100)
        result = calc.compute_category(category, list(category.items.all()), [], TODAY)
        assert result['days']['likely'] == 100.0

    def test_expired_items_are_excluded(self):
        """已过期 = 不可用 —— 算进去等于自欺欺人"""
        category = _category(name='用', mode='on_demand', aggregate='sum')
        piece = _unit(category, '件', '件')
        _item(category, '过期饼干', 10, piece, days_per_unit=5, status='expired')
        result = calc.compute_category(category, list(category.items.all()), [], TODAY)
        assert result['days']['likely'] is None
        assert result['usable_item_count'] == 0


# ══════════════════════════════════════════════════════════════
# ⑥ 算不出来就说算不出来
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestHonestGaps:

    def test_missing_days_per_unit_returns_none(self):
        category = _category(name='用', mode='on_demand', aggregate='sum')
        piece = _unit(category, '件', '件')
        _item(category, '纸巾', 10, piece)  # 没填单件可用天数
        result = calc.compute_category(category, list(category.items.all()), [], TODAY)
        assert result['expected'] is None
        assert result['expected'] != 0
        assert calc.ISSUE_NO_DAYS_PER_UNIT in [i['code'] for i in result['issues']]

    def test_items_without_recipe_are_reported(self):
        """有库存却没编进配方 —— 不是 0 天，是「还没告诉系统你怎么吃」"""
        category = _category()
        gram = _unit(category, '克', '克')
        _item(category, '米', 5000, gram)
        result = calc.compute_category(category, list(category.items.all()), [], TODAY)
        assert result['expected'] is None
        assert calc.ISSUE_NO_RECIPE in [i['code'] for i in result['issues']]

    def test_orphan_item_is_not_silently_swallowed(self):
        """编了库存却没进配方的食材要点名出来 —— 看不见的数据比错的数据更危险"""
        category = _category()
        gram = _unit(category, '克', '克')
        rice = _item(category, '米', 5000, gram)
        _item(category, '面粉', 2000, gram)   # 没进配方
        recipe = SurvivalRecipe.objects.create(
            user_id=1, category=category, name='一餐', meals_per_day=3,
        )
        _line(recipe, rice, 100)

        result = calc.compute_category(category, list(category.items.all()), [recipe], TODAY)
        orphan = [i for i in result['issues'] if i['code'] == calc.ISSUE_ORPHAN_ITEM]
        assert orphan
        assert '面粉' in orphan[0]['items']


# ══════════════════════════════════════════════════════════════
# ⑦ 零食
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSnack:

    def test_snack_does_not_feed_the_meal_clock(self):
        """零食顶不了一顿饭：单独统计，不混进「能撑多少顿」"""
        category = _category()
        gram = _unit(category, '克', '克')
        piece = _unit(category, '包', '包')
        rice = _item(category, '米', 900, gram)
        _item(category, '巧克力', 10, piece, satiety='snack', days_per_unit=2)
        recipe = SurvivalRecipe.objects.create(
            user_id=1, category=category, name='一餐', meals_per_day=3,
        )
        _line(recipe, rice, 100)  # 9 餐 ÷ 3 = 3 天

        result = calc.compute_category(category, list(category.items.all()), [recipe], TODAY)
        assert result['days']['likely'] == 3.0
        assert result['snack_days'] == 20.1   # 10 包 × 2 天，走三档后的期望值


# ══════════════════════════════════════════════════════════════
# ⑧ 分派只看 consume_mode，不看类别名
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestModeDispatch:

    def test_renaming_category_does_not_break_algorithm(self):
        """把「吃」改名成「口粮」仍然按配餐算 —— 算法不认名字"""
        category = _category(name='口粮', mode='meal', aggregate='min')
        gram = _unit(category, '克', '克')
        rice = _item(category, '米', 900, gram)
        recipe = SurvivalRecipe.objects.create(
            user_id=1, category=category, name='一餐', meals_per_day=3,
        )
        _line(recipe, rice, 100)

        result = calc.compute_category(category, list(category.items.all()), [recipe], TODAY)
        assert result['days']['likely'] == 3.0
        assert result['recipes']

    def test_daily_rate_mode_ignores_recipes(self):
        """按需消耗类不看配方，只看「单件可用天数」"""
        category = _category(name='用', mode='on_demand', aggregate='sum')
        piece = _unit(category, '件', '件')
        _item(category, '笔记本', 3, piece, days_per_unit=60)
        result = calc.compute_category(category, list(category.items.all()), [], TODAY)
        assert result['days']['likely'] == 180.0


# ══════════════════════════════════════════════════════════════
# ⑨ 短板 / 瓶颈 / 覆盖率
# ══════════════════════════════════════════════════════════════

class TestBottleneck:

    def test_asset_is_the_bottleneck(self):
        assert calc.classify_bottleneck(41.0, 486.0, 0.8) == 'asset'

    def test_cash_is_the_bottleneck(self):
        assert calc.classify_bottleneck(400.0, 100.0, 0.8) == 'cash'

    def test_close_values_are_balanced(self):
        """100 天 vs 105 天说「瓶颈在物」只会让人去补一件根本不缺的东西"""
        assert calc.classify_bottleneck(100.0, 105.0, 0.8) == 'balanced'

    def test_missing_side_falls_to_the_other(self):
        assert calc.classify_bottleneck(None, 100.0, 0.8) == 'cash'
        assert calc.classify_bottleneck(100.0, None, 0.8) == 'asset'
        assert calc.classify_bottleneck(None, None, 0.8) == 'balanced'

    def test_cash_days_reuse_emergency_months(self):
        assert calc.cash_days_from_months(16.2) == 486.0
        assert calc.cash_days_from_months(None) is None

    def test_find_bottleneck_picks_shortest_category(self):
        rows = [
            {'name': '吃', 'expected': 41.0},
            {'name': '穿', 'expected': 1168.0},
            {'name': '用', 'expected': 118.0},
        ]
        assert calc.find_bottleneck(rows) == ('吃', 41.0)

    def test_find_bottleneck_skips_uncomputable(self):
        rows = [{'name': '吃', 'expected': None}, {'name': '用', 'expected': 118.0}]
        assert calc.find_bottleneck(rows) == ('用', 118.0)
        assert calc.find_bottleneck([{'name': '吃', 'expected': None}]) == (None, None)


class TestCoverage:

    def test_coverage_uses_redemption_window(self):
        row = calc.coverage_pct(41.0, date(2026, 10, 1), date(2029, 9, 30), TODAY)
        assert row['pct'] is not None
        # 今天(2026-09-21)还没进窗口 → 按整段窗口算，含首尾共 1096 天（2028 闰年）
        assert row['remaining_days'] == 1096
        assert row['pct'] > 0

    def test_missing_window_returns_reason(self):
        row = calc.coverage_pct(41.0, None, None, TODAY)
        assert row['pct'] is None
        assert row['reason'] == '赎回期窗口未配置'

    def test_finished_window_returns_reason(self):
        row = calc.coverage_pct(41.0, date(2020, 1, 1), date(2021, 1, 1), TODAY)
        assert row['pct'] is None
        assert row['remaining_days'] == 0


# ══════════════════════════════════════════════════════════════
# ⑩ 服务层：CRUD 保护与综合分析
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestServiceGuards:

    def test_delete_category_with_content_is_refused(self):
        category = _category(name='用', mode='on_demand', aggregate='sum')
        piece = _unit(category, '件', '件')
        _item(category, '纸巾', 1, piece, days_per_unit=10)
        with pytest.raises(ValueError) as exc:
            svc.delete_category(category.id)
        assert '不能直接删除' in str(exc.value)

    def test_delete_empty_category_works(self):
        category = _category(name='空类别', mode='on_demand', aggregate='sum')
        assert svc.delete_category(category.id) == category.id

    def test_delete_unit_in_use_is_refused(self):
        category = _category(name='用', mode='on_demand', aggregate='sum')
        piece = _unit(category, '件', '件')
        _item(category, '纸巾', 1, piece, days_per_unit=10)
        with pytest.raises(ValueError) as exc:
            svc.delete_unit(piece.id)
        assert '仍被' in str(exc.value)

    def test_delete_item_used_by_recipe_is_refused(self):
        category = _category()
        gram = _unit(category, '克', '克')
        rice = _item(category, '米', 900, gram)
        recipe = SurvivalRecipe.objects.create(
            user_id=1, category=category, name='一餐', meals_per_day=3,
        )
        _line(recipe, rice, 100)
        with pytest.raises(ValueError) as exc:
            svc.delete_item(rice.id)
        assert '配方' in str(exc.value)

    def test_seed_is_idempotent(self):
        first = svc.seed_survival_defaults()
        assert first['created_categories'] == len(SURVIVAL_CATEGORY_SEEDS)
        second = svc.seed_survival_defaults()
        assert second['created_categories'] == 0
        assert second['created_units'] == 0

    def test_seed_creates_categories_with_modes(self):
        """五个类别（v3.59.7 起多了「医药」）与各自的消耗模式"""
        svc.seed_survival_defaults()
        modes = {
            c.name: c.consume_mode
            for c in SurvivalCategory.objects.filter(user_id=1)
        }
        assert modes == {
            '吃': 'meal', '穿': 'depreciation', '用': 'on_demand',
            '数字': 'time_based', '医药': 'on_demand',
        }
        # 配餐类的跨配方口径必须是 min —— 与算法实际行为一致，不谎报
        eat = SurvivalCategory.objects.get(name='吃')
        assert eat.aggregate_mode == 'min'
        # ⚠️ 「用」也必须是 min（v3.59.7 修正，曾经是 sum）：
        #    牙膏用完了，洗发水囤再多也刷不了牙 —— 日用耗材之间是**并列**关系，
        #    不是「米粉与面条都能当一顿饭」那种可替代关系。
        #    用 sum 时一件洗脸巾就能把整类撑到几万天，短板永远不落在它身上，
        #    而错误结果是静默的：那个数看着完全合理。
        use = SurvivalCategory.objects.get(name='用')
        assert use.aggregate_mode == 'min'
        # ⚠️ 「穿」也必须是 min（v3.59.8 修正，曾经是 sum）：
        #    衣物之间是**并列**关系 —— 袜子破了，大衣囤再多也解决不了穿什么出门。
        #    用 sum 时三条睡衣记录相加 = 8760 天，四卡报「能撑 24.1 年」，
        #    而内裤、袜子、外衣、鞋一件都没录；错误结果是静默的，数字看着完全合理。
        wear = SurvivalCategory.objects.get(name='穿')
        assert wear.aggregate_mode == 'min'
        # 医药同理：缺一盒创可贴就是一个缺口，不能被别的东西摊薄
        med = SurvivalCategory.objects.get(name='医药')
        assert med.aggregate_mode == 'min'

    def test_analysis_reports_shortest_and_bottleneck(self):
        svc.seed_survival_defaults()
        eat = SurvivalCategory.objects.get(name='吃')
        gram = SurvivalUnit.objects.get(category=eat, name='克')
        rice = _item(eat, '米', 900, gram)
        recipe = SurvivalRecipe.objects.create(
            user_id=1, category=eat, name='一餐', meals_per_day=3,
        )
        _line(recipe, rice, 100)

        data = svc.get_analysis(reference_date=TODAY)
        assert data['available'] is True
        assert data['shortest_category'] == '吃'
        # 短板看**期望值**（不是最可能值）：9 餐 → 4.5 / 3 / 2.25 天 → E = 3.1
        assert data['shortest_days'] == 3.1
        assert data['overall']['days']['likely'] == 3.0
        assert data['overall']['expected'] == 3.1
        # 还没有资产快照 → 钱这条腿算不出来，原因要写清楚
        assert data['cash']['days'] is None
        assert data['cash']['basis']
        assert data['coverage']['reason'] == '赎回期窗口未配置'

    def test_analysis_lists_issues_with_category(self):
        category = _category()
        gram = _unit(category, '克', '克')
        _item(category, '米', 500, gram)
        data = svc.get_analysis(reference_date=TODAY)
        assert data['issues']
        assert data['issues'][0]['category'] == '吃'


# ══════════════════════════════════════════════════════════════
# ⑪ 接口
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSurvivalApis:
    """列表端点一律裸数组 —— 被全局分页包成 {count, results} 前端会静默变空"""

    def setup_method(self):
        self.client = APIClient()

    def test_category_list_is_bare_array(self):
        _category()
        resp = self.client.get('/api/wealth/survival/categories/')
        assert resp.status_code == 200
        assert isinstance(resp.data, list)
        assert resp.data[0]['name'] == '吃'
        assert resp.data[0]['aggregate_mode_effective'] == 'min'

    def test_unit_list_is_bare_array(self):
        category = _category()
        _unit(category, '克', '克')
        resp = self.client.get('/api/wealth/survival/units/')
        assert resp.status_code == 200
        assert isinstance(resp.data, list)

    def test_item_list_is_bare_array(self):
        category = _category()
        gram = _unit(category, '克', '克')
        _item(category, '米', 500, gram)
        resp = self.client.get('/api/wealth/survival/items/')
        assert resp.status_code == 200
        assert isinstance(resp.data, list)
        assert resp.data[0]['unit_name'] == '克'

    def test_recipe_list_carries_lines(self):
        category = _category()
        gram = _unit(category, '克', '克')
        rice = _item(category, '米', 500, gram)
        recipe = SurvivalRecipe.objects.create(
            user_id=1, category=category, name='一餐', meals_per_day=3,
        )
        _line(recipe, rice, 100)
        resp = self.client.get('/api/wealth/survival/recipes/')
        assert resp.status_code == 200
        assert isinstance(resp.data, list)
        assert resp.data[0]['lines'][0]['role_label'] == '主食位'

    def test_metrics_meta_is_bare_array(self):
        resp = self.client.get('/api/wealth/survival/metrics/meta/')
        assert resp.status_code == 200
        assert isinstance(resp.data, list)
        assert len(resp.data) == len(SURVIVAL_METRIC_NOTES)
        for item in resp.data:
            assert item['label']
            assert item['formula']
            assert item['note']
            # 前端按纯文本渲染 —— 星号会原样显示（v3.58.24 踩过的坑）
            assert not any('*' in line for line in item['note'])

    def test_meta_endpoint_exposes_enums(self):
        resp = self.client.get('/api/wealth/survival/meta/')
        assert resp.status_code == 200
        assert resp.data['consume_modes']
        assert resp.data['roles']
        assert resp.data['scenarios'] == ['optimistic', 'likely', 'pessimistic']
        assert resp.data['meal_scenarios']['likely'] == 3

    def test_analysis_endpoint(self):
        category = _category()
        gram = _unit(category, '克', '克')
        rice = _item(category, '米', 900, gram)
        recipe = SurvivalRecipe.objects.create(
            user_id=1, category=category, name='一餐', meals_per_day=3,
        )
        _line(recipe, rice, 100)
        resp = self.client.get('/api/wealth/survival/analysis/?date=2026-09-21')
        assert resp.status_code == 200
        assert resp.data['available'] is True
        assert resp.data['categories'][0]['days']['likely'] == 3.0
        assert resp.data['categories'][0]['recipes'][0]['meals'] == 9

    def test_seed_endpoint(self):
        resp = self.client.post('/api/wealth/survival/categories/seed/', {}, format='json')
        assert resp.status_code == 200
        assert len(resp.data['categories']) == len(SURVIVAL_CATEGORY_SEEDS)

    def test_create_category_via_api(self):
        resp = self.client.post(
            '/api/wealth/survival/categories/',
            {'name': '药', 'consume_mode': 'on_demand', 'aggregate_mode': 'sum'},
            format='json',
        )
        assert resp.status_code == 201
        assert resp.data['name'] == '药'

    def test_duplicate_category_name_is_400(self):
        _category()
        resp = self.client.post(
            '/api/wealth/survival/categories/',
            {'name': '吃', 'consume_mode': 'meal', 'aggregate_mode': 'min'},
            format='json',
        )
        assert resp.status_code == 400

    def test_duplicate_unit_name_in_category_is_400(self):
        category = _category()
        _unit(category, '克', '克')
        resp = self.client.post(
            '/api/wealth/survival/units/',
            {'category_id': category.id, 'name': '克', 'base_unit': '克', 'to_base_rate': 1},
            format='json',
        )
        assert resp.status_code == 400

    def test_item_with_unit_from_other_category_is_400(self):
        eat = _category(name='吃', mode='meal', aggregate='min')
        wear = _category(name='穿', mode='depreciation', aggregate='sum')
        piece = _unit(wear, '件', '件')
        resp = self.client.post(
            '/api/wealth/survival/items/',
            {'category_id': eat.id, 'name': '米', 'quantity': 1, 'unit_id': piece.id},
            format='json',
        )
        assert resp.status_code == 400

    def test_recipe_with_foreign_item_is_400(self):
        eat = _category(name='吃', mode='meal', aggregate='min')
        wear = _category(name='穿', mode='depreciation', aggregate='sum')
        piece = _unit(wear, '件', '件')
        coat = _item(wear, '大衣', 1, piece, days_per_unit=100)
        resp = self.client.post(
            '/api/wealth/survival/recipes/',
            {
                'category_id': eat.id, 'name': '一餐', 'meals_per_day': 3,
                'lines': [{'item_id': coat.id, 'role': 'staple', 'quantity_per_serving': '1'}],
            },
            format='json',
        )
        assert resp.status_code == 400

    def test_recipe_without_staple_is_400(self):
        """没有主食的配方算不出能撑多少顿 —— 与其算出个空，不如拦下来"""
        category = _category()
        ml = _unit(category, '毫升', '毫升')
        water = _item(category, '水', 3000, ml, satiety='water')
        resp = self.client.post(
            '/api/wealth/survival/recipes/',
            {
                'category_id': category.id, 'name': '只有水', 'meals_per_day': 3,
                'lines': [{'item_id': water.id, 'role': 'required', 'quantity_per_serving': '500'}],
            },
            format='json',
        )
        assert resp.status_code == 400

    def test_recipe_replaces_lines_on_update(self):
        """配方行整体替换：加一行、改一行、删一行在重建语义下都是一次写"""
        category = _category()
        gram = _unit(category, '克', '克')
        rice = _item(category, '米', 900, gram)
        noodle = _item(category, '面', 600, gram)
        recipe = SurvivalRecipe.objects.create(
            user_id=1, category=category, name='一餐', meals_per_day=3,
        )
        _line(recipe, rice, 100)

        resp = self.client.patch(
            f'/api/wealth/survival/recipes/{recipe.id}/',
            {'lines': [
                {'item_id': rice.id, 'role': 'staple', 'quantity_per_serving': '100'},
                {'item_id': noodle.id, 'role': 'staple', 'quantity_per_serving': '100'},
            ]},
            format='json',
        )
        assert resp.status_code == 200
        assert len(resp.data['lines']) == 2
        assert recipe.lines.count() == 2

    def test_delete_category_with_content_is_400(self):
        category = _category()
        gram = _unit(category, '克', '克')
        _item(category, '米', 500, gram)
        resp = self.client.delete(f'/api/wealth/survival/categories/{category.id}/')
        assert resp.status_code == 400
        assert '不能直接删除' in resp.data['detail']

    def test_delete_unit_in_use_is_400(self):
        category = _category()
        gram = _unit(category, '克', '克')
        _item(category, '米', 500, gram)
        resp = self.client.delete(f'/api/wealth/survival/units/{gram.id}/')
        assert resp.status_code == 400

    def test_delete_recipe_works(self):
        category = _category()
        gram = _unit(category, '克', '克')
        rice = _item(category, '米', 500, gram)
        recipe = SurvivalRecipe.objects.create(
            user_id=1, category=category, name='一餐', meals_per_day=3,
        )
        _line(recipe, rice, 100)
        resp = self.client.delete(f'/api/wealth/survival/recipes/{recipe.id}/')
        assert resp.status_code == 200
        assert SurvivalRecipe.objects.filter(id=recipe.id).count() == 0
        # 删配方不该连带删掉食材
        assert SurvivalItem.objects.filter(id=rice.id).count() == 1

    def test_item_create_and_update(self):
        category = _category(name='用', mode='on_demand', aggregate='sum')
        piece = _unit(category, '件', '件')
        resp = self.client.post(
            '/api/wealth/survival/items/',
            {
                'category_id': category.id, 'name': '纸巾', 'quantity': '10',
                'unit_id': piece.id, 'satiety': '', 'days_per_unit': '10',
            },
            format='json',
        )
        assert resp.status_code == 201
        item_id = resp.data['id']

        resp = self.client.patch(
            f'/api/wealth/survival/items/{item_id}/',
            {'quantity': '20'},
            format='json',
        )
        assert resp.status_code == 200
        assert resp.data['quantity'] == 20.0

    def test_negative_quantity_is_400(self):
        category = _category(name='用', mode='on_demand', aggregate='sum')
        piece = _unit(category, '件', '件')
        resp = self.client.post(
            '/api/wealth/survival/items/',
            {'category_id': category.id, 'name': '纸巾', 'quantity': '-1', 'unit_id': piece.id},
            format='json',
        )
        assert resp.status_code == 400
