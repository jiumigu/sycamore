"""快速记账的分类 / 子分类候选值（v3.62.17）

覆盖：
  ① **层级来自账本**：`分类 → 子分类` 的真源是 `wealth_bill_list` 的共现关系。
     规则表里 `category` 与 `subcategory` 是两个**平行**的匹配字段，彼此没有父子
     关系 —— 这一点是「选了分类才能筛子分类」这件事的根据，必须钉住。
  ② **候选 = 账本 ∪ 口径配置**：账本里高频、但**没有单独建规则**的子分类必须还在。
     🔴 这是本轮的核心回归点：口径配置里只有 14 个子分类匹配值，账本里实际用过
     60 个 —— 只取口径配置会把「早午晚餐」这类高频项整个抹掉（功能倒退）。
  ③ **排序按笔数降序**：每天要录一笔的场景，常用的必须在前。
  ④ **停用的规则不进候选**：停用 = 不再参与归类 ⇒ 新建账项也不该再选出这个分类名。
  ⑤ `ungrouped` 兜住「无法归到任何分类」的子分类：账本里分类为空的孤儿行，
     加上口径配置里在账本中找不到归属的值。
  ⑥ 空库不炸，三个键恒存在（前端不必做存在性判断）。
  ⑦ 接口契约：只读 200、**路径不被 `classify/rules/<pk>/` 抢走**。

新表由 conftest 的 session 级 django_db_setup 镜像建表
（`--no-migrations --reuse-db` 下新表不会自动出现）。
"""
from datetime import datetime

import pytest
from django.utils.timezone import make_aware
from rest_framework.test import APIClient

from apps.wealth.models import WealthBillList, WealthClassifyRule
from apps.wealth.services.classify_service import get_bill_category_options

OPTIONS_URL = '/api/wealth/classify/bill-options/'

# ⚠️ USE_TZ=True 下必须给 aware datetime，否则每次造数刷一条 RuntimeWarning
NOW = make_aware(datetime(2026, 9, 20, 12, 0, 0))


# ══════════════════════════════════════════════════════════════
# 造数工具
# ══════════════════════════════════════════════════════════════


def _bill(category='', subcategory='', n=1, transaction_type='支出', amount=10.0):
    """造 n 条「同分类同子分类」的账单。"""
    for i in range(n):
        WealthBillList.objects.create(
            transaction_type=transaction_type,
            date=make_aware(datetime(2026, 9, 10, 10, 0, 0)),
            amount=amount,
            category=category,
            subcategory=subcategory,
            merchant='',
            user_id=1,
            year=2026, month=9, day=10 + i if 10 + i <= 28 else 10,
            created_at=NOW, updated_at=NOW,
        )


def _rule(field='category', value='食品酒水', income='', nature='', cashflow='',
          active=True):
    return WealthClassifyRule.objects.create(
        rule_field=field, match_value=value,
        income_type=income or None, expense_nature=nature or None,
        cashflow_class=cashflow or None,
        priority=0, is_active=active, note='', user_id=1,
    )


def _values(rows):
    """[{'value': 'x', 'count': 1}] → ['x']"""
    return [r['value'] for r in rows]


# ══════════════════════════════════════════════════════════════
# ① 层级来自账本（不是规则表）
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestHierarchyFromBills:

    def test_subcategories_grouped_under_their_own_category(self):
        _bill(category='食品酒水', subcategory='早午晚餐', n=3)
        _bill(category='食品酒水', subcategory='水果-牛奶', n=1)
        _bill(category='行车交通', subcategory='公交', n=2)
        opts = get_bill_category_options()
        assert _values(opts['subcategories']['食品酒水']) == ['早午晚餐', '水果-牛奶']
        assert _values(opts['subcategories']['行车交通']) == ['公交']

    def test_same_subcategory_name_not_leaked_to_other_categories(self):
        """「早午晚餐」只属于「食品酒水」；不能因为它出现在别的分类下就串过去"""
        _bill(category='食品酒水', subcategory='早午晚餐', n=2)
        _bill(category='日常生活', subcategory='日常用品', n=1)
        opts = get_bill_category_options()
        assert '早午晚餐' not in _values(opts['subcategories']['日常生活'])
        assert '日常用品' not in _values(opts['subcategories']['食品酒水'])

    def test_category_ordering_by_count_desc(self):
        _bill(category='其他杂项', subcategory='其他支出', n=1)
        _bill(category='食品酒水', subcategory='早午晚餐', n=9)
        _bill(category='行车交通', subcategory='公交', n=4)
        opts = get_bill_category_options()
        assert _values(opts['categories']) == ['食品酒水', '行车交通', '其他杂项']


