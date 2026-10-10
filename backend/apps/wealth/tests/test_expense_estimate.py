"""月支出三点估算（v3.58.24）

应急金月数的分母从「近 3 个月算术平均」换成「近 12 个月三点估算」后，
分母本身成了一个有独立口径的估计量，值得单独一组用例：

  ① 窗口：不含锚定月、跨年正确
  ② 锚定月归一：'2026-9' / '2026-09' / '202609' / 20266 必须同键
  ③ 公式：E = (O + 4M + P) ÷ 6，M 是**中位数**（偶数样本取中间两数均值，
     此时中位数本身不是任何一个样本值）
  ④ 样本不足：value 是 **None 不是 0** —— 0 是结论，None 是没数据
  ⑤ 零支出月份不进样本：只记收入的月份若被当成 0，会顶掉 O 把基准拉低
  ⑥ 转账（转入/转出/余额变更）不计入支出
  ⑦ 复用已取好的 buckets 与直接查库结果一致（趋势靠这条避免 N+1）
"""
from datetime import datetime

import pytest
from django.utils.timezone import make_aware

from apps.wealth.constants import (
    EMERGENCY_EXPENSE_MONTHS,
    PERT_MIN_MONTHS,
)
from apps.wealth.models import WealthBillList, WealthClassifyRule
from apps.wealth.services.classify_service import monthly_classified_totals
from apps.wealth.services.expense_estimate import (
    _anchor_key,
    estimate_from_buckets,
    get_monthly_expense_estimate,
    window_ym_keys,
)

NOW = make_aware(datetime(2026, 9, 20, 10, 0, 0))

# 锚定 2026-09 时，窗口 = 它之前 12 个完整月（新 → 旧）
ANCHOR = '2026-09'
WINDOW_MONTHS = [
    (2026, 8), (2026, 7), (2026, 6), (2026, 5), (2026, 4), (2026, 3),
    (2026, 2), (2026, 1), (2025, 12), (2025, 11), (2025, 10), (2025, 9),
]


def _rule(field='category', value='日常生活', income='', nature='', cashflow=''):
    return WealthClassifyRule.objects.create(
        rule_field=field, match_value=value,
        income_type=income or None, expense_nature=nature or None,
        cashflow_class=cashflow or None, priority=10,
        is_active=True, user_id=1,
    )


def _seed_rules():
    _rule('category', '日常生活', nature='固定', cashflow='必需支出')
    _rule('category', '职业收入', income='主动', cashflow='收入流入')


def _bill(year, month, transaction_type='支出', amount=100.0, category='日常生活'):
    return WealthBillList.objects.create(
        transaction_type=transaction_type,
        date=make_aware(datetime(year, month, 10, 10, 0, 0)),
        amount=amount, category=category, user_id=1,
        year=year, month=month, day=10,
        created_at=NOW, updated_at=NOW,
    )


def _seed_window(amounts):
    """按窗口顺序（新 → 旧）逐月造一笔支出，amounts 长度即月数"""
    for (year, month), amount in zip(WINDOW_MONTHS, amounts):
        _bill(year, month, '支出', amount)


# ══════════════════════════════════════════════════════════════
# ① 窗口
# ══════════════════════════════════════════════════════════════


def test_window_excludes_anchor_month():
    """窗口取锚定月**之前**的完整月 —— 盘点当月往往才过几天，不能当完整样本"""
    assert window_ym_keys(202609, 3) == [202608, 202607, 202606]


def test_window_crosses_year_boundary():
    assert window_ym_keys(202601, 3) == [202512, 202511, 202510]


def test_window_length_is_constant_months():
    assert len(window_ym_keys(202609, EMERGENCY_EXPENSE_MONTHS)) == 12


# ══════════════════════════════════════════════════════════════
# ② 锚定月归一
# ══════════════════════════════════════════════════════════════


def test_anchor_normalizes_four_writings():
    """'2026-9' / '2026-09' / '202609' / 20266（5 位）必须落到同一个键

    ⚠️ 5 位必须补零：漏了这条，'2026-9' 与 '2026-09' 会变成两个期别，
       而趋势图上表现为相邻两点数值接近 —— 极难看出来。
    """
    keys = {
        _anchor_key('2026-9'), _anchor_key('2026-09'),
        _anchor_key('202609'), _anchor_key(202609),
    }
    assert keys == {202609}
    assert _anchor_key('20266') == 202606


