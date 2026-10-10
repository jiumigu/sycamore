"""生存资源盘点 · 一条必需品挂**多件**物品（v3.59.12）

为什么要有这一组用例：

    原来「对应物品」是单个外键，逼用户在「夏季睡衣」和「冬季睡衣」里二选一 ——
    而无论选哪件都答不对「睡衣还能撑多久」：冬天还是没得穿。
    现实里一条基准项常常需要几件**并列**才成立：

        睡衣分夏 / 秋 / 冬    卫生巾分日用 / 夜用    鞋分室内 / 室外

覆盖：
  ① ⭐ 组内多件**取最小**，不求和 —— 这与类别口径同一条判据：
     可替代才求和，并列缺一不可就取最小
  ② ⭐ 三档是**逐档取最小**，不是「挑出最短那件、再抄它的三档」——
     一件有到期日封顶、另一件没有时，两条曲线会交叉
  ③ ⭐ 只要**一件**算不出，整条报 unknown 且 `expected` 回到 None ——
     不拿部分数据充完整答案
  ④ 代表件（顶层 `item_id` / `item_name`）= 正常用量下最短的那件；
     `items` 数组里最短的在前、算不出的排最后
  ⑤ 重复 id 收敛成一件（中间表有 UNIQUE 约束，重复会崩在事务里）；
     空列表 = 清空关联、不传这个字段 = 不动它
  ⑥ 接口：`items` 数组随行下发；`shortest` 用代表件的名字
"""

from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient

from apps.wealth.models import (
    SurvivalCategory,
    SurvivalEssential,
    SurvivalItem,
    SurvivalUnit,
)
from apps.wealth.services import survival_calc as calc
from apps.wealth.services import survival_essential_service as ess_svc

DAY = date(2026, 9, 20)

BASE = '/api/wealth/survival/essentials/'


# ──────────────────────────────────────────────────────────────
# 造数
# ──────────────────────────────────────────────────────────────

def _setup(category_name='穿'):
    category, _ = SurvivalCategory.objects.get_or_create(
        user_id=1, name=category_name,
        defaults={'consume_mode': 'on_demand', 'aggregate_mode': 'min'},
    )
    unit, _ = SurvivalUnit.objects.get_or_create(
        user_id=1, category=category, name='件',
        defaults={'base_unit': '件', 'to_base_rate': 1},
    )
    return category, unit


def _item(category, unit, name, days=30, quantity=1, **kwargs):
    fields = {
        'quantity': quantity, 'unit': unit, 'status': 'stocked', 'days_per_unit': days,
    }
    fields.update(kwargs)
    return SurvivalItem.objects.create(user_id=1, category=category, name=name, **fields)


def _essential(category, name, items=None, scope='core', **kwargs):
    essential = SurvivalEssential.objects.create(
        user_id=1, name=name, category=category, scope=scope, **kwargs,
    )
    if items:
        essential.items.set(items)
    return essential


def _client():
    return APIClient()


def _days_of(item, today=DAY):
    """单件算出来的天数，用来说明「取最小」到底取了谁"""
    return calc.compute_item_life(item, today)['expected']


