"""覆盖率 + 强度口径（v3.62.43）

守七件事：
1. 覆盖率 = 有记录的期数 ÷ **该有的期数**；强度 = 总量 ÷ **有记录的期数**（两个分母不同）
2. 🔴 日记页每天自动建的空占位（`total=0`）**不算有记录** —— 否则文字覆盖率凭空 100%
3. 🔴 当前月不计入月粒度分母（月度记录是月结动作，月初不能无故掉一档）
4. **算不出来给 None，不是 0%**（未来年份 / 零期数）
5. 总览**没有** `total_points` / `yearly_target`（总分已拆，防回潮）
6. 最短板 = 覆盖率最低，只认覆盖率（不认达成率）
7. 雷达一轴两套值，达成率 = 点数 ÷ 该轴封顶
"""
import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.book.models import Book
from apps.health.models import HealthRecord
from apps.sugar.models import SugarRecord
from apps.summary.constants import (
    BOOK,
    HEALTH,
    MODULE_LIST,
    SUGAR,
    WEALTH,
    WORDS,
)
from apps.summary.services.progress_aggregator import ProgressAggregator as P
from apps.temporal.models import OneDayPage
from apps.wealth.models import WealthBalanceList

TODAY = timezone.localdate()
YEAR = TODAY.year
ELAPSED_DAYS = TODAY.timetuple().tm_yday
COMPLETED_MONTHS = TODAY.month - 1


def _pct(covered: int, periods: int) -> float:
    return round(covered / periods * 100, 1)


def _steps(day: dt.date, total: float = 10000):
    return HealthRecord.objects.create(
        time=timezone.make_aware(dt.datetime.combine(day, dt.time(8, 0))),
        total=total,
    )


@pytest.mark.django_db
class TestCoverageBasics:
    def test_day_coverage_counts_distinct_days(self):
        for offset in (0, 1, 5):
            _steps(TODAY - dt.timedelta(days=offset))

        cov = P._coverage(HEALTH, YEAR)
        assert cov['period_kind'] == 'day'
        assert cov['period_word'] == '天'
        assert cov['covered'] == 3
        assert cov['periods'] == ELAPSED_DAYS
        assert cov['pct'] == _pct(3, ELAPSED_DAYS)

    def test_same_day_multiple_rows_count_once(self):
        """一天记两条也只算「这一天有记录」—— 覆盖率的单位是天，不是条数"""
        _steps(TODAY, 3000)
        _steps(TODAY, 4000)

        assert P._coverage(HEALTH, YEAR)['covered'] == 1

    def test_intensity_divides_by_recorded_not_by_periods(self):
        """强度分母 = 有记录的天数（2），不是已过天数（292）"""
        _steps(TODAY, 8000)
        _steps(TODAY - dt.timedelta(days=1), 12000)

        cov = P._coverage(HEALTH, YEAR)
        assert cov['covered'] == 2
        assert cov['intensity'] == 10000.0     # 20000 / 2
        assert cov['intensity_unit'] == '步/天'

    def test_no_records_gives_none_not_zero(self):
        cov = P._coverage(HEALTH, YEAR)
        assert cov['covered'] == 0
        assert cov['pct'] == 0.0               # 有期数、但一条没记 ⇒ 0% 是事实
        assert cov['intensity'] is None        # 没有可平均的分母 ⇒ 算不出来

    def test_future_year_is_none(self):
        cov = P._coverage(HEALTH, YEAR + 1)
        assert cov['periods'] == 0
        assert cov['pct'] is None
        assert cov['intensity'] is None


@pytest.mark.django_db
class TestEmptyPlaceholder:
    def test_diary_placeholder_does_not_count(self):
        """🔴 空占位（total=0）不算「有记录」

        日记页每天自动建一条 `total=0`、标题固定的占位行。
        把它算成有记录，文字覆盖率会变成 100%，而实际上那天什么都没写。
        """
        OneDayPage.objects.create(title='幸福未被发现，就叫做普通的一天', begin_date=TODAY, oneday=0, page=0)
        OneDayPage.objects.create(title='真的写了', begin_date=TODAY - dt.timedelta(days=1), oneday=1200)
        # ⚠️ 不能直接传 `total`：`OneDayPage.save()` 会重算 `total = oneday + page`，
        #    传进去的 total 会被覆盖成 0（第一次写这个用例就在这里踩空了）

        cov = P._coverage(WORDS, YEAR)
        assert cov['covered'] == 1
        assert cov['intensity'] == 1200.0

    def test_all_placeholders_means_zero_coverage(self):
        OneDayPage.objects.create(title='占位', begin_date=TODAY, oneday=0, page=0)

        cov = P._coverage(WORDS, YEAR)
        assert cov['covered'] == 0
        assert cov['pct'] == 0.0
        assert cov['intensity'] is None


