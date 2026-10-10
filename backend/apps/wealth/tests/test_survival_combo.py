"""生存资源盘点 · 组合（v3.59.13）

为什么要有这一组用例：

    用户的原话是「燕麦米、绿豆、薏仁、紫米我是**分开登记**的，但烹饪时**一起下锅**」。
    分开登记是库存事实（各自算数量、各自算保质期），「一起下锅」是一次搭配声明。
    系统原本只能靠「在配方里加四行」来表达，而那四行之间没有任何东西说明它们是一锅的。

覆盖（每一条都对应一个「不测就会静默错」的点）：

  ① ⭐ 组内**取最小**（并列缺一不可）—— 四样都要下锅，能煮几顿看最先耗尽的那件
  ② ⭐ 「一行组合」与「展开成四行必配位」**数学等价**（min-of-min = min）——
     钉住它，是为了说明「不展开」是**展示层**的选择，不是算法妥协
  ③ ⭐ 组内**任一件算不出 ⇒ 整行算不出**，且问题要点到**那件物品**的名字；
     ⚠️ 这一条反向也成立：把算不出的那件排除掉，这道菜会**算得更耐吃**
  ④ ⭐ 缺口点名**组内具体物品**（`bottleneck_item` = 「薏仁」），不是组合名
  ⑤ 两类配方行（食材 / 组合）的聚合键**必须唯一** —— 它们来自两张表，
     裸 id 会撞号，撞了就把两条不同的行合并成一条（静默少一条约束）
  ⑥ 只通过组合下锅的食材**不算孤儿**（只数 `item_id` 会把它们全误报成白存）
  ⑦ 组合行挂主食位时对外**求和**（一锅粥一份 = 一顿），内部仍取最小
  ⑧ 组合的删除保护：被配方引用 → 400 可照做；引用它的物品 / 单位 / 类别同样删不掉
  ⑨ 服务层四道校验：空成员 / 重复成员 / 跨类别 / 用量非正
  ⑩ 一件物品**只能挂在一条基准项**上（后端硬拒，且要说得清挂在哪一条）

新表由 conftest 的 session 级 django_db_setup 镜像建表 ——
--no-migrations --reuse-db 下新 managed 表不会自动出现。
"""

from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient

from apps.wealth.models import (
    SurvivalCategory,
    SurvivalCombo,
    SurvivalComboItem,
    SurvivalEssential,
    SurvivalItem,
    SurvivalRecipe,
    SurvivalRecipeComboLine,
    SurvivalRecipeLine,
    SurvivalUnit,
)
from apps.wealth.services import survival_calc as calc
from apps.wealth.services import survival_combo_service as combo_svc
from apps.wealth.services import survival_service as svc

TODAY = date(2026, 9, 21)

COMBO_API = '/api/wealth/survival/combos/'
ESSENTIAL_API = '/api/wealth/survival/essentials/'
RECIPE_API = '/api/wealth/survival/recipes/'


# ──────────────────────────────────────────────────────────────
# 造数
# ──────────────────────────────────────────────────────────────

def _category(name='吃', mode='meal', aggregate='min'):
    return SurvivalCategory.objects.create(
        user_id=1, name=name, consume_mode=mode, aggregate_mode=aggregate,
    )


def _unit(category, name, base_unit=None, rate=1):
    return SurvivalUnit.objects.create(
        user_id=1, category=category, name=name,
        base_unit=base_unit or name, to_base_rate=rate,
    )


def _item(category, name, quantity, unit=None, **extra):
    payload = {
        'user_id': 1, 'category': category, 'name': name,
        'quantity': quantity, 'unit': unit,
        'satiety': extra.pop('satiety', 'filling'),
        'status': extra.pop('status', 'stocked'),
    }
    payload.update(extra)
    return SurvivalItem.objects.create(**payload)


def _combo(category, name, members):
    """members: [(item, 每餐用量)] 或 [(item, 每餐用量, unit)]"""
    combo = SurvivalCombo.objects.create(user_id=1, category=category, name=name)
    for raw in members:
        item, quantity = raw[0], raw[1]
        SurvivalComboItem.objects.create(
            combo=combo, item=item, quantity_per_serving=quantity,
            unit=raw[2] if len(raw) > 2 else None,
        )
    return combo