# ──────────────────────────────────────────────────────────────
# ① 组内取最小（不求和）
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPickShortestNotSum:
    def test_shortest_wins_not_the_sum(self):
        """三件睡衣（夏 / 秋 / 冬）→ 结论是**最短的那件**，不是三件相加"""
        category, unit = _setup()
        summer = _item(category, unit, '夏季睡衣', days=3000)
        autumn = _item(category, unit, '秋季睡衣', days=2000)
        winter = _item(category, unit, '冬季睡衣', days=1200)
        row = calc.compute_essential(
            _essential(category, '睡衣', items=[summer, autumn, winter]), DAY,
        )
        assert row['expected'] == pytest.approx(1200, rel=0.05)
        # 求和会得到一个 6200 天左右的、看着完全合理的数 —— 那正是要防的错
        assert row['expected'] < 2000
        assert row['level'] == 'adequate'

    def test_piling_up_the_longest_one_does_not_help(self):
        """🔴 反「求和」的关键用例：给最长的那件加库存，结论**不许动**

        求和口径下这个动作会把结论推高；而现实的答案是「冬季那件还是只够穿那些天」。
        所以这条用例专门盯住「不改结论」——它才是这个判据的可观测形式。
        """
        category, unit = _setup()
        summer = _item(category, unit, '夏季睡衣', days=3000)
        winter = _item(category, unit, '冬季睡衣', days=1200)
        before = calc.compute_essential(
            _essential(category, '睡衣', items=[summer, winter]), DAY,
        )

        summer.quantity = 100        # 夏季那件囤一百件
        summer.save()
        after = calc.compute_essential(
            SurvivalEssential.objects.get(id=before['essential_id']), DAY,
        )
        assert after['expected'] == pytest.approx(before['expected'], rel=1e-6)

    def test_three_parallel_items_each_visible(self):
        """取最小之后必须能看出「是谁拖的」—— 明细逐件摊开"""
        category, unit = _setup()
        items = [
            _item(category, unit, '日用卫生巾', days=90),
            _item(category, unit, '夜用卫生巾', days=20),
        ]
        row = calc.compute_essential(_essential(category, '卫生巾', items=items), DAY)
        assert [r['item_name'] for r in row['items']] == ['夜用卫生巾', '日用卫生巾']
        assert row['items'][0]['expected'] == pytest.approx(20, rel=0.05)
        assert row['items'][0]['level'] == 'critical'

    def test_single_item_behaves_exactly_as_before(self):
        """只挂一件时结果与旧的单值口径一致 —— 多选不该改变单件的算法"""
        category, unit = _setup()
        item = _item(category, unit, '牙膏', days=45)
        row = calc.compute_essential(_essential(category, '牙膏', items=[item]), DAY)
        assert row['item_id'] == item.id
        assert row['expected'] == pytest.approx(_days_of(item), rel=1e-6)


# ──────────────────────────────────────────────────────────────
# ② 三档逐档取最小
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPerScenarioMinimum:
    def test_each_scenario_takes_its_own_minimum(self):
        """🔴 逐档取最小 ≠ 抄最短那件的三档

        构造两条会**交叉**的曲线：
            A 无到期日，base 100 → 125 / 100 / 76.9（乐观档最长）
            B 90 天后过期，base 200 → 被保质期压成 90 / 90 / 90

        逐档取最小 → 90 / 90 / 76.9（乐观档来自 B、悲观档来自 A）
        抄最短那件（B）→ 90 / 90 / 90，会**漏掉 A 的悲观档 76.9**
        """
        category, unit = _setup()
        long_lived = _item(category, unit, '囤货', days=100)
        expiring = _item(
            category, unit, '快过期', days=200,
            expire_date=DAY + timedelta(days=90),
        )
        row = calc.compute_essential(
            _essential(category, '药品', items=[long_lived, expiring]), DAY,
        )
        assert row['days']['optimistic'] == pytest.approx(90, rel=0.05)   # 来自 B
        assert row['days']['likely'] == pytest.approx(90, rel=0.05)       # 来自 B
        assert row['days']['pessimistic'] == pytest.approx(76.9, rel=0.02)  # 来自 A
        # 单调性仍然成立（乐观 ≥ 正常 ≥ 悲观），逐档 min 不会破坏它
        assert row['days']['optimistic'] >= row['days']['likely'] >= row['days']['pessimistic']

    def test_expected_is_recomputed_from_the_minimized_triple(self):
        """期望值在**取最小之后**才算 —— 不能把各件的期望值再取最小"""
        category, unit = _setup()
        a = _item(category, unit, 'A', days=100)
        b = _item(category, unit, 'B', days=200)
        row = calc.compute_essential(_essential(category, '药品', items=[a, b]), DAY)
        assert row['expected'] == pytest.approx(_days_of(a), rel=1e-6)
        # 离散度也来自同一组三档，不是某件的
        assert row['spread'] is not None and row['spread'] > 0


