"""复盘两块补充 + 模板差异只读出口

对应第八轮审计的两件事：
- P0-1：模板改了、库里的 metric 行没改 ⇒ `template_drift` 必须能报出来（只读）
- 用户要求：每周复盘要能看到「本周该交的」与「本周流走的时间」
"""
import datetime as dt

import pytest
from django.utils import timezone

from apps.goals.models import Goal, Milestone
from apps.selfrun import services
from apps.selfrun.models import SelfRunMetric, SelfRunStage, SelfRunTemplate
from apps.temporal.models import TaskMeta

WEEK_START = dt.date(2026, 3, 2)     # 周一
WEEK_END = dt.date(2026, 3, 9)       # 下周一（半开区间右端）


def _stage():
    return SelfRunStage.objects.create(
        name='测试阶段', start_date=WEEK_START, end_date=WEEK_START + dt.timedelta(days=90),
    )


# ══════════════════════════════════════════════════════════
# ① 目标完成情况
# ══════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_extras_counts_due_done_and_overdue():
    goal = Goal.objects.create(title='目标A', user_id=1, status='in-progress')
    # 本期到期：2 个，其中 1 个完成
    Milestone.objects.create(goal=goal, title='到期已完成', status='completed',
                             target_date=WEEK_START + dt.timedelta(days=2))
    Milestone.objects.create(goal=goal, title='到期未完成', status='pending',
                             target_date=WEEK_START + dt.timedelta(days=4))
    # 历史逾期：1 个
    Milestone.objects.create(goal=goal, title='上期欠的', status='pending',
                             target_date=WEEK_START - dt.timedelta(days=10))
    # 下期才到期：不算
    Milestone.objects.create(goal=goal, title='以后再说', status='pending',
                             target_date=WEEK_END + dt.timedelta(days=3))

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)

    assert out['goals']['due'] == 2
    assert out['goals']['done'] == 1
    assert out['goals']['overdue'] == 1
    assert {i['title'] for i in out['goals']['items']} == {'到期已完成', '到期未完成'}


@pytest.mark.django_db
def test_extras_due_is_half_open_on_the_right():
    """`target_date == end` 不在本期（半开区间 `[start, end)`）。"""
    goal = Goal.objects.create(title='边界', user_id=1, status='in-progress')
    Milestone.objects.create(goal=goal, title='右端点', status='pending', target_date=WEEK_END)
    Milestone.objects.create(goal=goal, title='左端点', status='pending', target_date=WEEK_START)

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)

    assert out['goals']['due'] == 1
    assert out['goals']['items'][0]['title'] == '左端点'


# ══════════════════════════════════════════════════════════
# ② 时间流失
# ══════════════════════════════════════════════════════════

def _task(name, day, hours, attribution):
    from apps.temporal.models import TemporalTask

    TaskMeta.objects.get_or_create(
        task_name=name, defaults={'default_attribution': attribution, 'activity_type': '测试'},
    )
    TemporalTask.objects.create(
        task_name=name,
        start_time=timezone.make_aware(dt.datetime.combine(day, dt.time(9, 0))),
        duration_hours=hours,
    )


@pytest.mark.django_db
def test_extras_time_loss_ratio_and_top():
    _task('刷短视频', WEEK_START, 6.0, '流失')
    _task('发呆', WEEK_START + dt.timedelta(days=1), 2.0, '流失')
    _task('写代码', WEEK_START + dt.timedelta(days=1), 2.0, '成长')

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)
    loss = out['time_loss']

    assert loss['loss_hours'] == 8.0
    assert loss['total_hours'] == 10.0
    assert loss['ratio'] == 0.8
    assert loss['top'][0] == {'task_name': '刷短视频', 'hours': 6.0}
    assert len(loss['top']) == 2


@pytest.mark.django_db
def test_extras_time_loss_ratio_is_none_without_records():
    """一期没有任何时间记录 ⇒ `ratio = None`（不是 0%）。"""
    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)
    assert out['time_loss']['ratio'] is None
    assert out['time_loss']['loss_hours'] == 0.0


