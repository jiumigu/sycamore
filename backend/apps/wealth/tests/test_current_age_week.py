"""「现在处在第几岁第几周」口径测试 — apps.wealth.services.week_aggregator.current_age_week

对应缺陷（v3.60.15 修）：热力图在 31/32 岁之间出现 52 周缺口。
成因是「现在在哪一周」有两把尺子：
  · 周历表（真源）—— age_year 按日历年年序编、week_number 以「当年第一个周一」为第 1 周；
  · 旧 `/age-week/`（现算）—— `settings.WEALTH_BIRTH_DATE` + `today.isocalendar()[1]`。
两把尺子在跨年处错开一整年（外加 ISO 周与周历周的 1 周差），推演起点因此
落在历史终点之后 53 个索引，中间 52 格既非「已度过」也不在覆盖范围内。
"""
from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient

from apps.wealth.constants import (
    WEEKS_PER_YEAR, WINDOW_END_AGE, WINDOW_START_INDEX,
    age_week_to_global_index,
)
from apps.wealth.services import week_aggregator
from apps.wealth.services.coverage_calculator import calculate_coverage
from apps.wealth.services.week_aggregator import (
    CURRENT_AGE_WEEK_SOURCE_BIRTHDATE,
    CURRENT_AGE_WEEK_SOURCE_CALENDAR,
    current_age_week,
)
from apps.wealth.models import WealthLifeWeekCalendar

AGE_WEEK_URL = '/api/wealth/age-week/'
SUMMARY_URL = '/api/wealth/summary/'

# 现场坐标：2026-10-09 那天，周历表说「今天」在 31 岁第 40 周（索引 715）；
# 旧尺子（出生日期现算 + ISO 周）说在 32 岁第 41 周（索引 768）。
LAST_LIVED_INDEX = age_week_to_global_index(31, 40)   # 715
OLD_RULER_INDEX = age_week_to_global_index(32, 41)    # 768


def _seed_index(index: int, week_start: date, user_id: int = 1) -> WealthLifeWeekCalendar:
    """按全局索引造一行周历（age_year / week_number 由索引反推，与表口径一致）。"""
    return WealthLifeWeekCalendar.objects.create(
        global_week_index=index,
        age_year=18 + index // WEEKS_PER_YEAR,
        week_number=index % WEEKS_PER_YEAR + 1,
        week_start_date=week_start,
        week_end_date=week_start + timedelta(days=6),
        is_lived=True,
        user_id=user_id,
    )


def _seed_window_history(user_id: int = 1) -> None:
    """把窗口起点(19 岁第 1 周=索引 52)到「今天」(索引 715)的每一周都造出来。

    日期取过去的连续周，保证 `update_lived_status()` 不会把任何一行翻回未度过。
    """
    base = date(2013, 1, 7)  # 某个周一
    WealthLifeWeekCalendar.objects.bulk_create([
        WealthLifeWeekCalendar(
            global_week_index=WINDOW_START_INDEX + k,
            age_year=18 + (WINDOW_START_INDEX + k) // WEEKS_PER_YEAR,
            week_number=(WINDOW_START_INDEX + k) % WEEKS_PER_YEAR + 1,
            week_start_date=base + timedelta(weeks=k),
            week_end_date=base + timedelta(weeks=k, days=6),
            is_lived=True,
            user_id=user_id,
        )
        for k in range(LAST_LIVED_INDEX - WINDOW_START_INDEX + 1)
    ])


# ──────────────────────────────────────────────────────────────
# 一、真源：周历表赢，出生日期现算不得进入链路
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_position_comes_from_calendar_row() -> None:
    """有周历行时：位置取「最后一个已度过行」，并标明来源为 calendar"""
    _seed_window_history()

    info = current_age_week()

    assert (info['current_age'], info['current_week']) == (31, 40)
    assert info['global_week_index'] == LAST_LIVED_INDEX
    assert info['source'] == CURRENT_AGE_WEEK_SOURCE_CALENDAR


@pytest.mark.django_db
def test_calendar_wins_over_birth_date_ruler(monkeypatch: pytest.MonkeyPatch) -> None:
    """把出生日期现算打成一个哨兵值 ⇒ 结果必须无视它（钉住「不得回头现算」）"""
    _seed_window_history()
    sentinel = (60, 52)
    monkeypatch.setattr(week_aggregator, '_age_week_from_birth_date', lambda *a, **k: sentinel)

    info = current_age_week()

    assert (info['current_age'], info['current_week']) != sentinel
    assert info['global_week_index'] == LAST_LIVED_INDEX


@pytest.mark.django_db
def test_falls_back_to_birth_date_when_calendar_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """周历尚未初始化（无任何已度过行）：回落现算，且**显式标明**来源与 lived_weeks=0"""
    sentinel = (30, 12)
    monkeypatch.setattr(week_aggregator, '_age_week_from_birth_date', lambda *a, **k: sentinel)

    info = current_age_week()

    assert (info['current_age'], info['current_week']) == sentinel
    assert info['source'] == CURRENT_AGE_WEEK_SOURCE_BIRTHDATE
    assert info['lived_weeks'] == 0