def _recipe(category, name='早餐', meals_per_day=1):
    return SurvivalRecipe.objects.create(
        user_id=1, category=category, name=name, meals_per_day=meals_per_day,
    )


def _conjee(category, gram):
    """用户那锅杂粮粥：燕麦米 15 顿 / 绿豆 8 顿 / 薏仁 6 顿 / 紫米 10 顿"""
    oats = _item(category, '燕麦米', 600, gram)
    mung = _item(category, '绿豆', 240, gram)
    job = _item(category, '薏仁', 180, gram)
    black = _item(category, '紫米', 300, gram)
    combo = _combo(category, '杂粮粥', [
        (oats, 40), (mung, 30), (job, 30), (black, 30),
    ])
    return combo, {'燕麦米': oats, '绿豆': mung, '薏仁': job, '紫米': black}


def _client():
    return APIClient()


# ══════════════════════════════════════════════════════════════
# ① 组内取最小
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestComboAggregate:
    """四样都要下锅 —— 能煮几顿由**最先耗尽**的那件决定"""

    def test_combo_takes_the_shortest_member(self):
        category = _category()
        gram = _unit(category, '克')
        combo, items = _conjee(category, gram)
        recipe = _recipe(category)
        line = SurvivalRecipeComboLine.objects.create(recipe=recipe, combo=combo)

        row = calc.compute_combo_line(line, TODAY)
        # 15 / 8 / 6 / 10 → 取最小 = 6（薏仁）
        assert row['servings'] == 6
        assert [m['servings'] for m in row['members']] == [15, 8, 6, 10]

    def test_shortest_member_is_named_not_the_combo(self):
        """④ 缺口要点到**那件物品**：显示「杂粮粥不够了」用户不知道去买什么"""
        category = _category()
        gram = _unit(category, '克')
        combo, _ = _conjee(category, gram)
        recipe = _recipe(category)
        line = SurvivalRecipeComboLine.objects.create(recipe=recipe, combo=combo)

        row = calc.compute_combo_line(line, TODAY)
        assert row['bottleneck_item'] == '薏仁'
        assert row['item_name'] == '杂粮粥'   # 行的标题仍是组合名

    def test_recipe_bottleneck_points_at_the_member_item(self):
        """配方层的「短板」同样要落到具体物品上"""
        category = _category()
        gram = _unit(category, '克')
        rice = _item(category, '米粉', 2000, gram)
        combo, _ = _conjee(category, gram)
        recipe = _recipe(category)
        SurvivalRecipeLine.objects.create(
            recipe=recipe, item=rice, role='staple', quantity_per_serving=100,
        )
        SurvivalRecipeComboLine.objects.create(
            recipe=recipe, combo=combo, role='required',
        )

        row = calc.compute_recipe(recipe, TODAY)
        # 主食位 20 顿、必配位（组合）6 顿 → 6 顿
        assert row['staple_servings'] == 20
        assert row['meals'] == 6
        assert row['bottleneck_role'] == 'required'
        assert row['bottleneck_item'] == '薏仁'

    def test_combo_in_staple_position_sums_outward(self):
        """⑦ 对外求和、对内取最小 —— 一锅粥一份 = 一顿，与别的选择相加"""
        category = _category()
        gram = _unit(category, '克')
        rice = _item(category, '米粉', 2000, gram)         # 20 顿
        combo, _ = _conjee(category, gram)                 # 组内 6 顿
        recipe = _recipe(category)
        SurvivalRecipeLine.objects.create(
            recipe=recipe, item=rice, role='staple', quantity_per_serving=100,
        )
        SurvivalRecipeComboLine.objects.create(recipe=recipe, combo=combo, role='staple')

        row = calc.compute_recipe(recipe, TODAY)
        assert row['staple_servings'] == 26     # 20 + 6
        assert row['meals'] == 26


