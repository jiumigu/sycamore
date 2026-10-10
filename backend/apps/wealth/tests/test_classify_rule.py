"""账单项分类规则 / 归类结果（v3.58.22，P1-C）

覆盖：
  ① 匹配：精确相等（非模糊）、停用不参与、未知字段不匹配
  ② 胜负：优先级高者胜；**同优先级时更具体字段胜**（merchant > subcategory
     > category）—— 不靠 id 决胜，避免结论随建规则先后而变
  ③ 收支方向隔离：收入行只认收入侧标签、支出行只认支出侧标签，
     另一侧自动忽略（一条 merchant 规则可能同时命中收支两向）
  ④ 非计入类型（转入 / 转出 / 余额变更）即使命中规则也不出标签
  ⑤ 汇总恒等式：income.total = Σby_type + unclassified；
     expense.total = Σby_nature + unclassified
  ⑥ 覆盖率**分母各不相同**（收入维度用收入总额、支出维度用支出总额、
     现金流用收支合计）—— 用统一分母会把收入覆盖率稀释成假 0
  ⑦ 三个维度的字典键**恒存在**（缺失补 0），前端不必做 key 存在性判断
  ⑧ 未归类候选：只列未归类的、金额降序、建议建在最窄可用字段上
  ⑨ 影响预览：命中数 ≠ 改动数；低优先级候选规则命中一片却改动 0；
     **预览不写库**
  ⑩ CRUD：重复 (字段,值) 400、三标签全空 400、非法枚举 400、
     默认优先级按具体度派生、partial 只改备注不报错
  ⑪ 种子幂等：默认不覆盖用户改动、overwrite=True 覆盖、手工规则不受影响
  ⑫ 列表返回**裸数组** —— 防被全局分页包成 {count, results} 后前端静默显示为空

新表由 conftest 的 session 级 django_db_setup 镜像建表
（--no-migrations --reuse-db 下新表不会自动出现）。
"""
from datetime import datetime

import pytest
from django.utils.timezone import make_aware
from rest_framework.test import APIClient

from apps.wealth.constants import (
    CASHFLOW_CLASSES,
    CLASSIFY_DEFAULT_PRIORITY,
    CLASSIFY_SEED_RULES,
    EXPENSE_NATURES,
    INCOME_TYPES,
)
from apps.wealth.models import WealthBillList, WealthClassifyRule
from apps.wealth.services.classify_service import (
    available_periods,
    classify_bill,
    classify_summary,
    create_rule,
    delete_rule,
    get_rule_list,
    get_rule_summary,
    get_unclassified_candidates,
    match_classify_rule,
    preview_rule_impact,
    seed_classify_rules,
    update_rule,
)

RULES_URL = '/api/wealth/classify/rules/'
RESULTS_URL = '/api/wealth/classify/results/'
# ⚠️ USE_TZ=True 下必须给 aware datetime，否则每次造数都会刷一条
#    RuntimeWarning（naive datetime while time zone support is active），
#    几十条测试下来能把输出淹掉。注意 `date` 列在库里是无时区的 datetime，
#    Django 会按 UTC 存、按当前时区读回，往返无损；本模块的**月份过滤
#    走 year/month 整型列**，不依赖 date，故不受换算影响。
NOW = make_aware(datetime(2026, 9, 20, 12, 0, 0))


# ══════════════════════════════════════════════════════════════
# 造数工具
# ══════════════════════════════════════════════════════════════


def _rule(field='category', value='餐饮', income='', nature='', cashflow='',
          priority=None, active=True, note='') -> WealthClassifyRule:
    if priority is None:
        priority = CLASSIFY_DEFAULT_PRIORITY.get(field, 0)
    return WealthClassifyRule.objects.create(
        rule_field=field, match_value=value,
        income_type=income or None, expense_nature=nature or None,
        cashflow_class=cashflow or None, priority=priority,
        is_active=active, note=note, user_id=1,
    )


def _bill(year=2026, month=9, day=10, transaction_type='支出', amount=100.0,
          category='', subcategory='', merchant='') -> WealthBillList:
    return WealthBillList.objects.create(
        transaction_type=transaction_type,
        date=make_aware(datetime(year, month, day, 10, 0, 0)),
        amount=amount, category=category, subcategory=subcategory,
        merchant=merchant, user_id=1,
        year=year, month=month, day=day,
        created_at=NOW, updated_at=NOW,
    )


def _rules(*args):
    """按 (field, value) 建规则并返回「启用中的规则列表」——匹配函数的入参形态"""
    for arg in args:
        _rule(**arg)
    return list(
        WealthClassifyRule.objects.filter(user_id=1, is_active=True)
        .order_by('-priority', 'id')
    )


