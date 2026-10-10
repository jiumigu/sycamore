"""物件资产 · 计算引擎（v3.60.0）—— 算法唯一真源的用例

覆盖：
  ① 整月向下取整：2024-03-15 → 2026-09-24 = 30 月；2024-03-25 → 同一天 = 29 月
  ② 净值截断到 0（不出现负净值）；月折旧 = 金额 ÷ 年限，计算过程不提前舍入
  ③ 剩余月数**可为负** —— 超期是事实、不是错误，且**不产生 issue**
  ④ 报废时净值以**报废日定格**：换一个「今天」重算，结果必须一模一样
  ⑤ 五种「算不出」各一条：缺金额 / 缺日期 / 缺年限 / 购买日在未来 / 报废缺日
     —— 一律 None + issues，**绝不返回 0**（0 是「折完了」，不是「不确定」）
  ⑥ 年限换算只走 years_to_months（8.5 年 = 102 月）
  ⑦ 合计四项同发：total / counted / unpriced_count / unvalued_count
  ⑧ 🔴 损坏钉子（2026-09-26 订正口径）：condition='broken' ⇒ **净值恒为 0.00**，
     但件数 / 原值 / 已用 / 计划 / 超期 / 月折旧**一个都不动**，且 0 ≠ 「算不出」
  ⑨ 🔴 反向钉子：本模块不存在体型 / 价值档这两把尺子 + /meta/ 键名清单

新表由 conftest 的 session 级 django_db_setup 镜像建表 ——
--no-migrations --reuse-db 下新 managed 表不会自动出现。
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.wealth import constants as C
from apps.wealth.models import WealthProperty, WealthPropertyCategory
from apps.wealth.services import property_calc as calc

TODAY = date(2026, 9, 24)


def _category(name='家电'):
    return WealthPropertyCategory.objects.create(user_id=1, name=name)


def _prop(category, name='海尔冰箱', **extra):
    payload = {
        'user_id': 1,
        'category': category,
        'name': name,
        'status': extra.pop('status', 'in_use'),
        'condition': extra.pop('condition', 'normal'),
    }
    payload.update(extra)
    return WealthProperty.objects.create(**payload)


def _summary_rows(category):
    """把类别下的物件组装成 summarize 需要的行（与 service 层同口径）。

    ⚠️ `condition` 必须在场：summarize 用它数出 broken_count。
       少传它会在 summarize 里 KeyError —— 这是**刻意**的（宁可炸，不要默认值）。
    """
    rows = []
    for prop in WealthProperty.objects.filter(category=category):
        computed = calc.compute_property(prop, today=TODAY)
        rows.append({
            'status': prop.status,
            'condition': prop.condition,
            'purchase_amount': prop.purchase_amount,
            'current_value': computed['current_value'],
        })
    return rows


@pytest.mark.django_db
class TestYearsToMonths:
    """年限换算只此一处 —— 界面填年、库里存月。"""

    def test_integer_years(self):
        assert calc.years_to_months(8) == 96

    def test_fractional_years(self):
        # 8.5 年 = 8 年 6 月
        assert calc.years_to_months(8.5) == 102

    def test_half_year(self):
        assert calc.years_to_months(0.5) == 6

    def test_none_stays_none(self):
        # 留空就是留空 —— 不返回 0，也不给任何默认值
        assert calc.years_to_months(None) is None
        assert calc.years_to_months('') is None

    def test_garbage_returns_none(self):
        assert calc.years_to_months('八年') is None


class TestFormatMonths:
    def test_years_and_months(self):
        assert calc.format_months(38) == '3 年 2 月'

    def test_only_years(self):
        assert calc.format_months(120) == '10 年'

    def test_only_months(self):
        assert calc.format_months(5) == '5 月'

    def test_negative_is_kept(self):
        # 超期是事实：负数要照实显示，不能被 abs 掉
        assert calc.format_months(-26) == '-2 年 2 月'

    def test_none_is_dash(self):
        assert calc.format_months(None) == '—'


@pytest.mark.django_db
class TestAgeMonths:
    """整月向下取整 —— 不足一月不算。"""

    def test_day_reached_counts_full_month(self):
        prop = _prop(_category(), purchase_date=date(2024, 3, 15))
        assert calc.compute_property(prop, today=TODAY)['age_months'] == 30

    def test_day_not_reached_loses_a_month(self):
        prop = _prop(_category(), purchase_date=date(2024, 3, 25))
        assert calc.compute_property(prop, today=TODAY)['age_months'] == 29

    def test_same_day_is_exact(self):
        prop = _prop(_category(), purchase_date=date(2024, 9, 24))
        assert calc.compute_property(prop, today=TODAY)['age_months'] == 24


@pytest.mark.django_db
class TestCurrentValue:
    """直线法折旧、残值 0；截断到 0，不出现负净值。"""

    def test_partway_value(self):
        prop = _prop(
            _category(),
            purchase_amount=Decimal('6000'),
            purchase_date=date(2024, 9, 24),
            lifespan_months=60,
        )
        result = calc.compute_property(prop, today=TODAY)
        # 已用 24 月、月折旧 100 ⇒ 6000 − 2400 = 3600
        assert result['age_months'] == 24
        assert result['monthly_depreciation'] == Decimal('100.00')
        assert result['current_value'] == Decimal('3600.00')

    def test_cut_off_at_zero(self):
        prop = _prop(
            _category(),
            purchase_amount=Decimal('3600'),
            purchase_date=date(2024, 9, 24),
            lifespan_months=12,
        )
        result = calc.compute_property(prop, today=TODAY)
        assert result['current_value'] == Decimal('0.00')
        assert result['current_value'] >= 0

    def test_never_negative(self):
        prop = _prop(
            _category(),
            purchase_amount=Decimal('1200'),
            purchase_date=date(2016, 5, 10),
            lifespan_months=96,
        )
        assert calc.compute_property(prop, today=TODAY)['current_value'] == Decimal('0.00')


@pytest.mark.django_db
class TestRemainingMonths:
    """剩余月数可为负 —— 超期是事实，不是错误。"""

    def test_overdue_is_negative_and_not_an_issue(self):
        # 三样给齐（金额 / 日期 / 年限）—— 这样 issues 才真的为空，断言才有意义
        prop = _prop(
            _category(),
            purchase_amount=Decimal('1200'),
            purchase_date=date(2016, 5, 10),
            lifespan_months=96,
        )
        result = calc.compute_property(prop, today=TODAY)
        assert result['age_months'] == 124          # 10 年 4 月
        assert result['remaining_months'] == -28
        assert result['is_overdue'] is True
        assert result['overdue_months'] == 28
        # 🔴 超期**不产生 issue** —— 只给它一句中性标注，不当成错误
        assert result['issues'] == []

    def test_not_overdue(self):
        prop = _prop(_category(), purchase_date=date(2024, 9, 24), lifespan_months=60)
        result = calc.compute_property(prop, today=TODAY)
        assert result['remaining_months'] == 36
        assert result['is_overdue'] is False
        assert result['overdue_months'] == 0


@pytest.mark.django_db
class TestScrappedValueIsFrozen:
    """报废时净值以报废日定格 —— 之后不再随日历变化。"""

    def _scrapped(self):
        return _prop(
            _category(),
            name='旧洗衣机',
            status='scrapped',
            purchase_amount=Decimal('6000'),
            purchase_date=date(2024, 9, 24),
            lifespan_months=60,
            scrapped_date=date(2025, 9, 24),        # 12 个月后报废
        )

    def test_value_uses_scrap_date(self):
        result = calc.compute_property(self._scrapped(), today=TODAY)
        assert result['ref_date'] == date(2025, 9, 24)
        assert result['age_months'] == 12
        # 6000 − 12 × 100 = 4800
        assert result['current_value'] == Decimal('4800.00')

    def test_frozen_against_a_different_today(self):
        """换一个「今天」重算，结果必须完全一样 —— 这就是「定格」的全部含义。"""
        prop = self._scrapped()
        a = calc.compute_property(prop, today=date(2026, 9, 24))
        b = calc.compute_property(prop, today=date(2029, 1, 1))
        assert a['current_value'] == b['current_value']
        assert a['age_months'] == b['age_months']
        assert a['remaining_months'] == b['remaining_months']


@pytest.mark.django_db
class TestUncomputableReturnsNone:
    """算不出来就说算不出来 —— 返回 None + issues，**绝不返回 0**。"""

    def test_no_amount(self):
        prop = _prop(_category(), purchase_date=date(2024, 9, 24), lifespan_months=60)
        result = calc.compute_property(prop, today=TODAY)
        assert result['current_value'] is None
        assert result['monthly_depreciation'] is None
        # 剩余月数仍算得出 —— 它不依赖金额
        assert result['remaining_months'] == 36
        assert 'NO_AMOUNT' in {i['code'] for i in result['issues']}

    def test_no_purchase_date(self):
        prop = _prop(_category(), purchase_amount=Decimal('6000'), lifespan_months=60)
        result = calc.compute_property(prop, today=TODAY)
        assert result['current_value'] is None
        assert result['remaining_months'] is None
        assert 'NO_PURCHASE_DATE' in {i['code'] for i in result['issues']}

    def test_no_lifespan(self):
        prop = _prop(_category(), purchase_amount=Decimal('6000'),
                     purchase_date=date(2024, 9, 24))
        result = calc.compute_property(prop, today=TODAY)
        assert result['current_value'] is None
        assert result['remaining_months'] is None
        assert 'NO_LIFESPAN' in {i['code'] for i in result['issues']}

    def test_future_purchase_date(self):
        prop = _prop(
            _category(),
            purchase_amount=Decimal('6000'),
            purchase_date=date(2027, 1, 1),
            lifespan_months=60,
        )
        result = calc.compute_property(prop, today=TODAY)
        assert result['age_months'] is None
        assert result['current_value'] is None
        assert 'FUTURE_PURCHASE_DATE' in {i['code'] for i in result['issues']}

    def test_scrapped_without_date(self):
        prop = _prop(
            _category(),
            status='scrapped',
            purchase_amount=Decimal('6000'),
            purchase_date=date(2024, 9, 24),
            lifespan_months=60,
            scrapped_date=None,
        )
        result = calc.compute_property(prop, today=TODAY)
        # 不兜底成今天 —— 那等于假装它今天才报废
        assert result['ref_date'] is None
        assert result['current_value'] is None
        assert result['age_months'] is None
        assert 'NO_SCRAP_DATE' in {i['code'] for i in result['issues']}

    def test_every_issue_carries_a_label(self):
        """原因码必须能翻成人话（前端点开「—」看到的就是它）。"""
        prop = _prop(_category(), purchase_date=date(2024, 9, 24), lifespan_months=60)
        for issue in calc.compute_property(prop, today=TODAY)['issues']:
            assert issue['code'] in C.PROPERTY_ISSUE_LABELS
            assert issue['label'] and issue['label'] != issue['code']


@pytest.mark.django_db
class TestBrokenZeroesTheValue:
    """🔴 损坏 ⇒ 净值归 0（2026-09-26 订正的口径）。

    改口径之前这个类叫 `TestConditionIsOrthogonal`，钉的是「损坏不影响任何数字」。
    炸点很具体：用户看到两副已报废的眼镜（状况=损坏）净值还挂着 ¥151.48，
    要求「坏了就该是 0」。于是净值那一项改为按 0 计。

    这个类现在钉**三个方向**，缺一个都会出事：
      ① 净值必须真的归 0 —— 否则「坏了还值钱」会继续挂在账上；
      ② 除净值外**一个数都不许变**（件数 / 原值 / 已用 / 计划 / 超期 / 月折旧）——
         否则一次误标「损坏」会连带改写时间事实，那是更贵的那种错；
      ③ 0 不能变成「算不出」的另一种写法 —— 缺金额的损坏件照样是 0.00，不是 None。
    """

    def test_broken_zeroes_only_the_value(self):
        normal = _prop(
            _category(), name='正常的空调',
            purchase_amount=Decimal('6000'),
            purchase_date=date(2024, 9, 24), lifespan_months=60,
        )
        broken = _prop(
            _category(name='家具'), name='坏了的空调', condition='broken',
            purchase_amount=Decimal('6000'),
            purchase_date=date(2024, 9, 24), lifespan_months=60,
        )
        a = calc.compute_property(normal, today=TODAY)
        b = calc.compute_property(broken, today=TODAY)

        # ① 净值归 0，且说得出为什么
        assert a['current_value'] == Decimal('3600.00')
        assert a['zero_reason'] is None
        assert b['current_value'] == Decimal('0.00')
        assert b['zero_reason'] == calc.ZERO_REASON_BROKEN

        # ② 其余派生值一个都没动 —— 它们回答的是时间问题，与好不好使无关
        assert a['age_months'] == b['age_months'] == 24
        assert a['remaining_months'] == b['remaining_months'] == 36
        assert a['monthly_depreciation'] == b['monthly_depreciation'] == Decimal('100.00')
        assert a['is_overdue'] is False and b['is_overdue'] is False
        assert a['issues'] == b['issues'] == []
        assert a['ref_date'] == b['ref_date'] == TODAY

    def test_broken_still_counts_as_one_item(self):
        """件数与原值照常 —— 坏了但还留着，它照样是一件家当、也照样是花掉的钱。"""
        cat = _category()
        for name, cond in (('正常的空调', 'normal'), ('坏了的空调', 'broken')):
            _prop(
                cat, name=name, condition=cond,
                purchase_amount=Decimal('6000'),
                purchase_date=date(2024, 9, 24), lifespan_months=60,
            )
        result = calc.summarize(_summary_rows(cat))

        assert result['in_use_count'] == 2
        assert result['total_amount']['total'] == Decimal('12000')
        # 净值只剩正常那一件 —— 损坏那件按 0 计，但**仍然计入 counted**
        assert result['in_use_net_value']['total'] == Decimal('3600.00')
        assert result['in_use_net_value']['counted'] == 2
        assert result['in_use_net_value']['broken_count'] == 1
        # 它是「算得出，就是 0」，不是「算不出」—— 两个桶不许串
        assert result['in_use_net_value']['unvalued_count'] == 0

    def test_broken_without_amount_is_zero_not_none(self):
        """缺金额的损坏件：净值仍是 0.00，**不是** None。

        「坏了就不值钱」独立成立，不依赖金额填没填 —— 这里若返回 None，
        界面会显示「—」，而「—」读起来是「算不出来」，与事实正好相反。
        ⚠️ 但 NO_AMOUNT 这个 issue 要照旧报：它仍然影响原值合计。
        """
        prop = _prop(
            _category(), name='忘了多少钱的坏柜子', condition='broken',
            purchase_date=date(2024, 9, 24), lifespan_months=60,
        )
        computed = calc.compute_property(prop, today=TODAY)
        assert computed['current_value'] == Decimal('0.00')
        assert computed['zero_reason'] == calc.ZERO_REASON_BROKEN
        assert [i['code'] for i in computed['issues']] == ['NO_AMOUNT']

    def test_depreciated_and_broken_are_told_apart(self):
        """净值为 0 的两个来源必须能分开：「已折完」与「坏了」要采取的行动不同。"""
        worn_out = _prop(
            _category(), name='用够了的洗衣机',
            purchase_amount=Decimal('2400'),
            purchase_date=date(2016, 9, 24), lifespan_months=120,
        )
        broken = _prop(
            _category(name='家具'), name='半道坏了的柜子', condition='broken',
            purchase_amount=Decimal('2400'),
            purchase_date=date(2024, 9, 24), lifespan_months=120,
        )
        a = calc.compute_property(worn_out, today=TODAY)
        b = calc.compute_property(broken, today=TODAY)
        assert a['current_value'] == b['current_value'] == Decimal('0.00')
        assert a['zero_reason'] == calc.ZERO_REASON_DEPRECIATED
        assert b['zero_reason'] == calc.ZERO_REASON_BROKEN


@pytest.mark.django_db
class TestSummarize:
    """合计口径：四项同发、不按 0 计、不注水。"""

    def test_counts_and_totals(self):
        cat = _category()
        _prop(cat, name='冰箱', purchase_amount=Decimal('3200'),
              purchase_date=date(2021, 6, 1), lifespan_months=120)
        _prop(cat, name='空调', purchase_amount=Decimal('4500'),
              purchase_date=date(2016, 5, 10), lifespan_months=96)
        _prop(cat, name='旧洗衣机', status='scrapped',
              purchase_amount=Decimal('1800'),
              purchase_date=date(2014, 3, 2), lifespan_months=96,
              scrapped_date=date(2020, 3, 2))
        result = calc.summarize(_summary_rows(cat))

        assert result['in_use_count'] == 2
        assert result['scrapped_count'] == 1
        # 原值合计**含已报废** —— 「一共投进去多少钱」是历史总投入
        assert result['total_amount']['total'] == Decimal('9500')
        assert result['total_amount']['counted'] == 3
        assert result['total_amount']['unpriced_count'] == 0
        assert result['total_amount']['unvalued_count'] == 0
        # 净值只算还在手上的那两件
        assert result['in_use_net_value']['counted'] == 2

    def test_unpriced_reported_not_swallowed(self):
        """没填金额的物件不计入金额，但件数必须报出来。"""
        cat = _category()
        _prop(cat, name='冰箱', purchase_amount=Decimal('3200'),
              purchase_date=date(2021, 6, 1), lifespan_months=120)
        _prop(cat, name='忘了多少钱的柜子',
              purchase_date=date(2020, 1, 1), lifespan_months=120)
        result = calc.summarize(_summary_rows(cat))

        assert result['total_amount']['total'] == Decimal('3200')
        assert result['total_amount']['counted'] == 1
        assert result['total_amount']['unpriced_count'] == 1
        assert result['in_use_net_value']['unpriced_count'] == 1

    def test_unvalued_is_a_different_bucket_from_unpriced(self):
        """「填了金额但缺年限」与「没填金额」必须分开 —— 它们指向不同的动作。"""
        cat = _category()
        _prop(cat, name='有金额没年限',
              purchase_amount=Decimal('3200'), purchase_date=date(2021, 6, 1))
        result = calc.summarize(_summary_rows(cat))

        assert result['total_amount']['unpriced_count'] == 0
        assert result['in_use_net_value']['unpriced_count'] == 0
        assert result['in_use_net_value']['unvalued_count'] == 1
        assert result['in_use_net_value']['counted'] == 0

    def test_scrapped_excluded_from_net_value_but_kept_in_original(self):
        cat = _category()
        _prop(cat, name='已报废的', status='scrapped',
              purchase_amount=Decimal('1000'),
              purchase_date=date(2020, 1, 1), lifespan_months=120,
              scrapped_date=date(2023, 1, 1))
        result = calc.summarize(_summary_rows(cat))

        assert result['in_use_count'] == 0
        assert result['in_use_net_value']['total'] == Decimal('0')
        assert result['in_use_net_value']['counted'] == 0
        assert result['total_amount']['total'] == Decimal('1000')

    def test_empty_collection_is_zero_not_none(self):
        """一件都没有时合计是 0 —— 这是「真的没有」，不是「算不出」。"""
        result = calc.summarize([])
        assert result['in_use_count'] == 0
        assert result['total_amount']['total'] == Decimal('0')
        assert result['in_use_net_value']['total'] == Decimal('0')


class TestNoSecondRuler:
    """🔴 反向钉子：本模块**没有**体型 / 价值档这两把尺子。

    设计期已明确否决（设计文档 §4.3 专条）：
      「大物件 / 小玩意儿」是体积尺、「高价值物件」是金额尺，
      而类别是用途尺 —— 三把尺子混进一个必填下拉，相机那种物件会选不出来。
      价值判断改用「按金额排序」回答，**不落字段**。
    判据：能排序出来的，不要存成档位；能算出来的，不要存成标签。
    """

    def test_no_size_or_value_tier_constant(self):
        names = [n for n in dir(C) if n.startswith('PROPERTY_')]
        banned = ('SIZE', 'TIER', 'IMPORTANCE', 'VALUE_LEVEL', 'GRADE', 'BIG', 'SMALL')
        offenders = sorted(n for n in names if any(b in n for b in banned))
        assert offenders == [], f'出现了被否决的维度常量：{offenders}'

    def test_no_such_model_field(self):
        field_names = {f.name for f in WealthProperty._meta.get_fields()}
        banned = {'size_class', 'value_tier', 'importance', 'value_level'}
        assert field_names & banned == set()

    def test_meta_notes_cover_every_banner_key(self):
        """键名清单：前端要挂 ⓘ 的每个 key 都必须在后端存在。

        ⚠️ MetricTooltip 取不到 meta 是**静默不渲染** ——
           键名写错与「本来就没打算加 ⓘ」在界面上长得完全一样，能持续很久没人发现。
        """
        expected = {
            'in_use_count', 'total_amount', 'in_use_net_value', 'scrapped_count',
            'current_value', 'age_vs_lifespan', 'lifespan_months', 'condition',
        }
        assert expected <= set(C.PROPERTY_METRIC_NOTES)