# ══════════════════════════════════════════════════════════════
# ② 「一行组合」与「展开成四行必配位」等价
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestComboEqualsExpansion:
    """钉住等价性：不展开是**展示层**的选择（列表不膨胀、改组合能回溯生效），
    不是算法上的妥协 —— 两者的结论必须一模一样，否则「一行」就是在骗人。"""

    def test_same_meals_as_four_required_lines(self):
        category = _category()
        gram = _unit(category, '克')
        combo, items = _conjee(category, gram)

        combo_recipe = _recipe(category, name='组合版')
        SurvivalRecipeComboLine.objects.create(
            recipe=combo_recipe, combo=combo, role='required',
        )

        expanded = _recipe(category, name='展开版')
        for name, per_serving in (
            ('燕麦米', 40), ('绿豆', 30), ('薏仁', 30), ('紫米', 30),
        ):
            SurvivalRecipeLine.objects.create(
                recipe=expanded, item=items[name], role='required',
                quantity_per_serving=per_serving,
            )

        one = calc.compute_recipe(combo_recipe, TODAY)
        four = calc.compute_recipe(expanded, TODAY)
        assert one['meals'] == four['meals'] == 6
        assert one['required_servings'] == four['required_servings'] == 6
        assert one['trustworthy'] is True and four['trustworthy'] is True


# ══════════════════════════════════════════════════════════════
# ③④ 缺件不许静默：一件算不出 ⇒ 整行算不出，且要点名
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestComboBrokenMember:
    """反向判据：**把算不出的那件排除掉，这道菜会算得更耐吃** ——
    所以绝不允许「忽略它、在剩下几件里取最小」。"""

    def test_one_uncomputable_member_kills_the_line(self):
        category = _category()
        gram = _unit(category, '克')
        oats = _item(category, '燕麦米', 600, gram)
        # 没填单位的物品：算不出「每餐 30 克能供几顿」
        nameless = _item(category, '绿豆', 240, None)
        combo = _combo(category, '杂粮粥', [(oats, 40), (nameless, 30)])
        recipe = _recipe(category)
        line = SurvivalRecipeComboLine.objects.create(recipe=recipe, combo=combo)

        row = calc.compute_combo_line(line, TODAY)
        assert row['servings'] is None              # 整行算不出
        codes = [issue['code'] for issue in row['issues']]
        assert calc.ISSUE_NO_UNIT in codes
        # 点名到具体那件，而不是「这个组合有问题」
        assert any(issue.get('item') == '绿豆' for issue in row['issues'])

    def test_recipe_becomes_untrustworthy_when_a_member_breaks(self):
        category = _category()
        gram = _unit(category, '克')
        rice = _item(category, '米粉', 2000, gram)
        nameless = _item(category, '绿豆', 240, None)
        combo = _combo(category, '杂粮粥', [(nameless, 30)])
        recipe = _recipe(category)
        SurvivalRecipeLine.objects.create(
            recipe=recipe, item=rice, role='staple', quantity_per_serving=100,
        )
        SurvivalRecipeComboLine.objects.create(
            recipe=recipe, combo=combo, role='required',
        )

        row = calc.compute_recipe(recipe, TODAY)
        assert row['trustworthy'] is False
        # 必配位那一行算不出 ⇒ 它不进 required_min，但**问题在 issues 里**
        # ⚠️ 这正是「required_line_count > 0 而 required_servings 为 None」的第二种来由
        assert row['required_line_count'] == 1
        assert calc.ISSUE_NO_UNIT in [issue['code'] for issue in row['issues']]

    def test_expiry_cap_is_the_earliest_member(self):
        """整锅粥受**最早到期**的那件原料约束"""
        category = _category()
        gram = _unit(category, '克')
        combo, items = _conjee(category, gram)
        items['绿豆'].expire_date = TODAY + timedelta(days=5)
        items['绿豆'].save()
        recipe = _recipe(category)
        line = SurvivalRecipeComboLine.objects.create(recipe=recipe, combo=combo)

        row = calc.compute_combo_line(line, TODAY)
        assert row['expire_cap_days'] == 5

    def test_empty_combo_reports_instead_of_vanishing(self):
        """⑤ 空组合不能静默当成「无约束」—— 那一行看着像配好了，实际什么都没约束"""
        category = _category()
        combo = SurvivalCombo.objects.create(user_id=1, category=category, name='空壳')
        recipe = _recipe(category)
        line = SurvivalRecipeComboLine.objects.create(recipe=recipe, combo=combo)

        row = calc.compute_combo_line(line, TODAY)
        assert row['servings'] is None
        assert [issue['code'] for issue in row['issues']] == [calc.ISSUE_EMPTY_COMBO]


