"""财务规划比率（v3.58.23，P2-A）

覆盖：
  ① 判定线查表：左闭右开、负值落首档、无区间返回空级别、未知 key 不炸
  ② **同期多行去重**（旧表真实存在 2026-06 两行）：按期取数不抛
     MultipleObjectsReturned、趋势不出同月双点、写入更新最新一行
  ③ 资产来源：有任一新体系快照即整条切换到新体系（不逐月混合）；
     carry_forward 语义（本月未盘点取上一期且标 carried）
  ④ 应急金月数/刚性支出覆盖率：只对有记录的月份求均值（不除以固定月数，
     否则无记录月份被当成零支出、月数虚高）；与资产健康指标卡的数一致
  ⑤ 被动收入覆盖率：分母是总支出而非月均；窗口 12 个月
  ⑥ DTI：无「在还」负债 → 不可用且原因可执行；有 → 值正确；台账为空
     与「有行但都不在还」是两种不同原因
  ⑦ 净值增长率：净储蓄按盘点日半开区间（含期末日、不含期初日）；
     级别由残差符号派生；期初净资产非正 → 不可用
  ⑧ 支出质量指数：necessity 填写率低于门槛 → 不可用（不拿小样本除以全量）
  ⑨ **不可用的比率 value 一律 None，绝不返回 0**（0 是结论，None 是没数据）
  ⑩ 趋势：长度、升序、DTI 被排除且 series 里不留空数组
  ⑪ 接口：总览/趋势/锚定月/资产位置；锚定月列表是**裸数组**

比例数字依赖 wealth_classify_rule（分类规则），新表由 conftest 的
session 级 django_db_setup 镜像建表 —— --no-migrations --reuse-db 下
新表不会自动出现。
"""
from datetime import date, datetime, timedelta

import pytest
from django.utils.timezone import make_aware
from rest_framework.test import APIClient

from apps.wealth.constants import EMERGENCY_EXPENSE_MONTHS, QUALITY_MIN_COVERAGE
from apps.wealth.models import (
    WealthAssetAccount,
    WealthAssetSnapshot,
    WealthAssetSnapshotItem,
    WealthBillList,
    WealthCashFlow,
    WealthClassifyRule,
    WealthLiabilityDetail,
)
from apps.wealth.services.cashflow_service import (
    create_or_update_snapshot,
    get_asset_trend,
    get_cashflow_by_yearmon,
    get_cashflow_overview,
    get_snapshot_series,
    norm_yearmon,
)
from apps.wealth.services.ratio_grade import grade_ratio, ratio_meta
from apps.wealth.services.ratio_service import (
    available_anchor_months,
    get_ratio_overview,
    get_ratio_trend,
    resolve_asset_position,
    resolve_asset_series,
    resolve_asset_source,
)

RATIOS_URL = '/api/wealth/ratios/'
NOW = datetime.now()


# ══════════════════════════════════════════════════════════════
# 造数工具
# ══════════════════════════════════════════════════════════════


def _bill(year, month, day, transaction_type='支出', amount=100.0,
          category='', subcategory='', merchant='', necessity=None):
    return WealthBillList.objects.create(
        transaction_type=transaction_type,
        date=make_aware(datetime(year, month, day, 10, 0, 0)),
        amount=amount, category=category, subcategory=subcategory,
        merchant=merchant, necessity=necessity, user_id=1,
        year=year, month=month, day=day,
        created_at=make_aware(NOW), updated_at=make_aware(NOW),
    )


def _rule(field='category', value='日常生活', income='', nature='',
          cashflow='', priority=10):
    return WealthClassifyRule.objects.create(
        rule_field=field, match_value=value,
        income_type=income or None, expense_nature=nature or None,
        cashflow_class=cashflow or None, priority=priority,
        is_active=True, user_id=1,
    )


def _cash_flow(yearmon, btime, **accounts):
    defaults = dict(
        zplay=0, wechat=0, cash=0, jianbank=0, gongbank=0,
        zhongbank=0, nongbank=0, accumulationfund=0, lend=0, borrow=0,
    )
    defaults.update(accounts)
    return WealthCashFlow.objects.create(yearmon=yearmon, btime=btime, **defaults)


def _account(name, category='流动性', kind='储蓄卡', is_liquid=True,
             include_in_balance_sheet=True, sort=10):
    return WealthAssetAccount.objects.create(
        name=name, category=category, account_kind=kind,
        is_liquid=is_liquid, include_in_balance_sheet=include_in_balance_sheet,
        sort=sort, user_id=1,
    )


def _snapshot(yearmon, snapshot_date, borrow=0.0, items=()):
    snap = WealthAssetSnapshot.objects.create(
        yearmon=yearmon, snapshot_date=snapshot_date,
        borrow=borrow, user_id=1,
    )
    for account, amount in items:
        WealthAssetSnapshotItem.objects.create(
            snapshot=snap, account=account, amount=amount,
        )
    return snap


def _liability(name='房贷', monthly_payment=0.0, status='在还'):
    return WealthLiabilityDetail.objects.create(
        name=name, category='房贷', principal=100000, outstanding=80000,
        annual_rate=4.9, monthly_payment=monthly_payment, status=status,
        user_id=1,
    )


def _recent_pairs(count):
    """自当前月起往前 count 个自然月的 [(年, 月)]（降序，含当前月）"""
    year, month = NOW.year, NOW.month
    pairs = []
    for _ in range(count):
        pairs.append((year, month))
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    return pairs


def _recent_labels(count):
    return [f'{y:04d}-{m:02d}' for y, m in _recent_pairs(count)]


def _seed_classify_rules():
    """两条最简规则：支出算固定、收入算主动 —— 让各维度都有标签可算"""
    _rule('category', '日常生活', nature='固定', cashflow='必需支出')
    _rule('category', '职业收入', income='主动', cashflow='收入流入')