# ══════════════════════════════════════════════════════════════
# ① 匹配基础
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestMatchBasics:

    def test_exact_match(self):
        rules = _rules({'field': 'category', 'value': '餐饮', 'nature': '固定'})
        bill = {'category': '餐饮', 'subcategory': '', 'merchant': ''}
        assert match_classify_rule(bill, rules) is not None

    def test_match_is_exact_not_fuzzy(self):
        """「餐」不该命中「餐饮」—— 匹配是精确相等，不是包含"""
        rules = _rules({'field': 'category', 'value': '餐饮', 'nature': '固定'})
        bill = {'category': '餐', 'subcategory': '', 'merchant': ''}
        assert match_classify_rule(bill, rules) is None

    def test_no_match_returns_none(self):
        rules = _rules({'field': 'category', 'value': '餐饮', 'nature': '固定'})
        bill = {'category': '交通', 'subcategory': '', 'merchant': ''}
        assert match_classify_rule(bill, rules) is None

    def test_empty_bill_field_does_not_match_rule(self):
        """账单字段为 None 时不得命中（否则规则会靠「都不存在」吞掉一切）"""
        rules = _rules({'field': 'subcategory', 'value': 'x', 'nature': '固定'})
        bill = {'category': '餐饮', 'subcategory': None, 'merchant': None}
        assert match_classify_rule(bill, rules) is None

    def test_inactive_rule_not_loaded(self):
        _rule(field='category', value='餐饮', nature='固定', active=False)
        rules = list(WealthClassifyRule.objects.filter(user_id=1, is_active=True))
        assert rules == []
        assert match_classify_rule({'category': '餐饮'}, rules) is None

    def test_unknown_rule_field_never_matches(self):
        """已废弃 / 未来字段一律不匹配 —— 不许「按别的维度猜着算」"""
        stray = WealthClassifyRule(
            rule_field='unknown_field', match_value='餐饮',
            expense_nature='固定', priority=99, user_id=1,
        )
        # 不进库：只验证匹配函数对未知字段的处理
        assert match_classify_rule({'category': '餐饮'}, [stray]) is None

    def test_match_accepts_model_instance(self):
        rules = _rules({'field': 'category', 'value': '餐饮', 'nature': '固定'})
        bill = _bill(category='餐饮')
        assert match_classify_rule(bill, rules) is not None


# ══════════════════════════════════════════════════════════════
# ② 胜负规则
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPriority:

    def test_higher_priority_wins_over_more_specific_field(self):
        """优先级压过具体度：分类级规则被显式抬到 99 就能盖过子分类规则

        ⚠️ 竞争者必然来自**不同字段** —— 唯一键是 (user_id, rule_field,
           match_value)，同字段同匹配值本就只允许一条（否则哪条生效取决于
           创建顺序）。这也是「优先级只在跨字段时才有意义」的原因。
        """
        rules = _rules(
            {'field': 'subcategory', 'value': '垃圾食品', 'nature': '可变', 'priority': 20},
            {'field': 'category', 'value': '食品酒水', 'nature': '固定', 'priority': 99},
        )
        bill = {'category': '食品酒水', 'subcategory': '垃圾食品'}
        assert match_classify_rule(bill, rules).expense_nature == '固定'

    def test_same_priority_more_specific_field_wins(self):
        """同为 priority=10 时，子分类规则压过分类规则 —— 与具体度一致"""
        rules = _rules(
            {'field': 'category', 'value': '食品酒水', 'nature': '固定', 'priority': 10},
            {'field': 'subcategory', 'value': '垃圾食品', 'nature': '可变', 'priority': 10},
        )
        bill = {'category': '食品酒水', 'subcategory': '垃圾食品'}
        assert match_classify_rule(bill, rules).expense_nature == '可变'

    def test_merchant_beats_subcategory_on_tie(self):
        rules = _rules(
            {'field': 'subcategory', 'value': '早午晚餐', 'nature': '固定', 'priority': 10},
            {'field': 'merchant', 'value': '某餐厅', 'nature': '可变', 'priority': 10},
        )
        bill = {'category': '食品酒水', 'subcategory': '早午晚餐', 'merchant': '某餐厅'}
        assert match_classify_rule(bill, rules).expense_nature == '可变'

    def test_explicit_priority_can_override_specificity(self):
        """用户显式把整类规则抬到高优先级时，它就该压过细分规则"""
        rules = _rules(
            {'field': 'subcategory', 'value': '垃圾食品', 'nature': '可变', 'priority': 20},
            {'field': 'category', 'value': '食品酒水', 'nature': '固定', 'priority': 99},
        )
        bill = {'category': '食品酒水', 'subcategory': '垃圾食品'}
        assert match_classify_rule(bill, rules).expense_nature == '固定'

    def test_result_is_deterministic_regardless_of_insert_order(self):
        """同样两条规则换个创建顺序，结论必须一致（这就是不靠 id 决胜的理由）"""
        bills = {'category': '食品酒水', 'subcategory': '垃圾食品'}
        rules_a = _rules(
            {'field': 'category', 'value': '食品酒水', 'nature': '固定', 'priority': 10},
            {'field': 'subcategory', 'value': '垃圾食品', 'nature': '可变', 'priority': 10},
        )
        first = match_classify_rule(bills, rules_a).expense_nature

        WealthClassifyRule.objects.all().delete()
        rules_b = _rules(
            {'field': 'subcategory', 'value': '垃圾食品', 'nature': '可变', 'priority': 10},
            {'field': 'category', 'value': '食品酒水', 'nature': '固定', 'priority': 10},
        )
        assert match_classify_rule(bills, rules_b).expense_nature == first == '可变'


