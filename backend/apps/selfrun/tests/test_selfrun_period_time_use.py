"""历史复盘列表的「时间去向」列（v3.64.67）

用户诉求：不点开抽屉，也要在列表上看到「那一周我到底在干什么」——
成长 / 体验 / 维持 / 流失 各多少小时。

🔴 三条钉子：
1. **同源**：这一列与抽屉里「这一期我做了什么」顶部那行必须是同一份数
   （`_attr_totals` + 同一份 `contrib_excluded_names()`）。列表 44.6、点进去 47.2
   是最坏的一种错 —— 看着像「归档后又补记了」。
2. **一次取数**：100 期不是 100 次扫表（`period_time_use` 取一次再按本地日期分组）。
   这条用「查询次数」钉不住（实现可以变），但「各期只算自己窗口」是行为契约。
3. **现算 ≠ 快照**：它不在归档快照里，补记时间后历史各期会变；
   真 0（没记录）与「取不到」必须分开说。
"""
import datetime as dt

import pytest
from django.utils import timezone

from apps.selfrun import services
from apps.selfrun.models import SelfRunPeriod, SelfRunStage
from apps.temporal.models import TaskMeta, TemporalTask

URL = '/api/selfrun'

WEEK_START = dt.date(2026, 3, 2)      # 周一
WEEK_END = dt.date(2026, 3, 9)        # 下周一（半开）
PREV_START = dt.date(2026, 2, 23)
PREV_END = dt.date(2026, 3, 2)


def _stage():
    return SelfRunStage.objects.create(
        name='测试阶段', start_date=PREV_START, end_date=WEEK_START + dt.timedelta(days=60),
    )


def _period(stage, key, start, end, ptype='weekly', closed=True):
    return SelfRunPeriod.objects.create(
        stage=stage, period_type=ptype, period_key=key,
        period_start=start, period_end=end,
        closed_at=timezone.now() if closed else None,
    )


def _task(name, day, hours, attribution, hour=9):
    TaskMeta.objects.get_or_create(
        task_name=name, defaults={'default_attribution': attribution, 'activity_type': '测试'},
    )
    TemporalTask.objects.create(
        task_name=name,
        start_time=timezone.make_aware(dt.datetime.combine(day, dt.time(hour, 0))),
        duration_hours=hours,
    )


# ══════════════════════════════════════════════════════════
# ① 服务层：归因合计
# ══════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_time_use_sums_hours_by_attribution():
    stage = _stage()
    p = _period(stage, '2026-W10', WEEK_START, WEEK_END)
    _task('写代码', WEEK_START, 4.0, '成长')
    _task('看书', WEEK_START + dt.timedelta(days=1), 2.0, '成长')
    _task('刷短视频', WEEK_START + dt.timedelta(days=2), 3.5, '流失')

    out = services.period_time_use([p])[p.id]

    assert out['attr_totals'] == [
        {'label': '成长', 'hours': 6.0},
        {'label': '流失', 'hours': 3.5},
    ]
    assert out['total_hours'] == 9.5
    assert out['day_count'] == 3


@pytest.mark.django_db
def test_each_period_sees_only_its_own_window():
    """两期各算各的 —— 批量取数不能把整段窗口记到每一期头上。"""
    stage = _stage()
    prev = _period(stage, '2026-W09', PREV_START, PREV_END)
    cur = _period(stage, '2026-W10', WEEK_START, WEEK_END)
    _task('上周的事', PREV_START + dt.timedelta(days=1), 5.0, '体验')
    _task('这周的事', WEEK_START + dt.timedelta(days=1), 2.0, '维持')

    out = services.period_time_use([prev, cur])

    assert out[prev.id]['attr_totals'] == [{'label': '体验', 'hours': 5.0}]
    assert out[cur.id]['attr_totals'] == [{'label': '维持', 'hours': 2.0}]


@pytest.mark.django_db
def test_week_and_month_each_answer_their_own_window():
    """「全部」筛选下周与月会重叠 —— 同一条记录被两行读到是**对的**，各答各的窗口。"""
    stage = _stage()
    week = _period(stage, '2026-W10', WEEK_START, WEEK_END)
    month = _period(stage, '2026-03', dt.date(2026, 3, 1), dt.date(2026, 4, 1), 'monthly')
    _task('写代码', WEEK_START, 4.0, '成长')

    out = services.period_time_use([week, month])

    assert out[week.id]['total_hours'] == 4.0
    assert out[month.id]['total_hours'] == 4.0


@pytest.mark.django_db
def test_empty_period_is_real_zero_not_none():
    """🔴 一期没有任何记录 ⇒ `[]` + `0.0`（真 0），不是 `None`（取不到）。"""
    stage = _stage()
    p = _period(stage, '2026-W10', WEEK_START, WEEK_END)

    out = services.period_time_use([p])[p.id]

    assert out['attr_totals'] == []
    assert out['total_hours'] == 0.0
    assert out['day_count'] == 0


