"""生存资源盘点 · 必需品基准清单与缺口对账（v3.59.7）

覆盖：
  ① 五档分级：未录入 / 待补数据 / 告急 / 偏紧 / 充足 —— **五档各有各的处置**，
     合并任意两档都会把用户指向一个错误的动作
  ② ⭐ 核心判据一：**未录入 ≠ 缺 0 天** —— 没录的牙膏不进天数计算
     （那会把「还没录」说成「只够撑 0 天」，而 0 是「真的撑不了」的结论），
     但它必须在对账里被点名
  ③ ⭐ 核心判据二：核心项没录全 ⇒ `complete=False`，这是一个**独立的可信度信号**
  ④ `shortest` 只在「核心 + 算得出天数」的行里挑 —— 改善型见底不是生存短板，
     未录入的更不能以 0 天混进来
  ⑤ 排序按紧迫度：未闭合的核心项排最前，不按名字
  ⑥ 种子幂等；归属类别不存在时跳过并**报告**，不凭空建类别
  ⑦ CRUD：重名 400、关联物品不存在 400、空值归一为空列表
  ⑧ 删基准项**不动库存**；删物品则基准项回到「未录入」（中间表行跟着没，不级联）
  ⑨ 接口：列表是**裸数组**（不是 {count, results}），reconcile 走结构化对象

⚠️ 一件必需品可以关联**多件**物品（v3.59.12）：睡衣分夏/秋/冬、卫生巾分日用/夜用、
   鞋分室内/室外。组内多件**取最小**（并列缺一不可），不求和 ——
   那部分判据与用例在 `test_survival_essential_multi.py` 里，本文件只保留
   「一件都不挂」「挂一件」这些基础情形。

新表由 conftest 的 session 级 django_db_setup 补齐 —— `--no-migrations --reuse-db`
下它不会自动出现（skill §3 第 1 条：失败长相是「表不存在」，像代码错其实是环境错）。
"""

from datetime import date

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
from apps.wealth.services import survival_service as svc

DAY = date(2026, 9, 20)

BASE = '/api/wealth/survival/essentials/'
ANALYSIS = '/api/wealth/survival/analysis/'


# ──────────────────────────────────────────────────────────────
# 造数
# ──────────────────────────────────────────────────────────────

def _setup(category_name='用'):
    """一个最简场景 → (category, unit)

    ⚠️ 类别与单位用 `get_or_create` **复用**：同一用例里造第二件物品时再建同名类别
       会直接撞 `UniqueConstraint(user_id, name)`，报出来是 IntegrityError ——
       看着像实现错，其实是造数写得太粗。
    """
    category, _ = SurvivalCategory.objects.get_or_create(
        user_id=1, name=category_name,
        defaults={'consume_mode': 'on_demand', 'aggregate_mode': 'min'},
    )
    unit, _ = SurvivalUnit.objects.get_or_create(
        user_id=1, category=category, name='件',
        defaults={'base_unit': '件', 'to_base_rate': 1},
    )
    return category, unit


def _item(category, unit, name, **kwargs):
    fields = {'quantity': 1, 'unit': unit, 'status': 'stocked', 'days_per_unit': 30}
    fields.update(kwargs)
    return SurvivalItem.objects.create(user_id=1, category=category, name=name, **fields)


def _essential(category, name, items=None, scope='core', **kwargs):
    """⚙️ 造数：关联物品是**一组**（v3.59.12），传列表

    ⚠️ 先建行再 `.set()`：多对多不能写进 `objects.create(...)` 的 kwargs，
       塞进去会以 `TypeError: got unexpected keyword arguments` 抛出来 ——
       那个报错看着像模型少了个字段，其实只是多对多必须分两步。
    """
    essential = SurvivalEssential.objects.create(
        user_id=1, name=name, category=category, scope=scope, **kwargs,
    )
    if items:
        essential.items.set(items)
    return essential


def _client():
    return APIClient()


