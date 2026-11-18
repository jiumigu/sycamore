"""日结（「今天」四格）· 定档 / 改档 / 结算 —— 20 条

这一组钉住的是**写入口的边界**，不是界面长什么样：

① **一天一格** —— 同日重复 POST 是 409、不是幂等覆盖。
   覆盖会让「今天改过没有」无痕，而这一天只有一格，改没改过就是全部信息。
② **改档只准当天** —— 跨天 `locked`。昨天定了就定了，这是这个功能
   唯一真正约束人的地方；放松它，四格就退化成「随手改的记录」。
③ **风干不结算** —— 传 `outcome` 是 400，不落 `na` 值；
   反过来，改成风干时要**清掉**先前结的 `done/missed`，
   否则周色带会显示「风干 · 成了」。
④ **补记窗口 7 天、结算窗口 7 天，都是后端给的数** —— 前端 0 个阈值。
⑤ **`GET` 不写库** —— 本项目铁律，只读接口别 `get_or_create`。
"""
import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.selfrun.models import SelfRunDayCell

pytestmark = pytest.mark.django_db

TODAY_URL = '/api/selfrun/today/'
CELLS_URL = '/api/selfrun/day-cells/'


@pytest.fixture
def client():
    return APIClient()


def today() -> dt.date:
    return timezone.localdate()


def days_ago(n: int) -> dt.date:
    return today() - dt.timedelta(days=n)


def set_cell(quadrant='sow', *, day=None, outcome='', note=''):
    """直接落一行（模拟「那天已经定过档」）。"""
    return SelfRunDayCell.objects.create(
        cell_date=day or today(), quadrant=quadrant, outcome=outcome, note=note,
    )


def post_cell(client, quadrant='sow', *, day=None, note=None):
    """POST 一条定档（入参形状集中在这里，改口径只改一处）。"""
    body = {'quadrant': quadrant}
    if day is not None:
        body['cell_date'] = day.isoformat()
    if note is not None:
        body['note'] = note
    return client.post(CELLS_URL, body, format='json')


# ══════════════════════════════════════════════════════════════
# 定档
# ══════════════════════════════════════════════════════════════

def test_define_today(client):
    """不传 `cell_date` 就是今天，且 `is_backfilled=False`。"""
    r = post_cell(client, 'tend')
    assert r.status_code == 201
    body = r.json()
    assert body['cell']['cell_date'] == today().isoformat()
    assert body['cell']['quadrant'] == 'tend'
    assert body['cell']['quadrant_label'] == '疏苗'
    assert body['cell']['outcome'] == ''           # '' = 还没结算
    assert body['cell']['is_backfilled'] is False
    assert body['written'] == {'selfrun_day_cell': 1}


def test_same_day_twice_is_409_not_silent_overwrite(client):
    """① 同日重复 POST → 409，表里仍 1 行，且带上已存在的 `cell_id`。"""
    first = post_cell(client, 'sow').json()['cell']

    r = post_cell(client, 'reap')
    assert r.status_code == 409
    body = r.json()
    assert body['code'] == 'already_set'
    assert body['cell_id'] == first['id']
    assert SelfRunDayCell.objects.count() == 1
    # 原值没被改掉
    assert SelfRunDayCell.objects.get().quadrant == 'sow'


def test_backfill_three_days_ago_marks_itself(client):
    """② 补记 3 天前 → 201，且自动标 `is_backfilled`（由日期差算，不由入参）。"""
    r = post_cell(client, 'reap', day=days_ago(3))
    assert r.status_code == 201
    assert r.json()['cell']['is_backfilled'] is True


def test_backfill_too_late_is_400(client):
    """② 补记 8 天前 → 400 `too_late`（7 是边界，8 就出了窗口）。"""
    r = post_cell(client, 'reap', day=days_ago(8))
    assert r.status_code == 400
    assert r.json()['code'] == 'too_late'
    assert SelfRunDayCell.objects.count() == 0


def test_backfill_window_boundary_is_inclusive(client):
    """第 7 天仍可补 —— 边界不许写成 `<`（那样第 7 天会莫名其妙被拒）。"""
    assert post_cell(client, 'reap', day=days_ago(7)).status_code == 201


def test_future_day_is_rejected(client):
    """不给未来定档：那是给自己排班，不是记录今天走哪一格。"""
    r = post_cell(client, 'sow', day=today() + dt.timedelta(days=1))
    assert r.status_code == 400
    assert r.json()['code'] == 'future_date'