# ══════════════════════════════════════════════════════════════
# ⑤⑥ 聚合键唯一 / 孤儿判定
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestComboLineKeys:
    """两类行来自**两张表**，id 空间各自独立 —— 裸 id 会撞号，
    而撞号的后果是「两条不同的行被合并成一条」，静默少一条约束。"""

    def test_line_keys_are_unique_across_tables(self):
        category = _category()
        gram = _unit(category, '克')
        combo, _ = _conjee(category, gram)
        rice = _item(category, '米粉', 2000, gram)
        recipe = _recipe(category)
        SurvivalRecipeLine.objects.create(
            recipe=recipe, item=rice, role='staple', quantity_per_serving=100,
        )
        SurvivalRecipeComboLine.objects.create(
            recipe=recipe, combo=combo, role='required',
        )

        row = calc.compute_recipe(recipe, TODAY)
        keys = [line['line_key'] for line in row['lines']]
        assert len(keys) == len(set(keys)) == 2
        # 键由「种类 + id」拼成 —— 两张表的 id 撞号时也不会被合并成一条
        assert {line['line_kind'] for line in row['lines']} == {'item', 'combo'}
        for line in row['lines']:
            assert line['line_key'] == f"{line['line_kind']}-{line['line_id']}"

    def test_items_used_only_through_combos_are_not_orphans(self):
        """⑥ 只通过组合下锅的食材**不是**「白存」——
        只数 `item_id` 会把绿豆、薏仁、紫米全误报成孤儿，而它们正是本次要做的东西"""
        category = _category()
        gram = _unit(category, '克')
        combo, _ = _conjee(category, gram)
        recipe = _recipe(category)
        SurvivalRecipeComboLine.objects.create(recipe=recipe, combo=combo, role='staple')

        row = calc.compute_category(category, list(category.items.all()), [recipe], TODAY)
        codes = [issue['code'] for issue in row['issues']]
        assert calc.ISSUE_ORPHAN_ITEM not in codes


# ══════════════════════════════════════════════════════════════
# ⑨ 服务层校验
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestComboServiceGuards:
    """四道校验一条都不能省 —— 缺任何一条都会写出一个「界面看着配好了」的坏组合"""

    def test_empty_members_rejected(self):
        category = _category()
        with pytest.raises(ValueError, match='至少'):
            combo_svc.create_combo({
                'category_id': category.id, 'name': '空的', 'members': [],
            })

    def test_duplicate_member_rejected(self):
        """重复成员是一种**隐性倍率**：两行长得一样，用量却翻倍了"""
        category = _category()
        gram = _unit(category, '克')
        mung = _item(category, '绿豆', 600, gram)
        with pytest.raises(ValueError, match='出现了两次'):
            combo_svc.create_combo({
                'category_id': category.id, 'name': '双份绿豆',
                'members': [
                    {'item_id': mung.id, 'quantity_per_serving': 30},
                    {'item_id': mung.id, 'quantity_per_serving': 30},
                ],
            })

    def test_cross_category_member_rejected(self):
        """跨类别成员 = 「吃」的组合里混进「用」类的物品 ——
        与配方行那条校验同源，两边判据必须一样"""
        eat = _category(name='吃')
        use = _category(name='用', mode='on_demand', aggregate='sum')
        piece = _unit(use, '件')
        tissue = _item(use, '纸巾', 10, piece)
        with pytest.raises(ValueError, match='不属于'):
            combo_svc.create_combo({
                'category_id': eat.id, 'name': '乱搭',
                'members': [{'item_id': tissue.id, 'quantity_per_serving': 1}],
            })

    def test_non_positive_quantity_rejected(self):
        category = _category()
        gram = _unit(category, '克')
        mung = _item(category, '绿豆', 600, gram)
        with pytest.raises(ValueError, match='大于零'):
            combo_svc.create_combo({
                'category_id': category.id, 'name': '零用量',
                'members': [{'item_id': mung.id, 'quantity_per_serving': 0}],
            })

    def test_combo_can_live_in_any_category(self):
        """用户拍板：**其他类别也要组合**（不是只给「吃」做）"""
        use = _category(name='用', mode='on_demand', aggregate='sum')
        piece = _unit(use, '件')
        a = _item(use, '牙膏', 2, piece)
        b = _item(use, '牙刷', 1, piece)
        row = combo_svc.create_combo({
            'category_id': use.id, 'name': '洗漱包',
            'members': [
                {'item_id': a.id, 'quantity_per_serving': 1},
                {'item_id': b.id, 'quantity_per_serving': 1},
            ],
        })
        assert row['member_count'] == 2
        assert row['category_id'] == use.id


