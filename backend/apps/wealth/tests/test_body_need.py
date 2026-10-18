"""身上之物 · 接口测试（v3.62.4）

覆盖范围：部位主数据的增删改查与「有引用不许删」、位的新增/编辑/删除、
三把尺子的正交性、两个关联源互斥、`satisfaction_blank_reason` 的两态、
顶部计数与清单筛选同源、口径元信息的键名清单。

刻意**不重复** `test_property.py` 的用例 —— 那边钉的是「已买回来的东西」，
这边钉的是「还没找到的东西」，两者字段与产出口都不同。

五条最容易静默失效的纪律，各有专门用例：

    ① **空 ≠ 凑合**：`satisfaction` 为空时，`no_item`（还没东西在用）与
       `unrated`（有东西在用但没评过）必须分得开。合并显示看起来完全正常。
    ② **两个关联源互斥**：同时挂两件时 400；**PATCH 只送一个**也要判 ——
       只看入参不合并原值，就会出现「一行挂着两件、界面只显示一件」。
    ③ **计数与筛选同源**：顶部念「还有 N 件没搞定」、点进去必须正好 N 行。
       两处各写一遍判据，就会出现「念 5 件、看到 3 行」且没人会发现。
    ④ **裸数组**：被 DRF 全局分页包成 `{count, results}` 后，前端按数组消费
       会静默显示为空（项目硬坑③）—— 界面上看起来就是「一条都没有」。
    ⑤ **口径元信息的键名**：气泡组件按 key 取值，键名写错**静默不渲染**
       —— 界面上什么都不会出错，只是那行说明不见了（硬坑⑪）。
"""

import pytest
from rest_framework.test import APIClient

from apps.wealth.constants import (
    BODY_FIND_STATUS_CHOICES,
    BODY_SATISFACTION_CHOICES,
)
from apps.wealth.models import (
    SurvivalCategory,
    SurvivalItem,
    WealthBodyNeed,
    WealthBodyPart,
    WealthProperty,
    WealthPropertyCategory,
)

PARTS = '/api/wealth/body/parts/'
PART_SEED = '/api/wealth/body/parts/seed/'
NEEDS = '/api/wealth/body/needs/'
SUMMARY = '/api/wealth/body/summary/'
META = '/api/wealth/body/meta/'


# ──────────────────────────────────────────────────────────────
# 造数
# ──────────────────────────────────────────────────────────────

def _part(api, name='眼', **extra):
    data = {'name': name}
    data.update(extra)
    response = api.post(PARTS, data, format='json')
    assert response.status_code == 201, response.json()
    return response.json()['id']


def _need(api, part_id, name='眼镜', **overrides):
    data = {'part_id': part_id, 'name': name}
    data.update(overrides)
    response = api.post(NEEDS, data, format='json')
    assert response.status_code == 201, response.json()
    return response.json()


def _property(name='宝岛眼镜'):
    """一件物件资产 —— 注意它是**已经买回来的**，与「位」不是一回事。"""
    category = WealthPropertyCategory.objects.create(user_id=1, name='其他')
    return WealthProperty.objects.create(
        user_id=1, category=category, name=name, status='in_use', condition='normal',
    )


def _survival_item(name='匹克小白鞋'):
    """一条物品清单 —— 鞋衣面霜在这边，眼镜在物件资产那边（双源的真实来由）。"""
    category, _ = SurvivalCategory.objects.get_or_create(user_id=1, name='穿')
    return SurvivalItem.objects.create(user_id=1, category=category, name=name)