@pytest.mark.django_db
class TestMonthlyGranularity:
    def test_current_month_not_in_denominator(self):
        """🔴 月度记录是月结动作：本月还没过完，不该算成缺失

        2 月时应得「1 个完整月」，而不是「2 个月里记了 1 个 ⇒ 50%」。
        """
        for m in range(1, COMPLETED_MONTHS + 1):
            WealthBalanceList.objects.create(
                yearmon=f'{YEAR}-{m:02d}', wageincome=10000, otherincome=0, outmoney=5000,
            )

        cov = P._coverage(WEALTH, YEAR)
        assert cov['period_kind'] == 'month'
        assert cov['periods'] == COMPLETED_MONTHS
        assert cov['covered'] == COMPLETED_MONTHS
        assert cov['pct'] == 100.0

    def test_current_month_record_does_not_break_ratio(self):
        """本月已录一行也不算进分母（covered 与 periods 都只看完整月）"""
        for m in range(1, COMPLETED_MONTHS + 1):
            WealthBalanceList.objects.create(yearmon=f'{YEAR}-{m:02d}', wageincome=1000)
        WealthBalanceList.objects.create(yearmon=f'{YEAR}-{TODAY.month:02d}', wageincome=1000)

        cov = P._coverage(WEALTH, YEAR)
        assert cov['covered'] == COMPLETED_MONTHS
        assert cov['periods'] == COMPLETED_MONTHS
        assert cov['pct'] == 100.0

    def test_january_has_no_completed_month(self):
        """1 月时月粒度维度算不出来 ⇒ None（不是 0%）"""
        if TODAY.month != 1:
            pytest.skip('仅在 1 月有意义')
        assert P._coverage(WEALTH, YEAR)['pct'] is None


@pytest.mark.django_db
class TestBookAndSugar:
    def test_book_counts_completed_only(self):
        """月粒度：只数「读完」的书，且只看**已结完的月**（当前月要等下个月才进分母）"""
        if COMPLETED_MONTHS < 1:
            pytest.skip('今年还没有完整月')
        done_day = dt.date(YEAR, 1, 15)
        Book.objects.create(btitle='读完的', status='已完成', readDate=done_day)
        Book.objects.create(btitle='在读的', status='在读', readDate=done_day)

        cov = P._coverage(BOOK, YEAR)
        # 同一个月内两本只算「这个月有读完」这一期
        assert cov['covered'] == 1
        assert cov['intensity'] == 1.0

    def test_sugar_counts_days(self):
        for offset in (0, 2):
            SugarRecord.objects.create(
                title='今天的好事',
                level_of_happiness=Decimal('8'),
                time=TODAY - dt.timedelta(days=offset),
            )

        cov = P._coverage(SUGAR, YEAR)
        assert cov['covered'] == 2
        assert cov['intensity'] == 8.0
        assert cov['intensity_unit'] == '级/天'


@pytest.mark.django_db
class TestOverviewShape:
    def test_no_total_points_anymore(self):
        """🔴 总分不许回潮：这两个键一旦回来，页面又会有人去相加"""
        ov = P.get_yearly_overview(YEAR)
        for key in ('total_points', 'yearly_target', 'progress_percent',
                    'remaining_points', 'monthly_target'):
            assert key not in ov, f'{key} 已随总分退役，别再返回'

    def test_window_is_reported(self):
        ov = P.get_yearly_overview(YEAR)
        assert ov['window']['elapsed_days'] == ELAPSED_DAYS
        assert ov['window']['elapsed_months'] == COMPLETED_MONTHS

    def test_every_module_carries_both_numbers(self):
        ov = P.get_yearly_overview(YEAR)
        assert len(ov['modules']) == len(MODULE_LIST)
        for m in ov['modules']:
            cov = m['coverage']
            assert {'covered', 'periods', 'pct', 'intensity', 'label'} <= set(cov)
            assert cov['label'] in ('记录覆盖', '记账覆盖', '出行覆盖', '阅读覆盖')

    def test_monthly_detail_has_no_total(self):
        detail = P.get_monthly_detail(YEAR, TODAY.month)
        for key in ('total_points', 'month_target', 'target_percent'):
            assert key not in detail


def _mod(module: str, label: str, pct: float | None, covered: int = 0, periods: int = 100):
    """构造一条最小的 module entry，用来单测 `_weakest` 的判定规则"""
    return {
        'module': module,
        'label': label,
        'color': '#000000',
        'coverage': {
            'pct': pct,
            'covered': covered,
            'periods': periods,
            'period_word': '天',
            'recent_pct': None,
            'recent_covered': None,
            'recent_periods': 30,
        },
    }