# ══════════════════════════════════════════════════════════
# ③ 模板差异（只读）
# ══════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_template_drift_reports_field_differences():
    stage = _stage()
    metric = SelfRunMetric.objects.create(
        stage=stage, template_key='content_output', name='内容输出',
        period_type='monthly', unit='条', direction='at_least',
        goal_value=8, floor_value=4, agg='count', source_kind='auto',
        source_config={'kind': 'diary_migu_count', 'where': {'otype_eq': 'MIGU'}},
        status='active',
    )

    drift = services.template_drift(stage)
    row = next(d for d in drift if d['metric_id'] == metric.id)
    fields = {d['field'] for d in row['diffs']}

    assert 'name' in fields
    assert 'unit' in fields
    assert 'source_config' in fields
    assert 'goal_value' in fields, '目标 8 vs 模板 4 也要报出来'


@pytest.mark.django_db
def test_template_drift_is_read_only():
    """🔴 只报差异，绝不改库 —— 目标值是用户手调的输入。"""
    stage = _stage()
    SelfRunMetric.objects.create(
        stage=stage, template_key='go_out_days', name='出门天数',
        period_type='weekly', unit='天', direction='at_least',
        goal_value=3, floor_value=1, agg='count', source_kind='auto',
        source_config={'kind': 'temporal_days', 'where': {'l2': ['外出']}},
        status='active',
    )

    services.template_drift(stage)

    m = SelfRunMetric.objects.get(stage=stage, template_key='go_out_days')
    assert float(m.goal_value) == 3.0, '模板是 5，但库里是用户手调的 3 —— 不许覆盖'


@pytest.mark.django_db
def test_template_drift_empty_when_aligned():
    stage = _stage()
    tpl = SelfRunTemplate.objects.get(key='go_out_days')
    SelfRunMetric.objects.create(
        stage=stage, template_key='go_out_days', name=tpl.name,
        period_type=tpl.period_type, unit=tpl.unit, direction=tpl.direction,
        goal_value=tpl.goal_value, floor_value=tpl.floor_value, agg=tpl.agg,
        source_kind=tpl.source_kind, source_config=tpl.source_config,
        status='active',
    )

    assert services.template_drift(stage) == []


# ══════════════════════════════════════════════════════════
# ④ 这一周我做了什么（复盘页的「勾回忆」块）
# ══════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_what_happened_groups_by_day_and_caps_items():
    """每天最多列 3 件（版面预算），剩下的用 `more` 计数——不能让人以为这周只做了 3 件事。"""
    for i in range(5):
        _task(f'任务{i}', WEEK_START, float(i + 1), '成长')
    _task('另一天的事', WEEK_START + dt.timedelta(days=1), 2.0, '体验')

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['what_happened']

    assert out['day_count'] == 2
    monday = out['days'][0]
    assert monday['weekday'] == '周一'
    assert monday['total_hours'] == 15.0
    assert [i['task_name'] for i in monday['items']] == ['任务4', '任务3', '任务2']
    assert monday['more'] == 2


@pytest.mark.django_db
def test_what_happened_uses_local_date_not_utc():
    """本地 07:00 的记录在 UTC 里是**前一天 23:00**，必须落在本地当天。

    `USE_TZ=True` + `Asia/Shanghai`：直接 `.date()` 会把它记到前一天，
    而「早上七点」正好天天落在这个区间——错一天，回忆就对不上号。
    """
    from apps.temporal.models import TemporalTask

    TaskMeta.objects.get_or_create(task_name='早起写代码', defaults={'default_attribution': '成长'})
    TemporalTask.objects.create(
        task_name='早起写代码',
        start_time=timezone.make_aware(dt.datetime.combine(WEEK_START, dt.time(7, 0))),
        duration_hours=1.0,
    )

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['what_happened']

    assert out['days'][0]['date'] == WEEK_START.isoformat()
    assert out['days'][0]['weekday'] == '周一'