def _fixed_scenario():
    """确定性场景：2026-07/08/09 三个月，各一笔支出 3000 + 一笔收入 10000

    两期盘点：2026-08 净资产 80000、2026-09 净资产 82000。
    盘点日 2026-08-27 / 2026-09-08，故只有 2026-09-05 的流水落在
    净值增长率的净储蓄窗口内 —— 这是刻意为「半开区间」准备的。
    """
    _seed_classify_rules()
    _cash_flow('2026-08', date(2026, 8, 27), zplay=8000, wechat=5000, cash=1000,
               jianbank=20000, accumulationfund=50000, lend=8000, borrow=12000)
    _cash_flow('2026-09', date(2026, 9, 8), zplay=10000, wechat=5000, cash=1000,
               jianbank=20000, accumulationfund=50000, lend=8000, borrow=12000)
    # 2026-08-20 在期初日之前 → 不算进 8/27→9/8 的净储蓄
    _bill(2026, 8, 20, '支出', 3000, category='日常生活', necessity='可选')
    _bill(2026, 8, 20, '收入', 10000, category='职业收入')
    _bill(2026, 7, 15, '支出', 3000, category='日常生活', necessity='必要')
    _bill(2026, 7, 15, '收入', 10000, category='职业收入')
    # 只有这一笔落在净储蓄窗口内
    _bill(2026, 9, 5, '支出', 3000, category='日常生活', necessity='冲动')
    _bill(2026, 9, 5, '收入', 10000, category='职业收入')


def _ratio_of(payload, key):
    for ratio in payload['ratios']:
        if ratio['key'] == key:
            return ratio
    raise AssertionError(f'总览里没有 {key}')


# ══════════════════════════════════════════════════════════════
# ① 判定线查表
# ══════════════════════════════════════════════════════════════


class TestRatioGrade:
    """判定线是纯函数，不落库 —— 这些用例不需要 django_db"""

    def test_band_boundary_is_left_closed(self):
        """区间左闭右开：6.0 必须落「充足」，不能同时满足两档"""
        assert grade_ratio('emergency_months', 5.99)['level'] == 'warn'
        assert grade_ratio('emergency_months', 6.0)['level'] == 'good'

    def test_negative_value_falls_into_first_band(self):
        """负值（净值为负时的比率）自动落首档，不需要服务层补特例"""
        assert grade_ratio('emergency_months', -5)['level'] == 'danger'
        assert grade_ratio('dti', -1)['level'] == 'good'

    def test_lower_better_direction_bands(self):
        assert grade_ratio('dti', 29.9)['level'] == 'good'
        assert grade_ratio('dti', 30.0)['level'] == 'warn'
        assert grade_ratio('dti', 40.0)['level'] == 'danger'

    def test_none_value_has_no_level(self):
        assert grade_ratio('dti', None) == {'level': None, 'level_label': None}

    def test_ratio_without_bands_has_no_level(self):
        """净值增长率/支出质量指数报告未给判定线 —— 不发明阈值"""
        assert grade_ratio('net_worth_growth', 5)['level'] is None
        assert grade_ratio('expense_quality', 30)['level'] is None

    def test_unknown_key_does_not_raise(self):
        assert grade_ratio('not_a_ratio', 1) == {'level': None, 'level_label': None}
        assert ratio_meta('not_a_ratio')['label'] == 'not_a_ratio'

    def test_meta_exposes_bands_for_frontend(self):
        """区间随接口下发 —— 前端据此画刻度，不必复制任何阈值数字"""
        meta = ratio_meta('emergency_months')
        assert isinstance(meta['bands'], list)
        assert meta['bands'][0] == [0, 3, 'danger', '不足']
        assert meta['target'] == 6

    def test_all_ratio_keys_have_meta(self):
        from apps.wealth.constants import RATIO_ORDER

        for key in RATIO_ORDER:
            meta = ratio_meta(key)
            assert meta['label'] and meta['formula'], f'{key} 缺 label/formula'

    def test_health_card_ratios_are_graded_here_too(self):
        """资产健康指标卡的三个占比：档位也在同一张表判定（不另立一份）。

        原先是写死在 HealthMetrics.vue 里的 `> 30 ? warn : > 10 ? good : bad`
        一类表达式 —— 报告 3.4 点名的「已实现指标阈值硬编码」正指这些。
        """
        # 活期占比：低于 10 是「过紧」（danger），10–30 合理，30 以上「闲置偏多」
        assert grade_ratio('liquidity_ratio', 5)['level'] == 'danger'
        assert grade_ratio('liquidity_ratio', 10)['level'] == 'good'
        assert grade_ratio('liquidity_ratio', 30)['level'] == 'warn'
        # 负债率：30 与 50 是两条分界，均为左闭右开
        assert grade_ratio('debt_ratio', 29.9)['level'] == 'good'
        assert grade_ratio('debt_ratio', 30)['level'] == 'warn'
        assert grade_ratio('debt_ratio', 50)['level'] == 'danger'
        # 公积金占比：高档位是 warn 而非 danger（公积金不是坏资产，只是流动性差）
        assert grade_ratio('provident_fund_ratio', 49.9)['level'] == 'normal'
        assert grade_ratio('provident_fund_ratio', 50)['level'] == 'warn'

    def test_health_card_ratios_expose_meta(self):
        for key in ('liquidity_ratio', 'debt_ratio', 'provident_fund_ratio'):
            meta = ratio_meta(key)
            assert meta['label'] and meta['formula'], f'{key} 缺 label/formula'
            assert meta['bands'], f'{key} 缺判定区间'

    def test_health_card_ratios_not_in_ratio_panel(self):
        """三项卡片指标**不进**比率面板 —— RATIO_ORDER 是面板的唯一出口清单"""
        from apps.wealth.constants import RATIO_BANDS, RATIO_ORDER

        for key in ('liquidity_ratio', 'debt_ratio', 'provident_fund_ratio'):
            assert key in RATIO_BANDS, f'{key} 应在判定线总表里'
            assert key not in RATIO_ORDER, f'{key} 不该出现在比率面板'


