"""阶段分段 + 阶段对照（v3.64.61）

守六件事：

1. 🔴 区间是**闭区间**、只取**顶层**（`parent IS NULL`）—— 与
   `selfrun.services.stage_timeline()` 同一把尺子，否则同一天会既属
   「阶段内」又属「空档」。
2. 🔴 一个月内发生切换 ⇒ `is_mixed` + 逐段 `segments`，不能只印一个名字。
3. 🔴 一个月没有任何阶段 ⇒ `reason='no_stage'`，**不回退成上一段的名字**
   （那会凭空延长一段人生）。
4. 🔴 阶段整段早于系统有数据 ⇒ `pct=None` + `before_data`，**不是 0%**。
   分母起点取 `max(阶段起点, 该维度最早数据日)`。
5. 🔴 月粒度维度在不足一个完整月的阶段里 ⇒ `no_complete_period`，不是 0%。
6. 🔴 可观测维度 < 2 时不给最短板；返回里**没有 intensity**（只比覆盖率）。
"""
import datetime as dt

import pytest
from django.utils import timezone

from apps.health.models import HealthRecord
from apps.selfrun.models import SelfRunStage
from apps.summary.services.stage_span_service import (
    REASON_BEFORE_DATA,
    REASON_NO_COMPLETE_PERIOD,
    REASON_NO_STAGE,
    StageSpanService,
)
from apps.wealth.models import WealthBalanceList

TODAY = timezone.localdate()
YEAR = TODAY.year
JAN1 = dt.date(YEAR, 1, 1)


def _days_ago(n: int) -> dt.date:
    """本年内往前退 n 天（年初时退化到 1/1，保证测试不跨年）"""
    return max(TODAY - dt.timedelta(days=n), JAN1)


def _steps(day: dt.date, total: float = 10000):
    return HealthRecord.objects.create(
        time=timezone.make_aware(dt.datetime.combine(day, dt.time(8, 0))),
        total=total,
    )


def _record_stage(name, start, end=None):
    return SelfRunStage.objects.create(
        name=name, stage_kind='record', status='closed',
        start_date=start, end_date=end,
    )


def _run_stage(name, start, end=None, parent=None):
    return SelfRunStage.objects.create(
        name=name, stage_kind='run', status='active',
        start_date=start, end_date=end, parent=parent,
    )


@pytest.mark.django_db
class TestMonthSpans:
    def test_no_stage_at_all(self):
        data = StageSpanService.month_spans(YEAR)
        assert data['stages'] == []
        assert data['uncovered_months'] == list(range(1, 13))
        assert all(m['reason'] == REASON_NO_STAGE for m in data['months'])
        assert all(m['label'] is None for m in data['months'])
        assert all(m['covered_days'] == 0 for m in data['months'])

    def test_full_year_stage_covers_every_month(self):
        _record_stage('谋生期', JAN1, dt.date(YEAR, 12, 31))
        data = StageSpanService.month_spans(YEAR)

        assert data['uncovered_months'] == []
        assert all(m['label'] == '谋生期' for m in data['months'])
        assert all(m['kind'] == 'record' for m in data['months'])
        assert all(not m['is_mixed'] for m in data['months'])
        assert data['stages'] == [
            {'stage_id': data['stages'][0]['stage_id'], 'name': '谋生期', 'kind': 'record'},
        ]

    def test_mid_month_switch_marks_mixed_and_picks_longer_segment(self):
        _record_stage('旧段', JAN1, dt.date(YEAR, 6, 10))
        _record_stage('新段', dt.date(YEAR, 6, 11), dt.date(YEAR, 12, 31))
        data = StageSpanService.month_spans(YEAR)

        jun = data['months'][5]
        assert jun['is_mixed'] is True
        assert [s['name'] for s in jun['segments']] == ['旧段', '新段']
        # 6/1–6/10 十天 vs 6/11–6/30 二十天 ⇒ 主段是「新段」
        assert jun['label'] == '新段'
        assert jun['covered_days'] == 30

        # 切换当月之前 / 之后都是单一归属
        assert data['months'][4]['label'] == '旧段'
        assert data['months'][6]['label'] == '新段'

    def test_child_stage_is_not_listed(self):
        parent = _record_stage('求学期', JAN1, dt.date(YEAR, 12, 31))
        SelfRunStage.objects.create(
            name='大学期', stage_kind='record', status='closed',
            start_date=dt.date(YEAR, 9, 1), end_date=dt.date(YEAR, 12, 31),
            parent=parent,
        )
        data = StageSpanService.month_spans(YEAR)

        names = [s['name'] for s in data['stages']]
        # 🔴 子阶段不摊到七维上：一个月只有一格，两个名字印不下
        assert names == ['求学期']
        assert all(m['label'] == '求学期' for m in data['months'])
        assert all(not m['is_mixed'] for m in data['months'])

    def test_open_ended_stage_covers_rest_of_year(self):
        _run_stage('赎回期', dt.date(YEAR, 10, 1), None)
        data = StageSpanService.month_spans(YEAR)

        assert data['uncovered_months'] == list(range(1, 10))
        assert data['months'][9]['label'] == '赎回期'
        assert data['months'][11]['label'] == '赎回期'

    def test_gap_between_stages_does_not_inherit_previous_name(self):
        _record_stage('早年', JAN1, dt.date(YEAR, 3, 31))
        _record_stage('近年', dt.date(YEAR, 9, 1), dt.date(YEAR, 12, 31))
        data = StageSpanService.month_spans(YEAR)

        # 4–8 月是空档：必须说「没有阶段」，不能说成「早年」的延续
        for idx in range(3, 8):
            assert data['months'][idx]['label'] is None
            assert data['months'][idx]['reason'] == REASON_NO_STAGE
        assert data['uncovered_months'] == [4, 5, 6, 7, 8]