# ══════════════════════════════════════════════════════════════
# ③④ 方向隔离与非计入类型
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestDirectionIsolation:

    def test_income_row_ignores_expense_labels(self):
        rules = _rules({'field': 'merchant', 'value': '支付宝', 'income': '主动',
                        'nature': '可变', 'cashflow': '品质支出'})
        bill = {'transaction_type': '收入', 'merchant': '支付宝'}
        labels = classify_bill(bill, rules)
        assert labels['income_type'] == '主动'
        assert labels['expense_nature'] is None      # 支出刚性不该贴到收入行
        assert labels['cashflow_class'] is None      # 品质支出是支出侧，忽略

    def test_expense_row_ignores_income_labels(self):
        rules = _rules({'field': 'merchant', 'value': '支付宝', 'income': '被动',
                        'nature': '固定', 'cashflow': '必需支出'})
        bill = {'transaction_type': '支出', 'merchant': '支付宝'}
        labels = classify_bill(bill, rules)
        assert labels['income_type'] is None
        assert labels['expense_nature'] == '固定'
        assert labels['cashflow_class'] == '必需支出'

    def test_income_row_takes_income_side_cashflow(self):
        rules = _rules({'field': 'category', 'value': '职业收入', 'income': '主动',
                        'cashflow': '收入流入'})
        labels = classify_bill({'transaction_type': '收入', 'category': '职业收入'}, rules)
        assert labels['cashflow_class'] == '收入流入'

    @pytest.mark.parametrize('ttype', ['转入', '转出', '余额变更'])
    def test_non_counted_types_get_no_labels(self, ttype):
        """账户间搬运与余额修正不是收支，贴任何收支标签都是错的"""
        rules = _rules({'field': 'category', 'value': '餐饮', 'nature': '固定',
                        'cashflow': '必需支出'})
        labels = classify_bill({'transaction_type': ttype, 'category': '餐饮'}, rules)
        assert labels['income_type'] is None
        assert labels['expense_nature'] is None
        assert labels['cashflow_class'] is None
        # 但仍返回命中来源，便于排查「为什么这笔没归类」
        assert labels['rule_id'] is not None

    def test_unmatched_returns_all_none(self):
        labels = classify_bill({'transaction_type': '支出', 'category': '不存在'}, [])
        assert labels == {'rule_id': None, 'matched_field': None, 'matched_value': None,
                          'income_type': None, 'expense_nature': None, 'cashflow_class': None}