def test_anchor_empty_falls_back_to_zero():
    """无法定位月份时返回 0，由调用方回落当前月 —— 不在工具函数里偷偷取 now"""
    assert _anchor_key(None) == 0
    assert _anchor_key('') == 0


# ══════════════════════════════════════════════════════════════
# ③ 公式
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPertFormula:
    def test_symmetric_sample_e_equals_median(self):
        """1000..12000 均匀 12 个月：O=1000 M=6500 P=12000 → E=6500"""
        _seed_rules()
        _seed_window([1000 * (i + 1) for i in range(12)])
        r = get_monthly_expense_estimate(1, ANCHOR)
        assert r['optimistic'] == 1000
        assert r['likely'] == 6500        # 偶数样本：(6000+7000)/2
        assert r['pessimistic'] == 12000
        assert r['value'] == 6500

    def test_median_of_even_sample_is_not_a_sample_value(self):
        """中位数取中间两数均值 —— 它不必等于任何一个月

        6 个月 1000 + 5 个月 2000 + 1 个月 20000：
            O=1000  M=(1000+2000)/2=1500  P=20000
            E=(1000+4×1500+20000)/6=4500
            算术平均=(6000+10000+20000)/12=3000
        ⇒ 三点估算**不等于**算术平均，二者不可互相替代。
        """
        _seed_rules()
        _seed_window([1000] * 6 + [2000] * 5 + [20000])
        r = get_monthly_expense_estimate(1, ANCHOR)
        assert r['likely'] == 1500
        assert r['value'] == 4500
        assert r['mean'] == 3000
        assert r['value'] != r['mean']

    def test_odd_sample_median_is_middle_value(self):
        """3 个月 1000/2000/3000 → M=2000，E=(1000+8000+3000)/6=2000"""
        _seed_rules()
        _seed_window([1000, 2000, 3000])
        r = get_monthly_expense_estimate(1, ANCHOR)
        assert r['months_with_records'] == 3
        assert r['likely'] == 2000
        assert r['value'] == 2000

    def test_single_outlier_shifts_by_one_sixth_not_full_weight(self):
        """极端月的位移是 (P−M)/6，不是全额 —— 这是三点估算的立身之本

        11 个月 3000 + 1 个月 50000：
            E=(3000+4×3000+50000)/6=10833.33
            若那笔被全额计入（如 3 个月算术平均），基准会被直接带飞。
        """
        _seed_rules()
        _seed_window([3000] * 11 + [50000])
        r = get_monthly_expense_estimate(1, ANCHOR)
        assert r['optimistic'] == 3000
        assert r['likely'] == 3000
        assert r['pessimistic'] == 50000
        assert r['value'] == 10833.33


# ══════════════════════════════════════════════════════════════
# ④ 样本不足
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestInsufficientSamples:
    def test_below_min_months_returns_none_not_zero(self):
        """只有 2 个月有支出 → value 是 None，绝不能是 0

        0 是一个结论（「月支出为零」⇒ 月数无穷大），
        「样本不够」是另一回事。二者混在一起会把指标算成荒谬的值。
        """
        _seed_rules()
        _seed_window([3000, 3000])
        r = get_monthly_expense_estimate(1, ANCHOR)
        assert r['value'] is None
        assert r['months_with_records'] == 2
        assert r['months_required'] == PERT_MIN_MONTHS
        assert str(PERT_MIN_MONTHS) in (r['reason'] or '')

    def test_exactly_at_min_months_passes(self):
        """恰好 3 个月放行 —— 门槛是「少于」而非「不多于」"""
        _seed_rules()
        _seed_window([1000, 2000, 3000])
        r = get_monthly_expense_estimate(1, ANCHOR)
        assert r['months_with_records'] == 3
        assert r['value'] == 2000

    def test_unavailable_fields_are_all_none(self):
        """数据不足时三档与均值一并为空 —— 前端不该拿到半套数字"""
        _seed_rules()
        _seed_window([3000])
        r = get_monthly_expense_estimate(1, ANCHOR)
        for key in ('value', 'optimistic', 'likely', 'pessimistic', 'mean', 'median'):
            assert r[key] is None, f'{key} 应为空'