@pytest.mark.django_db
def test_what_happened_attr_totals_follow_attribution_order():
    _task('写代码', WEEK_START, 2.0, '成长')
    _task('旅游', WEEK_START, 3.0, '体验')
    _task('刷短视频', WEEK_START, 6.0, '流失')

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['what_happened']

    assert [a['label'] for a in out['attr_totals']] == ['成长', '体验', '流失']
    assert out['attr_totals'][2]['hours'] == 6.0


@pytest.mark.django_db
def test_what_happened_merges_same_task_in_one_day():
    """同一天同一任务的多条记录合并成一格。

    不合并的话，前 3 格里会有两格都是「刷短视频 2.6 / 1.0」——
    一天看起来只做了 2 件事，而这天实际有 3 件。
    """
    _task('刷短视频', WEEK_START, 2.6, '流失')
    _task('刷短视频', WEEK_START, 1.0, '流失')
    _task('写代码', WEEK_START, 1.5, '成长')

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['what_happened']

    assert [(i['task_name'], i['hours']) for i in out['days'][0]['items']] == [
        ('刷短视频', 3.6), ('写代码', 1.5),
    ]
    assert out['days'][0]['total_hours'] == 5.1
    assert out['days'][0]['more'] == 0


@pytest.mark.django_db
def test_what_happened_excludes_sleep_tasks():
    """睡眠类不进「我做了什么」——名单与贡献图同一份。

    不排掉的话，每天都有一条「休息睡眠 8h」恒排第一，这一块等于白做；
    而「睡了多久」在健康/护栏卡里已经有出口。
    """
    _task('休息睡眠', WEEK_START, 8.0, '维持')
    _task('写代码', WEEK_START, 3.0, '成长')

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['what_happened']

    assert [i['task_name'] for i in out['days'][0]['items']] == ['写代码']
    assert out['days'][0]['total_hours'] == 3.0
    assert [a['label'] for a in out['attr_totals']] == ['成长']


@pytest.mark.django_db
def test_what_happened_empty_period():
    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['what_happened']
    assert out['days'] == []
    assert out['day_count'] == 0
    assert out['attr_totals'] == []
    assert out['blocks'] == []
    assert out['span'] is None
    assert out['truncated'] == 0
    # 列**照样有 7 天**：时间轴要先画得出一周的格，才能在上面说「这周空的」
    assert [c['weekday'] for c in out['columns']] == [
        '周一', '周二', '周三', '周四', '周五', '周六', '周日',
    ]


# ── 时段轴（v3.64.35）──────────────────────────────────────────
#
# 这一段的每一条都在防同一个事故：**图上的块和列表里的数对不上。**
# 两套视图出自同一个 `_what_happened`，所以「块分钟之和 ÷ 60 == days 的 total_hours」
# 是这轮唯一真正的验收口径（见 `test_blocks_minutes_match_day_hours`）。

def _timed(name, day, hour, minute, hours, attribution, with_end=True):
    """造一条起止明确的记录。

    ⚠️ `with_end=False` 时**只给时长不给终点** —— 真实库里 `end_time` 可空
       （W44 那周 47 条都有，但字段本身允许空），两条分支都要走到。
    """
    from apps.temporal.models import TemporalTask

    TaskMeta.objects.get_or_create(
        task_name=name, defaults={'default_attribution': attribution, 'activity_type': '测试'},
    )
    start = timezone.make_aware(dt.datetime.combine(day, dt.time(hour, minute)))
    return TemporalTask.objects.create(
        task_name=name,
        start_time=start,
        end_time=(start + dt.timedelta(hours=hours)) if with_end else None,
        duration_hours=hours,
    )


@pytest.mark.django_db
def test_blocks_keep_each_record_separate():
    """时段轴**不合并**同名任务：3 条「刷短视频」就是 3 块。

    合并日期那块（`days`）问的是「今天做了几件事」，所以同名合并；
    时间轴问的是「几点到几点」，合并了就没有位置可言。
    """
    _timed('刷短视频', WEEK_START, 9, 0, 1.0, '流失')
    _timed('刷短视频', WEEK_START, 10, 30, 1.0, '流失')
    _timed('刷短视频', WEEK_START, 13, 0, 1.0, '流失')

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['what_happened']

    assert len(out['blocks']) == 3
    assert [b['from'] for b in out['blocks']] == [540.0, 630.0, 780.0]
    # 同一个函数产出的另一套视图：列表里仍然是**一格**
    assert [i['task_name'] for i in out['days'][0]['items']] == ['刷短视频']
    assert out['days'][0]['items'][0]['hours'] == 3.0