@pytest.mark.django_db
def test_sleep_tasks_are_excluded():
    """睡眠类两边都排掉（与 `what_happened` 同一份名单）—— 否则「休息睡眠」恒居第一。"""
    stage = _stage()
    p = _period(stage, '2026-W10', WEEK_START, WEEK_END)
    _task('休息睡眠', WEEK_START, 8.0, '维持')
    _task('写代码', WEEK_START, 4.0, '成长')

    out = services.period_time_use([p])[p.id]

    assert out['attr_totals'] == [{'label': '成长', 'hours': 4.0}]
    assert out['total_hours'] == 4.0


@pytest.mark.django_db
def test_matches_what_happened_attr_totals():
    """🔴 同源：列表这一列与抽屉里那张卡顶部**必须逐字相等**。"""
    stage = _stage()
    p = _period(stage, '2026-W10', WEEK_START, WEEK_END)
    _task('写代码', WEEK_START, 4.04, '成长')
    _task('看书', WEEK_START + dt.timedelta(days=1), 2.0, '体验')
    _task('刷短视频', WEEK_START + dt.timedelta(days=2), 3.5, '流失')

    from_list = services.period_time_use([p])[p.id]['attr_totals']
    from_card = services.compute_period_extras(
        'weekly', WEEK_START, WEEK_END,
    )['what_happened']['attr_totals']

    assert from_list == from_card


@pytest.mark.django_db
def test_total_is_sum_of_rounded_items():
    """🔴 合计 = **显示精度下各项之和**，不是原始和再取整。

    原始和 1.04+1.04 = 2.08 ⇒ 直接取整是 2.1；而列上印的是 1.0 + 1.0 = 2.0。
    用户唯一能自查的就是「几个数加起来等于合计」，两把尺子会让它对不上。
    """
    stage = _stage()
    p = _period(stage, '2026-W10', WEEK_START, WEEK_END)
    _task('写代码', WEEK_START, 1.04, '成长')
    _task('散步', WEEK_START, 1.04, '体验')

    out = services.period_time_use([p])[p.id]

    assert [a['hours'] for a in out['attr_totals']] == [1.0, 1.0]
    assert out['total_hours'] == 2.0


@pytest.mark.django_db
def test_uses_local_date_not_utc():
    """UTC 23:00 = 本地次日 07:00 ⇒ 算**第二天**那一期。

    `start_time` 存 UTC（`USE_TZ=True`），直接 `.date()` 会把「早上的事」
    算到前一天 —— 与 `_what_happened` 同一条坑。
    """
    stage = _stage()
    prev = _period(stage, '2026-W09', PREV_START, PREV_END)
    cur = _period(stage, '2026-W10', WEEK_START, WEEK_END)
    # 3-01 23:00 UTC = 3-02 07:00 CST ⇒ 属于 W10
    TemporalTask.objects.create(
        task_name='早起写作',
        start_time=dt.datetime(2026, 3, 1, 23, 0, tzinfo=dt.timezone.utc),
        duration_hours=2.0,
    )
    TaskMeta.objects.get_or_create(
        task_name='早起写作',
        defaults={'default_attribution': '成长', 'activity_type': '测试'},
    )

    out = services.period_time_use([prev, cur])

    assert out[prev.id]['total_hours'] == 0.0
    assert out[cur.id]['total_hours'] == 2.0


@pytest.mark.django_db
def test_no_periods_returns_empty_dict():
    assert services.period_time_use([]) == {}


# ══════════════════════════════════════════════════════════
# ② 端点：列表带 / 详情不带
# ══════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_list_endpoint_includes_time_use(client):
    stage = _stage()
    p = _period(stage, '2026-W10', WEEK_START, WEEK_END)
    _period(stage, '2026-W11', WEEK_END, WEEK_END + dt.timedelta(days=7))
    _task('写代码', WEEK_START, 4.0, '成长')

    body = client.get(f'{URL}/periods/').json()
    row = next(r for r in body if r['id'] == p.id)

    assert row['time_use']['attr_totals'] == [{'label': '成长', 'hours': 4.0}]
    assert row['time_use']['total_hours'] == 4.0
    assert row['time_use']['day_count'] == 1


@pytest.mark.django_db
def test_list_endpoint_does_not_mix_periods(client):
    """两行各是各的数 —— 别把整段窗口的和印在每一行上。"""
    stage = _stage()
    a = _period(stage, '2026-W10', WEEK_START, WEEK_END)
    b = _period(stage, '2026-W11', WEEK_END, WEEK_END + dt.timedelta(days=7))
    _task('写代码', WEEK_START, 4.0, '成长')
    _task('刷短视频', WEEK_END, 1.0, '流失')

    body = {r['id']: r for r in client.get(f'{URL}/periods/').json()}

    assert body[a.id]['time_use']['total_hours'] == 4.0
    assert body[b.id]['time_use']['total_hours'] == 1.0


@pytest.mark.django_db
def test_detail_endpoint_has_no_time_use(client):
    """🔴 详情 / 归档 / 重开共用 `SelfRunPeriodSerializer` —— 那个类不许带上这个键。

    带上了就会让「接口没算」（`null`）与「这一期没记录」（`[]`）混成一件事。
    """
    stage = _stage()
    p = _period(stage, '2026-W10', WEEK_START, WEEK_END)

    body = client.get(f'{URL}/periods/{p.id}/').json()

    assert 'time_use' not in body['period']