# ══════════════════════════════════════════════════════════════
# ② 候选 = 账本 ∪ 口径配置（本轮核心）
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestUnionOfBillsAndRules:

    def test_high_frequency_subcategory_kept_without_its_own_rule(self):
        """🔴 核心回归：「早午晚餐」没有自己的子分类规则，也必须在候选里。

        它被「分类 = 食品酒水」的分类级规则整体覆盖，**不需要**单独建规则 ——
        所以口径配置那张表里根本没有它。候选若只取口径配置，用户每次记账
        都选不到自己最常用的子分类（60 个砍到 14 个）。
        """
        _rule(field='category', value='食品酒水', nature='固定')
        _bill(category='食品酒水', subcategory='早午晚餐', n=10)
        opts = get_bill_category_options()
        assert '早午晚餐' in _values(opts['subcategories']['食品酒水'])
        assert '食品酒水' in _values(opts['categories'])

    def test_bill_subcategories_never_shrink_against_bill_distinct(self):
        """账本里有几个子分类，候选里就该有几个（口径配置只许做加法）"""
        _bill(category='食品酒水', subcategory='早午晚餐', n=5)
        _bill(category='食品酒水', subcategory='线上生鲜', n=3)
        _bill(category='日常生活', subcategory='话费', n=2)
        opts = get_bill_category_options()
        listed = {v for rows in opts['subcategories'].values() for v in _values(rows)}
        listed |= set(_values(opts['ungrouped']))
        assert {'早午晚餐', '线上生鲜', '话费'} <= listed

    def test_rule_only_values_are_appended_with_zero_count(self):
        """口径配置里登记过、账本里还没记过的分类名也要能选（排在各组末尾）"""
        _bill(category='食品酒水', subcategory='早午晚餐', n=2)
        _rule(field='category', value='新登记分类')
        opts = get_bill_category_options()
        cats = opts['categories']
        assert _values(cats) == ['食品酒水', '新登记分类']
        assert cats[-1]['count'] == 0

    def test_rule_only_subcategory_lands_in_ungrouped(self):
        """口径配置的子分类值，账本里找不到归属 ⇒ 进 ungrouped，不硬塞给每个分类"""
        _bill(category='食品酒水', subcategory='早午晚餐', n=1)
        _rule(field='subcategory', value='无归属子分类')
        opts = get_bill_category_options()
        assert '无归属子分类' in _values(opts['ungrouped'])
        assert '无归属子分类' not in _values(opts['subcategories']['食品酒水'])

    def test_merchant_rules_do_not_leak_into_options(self):
        """商户规则不是分类，不能混进这两个下拉"""
        _rule(field='merchant', value='某某超市')
        opts = get_bill_category_options()
        assert '某某超市' not in _values(opts['categories'])
        assert '某某超市' not in _values(opts['ungrouped'])