# ──────────────────────────────────────────────────────────────
# ① 五档分级
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestEssentialLevels:
    def test_missing_when_no_item_linked(self):
        """没关联物品 = 未录入 —— 这不是错误，是待办"""
        category, _ = _setup()
        row = calc.compute_essential(_essential(category, '牙膏'), DAY)
        assert row['level'] == 'missing'
        assert row['item_id'] is None
        assert row['expected'] is None
        assert row['days'] == {'optimistic': None, 'likely': None, 'pessimistic': None}
        assert [i['code'] for i in row['issues']] == ['essential_missing']

    def test_unknown_when_usage_not_filled(self):
        """物品在、但两条计量口径都没填 —— 「待补数据」，与「未录入」是两回事

        前者要去补用量口径，后者要去录入。合并成一档，界面就只能说
        「有问题」，用户不知道该改什么。
        """
        category, unit = _setup()
        item = _item(category, unit, '牙膏', days_per_unit=None, uses_per_unit=None)
        row = calc.compute_essential(_essential(category, '牙膏', items=[item]), DAY)
        assert row['level'] == 'unknown'
        assert row['item_id'] == item.id
        assert 'no_days_per_unit' in [i['code'] for i in row['issues']]

    def test_expired_item_is_unknown_not_critical(self):
        """过期不是「只够撑 0 天」

        它的处置是「去换一件新的」，而不是「今天就得饿着」——
        混进 critical 会让人以为还有 0 天缓冲，实际是根本不能用。
        """
        category, unit = _setup()
        item = _item(category, unit, '过期药', status='expired')
        row = calc.compute_essential(_essential(category, '退烧药', items=[item]), DAY)
        assert row['level'] == 'unknown'
        assert 'no_stock' in [i['code'] for i in row['issues']]

    @pytest.mark.parametrize(
        'days,expected_level',
        [(10, 'critical'), (45, 'tight'), (365, 'adequate')],
    )
    def test_numeric_levels(self, days, expected_level):
        category, unit = _setup()
        item = _item(category, unit, f'物品{days}', days_per_unit=days)
        row = calc.compute_essential(_essential(category, f'必需{days}', items=[item]), DAY)
        assert row['level'] == expected_level
        assert row['expected'] == pytest.approx(days, rel=0.05)

    def test_level_function_alone(self):
        """分档只看天数 —— 阈值真源在 constants，这里钉住边界"""
        assert calc.essential_level(None) == 'unknown'
        assert calc.essential_level(0) == 'critical'
        assert calc.essential_level(29.9) == 'critical'
        assert calc.essential_level(30) == 'tight'
        assert calc.essential_level(89.9) == 'tight'
        assert calc.essential_level(90) == 'adequate'


# ──────────────────────────────────────────────────────────────
# ②③ 汇总与可信度信号
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestEssentialSummary:
    def test_missing_core_is_unclosed(self):
        category, _ = _setup()
        _essential(category, '牙膏')
        summary = calc.summarize_essentials(ess_svc.get_essential_list())
        assert summary['core_total'] == 1
        assert summary['unclosed_core_count'] == 1
        assert summary['unclosed_core'][0]['name'] == '牙膏'
        assert summary['complete'] is False

    def test_complete_when_all_core_have_days(self):
        category, unit = _setup()
        _essential(category, '牙膏', items=[_item(category, unit, '牙膏', days_per_unit=60)])
        summary = calc.summarize_essentials(ess_svc.get_essential_list())
        assert summary['complete'] is True
        assert summary['unclosed_core'] == []

    def test_missing_optional_does_not_block_complete(self):
        """改善型没录**不算**未闭合

        洗脸巾没有就是没有，不该拦住「这份对账已经过关」的结论 ——
        否则用户会被一个他根本不打算囤的东西永久拖着，很快学会无视这个提示。
        """
        category, unit = _setup()
        _essential(category, '牙膏', items=[_item(category, unit, '牙膏')], scope='core')
        _essential(category, '洗脸巾', scope='optional')
        summary = calc.summarize_essentials(ess_svc.get_essential_list())
        assert summary['total'] == 2
        assert summary['core_total'] == 1
        assert summary['unclosed_core_count'] == 0
        assert summary['complete'] is True
        # 但改善型的缺口仍然计数，只是不拦结论
        assert summary['level_counts']['missing'] == 1
        assert summary['core_level_counts']['missing'] == 0

    def test_unknown_core_counts_as_unclosed(self):
        category, unit = _setup()
        item = _item(category, unit, '牙膏', days_per_unit=None, uses_per_unit=None)
        _essential(category, '牙膏', items=[item])
        summary = calc.summarize_essentials(ess_svc.get_essential_list())
        assert summary['unclosed_core_count'] == 1
        assert summary['unclosed_core'][0]['level'] == 'unknown'