@pytest.mark.django_db
class TestWeakest:
    def test_picks_lowest_coverage(self):
        """纯函数口径：谁覆盖率最低谁是最短板，与列表顺序无关"""
        rows = [
            _mod(HEALTH, '健康', 14.4, 42, 292),
            _mod(SUGAR, '小确幸', 12.0, 35, 292),
            _mod(WEALTH, '财富', 100.0, 9, 9),
        ]
        assert P._weakest(rows)['module'] == SUGAR

    def test_ignores_uncomputable(self):
        """pct=None（算不出来）不参与比较，否则「未来年份」会被当成 0% 顶到最前"""
        rows = [
            _mod(HEALTH, '健康', None, 0, 0),
            _mod(SUGAR, '小确幸', 40.0, 10, 25),
        ]
        assert P._weakest(rows)['module'] == SUGAR

    def test_all_uncomputable_gives_none(self):
        rows = [_mod(HEALTH, '健康', None, 0, 0)]
        assert P._weakest(rows) is None

    def test_uses_coverage_not_achievement(self):
        """达成率依赖每轴封顶（拍出来的数）—— 给它再高的达成率也不该影响点名"""
        rows = [
            _mod(HEALTH, '健康', 14.4, 42, 292),
            _mod(SUGAR, '小确幸', 12.0, 35, 292),
        ]
        for r in rows:
            r['achievement_pct'] = 99.0 if r['module'] == HEALTH else 1.0
        assert P._weakest(rows)['module'] == SUGAR

    def test_overview_weakest_matches_its_own_modules(self):
        """集成口径：返回的 weakest 必须真的是这份 modules 里最低的那个"""
        ov = P.get_yearly_overview(YEAR)
        candidates = [m for m in ov['modules'] if m['coverage']['pct'] is not None]
        if not candidates:
            pytest.skip('本年度没有可计算的覆盖率')
        lowest = min(m['coverage']['pct'] for m in candidates)
        assert ov['weakest']['coverage_pct'] == lowest


@pytest.mark.django_db
class TestTrend:
    def test_shape_is_object_with_both_lenses(self):
        """v3.62.44：趋势不再是平铺点数，而是「元信息 + 每月两套值」"""
        tr = P.get_trend(YEAR)
        assert set(tr) >= {'year', 'modules', 'months', 'intensity_max', 'unit_note'}
        assert len(tr['months']) == 12
        assert len(tr['modules']) == len(MODULE_LIST)
        assert all('intensity_unit' in m and 'color' in m for m in tr['modules'])

    def test_future_months_are_none_on_both(self):
        tr = P.get_trend(YEAR)
        for row in tr['months']:
            if row['month'] > TODAY.month:
                assert row['is_future'] is True
                assert row['coverage'][HEALTH] is None
                assert row['intensity'][HEALTH] is None   # 不是 0

    def test_past_month_with_no_record_is_zero_not_none(self):
        tr = P.get_trend(YEAR)
        first = tr['months'][0]
        assert first['is_future'] is False
        assert first['coverage'][HEALTH] == 0.0

    def test_intensity_accompanies_coverage(self):
        """🔴 有覆盖率就一定有强度：只给覆盖率等于把「记得很差」藏起来"""
        _steps(TODAY, 8000)
        tr = P.get_trend(YEAR)
        for row in tr['months']:
            for mod in MODULE_LIST:
                cov = row['coverage'][mod]
                iv = row['intensity'][mod]
                if cov is None:
                    assert iv is None, f'{row["month"]}月 {mod} 覆盖率为空却有强度'
                elif cov > 0:
                    assert iv is not None, f'{row["month"]}月 {mod} 有覆盖却没有强度'

    def test_unclosed_month_has_neither(self):
        """月度维度在当前月还没结 ⇒ 覆盖率与强度都为 None（不给自己打架的格子）"""
        tr = P.get_trend(YEAR)
        cur = tr['months'][TODAY.month - 1]
        if TODAY.month - 1 < 12:
            assert cur['coverage'][WEALTH] is None
            assert cur['intensity'][WEALTH] is None

    def test_covered_and_periods_are_sent(self):
        """提示框要显示「42/292 天」，这个数必须由后端给，前端不反推"""
        tr = P.get_trend(YEAR)
        jan = tr['months'][0]
        assert jan['covered'][HEALTH] == 0
        assert jan['periods'][HEALTH] == 31