# ──────────────────────────────────────────────────────────────
# ③ 一件算不出 ⇒ 整条 unknown
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestOneUncomputableBlocksAll:
    def test_one_uncomputable_makes_whole_unknown(self):
        """🔴 不能拿部分数据充完整答案

        三件里有一件没填用量口径 → 整条报「待补数据」，而不是
        「另外两件能撑 300 天」—— 后者会把一个**待办**说成一个**结论**，
        用户看到 300 天就不会去补那一件了。
        """
        category, unit = _setup()
        ok = _item(category, unit, '正常件', days=300)
        broken = _item(category, unit, '缺口径件', days=None, uses_per_unit=None)
        row = calc.compute_essential(
            _essential(category, '药品', items=[ok, broken]), DAY,
        )
        assert row['level'] == 'unknown'
        assert row['expected'] is None
        assert row['days'] == {'optimistic': None, 'likely': None, 'pessimistic': None}

    def test_issues_name_the_broken_item(self):
        """要能看出**是哪一件**坏了 —— 只说「这条算不出」，用户还得逐件翻"""
        category, unit = _setup()
        ok = _item(category, unit, '正常件', days=300)
        broken = _item(category, unit, '缺口径件', days=None, uses_per_unit=None)
        row = calc.compute_essential(
            _essential(category, '药品', items=[ok, broken]), DAY,
        )
        codes = [i['code'] for i in row['issues']]
        assert 'no_days_per_unit' in codes
        broken_issue = next(i for i in row['issues'] if i['code'] == 'no_days_per_unit')
        assert broken_issue['item'] == '缺口径件'

    def test_expired_one_alongside_a_healthy_one(self):
        """过期那件同样把整条拉进 unknown —— 它是「去换一件新的」这个动作"""
        category, unit = _setup()
        ok = _item(category, unit, '正常件', days=300)
        expired = _item(category, unit, '过期件', days=300, status='expired')
        row = calc.compute_essential(
            _essential(category, '药品', items=[ok, expired]), DAY,
        )
        assert row['level'] == 'unknown'
        assert 'no_stock' in [i['code'] for i in row['issues']]

    def test_all_healthy_stays_computable(self):
        """反面对照：都健康就不许无缘无故降级"""
        category, unit = _setup()
        row = calc.compute_essential(
            _essential(category, '药品', items=[
                _item(category, unit, 'A', days=300),
                _item(category, unit, 'B', days=200),
            ]), DAY,
        )
        assert row['level'] == 'adequate'
        assert row['expected'] is not None


# ──────────────────────────────────────────────────────────────
# ④ 代表件与明细顺序
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestRepresentativeAndOrder:
    def test_representative_is_the_shortest(self):
        category, unit = _setup()
        long_one = _item(category, unit, '多的', days=500)
        short_one = _item(category, unit, '少的', days=30)
        row = calc.compute_essential(
            _essential(category, '药品', items=[long_one, short_one]), DAY,
        )
        assert row['item_id'] == short_one.id
        assert row['item_name'] == '少的'

    def test_items_sorted_shortest_first_uncomputable_last(self):
        category, unit = _setup()
        a = _item(category, unit, '撑得久', days=500)
        b = _item(category, unit, '最短', days=30)
        c = _item(category, unit, '算不出', days=None, uses_per_unit=None)
        row = calc.compute_essential(
            _essential(category, '药品', items=[a, b, c]), DAY,
        )
        assert [r['item_name'] for r in row['items']] == ['最短', '撑得久', '算不出']

    def test_representative_falls_back_when_nothing_computable(self):
        """一件都算不出时代表件仍有值（id 最小那件）—— 界面要说得出「是哪件的锅」"""
        category, unit = _setup()
        a = _item(category, unit, 'A', days=None, uses_per_unit=None)
        b = _item(category, unit, 'B', days=None, uses_per_unit=None)
        row = calc.compute_essential(_essential(category, '药品', items=[a, b]), DAY)
        assert row['item_id'] == a.id
        assert row['level'] == 'unknown'