# ──────────────────────────────────────────────────────────────
# ④ shortest
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestEssentialShortest:
    def test_shortest_picks_core_minimum(self):
        category, unit = _setup()
        _essential(category, '牙膏', items=[_item(category, unit, '牙膏', days_per_unit=5)])
        _essential(category, '洗发水', items=[_item(category, unit, '洗发水', days_per_unit=200)])
        rows = ess_svc.get_essential_list()
        shortest = calc.find_essential_shortest(rows)
        assert shortest['name'] == '牙膏'
        assert shortest['level'] == 'critical'
        assert shortest['days'] == pytest.approx(5, rel=0.1)

    def test_optional_is_never_shortest(self):
        """改善型见底不是生存短板 —— 洗脸巾用完只是不方便"""
        category, unit = _setup()
        _essential(category, '牙膏', items=[_item(category, unit, '牙膏', days_per_unit=200)])
        _essential(
            category, '洗脸巾',
            items=[_item(category, unit, '洗脸巾', days_per_unit=3)], scope='optional',
        )
        shortest = calc.find_essential_shortest(ess_svc.get_essential_list())
        assert shortest['name'] == '牙膏'

    def test_missing_is_not_shortest(self):
        """未录入的不许以「0 天」混进来 —— 那是假短板，它只是还没录"""
        category, unit = _setup()
        _essential(category, '牙膏')
        _essential(category, '洗发水', items=[_item(category, unit, '洗发水', days_per_unit=200)])
        shortest = calc.find_essential_shortest(ess_svc.get_essential_list())
        assert shortest['name'] == '洗发水'

    def test_shortest_is_none_when_nothing_countable(self):
        category, _ = _setup()
        _essential(category, '牙膏')
        assert calc.find_essential_shortest(ess_svc.get_essential_list()) is None


# ──────────────────────────────────────────────────────────────
# ⑤ 排序
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestEssentialOrdering:
    def test_unclosed_core_comes_first(self):
        """排序按「该先处理哪件」，不按名字 —— 按名字排等于把要紧的藏进中间"""
        category, unit = _setup()
        _essential(category, 'a充足', items=[_item(category, unit, 'a', days_per_unit=365)])
        _essential(category, 'z未录入')          # 未录入的核心项
        rows = ess_svc.get_essential_list()
        assert rows[0]['name'] == 'z未录入'
        assert rows[0]['level'] == 'missing'

    def test_order_mode_uses_sort_order(self):
        category, unit = _setup()
        _essential(category, '乙', sort_order=1)
        _essential(category, '甲', sort_order=0)
        rows = ess_svc.get_essential_list(sort_by_urgency=False)
        assert [r['name'] for r in rows] == ['甲', '乙']

    def test_core_before_optional(self):
        category, unit = _setup()
        _essential(category, '改善', scope='optional')
        _essential(category, '核心')
        rows = ess_svc.get_essential_list()
        assert rows[0]['name'] == '核心'


# ──────────────────────────────────────────────────────────────
# ⑥ 种子
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestSeedEssentials:
    def test_defaults_seed_categories_and_essentials(self):
        result = svc.seed_survival_defaults()
        assert result['created_categories'] >= 5          # 吃 / 穿 / 用 / 数字 / 医药
        assert result['essentials']['created'] > 0
        assert result['essentials']['missing_categories'] == []
        assert SurvivalEssential.objects.filter(user_id=1).count() > 0

    def test_seed_is_idempotent(self):
        svc.seed_survival_defaults()
        first = SurvivalEssential.objects.filter(user_id=1).count()
        again = svc.seed_survival_defaults()
        assert again['essentials']['created'] == 0
        assert SurvivalEssential.objects.filter(user_id=1).count() == first

    def test_seed_reports_missing_category_instead_of_creating_it(self):
        """类别不存在就跳过并报告，**不凭空建类别** —— 那会改乱用户的分类结构"""
        SurvivalCategory.objects.create(
            user_id=1, name='吃', consume_mode='meal', aggregate_mode='min',
        )
        result = ess_svc.seed_essentials()
        assert '用' in result['missing_categories']
        assert '医药' in result['missing_categories']
        assert not SurvivalCategory.objects.filter(user_id=1, name='医药').exists()
        # 吃类的两项必需品仍然写进去了
        assert SurvivalEssential.objects.filter(user_id=1, category__name='吃').count() == 2

    def test_seed_does_not_overwrite_user_edits(self):
        """默认**不覆盖** —— 用户改过的性质与关联不该被一次 seed 抹掉"""
        svc.seed_survival_defaults()
        essential = SurvivalEssential.objects.get(user_id=1, name='牙膏')
        essential.scope = 'optional'
        essential.save()
        svc.seed_survival_defaults()
        essential.refresh_from_db()
        assert essential.scope == 'optional'

    def test_seed_overwrite_updates(self):
        svc.seed_survival_defaults()
        essential = SurvivalEssential.objects.get(user_id=1, name='牙膏')
        essential.scope = 'optional'
        essential.save()
        svc.seed_survival_defaults(overwrite=True)
        essential.refresh_from_db()
        assert essential.scope == 'core'

    def test_essentials_carry_hint_and_unit(self):
        """种子给的是「名字 + 归属 + 提示」，**不含数量** —— 数量是用户自己的事实"""
        svc.seed_survival_defaults()
        essential = SurvivalEssential.objects.get(user_id=1, name='牙膏')
        assert essential.hint
        assert essential.unit_name == '支'
        assert essential.category.name == '用'
        assert essential.items.count() == 0