@pytest.mark.django_db
def test_blocks_split_across_midnight():
    """23:00 起 3 小时 ⇒ 切两段，各归各的一天。

    整块挪到第二天，「昨晚熬夜」就变成「今天凌晨」；
    不切而画在第一天，块会冲出 24:00 的底边。

    ⚠️ 列表（`days`）仍按**开始日**归类：先说「周一起那个动作」，
       再看时间轴上周二凌晨那 2 小时 —— 它们本来就是两件事（发生过 vs 被记起）。
    """
    _timed('熬夜写代码', WEEK_START, 23, 0, 3.0, '成长')

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['what_happened']

    assert len(out['blocks']) == 2
    head, tail = out['blocks']
    assert (head['date'], head['from'], head['to'], head['split']) == (
        WEEK_START.isoformat(), 1380.0, 1440.0, 'head')
    assert (tail['date'], tail['from'], tail['to'], tail['split']) == (
        (WEEK_START + dt.timedelta(days=1)).isoformat(), 0.0, 120.0, 'tail')
    # 起点仍在周一（列表口径不动）
    assert out['days'][0]['date'] == WEEK_START.isoformat()


@pytest.mark.django_db
def test_blocks_minutes_match_day_hours():
    """块分钟之和 ÷ 60 == 列表里那天的 total_hours。

    这是「图与表同源」的唯一验收口径 —— 两套视图一旦分家，
    用户会看到「图上 8 小时、列表写 9.5h」，而且两边都不像错的。
    """
    _timed('牛马工作', WEEK_START, 9, 0, 4.0, '谋生')
    _timed('刷短视频', WEEK_START, 14, 0, 2.5, '流失')
    _timed('日常家务', WEEK_START, 18, 30, 1.0, '维持')

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['what_happened']

    total_min = sum(b['minutes'] for b in out['blocks'])
    assert round(total_min / 60, 1) == out['days'][0]['total_hours']
    assert out['days'][0]['total_hours'] == 7.5


@pytest.mark.django_db
def test_blocks_exclude_sleep():
    """睡眠同样不进时间轴 —— 与列表用同一份排除名单。

    只排列表不排图，图上会有一条每天恒在的 8 小时巨块把白天压扁。
    """
    _timed('休息睡眠', WEEK_START, 0, 30, 7.5, '维持')
    _timed('写代码', WEEK_START, 9, 0, 2.0, '成长')

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['what_happened']

    assert [b['task_name'] for b in out['blocks']] == ['写代码']


@pytest.mark.django_db
def test_span_covers_earliest_and_latest():
    """`span` 给纵轴范围：主体块的最早开始 → 全部块的最晚结束。

    ⚠️ 不给 0–24：记录多半从 7 点起，画满 24 小时会在上方留一大片空白。
        但「不固定」不等于「越紧越好」—— 一条 5 分钟的跨午夜尾巴就能把
        纵轴拉回 00:00，见 `test_span_skips_thin_midnight_fragment`。
    """
    _timed('早起', WEEK_START, 7, 5, 1.0, '成长')
    _timed('睡前刷手机', WEEK_START, 22, 0, 1.5, '流失')

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['what_happened']

    assert out['span'] == {'from': 425.0, 'to': 1410.0}