@pytest.mark.django_db
class TestStageCompare:
    def test_stage_entirely_before_data_gives_none(self):
        """系统 2019 才起步 ⇒ 2001–2017 那段七个维度都不该是 0%"""
        _steps(TODAY)  # 先让「健康」这个维度有数据
        _record_stage('求学期', dt.date(2001, 3, 1), dt.date(2017, 10, 1))

        row = StageSpanService.stage_compare()['stages'][0]
        assert row['coverage']['health']['pct'] is None
        assert row['coverage']['health']['reason'] == REASON_BEFORE_DATA
        assert row['coverage']['health']['periods'] == 0

    def test_day_coverage_counts_only_days_with_records(self):
        start = _days_ago(9)
        _run_stage('赎回期', start, TODAY)
        for offset in (0, 3, 7):
            _steps(TODAY - dt.timedelta(days=offset))

        row = StageSpanService.stage_compare()['stages'][0]
        cov = row['coverage']['health']
        assert cov['covered'] == 3
        assert cov['periods'] == (TODAY - start).days + 1
        assert cov['pct'] == round(3 / cov['periods'] * 100, 1)
        assert cov['reason'] is None

    def test_month_dimension_needs_a_complete_month(self):
        """阶段不足一个完整月 ⇒ 月粒度维度算不出来（不是 0%）"""
        start = _days_ago(5)
        _run_stage('赎回期', start, TODAY)
        WealthBalanceList.objects.create(yearmon=f'{YEAR}-{TODAY.month:02d}', wageincome=1000)

        row = StageSpanService.stage_compare()['stages'][0]
        cov = row['coverage']['wealth']
        assert cov['periods'] == 0
        assert cov['pct'] is None
        assert cov['reason'] == REASON_NO_COMPLETE_PERIOD

    def test_weakest_is_none_when_fewer_than_two_comparable(self):
        """只有健康一个维度有数据 ⇒ 不点名「最短板」（一个候选没有比较意义）"""
        start = _days_ago(9)
        _run_stage('只有健康', start, TODAY)
        _steps(TODAY)

        row = StageSpanService.stage_compare()['stages'][0]
        assert row['comparable_modules'] == 1
        assert row['weakest'] is None

    def test_payload_has_no_intensity(self):
        """只比覆盖率 ⇒ 返回里不该出现强度（那是绝对量，跨阶段不可比）"""
        start = _days_ago(9)
        _run_stage('赎回期', start, TODAY)
        _steps(TODAY)

        row = StageSpanService.stage_compare()['stages'][0]
        for cov in row['coverage'].values():
            assert 'intensity' not in cov
            assert 'intensity_unit' not in cov

    def test_future_stage_is_flagged_and_empty(self):
        future = TODAY + dt.timedelta(days=30)
        _run_stage('还没开始', future, future + dt.timedelta(days=365))

        row = StageSpanService.stage_compare()['stages'][0]
        assert row['in_future'] is True
        assert row['days'] == 0
        assert row['weakest'] is None

    def test_top_level_only(self):
        parent = _run_stage('三年赎回期', JAN1, None)
        SelfRunStage.objects.create(
            name='离职适应期', stage_kind='run', status='active',
            start_date=JAN1, end_date=dt.date(YEAR, 12, 31), parent=parent,
        )
        rows = StageSpanService.stage_compare()['stages']

        assert [r['name'] for r in rows] == ['三年赎回期']

    def test_stages_are_in_life_order(self):
        _record_stage('近期', dt.date(YEAR - 1, 1, 1), dt.date(YEAR - 1, 12, 31))
        _record_stage('早年', dt.date(YEAR - 5, 1, 1), dt.date(YEAR - 4, 12, 31))
        rows = StageSpanService.stage_compare()['stages']

        # 正序 = 从早年走到现在，与 selfrun 时间轴一致（不是「新在前」）
        assert [r['name'] for r in rows] == ['早年', '近期']