# ══════════════════════════════════════════════════════════════
# ① 部位
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestBodyPart:
    def test_create_and_list_in_sort_order(self):
        api = APIClient()
        _part(api, '眼', sort_order=0)
        _part(api, '脚', sort_order=1)
        rows = api.get(PARTS).json()
        assert isinstance(rows, list)
        assert [r['name'] for r in rows] == ['眼', '脚']
        # 新建的部位下还没有位 —— 这个数就是「为什么它删得掉」
        assert all(r['need_count'] == 0 for r in rows)

    def test_duplicate_name_is_rejected(self):
        """同名部位必须 400 —— 唯一约束在 `Meta.constraints` 里，
        DRF 不会自动替我验（项目已踩三次），所以服务层手写了这条检查。"""
        api = APIClient()
        _part(api, '眼')
        response = api.post(PARTS, {'name': '眼'}, format='json')
        assert response.status_code == 400
        assert '眼' in response.json()['detail']

    def test_blank_name_is_rejected(self):
        api = APIClient()
        assert api.post(PARTS, {'name': ''}, format='json').status_code == 400

    def test_delete_part_in_use_is_400_with_actionable_hint(self):
        """🔴 还有位引用时不许删 —— 400 + 把数量报出来让人能照做。

        级联删除会让「删掉一个建错的空部位」与「删掉整个部位下的所有位」
        走同一个按钮，代价完全不对称且不可逆。
        """
        api = APIClient()
        part_id = _part(api, '眼')
        _need(api, part_id, '眼镜')
        response = api.delete(f'{PARTS}{part_id}/')
        assert response.status_code == 400
        assert '1' in response.json()['detail']
        assert WealthBodyPart.objects.filter(id=part_id).exists()

    def test_delete_empty_part_ok(self):
        api = APIClient()
        part_id = _part(api, '耳')
        assert api.delete(f'{PARTS}{part_id}/').status_code == 200
        assert not WealthBodyPart.objects.filter(id=part_id).exists()

    def test_seed_creates_parts_only_never_needs(self):
        """seed **只建部位，不预设任何位** —— 位是用户自己的数据，系统不代猜。

        ⚠️ 那条 6 条位的 seed 在**迁移**里跑一次（`--no-migrations` 的测试库
        根本不跑它），接口这个 seed 一个字都不该写进 `wealth_body_need`。
        """
        api = APIClient()
        result = api.post(PART_SEED, {}, format='json').json()
        assert result['created'] == 11
        assert len(result['parts']) == 11
        assert WealthBodyNeed.objects.count() == 0

    def test_seed_is_idempotent(self):
        api = APIClient()
        api.post(PART_SEED, {}, format='json')
        again = api.post(PART_SEED, {}, format='json').json()
        assert again['created'] == 0
        assert again['skipped'] == 11
        assert WealthBodyPart.objects.count() == 11

    def test_seed_without_overwrite_keeps_user_edits(self):
        """`overwrite` 为假时**不碰**用户改过的说明与排序。"""
        api = APIClient()
        api.post(PART_SEED, {}, format='json')
        part_id = api.get(PARTS).json()[0]['id']
        api.patch(f'{PARTS}{part_id}/', {'note': '我自己写的'}, format='json')
        api.post(PART_SEED, {}, format='json')
        row = next(r for r in api.get(PARTS).json() if r['id'] == part_id)
        assert row['note'] == '我自己写的'