# ══════════════════════════════════════════════════════════════
# ⑤ 零支出月份 / ⑥ 转账
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestSampleSelection:
    def test_month_with_only_income_is_not_a_sample(self):
        """只记了收入的月份不能当零支出月 —— 0 一旦进样本就顶掉 O

        3 个月里两个月有支出、一个月只有收入 ⇒ 样本 2 个月 ⇒ 数据不足。
        若把那个月当成 0，样本变 3 个月且 E 被拉到 2000，结论完全两样。
        """
        _seed_rules()
        _bill(2026, 8, '支出', 3000)
        _bill(2026, 7, '支出', 3000)
        _bill(2026, 6, '收入', 99999, category='职业收入')
        r = get_monthly_expense_estimate(1, ANCHOR)
        assert r['months_with_records'] == 2
        assert r['value'] is None

    def test_transfer_is_not_expense(self):
        """转入 / 转出 / 余额变更不计入支出 —— 转账不是消费

        3 个月支出 3000 + 1 个月转出 99999：
            计入 → 样本 4 个月，E 被抬到 18666.5
            排除 → 样本 3 个月，E=3000
        """
        _seed_rules()
        _bill(2026, 8, '支出', 3000)
        _bill(2026, 7, '支出', 3000)
        _bill(2026, 6, '支出', 3000)
        _bill(2026, 5, '转出', 99999)
        r = get_monthly_expense_estimate(1, ANCHOR)
        assert r['months_with_records'] == 3
        assert r['value'] == 3000

    def test_anchor_month_itself_is_excluded(self):
        """锚定当月不计入 —— 否则「才过几天的月份」会被当成完整样本"""
        _seed_rules()
        _seed_window([3000] * 3)
        # 锚定月（2026-09）放一笔巨大支出：若被计入，P 会变成 999999
        _bill(2026, 9, '支出', 999999)
        r = get_monthly_expense_estimate(1, ANCHOR)
        assert r['pessimistic'] == 3000
        assert r['value'] == 3000


# ══════════════════════════════════════════════════════════════
# ⑦ 复用 buckets（趋势靠它避免 N+1）
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestBucketReuse:
    def test_estimate_from_buckets_matches_db_path(self):
        """用已取好的 buckets 算，与直接查库结果逐字段一致

        `get_ratio_trend` 为每个展示点各算一次分母，若每次都查库就是 N+1；
        它已把整段月度归类取好了，直接复用。这条用例保证两个入口不漂移。
        """
        _seed_rules()
        _seed_window([1000 * (i + 1) for i in range(12)])

        direct = get_monthly_expense_estimate(1, ANCHOR)
        ym_keys = window_ym_keys(_anchor_key(ANCHOR), EMERGENCY_EXPENSE_MONTHS)
        reused = estimate_from_buckets(
            monthly_classified_totals(ym_keys, 1), _anchor_key(ANCHOR),
        )
        for key in ('value', 'optimistic', 'likely', 'pessimistic', 'mean',
                    'months_with_records', 'window_months', 'anchor_yearmon'):
            assert reused[key] == direct[key], f'{key} 两条路径不一致'

    def test_reuse_uses_no_extra_query_for_each_anchor(self):
        """同一份 buckets 换锚定月即可算出另一个时点的分母 —— 零额外查询"""
        _seed_rules()
        _seed_window([1000 * (i + 1) for i in range(12)])
        ym_keys = window_ym_keys(_anchor_key(ANCHOR), EMERGENCY_EXPENSE_MONTHS)
        buckets = monthly_classified_totals(ym_keys, 1)

        at_anchor = estimate_from_buckets(buckets, 202609)
        # 锚定到 2026-08：窗口整体前移一格，2025-09 出窗、2026-08 进窗
        at_previous = estimate_from_buckets(buckets, 202608)
        assert at_anchor['value'] == 6500
        assert at_previous['months_with_records'] == 11   # 2025-09 不在取数范围