# ══════════════════════════════════════════════════════════════
# ①-b 资产健康指标卡的档位下发（阈值收回后端的接线验证）
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestHealthCardLevels:
    """卡上四项的 level 必须真的从响应里出来 —— 光有判定线不算完成。

    这类「判定线写好了但没接上」的失效是静默的：接口照常 200、
    前端拿到 level=undefined 后 `if (!level)` 分支把颜色退成灰的，
    界面看着正常，只是再也反映不了任何阈值。
    """

    def _overview(self):
        # 现金 50000 / 公积金 60000 / 借款 20000，无应收
        # → 总资产 110000：活期占比 45.5%（闲置偏多）、负债率 18.2%（稳健）、
        #   公积金占比 54.5%（占比偏高）
        _cash_flow('2026-06', date(2026, 6, 29), zplay=50000,
                   accumulationfund=60000, borrow=20000)
        return get_cashflow_overview()

    def test_card_ratios_carry_level_from_backend(self):
        hm = self._overview()['health_metrics']
        assert hm['liquidity_ratio_level'] == grade_ratio(
            'liquidity_ratio', hm['liquidity_ratio'])['level'] == 'warn'
        assert hm['debt_ratio_level'] == grade_ratio(
            'debt_ratio', hm['debt_ratio'])['level'] == 'good'
        assert hm['provident_fund_ratio_level'] == grade_ratio(
            'provident_fund_ratio', hm['provident_fund_ratio'])['level'] == 'warn'

    def test_card_levels_have_human_labels(self):
        hm = self._overview()['health_metrics']
        assert hm['liquidity_ratio_level_label'] == '闲置偏多'
        assert hm['debt_ratio_level_label'] == '稳健'
        assert hm['provident_fund_ratio_level_label'] == '占比偏高'

    def test_api_serializes_the_level_fields(self):
        """漏了序列化器字段 = 接口里没有这个 key，前端静默拿 undefined"""
        self._overview()
        data = APIClient().get('/api/wealth/cashflow/overview/').json()
        hm = data['health_metrics']
        for key in ('liquidity_ratio_level', 'liquidity_ratio_level_label',
                    'debt_ratio_level', 'debt_ratio_level_label',
                    'provident_fund_ratio_level',
                    'provident_fund_ratio_level_label',
                    'emergency_months_level', 'emergency_months_level_label'):
            assert key in hm, f'响应缺 {key}'


# ══════════════════════════════════════════════════════════════
# ② 同期多行去重（旧表真实有 2026-06 两行）
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestSnapshotDedupe:

    def test_series_keeps_latest_btime_per_yearmon(self):
        _cash_flow('2026-06', date(2026, 6, 3), zplay=100)
        _cash_flow('2026-06', date(2026, 6, 29), zplay=200)
        _cash_flow('2026-07', date(2026, 7, 26), zplay=300)

        series = get_snapshot_series()
        assert [cf.yearmon for cf in series] == ['2026-06', '2026-07']
        assert series[0].zplay == 200          # 取 btime 更晚的那行

    def test_by_yearmon_does_not_raise_on_duplicate(self):
        """原实现用 .get(yearmon=...) —— 同期多行会抛 MultipleObjectsReturned"""
        _cash_flow('2026-06', date(2026, 6, 3), zplay=100)
        _cash_flow('2026-06', date(2026, 6, 29), zplay=200)

        data = get_cashflow_by_yearmon('2026-06')
        assert data is not None
        assert data['accounts']['zplay'] == 200

    def test_by_yearmon_accepts_compact_form(self):
        """202606 / 2026-06 必须命中同一期，而不是各自成为一期"""
        _cash_flow('2026-06', date(2026, 6, 29), zplay=200)
        assert get_cashflow_by_yearmon('202606')['yearmon'] == '2026-06'
        assert get_cashflow_by_yearmon('2026-06')['yearmon'] == '2026-06'

    def test_by_yearmon_missing_returns_none(self):
        _cash_flow('2026-06', date(2026, 6, 29), zplay=200)
        assert get_cashflow_by_yearmon('2025-10') is None
        assert get_cashflow_by_yearmon('') is None

    def test_trend_has_no_duplicate_months(self):
        """不去重会让趋势图同一 x 轴出现两个 y，且「近 N 月」实际不足 N 个月"""
        _cash_flow('2026-05', date(2026, 5, 10), zplay=100)
        _cash_flow('2026-05', date(2026, 5, 25), zplay=150)
        _cash_flow('2026-06', date(2026, 6, 29), zplay=200)

        trend = get_asset_trend(months=12)
        months = [t['yearmon'] for t in trend]
        assert months == ['2026-05', '2026-06']
        assert len(months) == len(set(months))

    def test_write_updates_latest_row_instead_of_raising(self):
        """update_or_create 在同期多行上会抛 —— 用户点「编辑」直接 500"""
        _cash_flow('2026-06', date(2026, 6, 3), zplay=100)
        _cash_flow('2026-06', date(2026, 6, 29), zplay=200)

        obj = create_or_update_snapshot({
            'yearmon': '2026-06', 'zplay': 999, 'btime': date(2026, 6, 29),
        })
        assert obj.zplay == 999
        assert WealthCashFlow.objects.filter(yearmon='2026-06').count() == 2  # 旧行不删

    def test_write_creates_when_absent(self):
        obj = create_or_update_snapshot({
            'yearmon': '202607', 'zplay': 50, 'btime': date(2026, 7, 1),
        })
        assert obj.yearmon == '2026-07'      # 归一后落库
        assert obj.zplay == 50

    def test_norm_yearmon(self):
        assert norm_yearmon('2026-06') == '2026-06'
        assert norm_yearmon('202606') == '2026-06'
        assert norm_yearmon('2026-6') == '2026-06'
        assert norm_yearmon(None) == ''