# ══════════════════════════════════════════════════════════════
# ⑧ 删除保护
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestComboDeleteGuards:
    def test_combo_in_use_cannot_be_deleted(self):
        category = _category()
        gram = _unit(category, '克')
        combo, _ = _conjee(category, gram)
        recipe = _recipe(category)
        SurvivalRecipeComboLine.objects.create(recipe=recipe, combo=combo, role='staple')

        with pytest.raises(ValueError, match='还被 1 个配方引用'):
            combo_svc.delete_combo(combo.id)

    def test_free_combo_can_be_deleted(self):
        category = _category()
        gram = _unit(category, '克')
        combo, _ = _conjee(category, gram)
        assert combo_svc.delete_combo(combo.id) == combo.id
        assert SurvivalCombo.objects.filter(id=combo.id).count() == 0
        # 删组合不该连带删掉里面的物品（那是用户的资产）
        assert SurvivalItem.objects.filter(category=category).count() == 4

    def test_item_used_by_combo_cannot_be_deleted(self):
        """物品还被组合引用时删不掉 —— 漏了这一处会抛 ProtectedError 变成 500"""
        category = _category()
        gram = _unit(category, '克')
        combo, items = _conjee(category, gram)
        with pytest.raises(ValueError, match='组合引用'):
            svc.delete_item(items['绿豆'].id)

    def test_unit_used_by_combo_cannot_be_deleted(self):
        """成员显式指定用量单位时，那个单位也算「被引用」——
        漏了这一处，`unit.delete()` 会抛 ProtectedError 变成 500"""
        category = _category()
        gram = _unit(category, '克')
        spoon = _unit(category, '小勺')
        mung = _item(category, '绿豆', 240, gram)
        _combo(category, '杂粮粥', [(mung, 3, spoon)])

        with pytest.raises(ValueError, match='组合成员'):
            svc.delete_unit(spoon.id)

    def test_category_with_combo_cannot_be_deleted(self):
        """删类别要先清空 —— 否则会静默连带删掉组合，而组合可能正被配方引用"""
        category = _category()
        gram = _unit(category, '克')
        _conjee(category, gram)
        items = SurvivalItem.objects.filter(category=category)
        assert items.count() == 4
        with pytest.raises(ValueError, match='个组合'):
            svc.delete_category(category.id)