# ══════════════════════════════════════════════════════════════
# ⑤⑥⑦ 汇总口径
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestClassifySummary:

    def _seed(self):
        _rule(field='category', value='职业收入', income='主动', cashflow='收入流入')
        _rule(field='category', value='利息', income='被动', cashflow='收入流入')
        _rule(field='category', value='房租', nature='固定', cashflow='必需支出')
        _rule(field='category', value='娱乐', nature='可变', cashflow='品质支出')

    def test_income_identity_holds(self):
        self._seed()
        _bill(transaction_type='收入', amount=1000, category='职业收入')
        _bill(transaction_type='收入', amount=300, category='利息')
        _bill(transaction_type='收入', amount=99, category='未配规则')
        s = classify_summary('2026-09')
        assert s['income']['total'] == pytest.approx(1399.0)
        assert sum(s['income']['by_type'].values()) + s['income']['unclassified'] \
            == pytest.approx(s['income']['total'])

    def test_expense_identity_holds(self):
        self._seed()
        _bill(amount=800, category='房租')
        _bill(amount=200, category='娱乐')
        _bill(amount=50, category='未配规则')
        s = classify_summary('2026-09')
        assert s['expense']['total'] == pytest.approx(1050.0)
        assert sum(s['expense']['by_nature'].values()) + s['expense']['unclassified'] \
            == pytest.approx(s['expense']['total'])

    def test_dimension_dicts_always_have_all_keys(self):
        """三个字典的键恒存在（缺失补 0）—— 前端不必做 key 存在性判断"""
        self._seed()
        _bill(category='房租')
        s = classify_summary('2026-09')
        assert set(s['income']['by_type'].keys()) == set(INCOME_TYPES)
        assert set(s['expense']['by_nature'].keys()) == set(EXPENSE_NATURES)
        for key in CASHFLOW_CLASSES:
            assert key in s['cashflow']
        assert 'unclassified' in s['cashflow']

    def test_coverage_denominators_are_per_dimension(self):
        """收入覆盖率的分母是**收入总额**，不是收支总额。

        若用统一分母，收入维度会被庞大的支出额稀释成接近 0 —— 看着像规则没生效。
        """
        self._seed()
        _bill(transaction_type='收入', amount=1000, category='职业收入')
        _bill(transaction_type='收入', amount=1000, category='未配规则')
        _bill(amount=100000, category='房租')   # 巨额支出，不该影响收入覆盖率
        s = classify_summary('2026-09')
        assert s['coverage']['income_type'] == pytest.approx(0.5)
        assert s['coverage']['expense_nature'] == pytest.approx(1.0)

    def test_cashflow_coverage_uses_both_directions(self):
        self._seed()
        _bill(transaction_type='收入', amount=100, category='职业收入')
        _bill(amount=300, category='未配规则')
        s = classify_summary('2026-09')
        assert s['coverage']['cashflow_class'] == pytest.approx(0.25)

    def test_empty_period_does_not_divide_by_zero(self):
        self._seed()
        s = classify_summary('1999-01')
        assert s['coverage'] == {'income_type': 0.0, 'expense_nature': 0.0,
                                 'cashflow_class': 0.0}
        assert s['bill_count'] == 0

    def test_excluded_types_reported_and_not_counted(self):
        """转入 / 转出 / 余额变更显式报出，且一分钱都不进收支合计"""
        self._seed()
        _bill(amount=100, category='房租')
        _bill(transaction_type='转出', amount=50000, category='')
        _bill(transaction_type='转入', amount=50000, category='')
        _bill(transaction_type='余额变更', amount=7, category='')
        s = classify_summary('2026-09')
        assert s['expense']['total'] == pytest.approx(100.0)
        assert s['income']['total'] == pytest.approx(0.0)
        assert s['bill_count'] == 1
        by_type = {row['transaction_type']: row for row in s['excluded']}
        assert by_type['转出']['amount'] == pytest.approx(50000.0)
        assert by_type['转出']['count'] == 1
        assert by_type['余额变更']['amount'] == pytest.approx(7.0)
        # 五类现金流里不该出现这 50000，只剩那笔 100 的房租
        assert sum(s['cashflow'][k] for k in CASHFLOW_CLASSES) == pytest.approx(100.0)
        assert s['cashflow']['必需支出'] == pytest.approx(100.0)

    def test_yearmon_filters_to_that_month_only(self):
        self._seed()
        _bill(year=2026, month=8, amount=999, category='房租')
        _bill(year=2026, month=9, amount=100, category='房租')
        assert classify_summary('2026-09')['expense']['total'] == pytest.approx(100.0)
        assert classify_summary('2026-08')['expense']['total'] == pytest.approx(999.0)

    def test_none_yearmon_means_all_periods(self):
        self._seed()
        _bill(year=2020, month=1, amount=10, category='房租')
        _bill(year=2026, month=9, amount=20, category='房租')
        s = classify_summary(None)
        assert s['period_label'] == '全周期'
        assert s['expense']['total'] == pytest.approx(30.0)

    def test_invalid_yearmon_treated_as_all_periods(self):
        self._seed()
        _bill(amount=10, category='房租')
        assert classify_summary('2026-13')['expense']['total'] == pytest.approx(10.0)

    def test_inactive_rule_does_not_apply(self):
        _rule(field='category', value='房租', nature='固定', cashflow='必需支出')
        rule = WealthClassifyRule.objects.get(match_value='房租')
        rule.is_active = False
        rule.save()
        _bill(amount=100, category='房租')
        s = classify_summary('2026-09')
        assert s['expense']['unclassified'] == pytest.approx(100.0)