# ══════════════════════════════════════════════════════════════
# ② 位的增删改与三把尺子
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestBodyNeedCrud:
    def test_list_is_bare_array(self):
        """🔴 裸数组 —— 被全局分页包住后前端按数组消费会**静默显示为空**。"""
        api = APIClient()
        part_id = _part(api, '眼')
        _need(api, part_id, '眼镜')
        rows = api.get(NEEDS).json()
        assert isinstance(rows, list)
        assert rows[0]['name'] == '眼镜'
        assert rows[0]['part_name'] == '眼'

    def test_default_find_status_is_todo(self):
        api = APIClient()
        row = _need(api, _part(api, '眼'), '眼镜')
        assert row['find_status'] == 'todo'
        assert row['satisfaction'] is None

    def test_unknown_part_is_400_not_500(self):
        api = APIClient()
        response = api.post(NEEDS, {'part_id': 9999, 'name': '眼镜'}, format='json')
        assert response.status_code == 400
        assert '9999' in response.json()['detail']

    def test_blank_name_is_rejected(self):
        api = APIClient()
        part_id = _part(api, '眼')
        assert api.post(NEEDS, {'part_id': part_id, 'name': '  '}, format='json').status_code == 400

    def test_delete_need(self):
        api = APIClient()
        row = _need(api, _part(api, '手'), '护手霜')
        assert api.delete(f'{NEEDS}{row["id"]}/').status_code == 200
        assert WealthBodyNeed.objects.count() == 0

    def test_three_rulers_are_orthogonal(self):
        """🔴 三把尺子**互不推导** —— 四组组合都必须能存下来。

        「已找到 + 凑合」（定了就是它，但用着一般）与
        「寻找中 + 称心」（挺满意，但还想看看有没有更好的）都是**合法状态**，
        不是矛盾数据。若哪天有人给它们加了「联动修正」，这条会红。
        """
        api = APIClient()
        part_id = _part(api, '眼')
        prop = _property()
        combos = [
            ('settled', 'meh', prop.id),      # 定了，但一般
            ('searching', 'good', prop.id),   # 挺满意，但还在看别的
            ('todo', None, None),             # 压根还没有
            ('searching', 'meh', None),       # 在换，但旧的没挂上
        ]
        for index, (status, satis, prop_id) in enumerate(combos):
            row = _need(
                api, part_id, f'眼镜{index}',
                find_status=status, satisfaction=satis, property_id=prop_id,
            )
            assert row['find_status'] == status
            assert row['satisfaction'] == satis


# ══════════════════════════════════════════════════════════════
# ③ 满意留空：两种来由必须分得开
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSatisfactionBlankReason:
    def test_no_item_when_nothing_linked(self):
        """空的来由之一：**还没有任何东西在用**（连关联都没有）。"""
        api = APIClient()
        row = _need(api, _part(api, '手'), '护手霜')
        assert row['satisfaction'] is None
        assert row['satisfaction_blank_reason'] == 'no_item'

    def test_unrated_when_item_linked(self):
        """空的来由之二：**有东西在用，但还没评过** —— 该去评一次，不是没东西。"""
        api = APIClient()
        prop = _property('凑合戴的旧眼镜')
        row = _need(api, _part(api, '眼'), '眼镜', property_id=prop.id)
        assert row['satisfaction'] is None
        assert row['satisfaction_blank_reason'] == 'unrated'

    def test_unrated_also_for_survival_item_link(self):
        """两条关联源都要能触发 `unrated` —— 判据是「有没有挂东西」，
        不是「挂在哪张表」。"""
        api = APIClient()
        item = _survival_item()
        row = _need(api, _part(api, '脚'), '鞋子', survival_item_id=item.id)
        assert row['satisfaction_blank_reason'] == 'unrated'

    def test_blank_reason_is_none_when_rated(self):
        """评过之后**不再需要解释** —— 这时字段是 None，不是空串。"""
        api = APIClient()
        row = _need(api, _part(api, '脚'), '鞋子', satisfaction='meh')
        assert row['satisfaction'] == 'meh'
        assert row['satisfaction_blank_reason'] is None

    def test_blank_is_not_stored_as_meh(self):
        """🔴 空**不落值** —— 库里必须是 NULL，不能被写成 'meh'。

        写成 'meh' 就等于系统替用户说了「凑合」，而他从没这么说过。
        """
        api = APIClient()
        row = _need(api, _part(api, '手'), '护手霜')
        stored = WealthBodyNeed.objects.get(id=row['id'])
        assert stored.satisfaction is None

    def test_empty_string_is_normalized_to_none(self):
        """空串归一成 NULL —— 「空」只许有一种存法。"""
        api = APIClient()
        row = _need(api, _part(api, '手'), '护手霜', satisfaction='')
        assert row['satisfaction'] is None
        assert WealthBodyNeed.objects.get(id=row['id']).satisfaction is None

    def test_satisfaction_can_be_cleared(self):
        """评过之后可以撤掉 —— 所以服务层不能写 `if value is not None`。"""
        api = APIClient()
        row = _need(api, _part(api, '脚'), '鞋子', satisfaction='good')
        response = api.patch(f'{NEEDS}{row["id"]}/', {'satisfaction': None}, format='json')
        assert response.status_code == 200
        assert response.json()['satisfaction'] is None