def test_bad_quadrant_is_400(client):
    """不认识的格子报 400 —— 静默落一行 `grow` 会让四格的统计凭空多一格。"""
    r = post_cell(client, 'grow')
    assert r.status_code == 400
    assert SelfRunDayCell.objects.count() == 0


# ══════════════════════════════════════════════════════════════
# 改档
# ══════════════════════════════════════════════════════════════

def test_change_quadrant_today_keeps_outcome(client):
    """当天改档 → 200，且**不动已有结算**（结算说的是「那天成了没有」，与格无关）。"""
    cell = set_cell('sow', outcome='done')

    r = client.patch(f'{CELLS_URL}{cell.pk}/', {'quadrant': 'tend'}, format='json')
    assert r.status_code == 200
    assert r.json()['changed'] == ['quadrant']
    cell.refresh_from_db()
    assert cell.quadrant == 'tend'
    assert cell.outcome == 'done'


def test_change_quadrant_cross_day_is_locked(client):
    """③ 跨天改档 → 400 `locked`。昨天定了就定了。"""
    cell = set_cell('sow', day=days_ago(1))

    r = client.patch(f'{CELLS_URL}{cell.pk}/', {'quadrant': 'rest'}, format='json')
    assert r.status_code == 400
    assert r.json()['code'] == 'locked'
    cell.refresh_from_db()
    assert cell.quadrant == 'sow'


def test_switch_to_rest_clears_outcome(client):
    """③ 改成风干时清掉结算 —— 否则色带上会出现「风干 · 成了」。"""
    cell = set_cell('sow', outcome='done')

    r = client.patch(f'{CELLS_URL}{cell.pk}/', {'quadrant': 'rest'}, format='json')
    assert r.status_code == 200
    assert set(r.json()['changed']) == {'quadrant', 'outcome'}
    cell.refresh_from_db()
    assert cell.outcome == ''


def test_patch_nothing_is_400(client):
    cell = set_cell('sow')
    r = client.patch(f'{CELLS_URL}{cell.pk}/', {}, format='json')
    assert r.status_code == 400
    assert r.json()['code'] == 'empty_patch'


def test_patch_same_value_writes_nothing(client):
    """没变就不写 —— `written` 只列真的写了的表（0 行不出现）。"""
    cell = set_cell('sow')
    r = client.patch(f'{CELLS_URL}{cell.pk}/', {'quadrant': 'sow'}, format='json')
    assert r.status_code == 200
    assert r.json()['changed'] == []
    assert r.json()['written'] == {}


def test_patch_missing_cell_is_404(client):
    r = client.patch(f'{CELLS_URL}999999/', {'quadrant': 'reap'}, format='json')
    assert r.status_code == 404


# ══════════════════════════════════════════════════════════════
# 结算
# ══════════════════════════════════════════════════════════════

def test_settle_yesterday(client):
    cell = set_cell('sow', day=days_ago(1))
    r = client.patch(f'{CELLS_URL}{cell.pk}/', {'outcome': 'missed'}, format='json')
    assert r.status_code == 200
    assert r.json()['cell']['outcome'] == 'missed'
    assert r.json()['cell']['outcome_label'] == '没成'


def test_settle_window_seven_days_ok_eight_days_no(client):
    """④ 结算窗口与补记同宽：第 7 天能结，第 8 天不能。"""
    ok = set_cell('sow', day=days_ago(7))
    assert client.patch(f'{CELLS_URL}{ok.pk}/', {'outcome': 'done'}, format='json').status_code == 200

    late = set_cell('reap', day=days_ago(8))
    r = client.patch(f'{CELLS_URL}{late.pk}/', {'outcome': 'done'}, format='json')
    assert r.status_code == 400
    assert r.json()['code'] == 'too_late'


def test_rest_cell_cannot_be_settled(client):
    """③ 风干不结算 —— 休了就是休了，没有「成没成」。"""
    cell = set_cell('rest', day=days_ago(1))
    r = client.patch(f'{CELLS_URL}{cell.pk}/', {'outcome': 'done'}, format='json')
    assert r.status_code == 400
    assert r.json()['code'] == 'rest_not_settled'
    cell.refresh_from_db()
    assert cell.outcome == ''