# ══════════════════════════════════════════════════════════════
# ⑧ 未归类候选
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestUnclassifiedCandidates:

    def test_only_unclassified_listed(self):
        _rule(field='category', value='房租', nature='固定', cashflow='必需支出')
        _bill(amount=100, category='房租', subcategory='房租')
        _bill(amount=200, category='娱乐', subcategory='休闲玩乐')
        rows = get_unclassified_candidates('2026-09')['items']
        assert len(rows) == 1
        assert rows[0]['category'] == '娱乐'

    def test_sorted_by_amount_desc(self):
        _bill(amount=10, category='A', subcategory='a')
        _bill(amount=900, category='B', subcategory='b')
        _bill(amount=100, category='C', subcategory='c')
        rows = get_unclassified_candidates('2026-09')['items']
        assert [r['amount'] for r in rows] == [900.0, 100.0, 10.0]

    def test_groups_by_category_and_subcategory(self):
        _bill(amount=100, category='食品酒水', subcategory='早午晚餐')
        _bill(amount=50, category='食品酒水', subcategory='早午晚餐')
        _bill(amount=20, category='食品酒水', subcategory='垃圾食品')
        rows = get_unclassified_candidates('2026-09')['items']
        assert len(rows) == 2
        top = rows[0]
        assert top['subcategory'] == '早午晚餐'
        assert top['count'] == 2
        assert top['amount'] == pytest.approx(150.0)

    def test_suggests_narrowest_available_field(self):
        _bill(amount=100, category='食品酒水', subcategory='早午晚餐')
        _bill(amount=100, category='食品酒水', subcategory='')
        rows = {r['subcategory']: r for r in get_unclassified_candidates('2026-09')['items']}
        assert rows['早午晚餐']['suggested_field'] == 'subcategory'
        assert rows['早午晚餐']['suggested_value'] == '早午晚餐'
        assert rows['']['suggested_field'] == 'category'

    def test_totals_match_details(self):
        _bill(amount=100, category='A', subcategory='a')
        _bill(amount=30, category='B', subcategory='b')
        result = get_unclassified_candidates('2026-09')
        assert result['total_amount'] == pytest.approx(
            sum(r['amount'] for r in result['items']))
        assert result['total_count'] == sum(r['count'] for r in result['items'])

    def test_limit_applied_but_totals_keep_full_scope(self):
        """limit 只截断展示列表，total_* 仍是全量 —— 否则「还有多少钱没归类」会撒谎"""
        for i in range(5):
            _bill(amount=100 + i, category=f'C{i}', subcategory=f'c{i}')
        result = get_unclassified_candidates('2026-09', limit=2)
        assert len(result['items']) == 2
        assert result['total_count'] == 5
        assert result['total_amount'] == pytest.approx(510.0)

    def test_partially_classified_row_still_listed(self):
        """只缺一个维度也算未归类 —— 否则「收入有性质但没现金流类别」会被漏掉"""
        _rule(field='category', value='职业收入', income='主动')  # 刻意不设 cashflow
        _bill(transaction_type='收入', amount=100, category='职业收入', subcategory='职业收入')
        rows = get_unclassified_candidates('2026-09')['items']
        assert len(rows) == 1
        assert rows[0]['missing_dimensions'] == ['cashflow_class']

    def test_excluded_types_not_in_candidates(self):
        _bill(transaction_type='转出', amount=50000, category='')
        assert get_unclassified_candidates('2026-09')['items'] == []