# ══════════════════════════════════════════════════════════════
# ③ 资产来源与 carry_forward
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAssetSource:

    def test_legacy_when_no_new_snapshot(self):
        _cash_flow('2026-09', date(2026, 9, 8), zplay=1000)
        assert resolve_asset_source() == 'legacy_cash_flow'

    def test_switches_wholesale_to_new_snapshot(self):
        """只要有任一新体系快照就整体切换 —— 不逐月混合（否则趋势悄悄换源）"""
        _cash_flow('2026-09', date(2026, 9, 8), zplay=1000)
        account = _account('支付宝')
        _snapshot('2026-09', date(2026, 9, 8), items=[(account, 2000)])

        assert resolve_asset_source() == 'asset_snapshot'
        series = resolve_asset_series()
        assert list(series) == [202609]
        assert series[202609]['liquid'] == 2000      # 旧表的 1000 被忽略

    def test_none_when_no_data(self):
        assert resolve_asset_source() is None
        pos = resolve_asset_position()
        assert pos['available'] is False
        assert '没有' in pos['reason']

    def test_legacy_position_math(self):
        _cash_flow('2026-09', date(2026, 9, 8), zplay=10000, wechat=5000, cash=1000,
                   jianbank=20000, accumulationfund=50000, lend=8000, borrow=12000)
        pos = resolve_asset_position('2026-09')
        assert pos['liquid'] == 36000
        assert pos['financial_assets'] == 86000
        assert pos['total_assets'] == 94000
        assert pos['net_worth'] == 82000
        assert pos['receivable'] == 8000
        assert pos['self_use_total'] == 0.0

    def test_snapshot_position_uses_rollup(self):
        liquid = _account('活期卡', is_liquid=True)
        fund = _account('公积金', kind='公积金', is_liquid=False)
        house = _account('房子', category='自用', kind='房产', is_liquid=False,
                         include_in_balance_sheet=False)
        _snapshot('2026-09', date(2026, 9, 8), borrow=5000,
                  items=[(liquid, 10000), (fund, 30000), (house, 900000)])

        pos = resolve_asset_position('2026-09')
        assert pos['liquid'] == 10000          # 公积金不是 T+0 可取
        assert pos['self_use_total'] == 0.0    # 自用资产不计表
        assert pos['financial_assets'] == 40000
        assert pos['net_worth'] == 35000       # 40000 − 5000

    def test_carry_forward_takes_earlier_period(self):
        _cash_flow('2026-08', date(2026, 8, 27), zplay=1000)
        pos = resolve_asset_position('2026-09', carry_forward=True)
        assert pos['yearmon'] == '2026-08'
        assert pos['carried'] is True          # 必须标出来，否则用户以为本月盘过了

    def test_carry_forward_false_requires_exact_month(self):
        _cash_flow('2026-08', date(2026, 8, 27), zplay=1000)
        pos = resolve_asset_position('2026-09', carry_forward=False)
        assert pos['available'] is False
        assert '2026-09' in pos['reason']

    def test_carry_forward_false_hit_is_not_carried(self):
        _cash_flow('2026-08', date(2026, 8, 27), zplay=1000)
        pos = resolve_asset_position('2026-08', carry_forward=False)
        assert pos['available'] is True
        assert pos['carried'] is False

    def test_no_snapshot_before_anchor(self):
        _cash_flow('2026-09', date(2026, 9, 8), zplay=1000)
        pos = resolve_asset_position('2026-01', carry_forward=True)
        assert pos['available'] is False


# ══════════════════════════════════════════════════════════════
# ④⑤⑥⑦⑧ 六项比率
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestEmergencyAndRigid:

    def test_emergency_months_value(self):
        _fixed_scenario()
        # v3.58.24：应急金分母的窗口是「锚定月**之前**的 12 个完整月」，
        # 且至少要 3 个月有记录才出数。_fixed_scenario 覆盖 07/08/09，
        # 锚定 2026-09 时只有 07/08 落在窗口内 —— 故补 2026-06 一笔。
        # 补在 3 个月窗口之外，对刚性 / 支出质量 / 净储蓄的口径无影响。
        _bill(2026, 6, 15, '支出', 3000, category='日常生活')
        data = get_ratio_overview('2026-09')
        ratio = _ratio_of(data, 'emergency_months')
        assert ratio['value'] == 12.0              # 36000 ÷ 3000
        assert ratio['numerator']['value'] == 36000
        assert ratio['denominator']['value'] == 3000
        assert ratio['level'] == 'good'

    def test_sample_months_exclude_empty_ones_and_anchor_month(self):
        """进样本的月份：只算**有支出记录**的，且**不含锚定当月**

        v3.58.24 之前这条断言的是「不除以固定 3」；分母改成三点估算后
        不再是均值，但「哪些月份算样本」这件事同样致命 ——
        样本多一个月少一个月，O / M / P 三个点会全部跟着变。
        """
        _seed_classify_rules()
        _cash_flow('2026-09', date(2026, 9, 8), zplay=30000)
        for month in (6, 7, 8):
            _bill(2026, month, 5, '支出', 3000, category='日常生活')
        # 盘点当月也记一笔 —— 它**不该**进样本
        _bill(2026, 9, 5, '支出', 3000, category='日常生活')
        # 2026-05 完全没有支出记录 —— 既不计入样本，也不贡献一个 0

        ratio = _ratio_of(get_ratio_overview('2026-09'), 'emergency_months')

        assert ratio['extra']['record_months'] == 3          # 06/07/08，不含 09
        assert ratio['denominator']['value'] == 3000         # O=M=P=3000
        assert ratio['value'] == 10.0                        # 30000 ÷ 3000
        # 三点估算的底稿一并可查（气泡提示要展示「这个基准怎么来的」）
        assert ratio['extra']['pert_optimistic'] == 3000
        assert ratio['extra']['pert_likely'] == 3000
        assert ratio['extra']['pert_pessimistic'] == 3000

    def test_no_expense_records_is_unavailable_not_zero(self):
        _cash_flow('2026-09', date(2026, 9, 8), zplay=30000)
        ratio = _ratio_of(get_ratio_overview('2026-09'), 'emergency_months')
        assert ratio['available'] is False
        assert ratio['value'] is None
        assert '支出' in ratio['reason']

    def test_no_asset_snapshot_is_unavailable(self):
        _seed_classify_rules()
        _bill(2026, 9, 5, '支出', 3000, category='日常生活')
        ratio = _ratio_of(get_ratio_overview('2026-09'), 'emergency_months')
        assert ratio['available'] is False
        assert ratio['value'] is None

    def test_matches_health_metrics_card(self):
        """比率接口与资产健康指标卡必须给出同一个应急金月数

        ⚠️ 账单只造**完整月**（pairs[1:]）：盘点当月不进分母。
           两条路径共用 `expense_estimate` 的同一份实现，这里要验的
           正是「共用」—— 分母口径一变，两边必须同步变。
        """
        _seed_classify_rules()
        pairs = _recent_pairs(4)
        y, m = pairs[0]
        _cash_flow(f'{y:04d}-{m:02d}', date(y, m, 8), zplay=30000, wechat=6000)
        for yy, mm in pairs[1:]:
            _bill(yy, mm, 5, '支出', 3000, category='日常生活')

        card = get_cashflow_overview()['health_metrics']
        ratio = _ratio_of(get_ratio_overview(), 'emergency_months')
        assert card['emergency_fund_months'] == ratio['value'] == 12.0
        assert card['emergency_months_level'] == ratio['level'] == 'good'
        assert card['emergency_months_level_label'] == '充足'
        # 分母的底稿也要两边一致（卡片走的是独立查库那条路径）
        assert card['expense_estimate']['value'] == ratio['denominator']['value']
        assert card['expense_estimate']['months_with_records'] == 3

    def test_health_metrics_carries_level_and_pct(self):
        """判定级别由后端下发 —— 前端不再用 target/2 自己算警戒线"""
        _seed_classify_rules()
        pairs = _recent_pairs(4)
        y, m = pairs[0]
        _cash_flow(f'{y:04d}-{m:02d}', date(y, m, 8), zplay=4500)
        for yy, mm in pairs[1:]:
            _bill(yy, mm, 5, '支出', 3000, category='日常生活')

        card = get_cashflow_overview()['health_metrics']
        assert card['emergency_fund_months'] == 1.5
        assert card['emergency_months_level'] == 'danger'     # < 3
        assert card['emergency_months_pct'] == 25.0           # 1.5 / 6

    def test_rigid_coverage_value(self):
        _fixed_scenario()
        ratio = _ratio_of(get_ratio_overview('2026-09'), 'rigid_coverage')
        assert ratio['value'] == 12.0              # 36000 ÷ 3000 固定支出
        assert ratio['level'] == 'good'
        assert ratio['extra']['rigid_share'] == 100.0

    def test_rigid_coverage_unavailable_without_rules(self):
        """没有「固定」标签就算不出刚性支出 —— 不能当成 0 后除以 0"""
        _cash_flow('2026-09', date(2026, 9, 8), zplay=36000)
        _bill(2026, 9, 5, '支出', 3000, category='日常生活')
        ratio = _ratio_of(get_ratio_overview('2026-09'), 'rigid_coverage')
        assert ratio['available'] is False
        assert ratio['value'] is None
        assert '固定' in ratio['reason'] or '刚性' in ratio['reason']