@pytest.mark.django_db
def test_span_skips_thin_midnight_fragment():
    """跨午夜切出来的**短残片不参与纵轴上边界** —— 否则 5 分钟换 7 小时空白。

    实测 W42：三条尾巴 37 / 9 / 5 分钟（合计 51 分钟）把纵轴从 06:55 拉回
    00:00，图上多出 235px 空白，刻度上写着「02:00 / 04:00 / 06:00」却什么
    都没记。而这三段的身子在**前一天那一列**（23:35→24:00），什么都没丢。
    """
    # 23:35 起 1 小时 ⇒ 头段 25 分钟（到 24:00）+ 尾段 35 分钟（次日 00:00 起）
    _timed('睡前刷手机', WEEK_START, 23, 35, 1.0, '流失')
    _timed('早起', WEEK_START, 7, 5, 1.0, '成长')

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['what_happened']

    assert out['span'] == {'from': 425.0, 'to': 1440.0}
    # 残片**没被删**：前端要拿它在列顶标「＋35m」
    tail = [b for b in out['blocks'] if b['split'] == 'tail']
    assert len(tail) == 1
    assert tail[0]['from'] == 0.0 and tail[0]['minutes'] == 35.0
    # 它落在纵轴外面 —— 这正是「不该按位置画」的那一块
    assert tail[0]['to'] < out['span']['from']


@pytest.mark.django_db
def test_span_keeps_substantial_midnight_tail():
    """残片够长（≥ 1 小时）就要算进范围 —— 那是真的熬到了夜里两点。

    门槛设成 1 小时的理由：短于它的尾巴多半是「顺手记到 00:05」，
    长于它的是一片真实时段，藏起来等于篡改作息。
    """
    _timed('熬夜写代码', WEEK_START, 23, 0, 2.5, '成长')     # 23:00 → 次日 01:30

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['what_happened']

    assert out['span'] == {'from': 0.0, 'to': 1440.0}
    assert len(out['blocks']) == 2
    assert all(b['to'] <= out['span']['to'] and b['from'] >= out['span']['from']
               for b in out['blocks'])


@pytest.mark.django_db
def test_span_falls_back_when_only_fragments():
    """整周只有一条跨午夜记录（头尾都 < 1 小时）⇒ 退回用全部块。

    否则纵轴会是一个零长度区间（07:00–07:00），图直接画不出来。
    """
    _timed('深夜看小说', WEEK_START, 23, 50, 0.67, '流失')    # 23:50 → 次日 00:30

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['what_happened']

    assert out['span'] == {'from': 0.0, 'to': 1440.0}


@pytest.mark.django_db
def test_blocks_without_end_time_use_duration():
    """`end_time` 为空时用 `duration_hours` 推算终点，不留空洞。

    直接跳过这条记录会**静默少一块**：图和列表的合计就对不上了，
    而错误方向是「图比表少」，查起来要逐条比。
    """
    _timed('只有时长的记录', WEEK_START, 9, 0, 2.0, '成长', with_end=False)

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['what_happened']

    assert len(out['blocks']) == 1
    assert (out['blocks'][0]['from'], out['blocks'][0]['to']) == (540.0, 660.0)
    assert out['blocks'][0]['minutes'] == 120.0


@pytest.mark.django_db
def test_blocks_truncate_reports_count(monkeypatch):
    """超上限时**保长的**，并报出丢了几条。

    静默截断等于伪造：用户看到「那天就这几块」，少掉的部分没有任何提示。
    """
    monkeypatch.setattr(services, 'WHAT_HAPPENED_BLOCK_LIMIT', 3)
    for i, h in enumerate([1.0, 5.0, 2.0, 4.0, 3.0]):
        _timed(f'任务{i}', WEEK_START, 8 + i, 0, h, '成长')

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['what_happened']

    assert len(out['blocks']) == 3
    assert out['truncated'] == 2
    # 保住的是最长的三件（5h / 4h / 3h），不是最早的三个
    assert sorted((b['minutes'] / 60 for b in out['blocks']), reverse=True) == [5.0, 4.0, 3.0]