@pytest.mark.django_db
def test_birth_date_fallback_stays_inside_legal_range() -> None:
    """回落路径的越界保护：年龄夹到 18–78、周数夹到 1–52（越界索引会静默算到窗口外）"""
    from apps.wealth.constants import END_AGE, START_AGE

    age, week = week_aggregator._age_week_from_birth_date(today=date(1900, 1, 1))
    assert age == START_AGE and 1 <= week <= WEEKS_PER_YEAR

    age, week = week_aggregator._age_week_from_birth_date(today=date(2100, 1, 1))
    assert age == END_AGE and 1 <= week <= WEEKS_PER_YEAR


# ──────────────────────────────────────────────────────────────
# 二、缺口：历史终点与推演起点必须首尾相接
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_projection_starts_at_last_lived_week() -> None:
    """推演起点 = 最后一个已度过周（本轮的缺陷本体）"""
    _seed_window_history()
    info = current_age_week()

    coverage, support_weeks, _, _ = calculate_coverage(
        start_age=info['current_age'], start_week=info['current_week'],
        cash=100000.0, daily_budget=100.0, max_age=WINDOW_END_AGE,
    )

    assert coverage[0] == LAST_LIVED_INDEX
    assert support_weeks == len(coverage)


@pytest.mark.django_db
def test_no_unclaimed_week_between_history_and_coverage() -> None:
    """🔴 缺陷本体：窗口内「已度过 ∪ 被覆盖」不得出现空洞（31/32 岁之间曾有 52 周空洞）"""
    _seed_window_history()
    info = current_age_week()
    coverage, *_ = calculate_coverage(
        start_age=info['current_age'], start_week=info['current_week'],
        cash=100000.0, daily_budget=100.0, max_age=WINDOW_END_AGE,
    )

    lived = set(range(WINDOW_START_INDEX, LAST_LIVED_INDEX + 1))
    covered = set(coverage)
    holes = [i for i in range(WINDOW_START_INDEX, max(covered) + 1) if i not in lived | covered]

    assert holes == []


@pytest.mark.django_db
def test_old_birth_date_ruler_would_leave_a_52_week_hole() -> None:
    """钉住真因：用旧尺子的起点 (32,41) 算，历史与覆盖之间恰好裂开 52 周"""
    _seed_window_history()

    coverage, *_ = calculate_coverage(
        start_age=32, start_week=41, cash=100000.0, daily_budget=100.0, max_age=WINDOW_END_AGE,
    )

    assert coverage[0] == OLD_RULER_INDEX
    assert len(range(LAST_LIVED_INDEX + 1, coverage[0])) == 52


# ──────────────────────────────────────────────────────────────
# 三、同一页两个数字：lived_weeks 与 /summary/ 同源
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_lived_weeks_counts_only_window_rows() -> None:
    """口径：窗口外（18 岁那段）的已度过周不计入 lived_weeks"""
    _seed_window_history()
    _seed_index(10, date(2020, 1, 6))   # 18 岁第 11 周 —— 窗口之外

    info = current_age_week()

    assert info['lived_weeks'] == LAST_LIVED_INDEX - WINDOW_START_INDEX + 1  # 664


@pytest.mark.django_db
def test_lived_weeks_matches_summary_on_the_same_page() -> None:
    """页头「已度过 N 周」与推演面板基数是同一个数（否则进度条与页头打架）"""
    _seed_window_history()

    header = APIClient().get(SUMMARY_URL).json()
    panel = APIClient().get(AGE_WEEK_URL).json()

    assert header['lived_weeks'] == panel['lived_weeks'] == 664


@pytest.mark.django_db
def test_age_week_api_keeps_contract_and_adds_source() -> None:
    """接口契约：三个旧键仍在，新增 global_week_index / lived_weeks / source"""
    _seed_window_history()

    body = APIClient().get(AGE_WEEK_URL).json()

    for key in ('current_age', 'current_week', 'birth_date'):
        assert key in body
    assert body['global_week_index'] == LAST_LIVED_INDEX
    assert body['lived_weeks'] == 664
    assert body['source'] == CURRENT_AGE_WEEK_SOURCE_CALENDAR


@pytest.mark.django_db
def test_other_users_calendar_rows_do_not_move_my_position() -> None:
    """边界：别人（user 2）的周历行不影响我的当前位置"""
    _seed_window_history(user_id=1)
    _seed_index(OLD_RULER_INDEX, date(2026, 10, 5), user_id=2)

    info = current_age_week(user_id=1)

    assert info['global_week_index'] == LAST_LIVED_INDEX
    assert info['lived_weeks'] == 664