@pytest.mark.django_db
class TestPassiveCoverage:

    def test_zero_passive_income_is_a_conclusion_not_missing(self):
        """被动收入 0 是真实结论（完全靠主动收入），必须给出 0.0 而不是 None"""
        _fixed_scenario()
        ratio = _ratio_of(get_ratio_overview('2026-09'), 'passive_coverage')
        assert ratio['available'] is True
        assert ratio['value'] == 0.0
        assert ratio['level'] == 'danger'
        assert ratio['level_label'] == '起步'

    def test_passive_over_total_expense(self):
        _seed_classify_rules()
        _rule('subcategory', '利息收入', income='被动', cashflow='收入流入', priority=20)
        _cash_flow('2026-09', date(2026, 9, 8), zplay=1000)
        _bill(2026, 9, 5, '支出', 1000, category='日常生活')
        _bill(2026, 9, 6, '收入', 300, category='其他收入', subcategory='利息收入')

        ratio = _ratio_of(get_ratio_overview('2026-09'), 'passive_coverage')
        assert ratio['value'] == 30.0              # 300 ÷ 1000
        assert ratio['level'] == 'warn'            # 10–50 积累
        assert ratio['denominator']['value'] == 1000

    def test_full_coverage_reaches_financial_freedom_band(self):
        _seed_classify_rules()
        _rule('subcategory', '利息收入', income='被动', cashflow='收入流入', priority=20)
        _cash_flow('2026-09', date(2026, 9, 8), zplay=1000)
        _bill(2026, 9, 5, '支出', 1000, category='日常生活')
        _bill(2026, 9, 6, '收入', 1200, category='其他收入', subcategory='利息收入')

        ratio = _ratio_of(get_ratio_overview('2026-09'), 'passive_coverage')
        assert ratio['value'] == 120.0
        assert ratio['level'] == 'good'
        assert ratio['level_label'] == '财务自由'

    def test_no_expense_in_window_is_unavailable(self):
        _seed_classify_rules()
        _cash_flow('2026-09', date(2026, 9, 8), zplay=1000)
        ratio = _ratio_of(get_ratio_overview('2026-09'), 'passive_coverage')
        assert ratio['available'] is False
        assert ratio['value'] is None


@pytest.mark.django_db
class TestDti:

    def test_no_liability_ledger_is_unavailable_not_zero(self):
        """没录负债明细 ≠ 没有债。返回 0 会让空台账显示满分健康度"""
        _fixed_scenario()
        ratio = _ratio_of(get_ratio_overview('2026-09'), 'dti')
        assert ratio['available'] is False
        assert ratio['value'] is None
        assert '在还' in ratio['reason']

    def test_rows_but_none_active_has_distinct_reason(self):
        _fixed_scenario()
        _liability('旧车贷', monthly_payment=800, status='已结清')
        ratio = _ratio_of(get_ratio_overview('2026-09'), 'dti')
        assert ratio['available'] is False
        assert '没有一笔是「在还」' in ratio['reason']

    def test_dti_value_and_boundary_band(self):
        """月供 3000 ÷ 月均收入 10000 = 30.0 → 恰好落「承压」档"""
        _fixed_scenario()
        _liability('房贷', monthly_payment=2000, status='在还')
        _liability('消费贷', monthly_payment=1000, status='在还')

        ratio = _ratio_of(get_ratio_overview('2026-09'), 'dti')
        assert ratio['numerator']['value'] == 3000
        assert ratio['denominator']['value'] == 10000
        assert ratio['value'] == 30.0
        assert ratio['level'] == 'warn'
        assert ratio['level_label'] == '承压'

    def test_settled_liability_not_counted(self):
        _fixed_scenario()
        _liability('房贷', monthly_payment=2000, status='在还')
        _liability('旧车贷', monthly_payment=5000, status='已结清')
        ratio = _ratio_of(get_ratio_overview('2026-09'), 'dti')
        assert ratio['numerator']['value'] == 2000

    def test_income_avg_uses_months_with_records(self):
        _seed_classify_rules()
        _cash_flow('2026-09', date(2026, 9, 8), zplay=1000)
        _liability('房贷', monthly_payment=1000, status='在还')
        _bill(2026, 9, 5, '收入', 6000, category='职业收入')
        _bill(2026, 8, 5, '收入', 4000, category='职业收入')
        # 2026-07 无收入记录 → 分母是 5000 而不是 3333.33
        ratio = _ratio_of(get_ratio_overview('2026-09'), 'dti')
        assert ratio['denominator']['value'] == 5000
        assert ratio['value'] == 20.0
        assert ratio['extra']['record_months'] == 2

    def test_no_income_is_unavailable(self):
        _seed_classify_rules()
        _cash_flow('2026-09', date(2026, 9, 8), zplay=1000)
        _liability('房贷', monthly_payment=1000, status='在还')
        ratio = _ratio_of(get_ratio_overview('2026-09'), 'dti')
        assert ratio['available'] is False
        assert ratio['numerator']['value'] == 1000