# ──────────────────────────────────────────────────────────────
# ⑤ 去重 / 清空 / 不动
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestDedupAndClearing:
    def test_duplicate_ids_collapse_to_one(self):
        """同一件挂两遍不该崩

        中间表上有 UNIQUE(survivalessential_id, survivalitem_id)，重复项
        会以 IntegrityError 崩在事务里 —— 而界面上只剩一句「保存失败」，
        看不出是「同一件勾了两遍」。
        """
        category, unit = _setup()
        item = _item(category, unit, '牙膏', days=60)
        row = ess_svc.create_essential({
            'name': '牙膏', 'category_id': category.id,
            'item_ids': [item.id, item.id],
        })
        assert row['item_id'] == item.id
        assert SurvivalEssential.objects.get(id=row['essential_id']).items.count() == 1

    def test_empty_list_clears_links(self):
        """空列表 = 清空关联（用户把勾选全取消了）"""
        category, unit = _setup()
        item = _item(category, unit, '牙膏', days=60)
        row = ess_svc.create_essential({
            'name': '牙膏', 'category_id': category.id, 'item_ids': [item.id],
        })
        updated = ess_svc.update_essential(row['essential_id'], {'item_ids': []})
        assert updated['item_id'] is None
        assert updated['level'] == 'missing'

    def test_not_passing_item_ids_keeps_existing(self):
        """不传这个字段 = 这次不打算动它（与空列表**不是**一回事）

        写成 `if item_ids:` 会让「清空」退化成「不动」：
        用户取消勾选后点保存，界面看着清空了、刷新又回来。
        """
        category, unit = _setup()
        item = _item(category, unit, '牙膏', days=60)
        row = ess_svc.create_essential({
            'name': '牙膏', 'category_id': category.id, 'item_ids': [item.id],
        })
        updated = ess_svc.update_essential(row['essential_id'], {'scope': 'optional'})
        assert updated['item_id'] == item.id
        assert updated['scope'] == 'optional'

    def test_adding_a_second_item_later(self):
        """先挂一件、后来补第二件 —— 取最小立刻跟上"""
        category, unit = _setup()
        first = _item(category, unit, '夏季睡衣', days=3000)
        row = ess_svc.create_essential({
            'name': '睡衣', 'category_id': category.id, 'item_ids': [first.id],
        })
        assert row['expected'] == pytest.approx(3000, rel=0.05)

        winter = _item(category, unit, '冬季睡衣', days=1200)
        updated = ess_svc.update_essential(
            row['essential_id'], {'item_ids': [first.id, winter.id]},
        )
        assert updated['item_id'] == winter.id
        assert updated['expected'] == pytest.approx(1200, rel=0.05)


# ──────────────────────────────────────────────────────────────
# ⑥ 接口
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestMultiItemApi:
    def test_items_array_rides_along(self):
        category, unit = _setup()
        a = _item(category, unit, 'A', days=100)
        b = _item(category, unit, 'B', days=40)
        _essential(category, '药品', items=[a, b])
        resp = _client().get(BASE)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)          # 裸数组，不是 {count, results}
        assert [r['item_name'] for r in body[0]['items']] == ['B', 'A']
        assert body[0]['item_name'] == 'B'
        assert body[0]['expected'] == pytest.approx(40, rel=0.05)

    def test_create_with_multiple_items_via_api(self):
        category, unit = _setup()
        a = _item(category, unit, 'A', days=100)
        b = _item(category, unit, 'B', days=40)
        resp = _client().post(BASE, {
            'name': '药品', 'category_id': category.id, 'item_ids': [a.id, b.id],
        }, format='json')
        assert resp.status_code == 201
        assert resp.json()['item_id'] == b.id

    def test_duplicate_ids_via_api_still_created(self):
        """接口层同样要把重复收敛掉，不能把 IntegrityError 漏成 500"""
        category, unit = _setup()
        item = _item(category, unit, '牙膏', days=60)
        resp = _client().post(BASE, {
            'name': '牙膏', 'category_id': category.id, 'item_ids': [item.id, item.id],
        }, format='json')
        assert resp.status_code == 201

    def test_unknown_item_in_list_returns_400(self):
        category, unit = _setup()
        item = _item(category, unit, '牙膏', days=60)
        resp = _client().post(BASE, {
            'name': '牙膏', 'category_id': category.id,
            'item_ids': [item.id, 999999],
        }, format='json')
        assert resp.status_code == 400

    def test_shortest_uses_the_representative_item_name(self):
        """`shortest` 汇总里带的是**代表件**（正常用量下最短的那件）的名字"""
        category, unit = _setup()
        a = _item(category, unit, '撑得久', days=500)
        b = _item(category, unit, '最短那件', days=10)
        _essential(category, '药品', items=[a, b])
        body = _client().get(f'{BASE}reconcile/').json()
        assert body['shortest']['name'] == '药品'
        assert body['shortest']['item_name'] == '最短那件'
        assert body['shortest']['days'] == pytest.approx(10, rel=0.1)

    def test_unclosed_only_when_nothing_linked(self):
        """挂了至少一件就脱离「未录入」—— 挂多件不会把闭合条件改严"""
        category, unit = _setup()
        _essential(category, '牙膏', items=[_item(category, unit, '牙膏', days=60)])
        body = _client().get(f'{BASE}reconcile/').json()
        assert body['summary']['unclosed_core_count'] == 0
        assert body['summary']['complete'] is True