# ══════════════════════════════════════════════════════════════
# ⑨ 影响预览
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPreview:

    def test_counts_matched_bills_and_amount(self):
        _bill(amount=100, category='食品酒水', subcategory='垃圾食品')
        _bill(amount=50, category='食品酒水', subcategory='垃圾食品')
        _bill(amount=999, category='其他')
        result = preview_rule_impact(
            {'rule_field': 'subcategory', 'match_value': '垃圾食品',
             'expense_nature': '可变', 'cashflow_class': '品质支出'},
            yearmon='2026-09',
        )
        assert result['matched_count'] == 2
        assert result['matched_amount'] == pytest.approx(150.0)

    def test_changed_count_only_counts_real_label_changes(self):
        """已由更精确规则标好标签的行，不该被候选规则算成「会改动」"""
        _rule(field='subcategory', value='垃圾食品', nature='可变',
              cashflow='品质支出', priority=20)
        _bill(amount=100, category='食品酒水', subcategory='垃圾食品')
        result = preview_rule_impact(
            {'rule_field': 'category', 'match_value': '食品酒水',
             'expense_nature': '固定', 'cashflow_class': '必需支出', 'priority': 10},
            yearmon='2026-09',
        )
        # 候选规则（分类级、优先级 10）命中了这笔，但改不动它
        assert result['matched_count'] == 1
        assert result['changed_count'] == 0

    def test_high_priority_candidate_reports_changes(self):
        _rule(field='subcategory', value='垃圾食品', nature='固定',
              cashflow='必需支出', priority=20)
        _bill(amount=100, category='食品酒水', subcategory='垃圾食品')
        result = preview_rule_impact(
            {'rule_field': 'subcategory', 'match_value': '垃圾食品',
             'expense_nature': '可变', 'cashflow_class': '品质支出', 'priority': 99},
            yearmon='2026-09',
        )
        assert result['changed_count'] == 1
        assert result['samples'][0]['before']['expense_nature'] == '固定'
        assert result['samples'][0]['after']['expense_nature'] == '可变'

    def test_preview_does_not_write(self):
        _bill(amount=100, category='食品酒水', subcategory='垃圾食品')
        before = WealthClassifyRule.objects.count()
        preview_rule_impact(
            {'rule_field': 'subcategory', 'match_value': '垃圾食品',
             'expense_nature': '可变'},
            yearmon='2026-09',
        )
        assert WealthClassifyRule.objects.count() == before

    def test_preview_ignores_non_counted_types(self):
        _bill(transaction_type='转出', amount=999, category='食品酒水',
              subcategory='垃圾食品')
        result = preview_rule_impact(
            {'rule_field': 'subcategory', 'match_value': '垃圾食品',
             'expense_nature': '可变'},
            yearmon='2026-09',
        )
        assert result['matched_count'] == 0

    def test_invalid_field_raises(self):
        with pytest.raises(ValueError):
            preview_rule_impact({'rule_field': 'nope', 'match_value': 'x',
                                 'expense_nature': '可变'})

    def test_blank_value_raises(self):
        with pytest.raises(ValueError):
            preview_rule_impact({'rule_field': 'category', 'match_value': '  ',
                                 'expense_nature': '可变'})

    def test_priority_defaults_from_field(self):
        result = preview_rule_impact(
            {'rule_field': 'merchant', 'match_value': '某商户', 'expense_nature': '可变'},
        )
        assert result['priority'] == CLASSIFY_DEFAULT_PRIORITY['merchant']


# ══════════════════════════════════════════════════════════════
# ⑩ CRUD
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestRuleCrud:

    def test_create_defaults_priority_by_field(self):
        row = create_rule({'rule_field': 'subcategory', 'match_value': '垃圾食品',
                           'expense_nature': '可变'})
        assert row['priority'] == CLASSIFY_DEFAULT_PRIORITY['subcategory']

    def test_create_normalizes_blank_labels_to_none(self):
        row = create_rule({'rule_field': 'category', 'match_value': '餐饮',
                           'expense_nature': '固定', 'income_type': '',
                           'cashflow_class': '  '})
        assert row['income_type'] is None
        assert row['cashflow_class'] is None

    def test_update_only_note_does_not_crash(self):
        """partial 更新只传备注时，不该因为「载荷里没有 rule_field」算不出默认优先级"""
        row = create_rule({'rule_field': 'category', 'match_value': '餐饮',
                           'expense_nature': '固定'})
        updated = update_rule(row['id'], {'note': '改个备注'})
        assert updated['note'] == '改个备注'
        assert updated['expense_nature'] == '固定'
        assert updated['priority'] == CLASSIFY_DEFAULT_PRIORITY['category']

    def test_update_priority_null_falls_back_to_instance_field(self):
        row = create_rule({'rule_field': 'merchant', 'match_value': '某商户',
                           'expense_nature': '可变'})
        updated = update_rule(row['id'], {'priority': None})
        assert updated['priority'] == CLASSIFY_DEFAULT_PRIORITY['merchant']

    def test_update_missing_rule_raises(self):
        with pytest.raises(ValueError):
            update_rule(999999, {'note': 'x'})

    def test_delete_returns_id_and_missing_raises(self):
        row = create_rule({'rule_field': 'category', 'match_value': '餐饮',
                           'expense_nature': '固定'})
        assert delete_rule(row['id']) == row['id']
        with pytest.raises(ValueError):
            delete_rule(row['id'])

    def test_list_excludes_inactive_by_default(self):
        _rule(field='category', value='A', nature='固定', active=True)
        _rule(field='category', value='B', nature='固定', active=False)
        assert [r['match_value'] for r in get_rule_list()] == ['A']
        assert len(get_rule_list(include_inactive=True)) == 2

    def test_summary_counts_by_field_and_dimension(self):
        _rule(field='category', value='A', nature='固定', cashflow='必需支出')
        _rule(field='subcategory', value='b', income='被动', cashflow='收入流入')
        _rule(field='merchant', value='c', nature='可变', active=False)
        s = get_rule_summary()
        assert s['total'] == 3
        assert s['active'] == 2
        assert s['inactive'] == 1
        assert s['by_field'] == {'category': 1, 'subcategory': 1, 'merchant': 0}
        assert s['by_dimension']['income_type'] == 1
        assert s['by_dimension']['expense_nature'] == 1
        assert s['by_dimension']['cashflow_class'] == 2