@pytest.mark.django_db
class TestNetWorthGrowth:

    def test_net_saving_window_is_half_open_on_snapshot_dates(self):
        """含期末盘点日、不含期初盘点日 —— 期初那天已体现在期初余额里"""
        _fixed_scenario()
        ratio = _ratio_of(get_ratio_overview('2026-09'), 'net_worth_growth')
        assert ratio['extra']['bound'] == 'snapshot_date'
        assert ratio['extra']['period_start'] == '2026-08-27'
        assert ratio['extra']['period_end'] == '2026-09-08'
        assert ratio['extra']['saving_income'] == 10000    # 只有 09-05 那笔
        assert ratio['extra']['saving_expense'] == 3000
        assert ratio['extra']['net_saving'] == 7000
        assert ratio['extra']['prev_yearmon'] == '2026-08'

    def test_residual_sign_decides_level(self):
        """净值 +2000、储蓄 7000 → 残差 −5000（没跟上储蓄）"""
        _fixed_scenario()
        ratio = _ratio_of(get_ratio_overview('2026-09'), 'net_worth_growth')
        assert ratio['numerator']['value'] == 2000         # 82000 − 80000
        assert ratio['extra']['residual'] == -5000
        assert ratio['value'] == -6.25                     # −5000 ÷ 80000
        assert ratio['level'] == 'danger'
        assert ratio['level_label'] == '低于储蓄'

    def test_positive_residual_is_good(self):
        _seed_classify_rules()
        _cash_flow('2026-08', date(2026, 8, 27), zplay=10000, borrow=0)
        _cash_flow('2026-09', date(2026, 9, 8), zplay=20000, borrow=0)
        # 期间无任何流水 → 净储蓄 0，净资产却涨了 10000 → 残差 +10000
        ratio = _ratio_of(get_ratio_overview('2026-09'), 'net_worth_growth')
        assert ratio['extra']['net_saving'] == 0
        assert ratio['extra']['residual'] == 10000
        assert ratio['level'] == 'good'

    def test_neutral_when_fully_explained_by_saving(self):
        _seed_classify_rules()
        _cash_flow('2026-08', date(2026, 8, 27), zplay=10000)
        _cash_flow('2026-09', date(2026, 9, 8), zplay=15000)
        _bill(2026, 9, 5, '收入', 5000, category='职业收入')
        ratio = _ratio_of(get_ratio_overview('2026-09'), 'net_worth_growth')
        assert ratio['extra']['residual'] == 0
        assert ratio['level'] == 'normal'
        assert ratio['level_label'] == '与储蓄一致'

    def test_non_positive_opening_net_worth_is_unavailable(self):
        """期初净资产为负时任何增长率都会给出误导性的符号"""
        _seed_classify_rules()
        _cash_flow('2026-08', date(2026, 8, 27), zplay=1000, borrow=5000)
        _cash_flow('2026-09', date(2026, 9, 8), zplay=1000, borrow=5000)
        ratio = _ratio_of(get_ratio_overview('2026-09'), 'net_worth_growth')
        assert ratio['available'] is False
        assert ratio['value'] is None
        assert '期初净资产' in ratio['reason']

    def test_single_snapshot_is_unavailable(self):
        _seed_classify_rules()
        _cash_flow('2026-09', date(2026, 9, 8), zplay=1000)
        ratio = _ratio_of(get_ratio_overview('2026-09'), 'net_worth_growth')
        assert ratio['available'] is False
        assert '更早' in ratio['reason']

    def test_month_bound_fallback_when_btime_missing(self):
        """盘点日缺失时回落自然月区间，并**显式标注** bound='month'"""
        _seed_classify_rules()
        _cash_flow('2026-08', None, zplay=10000)
        _cash_flow('2026-09', None, zplay=10000)
        _bill(2026, 9, 5, '收入', 500, category='职业收入')
        ratio = _ratio_of(get_ratio_overview('2026-09'), 'net_worth_growth')
        assert ratio['extra']['bound'] == 'month'
        assert ratio['extra']['saving_income'] == 500


@pytest.mark.django_db
class TestExpenseQuality:

    def test_impulse_over_total_expense(self):
        _fixed_scenario()
        ratio = _ratio_of(get_ratio_overview('2026-09'), 'expense_quality')
        assert ratio['numerator']['value'] == 3000        # 只有 09 那笔标了冲动
        assert ratio['denominator']['value'] == 9000
        assert ratio['value'] == 33.33
        assert ratio['extra']['coverage'] == 1.0

    def test_low_coverage_is_unavailable(self):
        """全表 necessity 填写率仅 2.3% —— 小样本除以全量支出得到的不是结论"""
        _seed_classify_rules()
        _cash_flow('2026-09', date(2026, 9, 8), zplay=1000)
        for index in range(4):
            _bill(2026, 9, 1 + index, '支出', 100, category='日常生活')
        _bill(2026, 9, 9, '支出', 100, category='日常生活', necessity='冲动')  # 1/5

        ratio = _ratio_of(get_ratio_overview('2026-09'), 'expense_quality')
        assert ratio['available'] is False
        assert ratio['value'] is None
        assert f'{int(QUALITY_MIN_COVERAGE * 100)}%' in ratio['reason']
        assert ratio['extra']['filled_rows'] == 1
        assert ratio['extra']['total_rows'] == 5

    def test_coverage_exactly_at_threshold_passes(self):
        _seed_classify_rules()
        _cash_flow('2026-09', date(2026, 9, 8), zplay=1000)
        _bill(2026, 9, 1, '支出', 100, category='日常生活', necessity='冲动')
        _bill(2026, 9, 2, '支出', 100, category='日常生活')   # 未标注

        ratio = _ratio_of(get_ratio_overview('2026-09'), 'expense_quality')
        assert ratio['extra']['coverage'] == 0.5      # 恰好等于门槛 → 放行
        assert ratio['available'] is True
        assert ratio['value'] == 50.0

    def test_income_rows_do_not_affect_coverage(self):
        """necessity 是「这笔消费该不该花」—— 收入行不参与填写率统计"""
        _seed_classify_rules()
        _cash_flow('2026-09', date(2026, 9, 8), zplay=1000)
        _bill(2026, 9, 1, '支出', 100, category='日常生活', necessity='冲动')
        for day in range(2, 8):
            _bill(2026, 9, day, '收入', 50, category='职业收入')

        ratio = _ratio_of(get_ratio_overview('2026-09'), 'expense_quality')
        assert ratio['extra']['total_rows'] == 1
        assert ratio['extra']['coverage'] == 1.0
        assert ratio['value'] == 100.0

    def test_no_expense_rows_is_unavailable(self):
        _seed_classify_rules()
        _cash_flow('2026-09', date(2026, 9, 8), zplay=1000)
        ratio = _ratio_of(get_ratio_overview('2026-09'), 'expense_quality')
        assert ratio['available'] is False