# ══════════════════════════════════════════════════════════════
# ④ 归属：两个关联源互斥（PATCH 也要判）
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestLinkMutualExclusion:
    def test_linking_both_is_400_and_writes_nothing(self):
        """🔴 一个位最多挂一件 —— 两个都挂时 400，且**库里没有被写**。"""
        api = APIClient()
        part_id = _part(api, '眼')
        prop = _property()
        item = _survival_item()
        response = api.post(NEEDS, {
            'part_id': part_id, 'name': '眼镜',
            'property_id': prop.id, 'survival_item_id': item.id,
        }, format='json')
        assert response.status_code == 400
        assert WealthBodyNeed.objects.count() == 0

    def test_patch_merges_with_existing_link(self):
        """🔴 最阴的一条：PATCH **只送另一个关联字段**时也要判。

        只看入参（`attrs`）不看原值，就会「原挂物件 + 新挂物品清单」两件同时挂上，
        而界面上只显示其中一件 —— 看起来完全正常。
        """
        api = APIClient()
        prop = _property()
        item = _survival_item()
        row = _need(api, _part(api, '眼'), '眼镜', property_id=prop.id)
        response = api.patch(
            f'{NEEDS}{row["id"]}/', {'survival_item_id': item.id}, format='json',
        )
        assert response.status_code == 400
        stored = WealthBodyNeed.objects.get(id=row['id'])
        assert stored.property_id == prop.id
        assert stored.survival_item_id is None

    def test_switching_source_is_allowed(self):
        """换挂另一件是合法的（先清空再挂）—— 互斥不是「不许改」。"""
        api = APIClient()
        prop = _property()
        item = _survival_item()
        row = _need(api, _part(api, '脚'), '鞋子', property_id=prop.id)
        response = api.patch(f'{NEEDS}{row["id"]}/', {
            'property_id': None, 'survival_item_id': item.id,
        }, format='json')
        assert response.status_code == 200
        assert response.json()['linked_kind'] == 'survival_item'
        assert response.json()['linked_name'] == '匹克小白鞋'

    def test_linked_kind_and_name_for_property(self):
        """关联来源与名字由**后端**说清 —— 前端不做三分支判断。"""
        api = APIClient()
        prop = _property('宝岛若昀施耐特眼镜')
        row = _need(api, _part(api, '眼'), '眼镜', property_id=prop.id)
        assert row['linked_kind'] == 'property'
        assert row['linked_kind_label'] == '物件资产'
        assert row['linked_name'] == '宝岛若昀施耐特眼镜'

    def test_unknown_property_is_400(self):
        api = APIClient()
        part_id = _part(api, '眼')
        response = api.post(
            NEEDS, {'part_id': part_id, 'name': '眼镜', 'property_id': 9999},
            format='json',
        )
        assert response.status_code == 400

    def test_deleting_linked_property_keeps_the_need(self):
        """🔴 物件被删 ⇒ 关联变空，**但这一条位还在**（SET_NULL，不是 CASCADE）。

        「我该有一副眼镜」这件事不会因为卖掉旧眼镜就消失 ——
        删掉它等于把「还在找」的认知一起删了。
        """
        api = APIClient()
        prop = _property()
        row = _need(api, _part(api, '眼'), '眼镜', property_id=prop.id)
        prop.delete()
        stored = WealthBodyNeed.objects.get(id=row['id'])
        assert stored.property_id is None
        refreshed = api.get(f'{NEEDS}{row["id"]}/').json()
        assert refreshed['linked_kind'] is None
        assert refreshed['linked_name'] == ''
        # 关联没了 ⇒ 空的来由也**跟着变**（从 unrated 变成 no_item）
        assert refreshed['satisfaction_blank_reason'] == 'no_item'

    def test_deleting_linked_survival_item_keeps_the_need(self):
        api = APIClient()
        item = _survival_item()
        row = _need(api, _part(api, '脚'), '鞋子', survival_item_id=item.id)
        item.delete()
        assert api.get(f'{NEEDS}{row["id"]}/').status_code == 200
        assert api.get(f'{NEEDS}{row["id"]}/').json()['linked_kind'] is None