# ──────────────────────────────────────────────────────────────
# ⑦ CRUD 与防呆
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestEssentialCrud:
    def test_create_links_item(self):
        category, unit = _setup()
        item = _item(category, unit, '牙膏')
        row = ess_svc.create_essential({
            'name': '牙膏', 'category_id': category.id, 'scope': 'core',
            'item_ids': [item.id],
        })
        assert row['item_id'] == item.id
        assert row['level'] != 'missing'

    def test_blank_item_ids_normalize_to_empty(self):
        """前端送 `''` / `0` 表示「不关联」—— 直接塞进多对多会炸成 500"""
        category, _ = _setup()
        for name, blank in (
            ('整体空串', ''),
            ('整体零', 0),
            ('整体 None', None),
            ('列表里全是空值', ['', 0, None]),
        ):
            row = ess_svc.create_essential({
                'name': f'空{name}', 'category_id': category.id, 'item_ids': blank,
            })
            assert row['item_id'] is None
            assert row['level'] == 'missing'

    def test_unknown_item_raises_value_error(self):
        category, _ = _setup()
        with pytest.raises(ValueError):
            ess_svc.create_essential({
                'name': '牙膏', 'category_id': category.id, 'item_ids': [999999],
            })

    def test_unknown_category_raises_value_error(self):
        with pytest.raises(ValueError):
            ess_svc.create_essential({'name': '牙膏', 'category_id': 999999})

    def test_update_can_unlink_item(self):
        category, unit = _setup()
        item = _item(category, unit, '牙膏')
        row = ess_svc.create_essential({
            'name': '牙膏', 'category_id': category.id, 'item_ids': [item.id],
        })
        # ⚠️ 解除关联送**空列表**，而不是不传这个字段 —— 两者含义不同：
        #    空列表是「我把勾选全取消了」，不传是「这次不打算动它」。
        #    写成 `if item_ids:` 会让前者退化成后者：界面看着清空了、刷新又回来。
        updated = ess_svc.update_essential(row['essential_id'], {'item_ids': []})
        assert updated['item_id'] is None
        assert updated['level'] == 'missing'
        # 解除关联**不动库存**
        item.refresh_from_db()
        assert item.quantity == 1

    def test_delete_essential_keeps_item(self):
        """删基准项只影响这把尺子 —— 关联物品是用户的资产，不该跟着消失"""
        category, unit = _setup()
        item = _item(category, unit, '牙膏')
        row = ess_svc.create_essential({
            'name': '牙膏', 'category_id': category.id, 'item_ids': [item.id],
        })
        ess_svc.delete_essential(row['essential_id'])
        assert SurvivalEssential.objects.filter(id=row['essential_id']).count() == 0
        assert SurvivalItem.objects.filter(id=item.id).exists()

    def test_deleting_item_moves_essential_to_missing(self):
        """物品没了 → 基准项回到「未录入」，而不是跟着被删

        判据：删掉一件物品不该连带删掉「我本该有牙膏」这条认知 ——
        那正是要提醒用户去补的东西。删物品时中间表的行跟着没（不是基准项被删），
        于是它自动回到「一件都没挂」。
        """
        category, unit = _setup()
        item = _item(category, unit, '牙膏')
        ess = _essential(category, '牙膏', items=[item])
        item.delete()
        ess.refresh_from_db()
        assert ess.items.count() == 0
        assert SurvivalEssential.objects.filter(id=ess.id).exists()
        row = calc.compute_essential(ess, DAY)
        assert row['level'] == 'missing'