@pytest.mark.django_db
def test_blocks_payload_is_timezone_free():
    """下发的只有「当天第几分钟」，没有时间串。

    前端若拿到 `'2026-03-02 09:00'` 必然 `new Date()` 解析 —— `USE_TZ` 下差 8 小时，
    而它**看起来完全合法**（块在一个合理的位置），不会有任何报错。
    """
    _timed('写代码', WEEK_START, 9, 0, 2.0, '成长')

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['what_happened']

    block = out['blocks'][0]
    assert set(block) == {'date', 'from', 'to', 'minutes', 'task_name', 'attribution', 'split'}
    assert isinstance(block['from'], float) and isinstance(block['to'], float)
    assert 0 <= block['from'] < block['to'] <= 1440


# ══════════════════════════════════════════════════════════
# ⑤ 本期新增逾期（替代跨周恒定的「历史逾期」）
# ══════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_missed_is_due_minus_done():
    goal = Goal.objects.create(title='目标M', user_id=1, status='in-progress')
    Milestone.objects.create(goal=goal, title='交了', status='completed',
                             target_date=WEEK_START + dt.timedelta(days=1))
    Milestone.objects.create(goal=goal, title='没交', status='pending',
                             target_date=WEEK_START + dt.timedelta(days=3))
    Milestone.objects.create(goal=goal, title='没交2', status='pending',
                             target_date=WEEK_START + dt.timedelta(days=5))

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['goals']

    assert out['due'] == 3
    assert out['done'] == 1
    assert out['missed'] == 2


@pytest.mark.django_db
def test_time_loss_follows_mapping_table():
    """🔴 流失按映射表那列算，与仪表盘护栏卡、贡献图同一把尺子。

    旧实现按 `TaskMeta.default_attribution` 过滤、却依赖另一套「外挂规则」覆盖，
    被覆盖的任务会**静默漏掉**：复盘页说流失 0h，护栏卡却说超了 —— 同一件事两个数。
    规则表退役后只剩一列，这里钉住「按它算」。
    """
    _task('刷短视频', WEEK_START, 3.0, '流失')

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)

    assert out['time_loss']['loss_hours'] == 3.0
    assert out['what_happened']['days'][0]['items'][0]['attribution'] == '流失'


# ══════════════════════════════════════════════════════════
# ④ 这一期干成了什么（v3.64.37）
# ══════════════════════════════════════════════════════════

def _work(name, at):
    """造一件作品并把「成形于」挪到指定时刻（`auto_now_add` 会在 create 时覆盖）。"""
    from apps.works.models import Work

    w = Work.objects.create(name=name)
    Work.objects.filter(id=w.id).update(created_at=at)
    return w


def _sugar(title, day, joy_type='秩序型', level=10):
    from apps.sugar.models import SugarRecord

    return SugarRecord.objects.create(
        title=title, time=day, joy_type=joy_type, level_of_happiness=level,
    )


def _inbox(content, processed_at, status='done'):
    from apps.inbox.models import InboxItem

    return InboxItem.objects.create(
        content=content, status=status, processed_at=processed_at,
    )


@pytest.mark.django_db
def test_outcomes_works_are_half_open_on_the_right():
    """`created_at == end` 当天 00:00 属于下一期（半开区间）。"""
    from apps.selfrun import readers

    _work('期内成形', readers._aware(WEEK_START) + dt.timedelta(hours=12))
    _work('右端点成形', readers._aware(WEEK_END))

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['outcomes']

    assert out['works']['count'] == 1
    assert out['works']['items'][0]['title'] == '期内成形'


@pytest.mark.django_db
def test_outcomes_sugar_only_counts_order_type():
    """只收`秩序型`；其余类型不进，未标类型单列成 `untyped_count`（不静默消失）。"""
    _sugar('办完宽带', WEEK_START + dt.timedelta(days=1))
    _sugar('吃了大榴莲', WEEK_START + dt.timedelta(days=1), joy_type='感官型')
    _sugar('没标类型的一件', WEEK_START + dt.timedelta(days=2), joy_type='')

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['outcomes']

    assert out['finished']['count'] == 1
    assert out['finished']['items'][0]['title'] == '办完宽带'
    assert out['finished']['untyped_count'] == 1