# ══════════════════════════════════════════════════════════════
# ⑤ 计数与筛选同源
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSummaryAndFilterAgree:
    def _seed_rows(self, api, part_id):
        _need(api, part_id, '甲', find_status='todo')
        _need(api, part_id, '乙', find_status='todo')
        _need(api, part_id, '丙', find_status='searching')
        _need(api, part_id, '丁', find_status='settled')
        _need(api, part_id, '戊', find_status='settled')

    def test_summary_counts(self):
        api = APIClient()
        part_id = _part(api, '眼')
        self._seed_rows(api, part_id)
        data = api.get(SUMMARY).json()
        assert data == {
            'total': 5, 'todo': 2, 'searching': 1, 'settled': 2, 'pending_count': 3,
        }

    def test_pending_count_equals_pending_list_length(self):
        """🔴 顶部念的数与点进去看到的那几行**必须一致**。

        两处各写一遍判据，就会出现「念 5 件、点进去 3 行」
        —— 两个数都对不上，还没人会去查。
        """
        api = APIClient()
        part_id = _part(api, '眼')
        self._seed_rows(api, part_id)
        pending = api.get(NEEDS, {'pending': '1'}).json()
        assert len(pending) == api.get(SUMMARY).json()['pending_count'] == 3
        assert all(r['find_status'] != 'settled' for r in pending)

    def test_filters_are_find_status_and_part_and_search(self):
        api = APIClient()
        eyes = _part(api, '眼', sort_order=0)
        feet = _part(api, '脚', sort_order=1)
        _need(api, eyes, '眼镜', find_status='searching')
        _need(api, feet, '鞋子', find_status='settled')
        assert len(api.get(NEEDS, {'part': eyes}).json()) == 1
        assert len(api.get(NEEDS, {'find_status': 'settled'}).json()) == 1
        assert len(api.get(NEEDS, {'search': '眼镜'}).json()) == 1
        assert api.get(NEEDS, {'search': '眼镜'}).json()[0]['part_name'] == '眼'

    def test_empty_table_returns_zeros_not_null(self):
        """一条都没有时，计数是一个**全 0 的对象**（正确），不是 null（没就绪）。

        两者必须分得开：前者要在页面上正常显示「0 件」，
        后者要显示「请先执行迁移」（表还没建的部署状态）。
        """
        api = APIClient()
        assert api.get(SUMMARY).json()['total'] == 0
        assert api.get(SUMMARY).json()['pending_count'] == 0
        assert api.get(NEEDS).json() == []
        assert api.get(PARTS).json() == []

    def test_read_endpoints_never_seed(self):
        """🔴 读接口**不写库**，全仓也没有「表空就补」的兜底补种。

        迁移里的 seed 只跑一次（`--no-migrations` 的测试库根本不跑它，
        所以这里天然是空表）。这条钉的是：空表时读一圈接口，
        行数必须**还是 0** —— 用户删掉的东西不会自己回来。
        """
        api = APIClient()
        assert WealthBodyNeed.objects.count() == 0
        assert WealthBodyPart.objects.count() == 0
        api.get(NEEDS)
        api.get(SUMMARY)
        api.get(META)
        api.get(PARTS)
        assert WealthBodyNeed.objects.count() == 0
        assert WealthBodyPart.objects.count() == 0


# ══════════════════════════════════════════════════════════════
# ⑥ 口径元信息：键名清单 + 反向钉子
# ══════════════════════════════════════════════════════════════