# ══════════════════════════════════════════════════════════════
# ③ 排序
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestOrdering:

    def test_subcategories_ordered_by_count_desc(self):
        _bill(category='食品酒水', subcategory='线上生鲜', n=1)
        _bill(category='食品酒水', subcategory='早午晚餐', n=5)
        _bill(category='食品酒水', subcategory='水果-牛奶', n=3)
        opts = get_bill_category_options()
        assert _values(opts['subcategories']['食品酒水']) == [
            '早午晚餐', '水果-牛奶', '线上生鲜',
        ]

    def test_equal_count_order_is_deterministic(self):
        """同笔数时按**值**排序 —— 顺序必须确定，不能随入库顺序而变。

        ⚠️ 只断言「与值序一致 + 两次调用相同」，**不写死具体顺序**：
           中文的排序键是 Unicode 码点（不是拼音），写死等于把码点表钉进测试，
           日后有人换个排序键这条用例就会以「无法理解的差异」红掉。
        """
        _bill(category='食品酒水', subcategory='乙', n=2)
        _bill(category='食品酒水', subcategory='甲', n=2)
        values = _values(get_bill_category_options()['subcategories']['食品酒水'])
        assert set(values) == {'甲', '乙'}
        assert values == sorted(values)
        again = _values(get_bill_category_options()['subcategories']['食品酒水'])
        assert again == values

    def test_subcategories_all_is_flattened_by_backend_and_count_ordered(self):
        """🔴 全局候选由**后端**拍平 —— 前端不许自己合 `subcategories`。

        第一版让前端按各分类的键序拼接，结果「早午晚餐（30 笔）」被排到了
        「公交（2 笔）」后面：顺序这件事又有了一份局部口径。视图层直接吃这一份。
        """
        _bill(category='食品酒水', subcategory='早午晚餐', n=30)
        _bill(category='行车交通', subcategory='公交', n=2)
        _bill(category='食品酒水', subcategory='水果-牛奶', n=9)
        opts = get_bill_category_options()
        assert _values(opts['subcategories_all']) == ['早午晚餐', '水果-牛奶', '公交']

    def test_subcategories_key_order_follows_categories_order(self):
        """联动字典的**键序**必须与 `categories` 一致，且两次调用完全相同。

        ⚠️ 这条钉的是「拿 set 拼键」那个 bug：`set` 的迭代顺序不可预测，
           同一份数据两次请求可能给出不同键序 ⇒ 前端据此渲染的联动顺序会飘。
        """
        _bill(category='甲分类', subcategory='甲子', n=1)
        _bill(category='乙分类', subcategory='乙子', n=9)
        _bill(category='丙分类', subcategory='丙子', n=5)
        opts = get_bill_category_options()
        assert list(opts['subcategories']) == _values(opts['categories'])
        assert list(get_bill_category_options()['subcategories']) == list(opts['subcategories'])


# ══════════════════════════════════════════════════════════════
# ④ 停用规则 / ⑤ ungrouped / ⑥ 空库
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestEdgeCases:

    def test_inactive_rule_value_not_offered(self):
        """停用 = 不再参与归类 ⇒ 新建账项也不该再选它（否则永远归不了类）"""
        _rule(field='category', value='已停用分类', active=False)
        opts = get_bill_category_options()
        assert '已停用分类' not in _values(opts['categories'])

    def test_orphan_bill_subcategory_goes_ungrouped(self):
        """分类为空的账单行，其子分类不能硬塞进某个分类"""
        _bill(category='', subcategory='零花钱', n=2)
        opts = get_bill_category_options()
        assert _values(opts['ungrouped']) == ['零花钱']
        assert opts['subcategories'] == {}

    def test_ungrouped_orders_bills_first_then_rule_only(self):
        _bill(category='', subcategory='零花钱', n=3)
        _rule(field='subcategory', value='aaa无归属')
        opts = get_bill_category_options()
        assert _values(opts['ungrouped']) == ['零花钱', 'aaa无归属']

    def test_blank_values_are_dropped(self):
        """空串分类名不是候选（否则下拉里会出现一行空白）"""
        _bill(category='', subcategory='', n=2)
        _rule(field='category', value='   ')
        opts = get_bill_category_options()
        assert _values(opts['categories']) == []

    def test_empty_db_returns_well_formed_shape(self):
        opts = get_bill_category_options()
        assert opts['categories'] == []
        assert opts['subcategories'] == {}
        assert opts['subcategories_all'] == []
        assert opts['ungrouped'] == []


# ══════════════════════════════════════════════════════════════
# ⑦ 接口契约
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestBillOptionsApi:

    def test_get_returns_200_and_shape(self):
        _bill(category='食品酒水', subcategory='早午晚餐', n=1)
        resp = APIClient().get(OPTIONS_URL)
        assert resp.status_code == 200
        data = resp.json()
        # 三个键一个都不能少 —— 前端不做存在性判断（少了就静默空下拉）
        assert set(data) == {'categories', 'subcategories', 'subcategories_all', 'ungrouped'}
        assert _values(data['categories']) == ['食品酒水']

    def test_static_path_not_swallowed_by_pk_route(self):
        """🔴 路径必须命中本视图，而不是被 `classify/rules/<pk>/` 吃掉。

        被吃掉的症状是 404（`pk='bill-options'` 查不到规则）—— 看着像路由没注册。
        规则详情接口**不会**返回 categories 键，故用键名判定命中对象。
        """
        resp = APIClient().get(OPTIONS_URL)
        assert resp.status_code == 200
        assert 'categories' in resp.json()