# ══════════════════════════════════════════════════════════════
# 接口
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestComboApis:
    def test_list_is_bare_array(self):
        """被全局分页包成 {count, results} 时前端按数组消费会**静默变空**"""
        category = _category()
        gram = _unit(category, '克')
        _conjee(category, gram)
        resp = _client().get(COMBO_API)
        assert resp.status_code == 200
        assert isinstance(resp.data, list)
        assert len(resp.data) == 1
        assert resp.data[0]['member_count'] == 4
        assert resp.data[0]['members'][0]['item_name'] == '燕麦米'

    def test_create_update_delete_round_trip(self):
        category = _category()
        gram = _unit(category, '克')
        combo, _ = _conjee(category, gram)
        client = _client()

        resp = client.patch(f'{COMBO_API}{combo.id}/', {
            'members': [
                {'item_id': SurvivalItem.objects.get(name='燕麦米').id,
                 'quantity_per_serving': '50'},
            ],
        }, format='json')
        assert resp.status_code == 200
        assert resp.data['member_count'] == 1

        resp = client.delete(f'{COMBO_API}{combo.id}/')
        assert resp.status_code == 200

    def test_duplicate_name_in_category_is_400_not_500(self):
        category = _category()
        gram = _unit(category, '克')
        combo, _ = _conjee(category, gram)
        mung = SurvivalItem.objects.get(name='绿豆')
        resp = _client().post(COMBO_API, {
            'category_id': category.id, 'name': '杂粮粥',
            'members': [{'item_id': mung.id, 'quantity_per_serving': '30'}],
        }, format='json')
        assert resp.status_code == 400
        assert 'name' in resp.data

    def test_cross_category_member_is_400(self):
        eat = _category(name='吃')
        use = _category(name='用', mode='on_demand', aggregate='sum')
        piece = _unit(use, '件')
        tissue = _item(use, '纸巾', 10, piece)
        resp = _client().post(COMBO_API, {
            'category_id': eat.id, 'name': '乱搭',
            'members': [{'item_id': tissue.id, 'quantity_per_serving': '1'}],
        }, format='json')
        assert resp.status_code == 400

    def test_delete_combo_in_use_is_400(self):
        category = _category()
        gram = _unit(category, '克')
        combo, _ = _conjee(category, gram)
        assert _client().post(RECIPE_API, {
            'category_id': category.id, 'name': '早餐', 'meals_per_day': 1,
            'combo_lines': [{'combo_id': combo.id, 'role': 'staple'}],
        }, format='json').status_code == 201

        resp = _client().delete(f'{COMBO_API}{combo.id}/')
        assert resp.status_code == 400
        assert '不能直接删除' in resp.data['detail']

    def test_recipe_accepts_combo_line_and_returns_it(self):
        category = _category()
        gram = _unit(category, '克')
        combo, _ = _conjee(category, gram)
        resp = _client().post(RECIPE_API, {
            'category_id': category.id, 'name': '早餐', 'meals_per_day': 1,
            'combo_lines': [{'combo_id': combo.id, 'role': 'staple'}],
        }, format='json')
        assert resp.status_code == 201
        assert resp.data['combo_line_count'] == 1
        assert resp.data['combo_lines'][0]['combo_name'] == '杂粮粥'

    def test_cross_category_combo_in_recipe_is_400(self):
        eat = _category(name='吃')
        use = _category(name='用', mode='on_demand', aggregate='sum')
        piece = _unit(use, '件')
        a = _item(use, '牙膏', 2, piece)
        combo = _combo(use, '洗漱包', [(a, 1)])

        resp = _client().post(RECIPE_API, {
            'category_id': eat.id, 'name': '早餐', 'meals_per_day': 1,
            'combo_lines': [{'combo_id': combo.id, 'role': 'staple'}],
        }, format='json')
        assert resp.status_code == 400

    def test_same_combo_twice_is_silently_deduped(self):
        """同一组合挂两次 ⇒ 与挂一次完全一样（组合内部没有倍率）。
        静默去重而不是报错：报错只会让人觉得系统在挑刺（DB 的 UNIQUE 会 500）"""
        category = _category()
        gram = _unit(category, '克')
        combo, _ = _conjee(category, gram)
        resp = _client().post(RECIPE_API, {
            'category_id': category.id, 'name': '早餐', 'meals_per_day': 1,
            'combo_lines': [
                {'combo_id': combo.id, 'role': 'staple'},
                {'combo_id': combo.id, 'role': 'required'},
            ],
        }, format='json')
        assert resp.status_code == 201
        assert resp.data['combo_line_count'] == 1

    def test_update_lines_only_keeps_combo_lines(self):
        """只传 `lines` 时组合行必须原样留着 ——
        一律清空会让「懒得传」变成「静默删掉」"""
        category = _category()
        gram = _unit(category, '克')
        rice = _item(category, '米粉', 900, gram)
        combo, _ = _conjee(category, gram)
        recipe = _recipe(category)
        SurvivalRecipeComboLine.objects.create(recipe=recipe, combo=combo, role='staple')

        resp = _client().patch(f'{RECIPE_API}{recipe.id}/', {
            'lines': [{'item_id': rice.id, 'role': 'staple', 'quantity_per_serving': '100'}],
        }, format='json')
        assert resp.status_code == 200
        assert resp.data['combo_line_count'] == 1
        assert recipe.combo_lines.count() == 1

    def test_analysis_serializes_combo_lines(self):
        """⑤ 组合行的 `item_id` 为 None —— 序列化器必须允许为空，
        否则整个首屏分析接口 500，而界面上只是「加载失败」"""
        category = _category()
        gram = _unit(category, '克')
        combo, _ = _conjee(category, gram)
        recipe = _recipe(category)
        SurvivalRecipeComboLine.objects.create(recipe=recipe, combo=combo, role='staple')

        resp = _client().get('/api/wealth/survival/analysis/')
        assert resp.status_code == 200
        rows = resp.data['categories'][0]['recipes']
        combo_rows = [row for row in rows if row['recipe_id'] == recipe.id]
        assert combo_rows, '分析结果里应当有这个配方'
        line = combo_rows[0]['lines'][0]
        assert line['line_kind'] == 'combo'
        assert line['item_id'] is None
        assert line['combo_name'] == '杂粮粥'
        assert line['bottleneck_item'] == '薏仁'
        assert len(line['members']) == 4