# ══════════════════════════════════════════════════════════════
# ⑪ 种子
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestSeed:

    def test_seed_creates_all_expected(self):
        result = seed_classify_rules()
        assert result['created'] == len(CLASSIFY_SEED_RULES)
        assert WealthClassifyRule.objects.count() == len(CLASSIFY_SEED_RULES)

    def test_seed_is_idempotent(self):
        seed_classify_rules()
        again = seed_classify_rules()
        assert again['created'] == 0
        assert again['skipped'] == len(CLASSIFY_SEED_RULES)
        assert WealthClassifyRule.objects.count() == len(CLASSIFY_SEED_RULES)

    def test_seed_does_not_clobber_user_edits(self):
        seed_classify_rules()
        target = WealthClassifyRule.objects.get(rule_field='category', match_value='食品酒水')
        target.expense_nature = '可变'
        target.note = '用户改过'
        target.save()

        seed_classify_rules()
        target.refresh_from_db()
        assert target.expense_nature == '可变'
        assert target.note == '用户改过'

    def test_seed_overwrite_resets_values(self):
        seed_classify_rules()
        target = WealthClassifyRule.objects.filter(match_value='食品酒水').first()
        target.expense_nature = '可变'
        target.save()

        result = seed_classify_rules(overwrite=True)
        assert result['updated'] == len(CLASSIFY_SEED_RULES)
        target.refresh_from_db()
        assert target.expense_nature == '固定'

    def test_seed_leaves_manual_rules_alone(self):
        _rule(field='category', value='手工规则', nature='可变')
        seed_classify_rules()
        assert WealthClassifyRule.objects.filter(match_value='手工规则').exists()
        assert WealthClassifyRule.objects.count() == len(CLASSIFY_SEED_RULES) + 1

    def test_seed_rule_keys_are_unique(self):
        """种子自身不得有重复键，否则第二次执行就会被唯一约束拦下"""
        keys = [(row[0], row[1]) for row in CLASSIFY_SEED_RULES]
        assert len(keys) == len(set(keys))

    def test_seed_covers_both_directions_for_cashflow(self):
        seed_classify_rules()
        classes = set(
            WealthClassifyRule.objects.exclude(cashflow_class=None)
            .values_list('cashflow_class', flat=True)
        )
        assert '收入流入' in classes
        assert {'必需支出', '品质支出', '投资支出'} <= classes


# ══════════════════════════════════════════════════════════════
# 杂项：可选期列表
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAvailablePeriods:

    def test_descending_and_deduped(self):
        _bill(year=2026, month=8, amount=1)
        _bill(year=2026, month=8, amount=1)
        _bill(year=2026, month=9, amount=1)
        assert available_periods() == ['2026-09', '2026-08']

    def test_excludes_non_counted_types(self):
        _bill(transaction_type='转出', amount=1)
        assert available_periods() == []