# ══════════════════════════════════════════════════════════════
# ⑨ 通用形状
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestOverviewShape:

    def test_all_six_ratios_present_and_ordered(self):
        from apps.wealth.constants import RATIO_ORDER

        _fixed_scenario()
        data = get_ratio_overview('2026-09')
        assert [r['key'] for r in data['ratios']] == list(RATIO_ORDER)

    def test_every_ratio_carries_formula_bands_and_hint(self):
        _fixed_scenario()
        for ratio in get_ratio_overview('2026-09')['ratios']:
            assert ratio['label'] and ratio['formula'] and ratio['unit']
            assert ratio['hint'], f"{ratio['key']} 缺 hint"
            # 提示文案不得嵌入金额（金额要走前端脱敏）—— 数字只允许出现在
            # 判定相关的百分比说明里，这里用「不得含 ¥」做最小断言
            assert '¥' not in ratio['hint']

    def test_unavailable_never_returns_zero(self):
        _fixed_scenario()
        for ratio in get_ratio_overview('2026-09')['ratios']:
            if not ratio['available']:
                assert ratio['value'] is None
                assert ratio['reason']

    def test_gaps_mirror_unavailable_ratios(self):
        _fixed_scenario()
        data = get_ratio_overview('2026-09')
        gaps = {g['key'] for g in data['gaps']}
        unavailable = {r['key'] for r in data['ratios'] if not r['available']}
        assert gaps == unavailable

    def test_asset_position_source_is_declared(self):
        _fixed_scenario()
        data = get_ratio_overview('2026-09')
        assert data['asset_source'] == 'legacy_cash_flow'
        assert data['asset_source_label']
        assert data['asset_position']['net_worth'] == 82000

    def test_windows_are_reported(self):
        _fixed_scenario()
        windows = get_ratio_overview('2026-09')['windows']
        assert windows['expense']['months'] == 3
        assert windows['expense']['label'] == '2026-07 ~ 2026-09'
        assert windows['passive']['months'] == 12

    def test_carried_position_is_flagged(self):
        _seed_classify_rules()
        _cash_flow('2026-08', date(2026, 8, 27), zplay=10000)
        _bill(2026, 8, 5, '支出', 1000, category='日常生活')
        data = get_ratio_overview('2026-09')
        assert data['asset_position']['yearmon'] == '2026-08'
        assert data['asset_position']['carried'] is True


# ══════════════════════════════════════════════════════════════
# ⑩ 趋势
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestTrend:

    def test_months_ascending_and_series_aligned(self):
        _seed_classify_rules()
        _cash_flow(f'{NOW.year:04d}-{NOW.month:02d}', NOW.date(), zplay=10000)
        labels = _recent_labels(6)
        for y, m in _recent_pairs(6):
            _bill(y, m, 5, '支出', 1000, category='日常生活')

        data = get_ratio_trend(months=6)
        assert data['months'] == sorted(labels)
        for key, points in data['series'].items():
            assert len(points) == 6, f'{key} 点数不是 6'
            assert [p['ym'] for p in points] == sorted(labels)

    def test_dti_absent_from_series_but_explained(self):
        _seed_classify_rules()
        _cash_flow(f'{NOW.year:04d}-{NOW.month:02d}', NOW.date(), zplay=10000)
        data = get_ratio_trend(months=6)
        # 不留空数组：空数组会被读成「这个月没数据」，而真相是「永不入趋势」
        assert 'dti' not in data['series']
        excluded = {item['key'] for item in data['excluded']}
        assert excluded == {'dti'}
        assert data['excluded'][0]['reason']

    def test_window_is_wider_than_display(self):
        """最早一个点也要有完整滚动窗口，否则与总览算出来的对不上

        各月支出刻意不等额（1000×(偏移+1)），这样「窗口是否完整」会体现在
        数值上 —— 等额数据下两种实现给出同一个数，测试就白写了。

        ⚠️ 造数月数 = 展示 3 个月 + 应急金窗口 12 个月 = 15。
           分母窗口取的是「锚定月之前的 12 个完整月」，不含锚定月，
           所以最早那个点（偏移 2）要用偏移 3~14 这 12 个月。
           只造 12 个月的话它照样能算出一个值（样本 9 个月），
           但那是残缺窗口算出的数，与总览对不上 —— 正是本用例要抓的。
        """
        _seed_classify_rules()
        pairs = _recent_pairs(3 + EMERGENCY_EXPENSE_MONTHS)
        for offset, (y, m) in enumerate(pairs):
            _bill(y, m, 5, '支出', 1000 * (offset + 1), category='日常生活')
        for y, m in pairs[:3]:
            _cash_flow(f'{y:04d}-{m:02d}', date(y, m, 5), zplay=12000)

        data = get_ratio_trend(months=3)
        assert data['months'] == sorted(_recent_labels(3))

        points = data['series']['emergency_months']
        assert all(p['available'] for p in points), '存在窗口残缺的点'

        # 三点估算 E = (O + 4M + P) / 6，M 取中位数（偶数个样本取中间两数均值）
        # 最新点（偏移 0）：窗口 1~12 → 2000..13000，M=(7000+8000)/2=7500
        #   E=(2000+4×7500+13000)/6=7500  → 12000÷7500
        assert points[-1]['value'] == 1.6
        # 最早点（偏移 2）：窗口 3~14 → 4000..15000，M=(9000+10000)/2=9500
        #   E=(4000+4×9500+15000)/6=9500  → 12000÷9500
        # 若取数范围只覆盖展示的 3 个月，这里会拿 1000/2000/3000 去算，得 6.0
        assert points[0]['value'] == 1.26
        # 被动收入窗口 12 个月（含锚定月）→ 当前月刚好凑满
        assert data['series']['passive_coverage'][-1]['available'] is True

    def test_point_carries_level_for_frontend(self):
        _seed_classify_rules()
        _cash_flow(f'{NOW.year:04d}-{NOW.month:02d}', NOW.date(), zplay=30000)
        # 造满 12 个月 + 锚定月：分母窗口不含锚定月，等额数据下
        # O=M=P=3000，E 也等于 3000 —— 三点估算在样本一致时退化为该值
        for y, m in _recent_pairs(EMERGENCY_EXPENSE_MONTHS + 1):
            _bill(y, m, 5, '支出', 3000, category='日常生活')
        point = get_ratio_trend(months=3)['series']['emergency_months'][-1]
        assert point['value'] == 10.0
        assert point['level'] == 'good'
        assert point['level_label'] == '充足'

    def test_missing_snapshot_becomes_gap_not_zero(self):
        _seed_classify_rules()
        # 只在两个月前有快照：当前月没有 → 当前月的应急金是断点
        y, m = _recent_pairs(3)[2]
        _cash_flow(f'{y:04d}-{m:02d}', date(y, m, 5), zplay=30000)
        for yy, mm in _recent_pairs(3):
            _bill(yy, mm, 5, '支出', 3000, category='日常生活')

        points = get_ratio_trend(months=3)['series']['emergency_months']
        assert points[-1]['available'] is False
        assert points[-1]['value'] is None