def test_change_to_rest_and_settle_in_one_request_is_rejected(client):
    """同时传「改成风干 + 成了」→ 400，**别按旧象限放行**。

    顺序错的话会先写 outcome，然后 quadrant=rest，库里留下一行自相矛盾的记录。
    """
    cell = set_cell('sow')
    r = client.patch(
        f'{CELLS_URL}{cell.pk}/', {'quadrant': 'rest', 'outcome': 'done'}, format='json',
    )
    assert r.status_code == 400
    assert r.json()['code'] == 'rest_not_settled'
    cell.refresh_from_db()
    assert (cell.quadrant, cell.outcome) == ('sow', '')   # 整个请求没写进去


# ══════════════════════════════════════════════════════════════
# 首屏接上日结
# ══════════════════════════════════════════════════════════════

def test_today_carries_cell_with_candidates(client):
    """定档之后首屏就带 `cell`（含那一格的候选），不必再请求一次。"""
    from apps.inbox.models import InboxItem

    InboxItem.objects.create(content='一件待办')
    set_cell('tend')

    payload = client.get(TODAY_URL).json()
    cell = payload['cell']
    assert cell['quadrant'] == 'tend'
    assert [c['title'] for c in cell['candidates']] == ['一件待办']
    assert cell['total'] == 1
    # 四格照旧要给：其余三格缩成一行小字，靠的就是这些数
    assert len(payload['quadrants']) == 4


def test_today_without_cell_is_null(client):
    assert client.get(TODAY_URL).json()['cell'] is None


def test_settle_prompt_points_at_yesterday(client):
    """昨天定了、没结算 → 首屏给一条提示，`days_ago=1`。"""
    cell = set_cell('sow', day=days_ago(1))
    prompt = client.get(TODAY_URL).json()['settle_prompt']
    assert prompt['cell_id'] == cell.pk
    assert prompt['quadrant_label'] == '播种'
    assert prompt['days_ago'] == 1


def test_settle_prompt_disappears_after_settling(client):
    cell = set_cell('sow', day=days_ago(1))
    client.patch(f'{CELLS_URL}{cell.pk}/', {'outcome': 'done'}, format='json')
    assert client.get(TODAY_URL).json()['settle_prompt'] is None


def test_settle_prompt_skips_rest_cells(client):
    """⑤ 风干不问「成没成」—— 它不能占住那条唯一的提示位。"""
    set_cell('rest', day=days_ago(1))
    assert client.get(TODAY_URL).json()['settle_prompt'] is None


def test_settle_prompt_does_not_look_only_at_yesterday(client):
    """昨天没定档、前天定了没结算 → 仍然要提示前天（否则那格永远结不掉）。"""
    cell = set_cell('reap', day=days_ago(2))
    prompt = client.get(TODAY_URL).json()['settle_prompt']
    assert prompt['cell_id'] == cell.pk
    assert prompt['days_ago'] == 2


def test_settle_prompt_ignores_cells_past_the_window(client):
    """超过 7 天未结算：不再提示，色带上永久「未结算」（不是「没成」）。"""
    set_cell('sow', day=days_ago(8))
    assert client.get(TODAY_URL).json()['settle_prompt'] is None


# ══════════════════════════════════════════════════════════════
# 周色带
# ══════════════════════════════════════════════════════════════

def test_week_is_always_seven_and_fills_gaps_with_null(client):
    """9. 恒 7 条，缺的日子 `quadrant=None`（那天没定档，**不是**没做成）。"""
    set_cell('sow', day=today())

    week = client.get(TODAY_URL).json()['week']
    assert len(week) == 7
    assert week[-1]['date'] == today().isoformat()
    assert [d['quadrant'] for d in week] == [None] * 6 + ['sow']


def test_week_shows_outcome_and_backfill(client):
    """验收那条：定档 → 结算 → 色带变色（含补记标记）。"""
    old = set_cell('reap', day=days_ago(1))
    client.patch(f'{CELLS_URL}{old.pk}/', {'outcome': 'missed'}, format='json')
    set_cell('tend', day=days_ago(2))

    week = client.get(TODAY_URL).json()['week']
    by_date = {d['date']: d for d in week}
    assert by_date[days_ago(1).isoformat()]['outcome'] == 'missed'
    assert by_date[days_ago(2).isoformat()]['quadrant'] == 'tend'
    assert by_date[days_ago(2).isoformat()]['outcome'] is None    # 未结算 ≠ 没成