# ══════════════════════════════════════════════════════════════
# ⑫ 接口层
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestClassifyApi:

    def setup_method(self):
        self.client = APIClient()

    def test_rule_list_returns_bare_array(self):
        _rule(field='category', value='餐饮', nature='固定')
        resp = self.client.get(RULES_URL)
        assert resp.status_code == 200
        assert isinstance(resp.data, list)

    def test_create_rule(self):
        resp = self.client.post(RULES_URL, {
            'rule_field': 'subcategory', 'match_value': '垃圾食品',
            'expense_nature': '可变', 'cashflow_class': '品质支出',
        }, format='json')
        assert resp.status_code == 201
        assert resp.data['priority'] == CLASSIFY_DEFAULT_PRIORITY['subcategory']

    def test_duplicate_rule_returns_400_not_500(self):
        """UniqueConstraint 没以 unique=True 表达 ⇒ DRF 不自动校验 ⇒ 必须手写"""
        payload = {'rule_field': 'category', 'match_value': '餐饮',
                   'expense_nature': '固定'}
        assert self.client.post(RULES_URL, payload, format='json').status_code == 201
        resp = self.client.post(RULES_URL, payload, format='json')
        assert resp.status_code == 400

    def test_rule_with_no_label_returns_400(self):
        resp = self.client.post(RULES_URL, {
            'rule_field': 'category', 'match_value': '空规则',
        }, format='json')
        assert resp.status_code == 400

    def test_invalid_enum_returns_400(self):
        resp = self.client.post(RULES_URL, {
            'rule_field': 'category', 'match_value': 'x',
            'expense_nature': '随便写',
        }, format='json')
        assert resp.status_code == 400

    def test_invalid_rule_field_returns_400(self):
        resp = self.client.post(RULES_URL, {
            'rule_field': 'nope', 'match_value': 'x', 'expense_nature': '可变',
        }, format='json')
        assert resp.status_code == 400

    def test_update_rule(self):
        row = create_rule({'rule_field': 'category', 'match_value': '餐饮',
                           'expense_nature': '固定'})
        resp = self.client.patch(f'{RULES_URL}{row["id"]}/',
                                 {'expense_nature': '可变'}, format='json')
        assert resp.status_code == 200
        assert resp.data['expense_nature'] == '可变'

    def test_delete_rule_returns_hint(self):
        row = create_rule({'rule_field': 'category', 'match_value': '餐饮',
                           'expense_nature': '固定'})
        resp = self.client.delete(f'{RULES_URL}{row["id"]}/')
        assert resp.status_code == 200
        assert resp.data['deleted'] == row['id']
        assert 'hint' in resp.data

    def test_summary_endpoint(self):
        _rule(field='category', value='餐饮', nature='固定')
        resp = self.client.get(f'{RULES_URL}summary/')
        assert resp.status_code == 200
        assert resp.data['active'] == 1

    def test_seed_endpoint(self):
        resp = self.client.post(f'{RULES_URL}seed/', {}, format='json')
        assert resp.status_code == 200
        assert resp.data['created'] == len(CLASSIFY_SEED_RULES)

    def test_preview_endpoint(self):
        _bill(amount=100, category='食品酒水', subcategory='垃圾食品')
        resp = self.client.post(f'{RULES_URL}preview/', {
            'rule_field': 'subcategory', 'match_value': '垃圾食品',
            'expense_nature': '可变', 'yearmon': '2026-09',
        }, format='json')
        assert resp.status_code == 200
        assert resp.data['matched_count'] == 1

    def test_preview_bad_payload_returns_400(self):
        resp = self.client.post(f'{RULES_URL}preview/', {
            'rule_field': 'nope', 'match_value': 'x',
        }, format='json')
        assert resp.status_code == 400

    def test_periods_endpoint_returns_bare_array(self):
        _bill(year=2026, month=9, amount=1)
        resp = self.client.get(f'{RULES_URL}periods/')
        assert resp.status_code == 200
        assert isinstance(resp.data, list)
        assert resp.data == ['2026-09']

    def test_results_endpoint(self):
        _rule(field='category', value='房租', nature='固定', cashflow='必需支出')
        _bill(amount=800, category='房租')
        resp = self.client.get(RESULTS_URL, {'yearmon': '2026-09'})
        assert resp.status_code == 200
        assert resp.data['expense']['total'] == pytest.approx(800.0)
        assert resp.data['period_label'] == '2026-09'

    def test_results_endpoint_without_yearmon_is_all_periods(self):
        resp = self.client.get(RESULTS_URL)
        assert resp.status_code == 200
        assert resp.data['period_label'] == '全周期'

    def test_unclassified_endpoint(self):
        _bill(amount=100, category='食品酒水', subcategory='早午晚餐')
        resp = self.client.get(f'{RESULTS_URL}unclassified/', {'yearmon': '2026-09'})
        assert resp.status_code == 200
        assert resp.data['total_count'] == 1
        assert resp.data['items'][0]['suggested_field'] == 'subcategory'

    def test_unclassified_bad_limit_falls_back(self):
        _bill(amount=100, category='A', subcategory='a')
        resp = self.client.get(f'{RESULTS_URL}unclassified/', {'limit': 'abc'})
        assert resp.status_code == 200
        assert len(resp.data['items']) == 1
