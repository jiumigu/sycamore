"""阶段「第 N 天」口径（v3.63.13）

守一件事：**「第 N 天」是今天在阶段里的第几天，不是阶段的计划总长。**

起因：离职适应期 2026-11-01 → 2026-12-31，今天 10-22，页头却显示「第 61 天」。
旧实现 `end = end_date or today` —— 只要设了终点，就永远拿终点当「今天」，
于是「第 N 天」变成 `(终点 − 起点) + 1` = 计划总长，并且**每天都不变**。
"""
import datetime as dt

import pytest
from django.utils import timezone

from apps.selfrun.models import SelfRunStage
from apps.selfrun.serializers import SelfRunStageSerializer

pytestmark = pytest.mark.django_db


def _stage(start_offset, end_offset=None, status='active'):
    today = timezone.localdate()
    return SelfRunStage.objects.create(
        name='测试阶段',
        start_date=today + dt.timedelta(days=start_offset),
        end_date=None if end_offset is None else today + dt.timedelta(days=end_offset),
        status=status,
    )


def _days(stage):
    return SelfRunStageSerializer(stage).data['elapsed_days']


def _label(stage):
    return SelfRunStageSerializer(stage).data['days_label']


def _range(stage):
    return SelfRunStageSerializer(stage).data['range_label']


def test_running_counts_from_today_not_from_end():
    """进行中：终点在 20 天之后，今天是第 10 天 —— 不能算成 30 天（旧实现会）。"""
    s = _stage(start_offset=-9, end_offset=20)
    assert _days(s) == 10
    assert _label(s) == '第 10 天'


def test_not_started_is_zero_and_says_how_far():
    """还没开始：今天早于起点 ⇒ 0。

    「什么时候开始」由 `range_label` 说，`days_label` 只说**还差几天**
    —— v3.64.10 前它自己带 `MM-DD 起`，于是页头写成「未开始 · 11-01 起」
    却**永远没有终点**（用户 2026-10-31 提的就是这个）。
    """
    s = _stage(start_offset=5, end_offset=20)
    assert _days(s) == 0
    assert _label(s) == '还有 5 天开始'


def test_closed_freezes_at_total():
    """已归档：定格在总长，词也要换 —— 「第 61 天」用在归档阶段上会被读成还在跑。"""
    s = _stage(start_offset=-100, end_offset=-40, status='closed')
    assert _days(s) == 61
    assert _label(s) == '共 61 天'


def test_past_end_but_active_does_not_keep_growing():
    """过了终点却还没归档：天数停在上限，不会随日期继续涨。"""
    s = _stage(start_offset=-10, end_offset=-1)
    assert _days(s) == 10


def test_open_ended_uses_today():
    """没设终点：起点到今天 + 1。"""
    s = _stage(start_offset=-4, end_offset=None)
    assert _days(s) == 5
    assert _label(s) == '第 5 天'


def test_start_day_is_day_one():
    """起点当天 = 第 1 天（不是第 0 天）。"""
    s = _stage(start_offset=0, end_offset=None)
    assert _days(s) == 1
    assert _label(s) == '第 1 天'


# ── 区间 `range_label`：阶段从哪天到哪天（v3.64.10）──────────────
# 起因：页头只印 `days_label`，而它当时只在「未开始」时带一个 `MM-DD 起`，
# 于是阶段跑起来之后整页**看不到终点**，阶段总结里也读不出统计边界。

def test_range_label_has_both_ends_and_total_days():
    """有终点：起止都给，并算出总天数（含首尾：11-01→12-31 = 61 天）。"""
    s = SelfRunStage.objects.create(
        name='区间阶段',
        start_date=dt.date(2026, 11, 1),
        end_date=dt.date(2026, 12, 31),
    )
    assert _range(s) == '2026-11-01 ~ 2026-12-31（61 天）'


def test_range_label_open_ended_says_so():
    """没设终点：不许印一个假终点 —— 明说「不设终点，手动收尾」。"""
    s = SelfRunStage.objects.create(
        name='开放阶段', start_date=dt.date(2026, 11, 1), end_date=None,
    )
    assert _range(s) == '2026-11-01 起（不设终点，手动收尾）'


def test_start_date_lives_in_range_label_not_days_label():
    """起点日期只准在 `range_label` 出现 —— 两处都写，页头会像两个不同的值。"""
    s = _stage(start_offset=5, end_offset=20)
    assert f'{s.start_date:%Y-%m-%d}' in _range(s)
    assert f'{s.start_date:%m-%d}' not in _label(s)


# ── 相位词与进度词不能打架（v3.64.10）────────────────────────────

def test_status_display_says_not_started_before_start():
    """`active` 但还没到起点 ⇒ 显示「未开始」。

    库里 `active` 说的是「这是当前在册的那一个阶段」，不是「已经在跑了」。
    照旧印「进行中」，页头会写成「进行中 · 还有 1 天开始」。
    """
    s = _stage(start_offset=5, end_offset=20)
    assert SelfRunStageSerializer(s).data['status_display'] == '未开始'


def test_status_display_keeps_running_after_start():
    """已经在跑：仍说「进行中」（别把 active 一律改词）。"""
    s = _stage(start_offset=-2, end_offset=20)
    assert SelfRunStageSerializer(s).data['status_display'] == '进行中'