# ──────────────────────────────────────────────────────────────
# ⑧⑨ 接口
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestEssentialApi:
    def test_list_returns_bare_array(self):
        """裸数组，不是 {count, results} —— 被全局分页包住时前端会「假 0」"""
        category, _ = _setup()
        _essential(category, '牙膏')
        resp = _client().get(BASE)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert resp.json()[0]['name'] == '牙膏'

    def test_list_filters_by_scope_and_category(self):
        category, _ = _setup()
        _essential(category, '牙膏', scope='core')
        _essential(category, '洗脸巾', scope='optional')
        resp = _client().get(BASE, {'scope': 'optional'})
        assert [r['name'] for r in resp.json()] == ['洗脸巾']

    def test_reconcile_endpoint(self):
        category, unit = _setup()
        _essential(category, '牙膏', items=[_item(category, unit, '牙膏', days_per_unit=5)])
        resp = _client().get(f'{BASE}reconcile/')
        assert resp.status_code == 200
        body = resp.json()
        assert body['is_configured'] is True
        assert body['summary']['core_total'] == 1
        assert body['shortest']['name'] == '牙膏'

    def test_reconcile_when_nothing_configured(self):
        resp = _client().get(f'{BASE}reconcile/')
        assert resp.status_code == 200
        assert resp.json()['is_configured'] is False
        assert resp.json()['shortest'] is None

    def test_create_via_api(self):
        category, _ = _setup()
        resp = _client().post(BASE, {
            'name': '牙膏', 'category_id': category.id, 'scope': 'core',
        }, format='json')
        assert resp.status_code == 201
        assert resp.json()['level'] == 'missing'

    def test_duplicate_name_returns_400_not_500(self):
        """模型上是 UniqueConstraint(user_id, name)，DRF 不自动校验它 ——
        漏了手写校验就会以 IntegrityError(500) 的形式炸出来"""
        category, _ = _setup()
        _essential(category, '牙膏')
        resp = _client().post(BASE, {
            'name': '牙膏', 'category_id': category.id,
        }, format='json')
        assert resp.status_code == 400

    def test_create_with_unknown_item_returns_400(self):
        category, _ = _setup()
        resp = _client().post(BASE, {
            'name': '牙膏', 'category_id': category.id, 'item_ids': [999999],
        }, format='json')
        assert resp.status_code == 400

    def test_delete_via_api(self):
        category, _ = _setup()
        row = _essential(category, '牙膏')
        resp = _client().delete(f'{BASE}{row.id}/')
        assert resp.status_code == 200
        assert SurvivalEssential.objects.filter(id=row.id).count() == 0

    def test_seed_endpoint(self):
        """端点只写基准清单 —— 归属类别要先存在

        ⚠️ 刻意不在这里顺手建类别：`/categories/seed/` 才是建类别的入口，
           这里凭空建一个会让用户发现自己的分类结构被一个「写清单」的动作改动了。
           类别缺失走 `missing_categories` 报告，不静默补。
        """
        SurvivalCategory.objects.create(
            user_id=1, name='用', consume_mode='on_demand', aggregate_mode='min',
        )
        resp = _client().post(f'{BASE}seed/', {}, format='json')
        assert resp.status_code == 200
        assert resp.json()['created'] > 0
        assert '吃' in resp.json()['missing_categories']

    def test_analysis_includes_essentials_block(self):
        """综合分析里内联对账块（汇总 + 最短），明细仍走列表端点"""
        category, unit = _setup()
        _item(category, unit, '纸巾')
        _essential(category, '牙膏')
        resp = _client().get(ANALYSIS)
        assert resp.status_code == 200
        body = resp.json()
        assert body['available'] is True
        assert body['essentials']['is_configured'] is True
        assert body['essentials']['summary']['unclosed_core_count'] == 1
        assert body['essentials']['summary']['complete'] is False

    def test_essential_does_not_change_survival_days(self):
        """🔴 核心判据：未录入的必需项**不进天数计算**

        否则「还没录牙膏」会被算成「只够撑 0 天」——
        而 0 是「真的撑不了」的结论，两者要采取的行动完全不同。
        对账的职责是点名，不是改数。
        """
        category, unit = _setup()
        _item(category, unit, '纸巾', days_per_unit=50)
        _essential(category, '牙膏')          # 未录入
        body = _client().get(ANALYSIS).json()
        assert body['shortest_days'] == pytest.approx(50, rel=0.1)
        assert body['essentials']['summary']['unclosed_core_count'] == 1

    def test_meta_exposes_essential_options(self):
        body = _client().get('/api/wealth/survival/meta/').json()
        assert {o['value'] for o in body['essential_scopes']} == {'core', 'optional'}
        assert {o['value'] for o in body['essential_levels']} == {
            'missing', 'unknown', 'critical', 'tight', 'adequate',
        }
        # ⚠️ 分档阈值**刻意不下发**：到了前端就一定有人拿它重算一遍分档
        assert 'essential_level_floors' not in body

    def test_metric_note_covers_reconcile(self):
        body = _client().get('/api/wealth/survival/metrics/meta/').json()
        keys = {row['key'] for row in body}
        assert 'essential_reconcile' in keys
        note = next(r for r in body if r['key'] == 'essential_reconcile')['note']
        # 前端按纯文本渲染，星号会原样显示出来（这个坑本项目踩过三次）
        assert not any('*' in line for line in note)