@pytest.mark.django_db
class TestAchievementIsNetOverTarget:
    """v3.62.44：达成率 = 净额 ÷ 目标，**不套 floor**"""

    def test_negative_net_gives_negative_achievement(self):
        """净流出年份的达成率是负数 —— 不是 0%

        旧实现走 `_raw_to_points`（带 `points_floor=0`），亏损被抬成 0 点 ⇒
        达成率恒为 0%，界面上「亏了 1.69 万」和「一分没赚」长得一样。
        """
        WealthBalanceList.objects.create(
            yearmon=f'{YEAR}-01', wageincome=10000, otherincome=0, outmoney=20000,
        )
        entry = {m['module']: m for m in P.get_yearly_overview(YEAR)['modules']}[WEALTH]
        assert entry['raw_value'] == -10000
        assert entry['achievement_pct'] is not None
        assert entry['achievement_pct'] < 0
        # 目标 = 封顶点数 × 10000 元/点（封顶值来自雷达配置，测试环境取默认，别硬编码）
        assert entry['achievement_target'] == entry['axis_max'] * 10000
        assert entry['achievement_pct'] == round(
            -10000 / (entry['axis_max'] * 10000) * 100, 1,
        )

    def test_positive_net_matches_points_math(self):
        WealthBalanceList.objects.create(yearmon=f'{YEAR}-01', wageincome=30000, outmoney=5000)
        entry = {m['module']: m for m in P.get_yearly_overview(YEAR)['modules']}[WEALTH]
        assert entry['raw_value'] == 25000
        # 净额 25,000 元 = 2.5 点；达成率 = 2.5 ÷ 封顶
        assert entry['achievement_pct'] == round(2.5 / entry['axis_max'] * 100, 1)

    def test_points_still_floored_for_internal_use(self):
        """内部评分仍要 floor —— 只有「达成率」放开负号，别把两件事混了"""
        WealthBalanceList.objects.create(yearmon=f'{YEAR}-01', wageincome=0, outmoney=9000)
        entry = {m['module']: m for m in P.get_yearly_overview(YEAR)['modules']}[WEALTH]
        assert entry['points'] == 0.0
        assert entry['achievement_pct'] < 0

    def test_radar_marks_negative_axis(self):
        WealthBalanceList.objects.create(yearmon=f'{YEAR}-01', wageincome=0, outmoney=9000)
        wealth = {a['module']: a for a in P.get_radar(YEAR)['axes']}[WEALTH]
        assert wealth['achievement_negative'] is True
        assert wealth['achievement_target'] == wealth['axis_max'] * 10000
        assert wealth['net_amount'] == -9000


@pytest.mark.django_db
class TestMonthScopedIntensity:
    def test_single_month_intensity_divides_by_one(self):
        """🔴 单月视角：分子是这个月的总量，分母必须是「这个月有没有记」（0/1）

        用「全年有记录的月数」当分母，会把本月总量除以 9 —— 强度凭空小 9 倍。
        """
        if COMPLETED_MONTHS < 2:
            pytest.skip('需要至少 2 个完整月')
        for m in (1, 2, 3):
            WealthBalanceList.objects.create(yearmon=f'{YEAR}-{m:02d}', wageincome=30000, outmoney=0)

        detail = P.get_monthly_detail(YEAR, 1)
        wealth = {m['module']: m for m in detail['modules']}[WEALTH]
        # 1 月净额 30000 元，只有 1 个月有记录 ⇒ 强度 30000 元/月（不是 30000/3）
        assert wealth['coverage']['intensity'] == 30000.0
        assert wealth['coverage']['covered'] == 1
        assert wealth['coverage']['periods'] == 1


@pytest.mark.django_db
class TestRadar:
    def test_axes_have_both_lenses(self):
        radar = P.get_radar(YEAR)
        assert radar['basis_default'] == 'coverage'
        assert len(radar['axes']) == len(MODULE_LIST)
        for a in radar['axes']:
            assert 'coverage' in a and 'achievement' in a
            assert a['axis_max'] is not None

    def test_achievement_is_points_over_axis_max(self):
        _steps(TODAY, 20000)     # 2 点（2 万步 ÷ 1 万）
        axes = {a['module']: a for a in P.get_radar(YEAR)['axes']}
        health = axes[HEALTH]
        assert health['achievement'] == round(2 / health['axis_max'] * 100, 1)

    def test_coverage_matches_overview(self):
        ov = {m['module']: m for m in P.get_yearly_overview(YEAR)['modules']}
        for a in P.get_radar(YEAR)['axes']:
            assert a['coverage'] == ov[a['module']]['coverage']['pct']