# ══════════════════════════════════════════════════════════════
# ⑪ 接口
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestRatioApi:

    def test_overview_endpoint(self):
        _fixed_scenario()
        response = APIClient().get(RATIOS_URL, {'yearmon': '2026-09'})
        assert response.status_code == 200
        body = response.json()
        assert body['anchor_yearmon'] == '2026-09'
        assert len(body['ratios']) == 6
        assert body['asset_position']['net_worth'] == 82000

    def test_overview_endpoint_without_anchor(self):
        _seed_classify_rules()
        _cash_flow(f'{NOW.year:04d}-{NOW.month:02d}', NOW.date(), zplay=1000)
        response = APIClient().get(RATIOS_URL)
        assert response.status_code == 200
        assert response.json()['anchor_yearmon'] == f'{NOW.year:04d}-{NOW.month:02d}'

    def test_trend_endpoint(self):
        _seed_classify_rules()
        _cash_flow(f'{NOW.year:04d}-{NOW.month:02d}', NOW.date(), zplay=1000)
        response = APIClient().get(f'{RATIOS_URL}trend/', {'months': 4})
        assert response.status_code == 200
        body = response.json()
        assert len(body['months']) == 4
        assert isinstance(body['series'], dict)

    def test_trend_endpoint_clamps_months(self):
        _seed_classify_rules()
        _cash_flow(f'{NOW.year:04d}-{NOW.month:02d}', NOW.date(), zplay=1000)
        assert len(APIClient().get(f'{RATIOS_URL}trend/', {'months': 999}).json()['months']) == 36
        assert len(APIClient().get(f'{RATIOS_URL}trend/', {'months': 'x'}).json()['months']) == 12

    def test_anchors_endpoint_is_bare_array(self):
        """裸数组 —— 被全局分页包成 {count, results} 时前端按数组消费会静默为空"""
        _cash_flow('2026-08', date(2026, 8, 27), zplay=1000)
        _cash_flow('2026-09', date(2026, 9, 8), zplay=1000)
        response = APIClient().get(f'{RATIOS_URL}anchors/')
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert body == ['2026-09', '2026-08']

    def test_asset_position_endpoint(self):
        _cash_flow('2026-09', date(2026, 9, 8), zplay=1000)
        client = APIClient()

        exact = client.get(f'{RATIOS_URL}asset_position/',
                           {'yearmon': '2026-08', 'carry_forward': 0}).json()
        assert exact['available'] is False        # 该月无快照，且不容许向前取

        carried = client.get(f'{RATIOS_URL}asset_position/',
                             {'yearmon': '2026-09', 'carry_forward': 1}).json()
        assert carried['available'] is True
        assert carried['carried'] is False

        picked = client.get(f'{RATIOS_URL}asset_position/',
                            {'yearmon': '2026-09'}).json()
        assert picked['yearmon'] == '2026-09'

    def test_meta_endpoint_is_bare_array(self):
        """裸数组 —— 被全局分页包成 {count, results} 时前端按数组消费会静默为空"""
        response = APIClient().get(f'{RATIOS_URL}meta/')
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)

    def test_meta_covers_every_ratio_with_note(self):
        """九项都有 note —— 气泡提示的文案源，缺一项就会显示成空白气泡"""
        from apps.wealth.constants import RATIO_BANDS
        from apps.wealth.services.ratio_grade import all_ratio_meta

        metas = all_ratio_meta()
        assert {m['key'] for m in metas} == set(RATIO_BANDS)
        for meta in metas:
            assert meta['label'], f"{meta['key']} 缺 label"
            assert meta['note'], f"{meta['key']} 缺口径说明"
            assert isinstance(meta['note'], list) and meta['note']
            assert all(isinstance(line, str) and line for line in meta['note'])

    def test_meta_note_has_no_markdown_marks(self):
        """note 由前端当纯文本渲染 —— 带 `**` 之类标记会原样显示成星号"""
        from apps.wealth.services.ratio_grade import all_ratio_meta

        for meta in all_ratio_meta():
            for line in meta['note']:
                assert '**' not in line, f"{meta['key']} 的口径说明含 Markdown 标记"
                assert '==' not in line

    def test_meta_bands_match_grade_lookup(self):
        """下发的区间必须与查表结果自洽 —— 前端按 bands 画刻度、按 level 上色"""
        from apps.wealth.services.ratio_grade import all_ratio_meta, grade_ratio

        for meta in all_ratio_meta():
            if not meta['bands']:
                continue
            for _lo, hi, level, label in meta['bands']:
                if hi is None:
                    continue
                # 取区间内一点（下界与 hi 的中点）验证落在同一档
                mid = ((_lo if _lo is not None else hi - 1) + hi) / 2
                got = grade_ratio(meta['key'], mid)
                assert got['level'] == level, f"{meta['key']} 区间与查表不一致"
                assert got['level_label'] == label

    def test_available_anchor_months_from_snapshot_periods(self):
        """锚定月候选来自快照期别而非账单期别 —— 选了没快照的月份只会得到空白"""
        _seed_classify_rules()
        _cash_flow('2026-08', date(2026, 8, 27), zplay=1000)
        _cash_flow('2026-09', date(2026, 9, 8), zplay=1000)
        _bill(2026, 1, 5, '支出', 100, category='日常生活')   # 账单更密，但不该出现
        assert available_anchor_months() == ['2026-09', '2026-08']