def test_week_summary_counts_days_not_rows(client):
    """11. 汇总只数天数；风干不进「未结算」，也不进「没成」。"""
    done = set_cell('sow', day=days_ago(1))
    client.patch(f'{CELLS_URL}{done.pk}/', {'outcome': 'done'}, format='json')
    missed = set_cell('reap', day=days_ago(2))
    client.patch(f'{CELLS_URL}{missed.pk}/', {'outcome': 'missed'}, format='json')
    set_cell('rest', day=days_ago(3))                   # 风干：不结算，也不算欠着
    set_cell('tend', day=days_ago(4))                   # 定了没结算
    set_cell('sow', day=days_ago(30))                   # 窗口外，不该被数进来

    summary = client.get(TODAY_URL).json()['week_summary']
    assert summary == {
        'marked_days': 4,
        'settled_days': 2,
        'missed_days': 1,
        'unsettled_days': 1,
    }


def test_get_never_writes(client):
    """⑤ `GET` 不写库：定过档再连读 5 次，不出现任何 INSERT / UPDATE / DELETE。"""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    set_cell('sow', day=days_ago(1))

    with CaptureQueriesContext(connection) as ctx:
        for _ in range(5):
            client.get(TODAY_URL)

    writes = [
        q['sql'] for q in ctx.captured_queries
        if q['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))
    ]
    assert writes == []


# ══════════════════════════════════════════════════════════════
# 色带（`day-cells/week/`）—— v3.64.77
#
# 这四条钉住的是「这一格是哪天」：色带最容易错的地方不是颜色，
# 而是**区间错位一天**（于是「周三定了」显示在周二），以及
# 「没定档」被画成「没成」。
# ══════════════════════════════════════════════════════════════

WEEK_URL = '/api/selfrun/day-cells/week/'


def test_week_defaults_to_today_as_last_day(client):
    body = client.get(WEEK_URL).json()

    assert body['end'] == today().isoformat()
    assert len(body['days']) == 7
    assert body['days'][-1]['date'] == today().isoformat()
    assert body['days'][0]['date'] == days_ago(6).isoformat()


def test_week_end_moves_the_whole_window(client):
    """`end` 是**最后一天**，不是「从哪天开始」—— 差一天就整体错位。"""
    set_cell('sow', day=days_ago(10))
    set_cell('reap', day=days_ago(9))

    body = client.get(f'{WEEK_URL}?end={days_ago(9).isoformat()}').json()

    assert body['end'] == days_ago(9).isoformat()
    assert body['days'][-1]['date'] == days_ago(9).isoformat()
    assert body['days'][-1]['quadrant'] == 'reap'
    assert body['days'][-2]['quadrant'] == 'sow'
    # 今天不在这段区间里：历史周的色带不该把今天带进来
    assert today().isoformat() not in [d['date'] for d in body['days']]


def test_week_rejects_future_end(client):
    r = client.get(f'{WEEK_URL}?end={(today() + dt.timedelta(days=1)).isoformat()}')

    assert r.status_code == 400
    assert r.json()['code'] == 'future_end'


def test_week_rejects_bad_format_instead_of_falling_back(client):
    """格式错**不静默回落到今天** —— 回落会让人看着另一段时间却毫无信号。"""
    r = client.get(f'{WEEK_URL}?end=11-18')

    assert r.status_code == 400
    assert r.json()['code'] == 'bad_end'


def test_week_legend_matches_today_quadrants(client):
    """`legend` 与今日页的 `quadrants` 必须**同源**：色带在两页出现，
    各写一份词表/配色，改一处漏一处不会报错。"""
    week = client.get(WEEK_URL).json()['legend']
    quads = client.get(TODAY_URL).json()['quadrants']

    assert [(x['quadrant'], x['label'], x['color']) for x in week] == [
        (q['quadrant'], q['label'], q['color']) for q in quads
    ]


def test_week_unmarked_day_is_null_not_missed(client):
    """没定档的日子 `quadrant=None` —— 前端据此画空格，**不是**斜线。"""
    set_cell('sow', day=days_ago(1), outcome='missed')

    days = client.get(WEEK_URL).json()['days']
    by_date = {d['date']: d for d in days}

    assert by_date[days_ago(1).isoformat()]['outcome'] == 'missed'
    assert by_date[days_ago(2).isoformat()]['quadrant'] is None
    assert by_date[days_ago(2).isoformat()]['outcome'] is None