@pytest.mark.django_db
def test_outcomes_sugar_datefield_is_inclusive_of_the_day():
    """小确幸是 DateField：`time == end - 1 天` 仍在期内（不是半开的 DateTime）。"""
    _sugar('最后一天的事', WEEK_END - dt.timedelta(days=1))

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['outcomes']

    assert out['finished']['count'] == 1


@pytest.mark.django_db
def test_outcomes_inbox_done_enters_but_processed_does_not():
    """收件箱只有 `done` 算「干成了」；`processed` 是「转走了」，不算。"""
    at = timezone.make_aware(dt.datetime.combine(WEEK_START + dt.timedelta(days=2), dt.time(10, 0)))
    _inbox('配置好了 style3D 目录', at, status='done')
    _inbox('转成里程碑的那条', at, status='processed')

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['outcomes']

    assert out['finished']['count'] == 1
    assert out['finished']['items'][0]['title'] == '配置好了 style3D 目录'
    assert out['finished']['items'][0]['source'] == 'inbox'


@pytest.mark.django_db
def test_outcomes_merges_same_title_across_inbox_and_sugar():
    """同一件事两处都记过 ⇒ 只出一行，来源标 `both`（不许数两遍）。"""
    at = timezone.make_aware(dt.datetime.combine(WEEK_START + dt.timedelta(days=2), dt.time(10, 0)))
    _inbox('去福州参加系统分析师考试', at, status='done')
    _sugar('完成：去福州参加系统分析师考试', WEEK_START + dt.timedelta(days=2))

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['outcomes']

    assert out['finished']['count'] == 1
    row = out['finished']['items'][0]
    assert row['source'] == 'both'
    # 保留小确幸那条（它带着快乐档位），不把两边拼起来
    assert row['happiness_label']


@pytest.mark.django_db
def test_outcomes_does_not_merge_different_wordings():
    """措辞不同就是两件事 —— 宁可漏，不可错（不做模糊匹配）。"""
    at = timezone.make_aware(dt.datetime.combine(WEEK_START + dt.timedelta(days=2), dt.time(10, 0)))
    _inbox('发公众号关于一步的内容', at, status='done')
    _sugar('发表了文章', WEEK_START + dt.timedelta(days=2))

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['outcomes']

    assert out['finished']['count'] == 2


@pytest.mark.django_db
def test_outcomes_milestones_reuse_goals_items():
    """里程碑那一栏必须与「缺口」卡同源，不另查一次。"""
    goal = Goal.objects.create(title='目标A', user_id=1, status='in-progress')
    Milestone.objects.create(goal=goal, title='已完成A', status='completed',
                             target_date=WEEK_START + dt.timedelta(days=2))
    Milestone.objects.create(goal=goal, title='已完成B', status='completed',
                             target_date=WEEK_START + dt.timedelta(days=3))
    Milestone.objects.create(goal=goal, title='没完成', status='pending',
                             target_date=WEEK_START + dt.timedelta(days=4))

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)

    done_in_gap = [i for i in out['goals']['items'] if i['status'] == 'completed']
    assert out['outcomes']['milestones']['count'] == len(done_in_gap) == 2
    assert {i['title'] for i in out['outcomes']['milestones']['items']} == {'已完成A', '已完成B'}


@pytest.mark.django_db
def test_outcomes_truncates_but_keeps_full_count():
    """`count` 是全量、`items` 可截断 —— 前端才能说「还有 N 条」。"""
    for i in range(25):
        _sugar(f'第 {i} 件', WEEK_START + dt.timedelta(days=i % 6))

    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['outcomes']

    assert out['finished']['count'] == 25
    assert len(out['finished']['items']) == 20
    assert out['finished']['truncated'] is True


@pytest.mark.django_db
def test_outcomes_empty_period_is_flag_not_three_zeros():
    """全空 ⇒ `empty=True`（前端整卡不渲染，而不是显示三行 0）。"""
    out = services.compute_period_extras('weekly', WEEK_START, WEEK_END)['outcomes']

    assert out['empty'] is True
    assert out['works']['count'] == out['milestones']['count'] == out['finished']['count'] == 0