# ══════════════════════════════════════════════════════════════
# ⑩ 一件物品只能挂在一条基准项上
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestEssentialSingleOwner:
    """用户的原话：「已经进行过关联状态的物品，不要再出现在待关联列表里面，
    待后面物品越增越多时，列表会出现干扰性」。

    前端据此过滤候选，但**只滤前端等于界面看着干净、数据里仍是重复的** ——
    所以后端也硬拒，且要说清「它挂在哪一条上」。"""

    def _setup(self):
        category = _category(name='用', mode='on_demand', aggregate='sum')
        piece = _unit(category, '件')
        shoes = _item(category, '洞洞鞋', 1, piece, days_per_unit=365)
        return category, piece, shoes

    def test_second_link_is_rejected_with_the_owner_name(self):
        category, piece, shoes = self._setup()
        client = _client()
        assert client.post(ESSENTIAL_API, {
            'name': '鞋', 'category_id': category.id, 'item_ids': [shoes.id],
        }, format='json').status_code == 201

        resp = client.post(ESSENTIAL_API, {
            'name': '袜子', 'category_id': category.id, 'item_ids': [shoes.id],
        }, format='json')
        assert resp.status_code == 400
        assert '鞋' in str(resp.data)
        assert '只能挂在一处' in str(resp.data)

    def test_editing_itself_keeps_its_own_items(self):
        """⚠️ 排除**自己**：不留着自己已勾的那几件，编辑时「取消勾选」都点不到"""
        category, piece, shoes = self._setup()
        client = _client()
        created = client.post(ESSENTIAL_API, {
            'name': '鞋', 'category_id': category.id, 'item_ids': [shoes.id],
        }, format='json')
        resp = client.patch(f"{ESSENTIAL_API}{created.data['essential_id']}/", {
            'item_ids': [shoes.id],
        }, format='json')
        assert resp.status_code == 200
        assert resp.data['item_id'] == shoes.id

    def test_clearing_then_relinking_works(self):
        """先摘掉再挂到别处 —— 这是唯一的合法路径，必须走得通"""
        category, piece, shoes = self._setup()
        client = _client()
        first = client.post(ESSENTIAL_API, {
            'name': '鞋', 'category_id': category.id, 'item_ids': [shoes.id],
        }, format='json')
        assert client.patch(f"{ESSENTIAL_API}{first.data['essential_id']}/", {
            'item_ids': [],
        }, format='json').status_code == 200

        resp = client.post(ESSENTIAL_API, {
            'name': '袜子', 'category_id': category.id, 'item_ids': [shoes.id],
        }, format='json')
        assert resp.status_code == 201

    def test_service_layer_rejects_too(self):
        """服务层那一份是给脚本 / 种子 / 别的调用方用的 —— 只留序列化器会漏"""
        from apps.wealth.services import survival_essential_service as ess_svc

        category, piece, shoes = self._setup()
        owner = SurvivalEssential.objects.create(user_id=1, category=category, name='鞋')
        owner.items.set([shoes])

        with pytest.raises(ValueError, match='只能挂在一处'):
            ess_svc.create_essential({
                'name': '袜子', 'category_id': category.id, 'item_ids': [shoes.id],
            })