# 🔴 前端要用的键名，**逐个念出来**（硬坑⑪：键名写错静默不渲染）
REQUIRED_METRIC_KEYS = frozenset({
    'pending_count',   # 顶部那张「还没搞定」的卡 + 它的 ⓘ
    'find_status',     # 三张进度卡共用的 ⓘ + 表格「进度」列
    'satisfaction',    # 表格「满意」列
    'linked_item',     # 表格「用的是哪一件」列
    'wish',            # 表格「想找什么样的」
})

# 被**否决**的维度 —— 一旦出现在 meta 或模型里，说明有人把它们加回来了
REJECTED_BODY_KEYS = frozenset({
    'size_class', 'value_tier', 'importance',      # 体型 / 价值档 / 重要度
    'given_up', 'unwanted', 'skip', 'abandoned',   # 「不想找了」那一档
})


@pytest.mark.django_db
class TestBodyMeta:
    def test_metric_keys_are_all_present(self):
        data = APIClient().get(META).json()
        keys = {item['key'] for item in data['metric_meta']}
        missing = REQUIRED_METRIC_KEYS - keys
        assert not missing, f'前端要的键少了这些：{sorted(missing)}'

    def test_every_metric_meta_has_full_shape(self):
        """气泡组件的字段一个都不能少（少字段 = 渲染不出来，且不报错）。"""
        data = APIClient().get(META).json()
        assert data['metric_meta']
        for item in data['metric_meta']:
            assert set(item) == {
                'key', 'label', 'unit', 'direction', 'formula', 'note', 'bands',
            }
            assert item['note'], f'{item["key"]} 的说明是空的'
            # 本模块**不设绝对判定线** —— 位是你自己列的，几条算多只有你知道
            assert item['bands'] == []
            assert item['direction'] == 'neutral'

    def test_enums_come_from_meta(self):
        """枚举随接口下发、前端零副本 —— 三态 + 三档，一个字都不在前端复写。"""
        data = APIClient().get(META).json()
        assert [(o['value'], o['label']) for o in data['find_statuses']] == [
            ('todo', '待寻'), ('searching', '寻找中'), ('settled', '已找到'),
        ]
        assert [o['value'] for o in data['satisfactions']] == [
            v for v, _ in BODY_SATISFACTION_CHOICES
        ]
        assert len(data['find_statuses']) == len(BODY_FIND_STATUS_CHOICES)

    def test_blank_reasons_carry_both_short_and_label(self):
        """两种来由各给 `short`（格子里的字）与 `label`（悬停的解释）。

        ⚠️ 只给长句的话，前端得自己截短 —— 那是第二份映射，
           改后端文案时它不会被改到，而界面上照旧说得通。
        """
        data = APIClient().get(META).json()
        reasons = {r['value']: r for r in data['blank_reasons']}
        assert set(reasons) == {'no_item', 'unrated'}
        for item in reasons.values():
            assert item['short'] and item['label']
        # 两种空的**说法必须不同** —— 合并成一个「—」就分不出该去补什么
        assert reasons['no_item']['short'] != reasons['unrated']['short']

    def test_rejected_keys_do_not_come_back(self):
        """反向钉子：被否决的维度不许出现在 meta 里。

        「不想找了」会变成兜底桶（同时装「真的不需要」与「暂时懒得找」），
        体型 / 价值档 / 重要度是另外两把尺子 —— 都不属于这里。
        """
        data = APIClient().get(META).json()
        flat = repr(data)
        for key in REJECTED_BODY_KEYS:
            assert key not in flat, f'被否决的键「{key}」又回来了'

    def test_meta_does_not_reuse_property_keys(self):
        """本模块**没有**物件资产那一套键（价格 / 净值 / 状况）——
        两边不是同一种东西，键名也不该长一样。"""
        data = APIClient().get(META).json()
        keys = {item['key'] for item in data['metric_meta']}
        assert not keys & {'in_use_count', 'total_amount', 'in_use_net_value',
                           'scrapped_count', 'current_value', 'condition'}
