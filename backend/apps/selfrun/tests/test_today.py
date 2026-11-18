"""「今天」四格 · 取数与候选（v3.64.75 / 76 / 78）—— 33 条

这一页只回答一件事：**今天走哪一格、那一格里有哪三件**。
它自己**不实现任何完成逻辑** —— 候选行的「标完成」调的是
goals / inbox / works **现有的**接口。

🔴 候选是**现算**的，所以这一组大多不走 HTTP：直接调
   `today.build_cell_payload()`（它是「一条日结 → 首屏 cell」的唯一实现，
   候选、`total`、`empty_reason`、`no_focus` 都在里面）。
   走 HTTP 只测那两件真的跟网络有关的事：首屏形状、`GET` 不写库。

🔴 这一组钉住六件最容易静默出错的事：

① **计数与候选同源** —— 格子上写「疏苗 3 件」而点开 0 件，是最典型的
   共盲区（两处各写一遍过滤条件，谁也不知道哪边漏了）。
② **风干恒可点** —— 它 `count=0` 是「这一格本来就没有清单」，不是「没有活」。
   前端若按 `count == 0` 统一置灰，风干就永远点不了；所以 `selectable` 必须
   由后端单独给。
③ **已放弃目标下的里程碑不出现** —— 目标是放弃了，它下面的里程碑却还在
   催你「逾期 6 天」，等于替一个已经结束的计划讨债。
④ **`priority` 不能直接 order_by** —— 它是 'high'/'medium'/'low' 字符串，
   字典序会排成 high → low → medium，而页面上完全看不出是排错了。
⑤ **`done.path` 不含 `/api`** —— 前端 `baseURL` 已是 `/api`，多一层前缀
   就是 `/api/api/...` 的 404，而 404 在页面上只说「失败」。
⑥ **三种空不许混** —— `quadrant=None`（没定档）/ `count=0`（真没有活）/
   `empty_reason`（为什么没有）是三件事，各自有各自的字段。
"""
import datetime as dt

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.book.models import Book
from apps.book.services import ReadingFocusService
from apps.goals.models import Goal, Milestone
from apps.inbox.models import InboxItem
from apps.selfrun import today as today_mod
from apps.selfrun.models import SelfRunDayCell
from apps.works.models import Work

pytestmark = pytest.mark.django_db

TODAY_URL = '/api/selfrun/today/'


@pytest.fixture
def client():
    return APIClient()


def today() -> dt.date:
    return timezone.localdate()


def make_goal(title='目标A', status='in-progress'):
    return Goal.objects.create(title=title, user_id=1, status=status)


def make_milestone(goal, title, *, status='pending', target_date=None, order_num=0):
    return Milestone.objects.create(
        goal=goal, title=title, status=status,
        target_date=target_date, order_num=order_num,
    )


def make_book(title='起床后的黄金1小时', status='reading'):
    return Book.objects.create(
        years='2026', btitle=title, author='池田千惠',
        btype='认知提升类', status=status, reading_depth=3, recommend=3,
    )


def pool_of(quadrant):
    """某一格的候选（不落库、不经 HTTP）。

    🔴 用生产代码 `build_cell_payload()` 而不是在这里重算一遍 ——
       测试里另写一份「no_focus 怎么判」就等于把被测逻辑抄进断言，
       抄错的时候两边一起错，用例照样绿。
    """
    stub = SelfRunDayCell(cell_date=today(), quadrant=quadrant)
    return today_mod.build_cell_payload(stub, today=today())


def _quad(payload, key):
    return next(q for q in payload['quadrants'] if q['quadrant'] == key)


# ══════════════════════════════════════════════════════════════
# 首屏形状
# ══════════════════════════════════════════════════════════════

def test_today_shape(client):
    """首屏该有的都在；没定档时 `cell` 为 null。"""
    r = client.get(TODAY_URL)
    assert r.status_code == 200
    body = r.json()

    assert body['date'] == today().isoformat()
    assert body['weekday'] in ('周一', '周二', '周三', '周四', '周五', '周六', '周日')
    assert body['cell'] is None
    assert [q['quadrant'] for q in body['quadrants']] == ['sow', 'reap', 'tend', 'rest']
    for q in body['quadrants']:
        assert q['label'] and q['color'].startswith('#')
        assert isinstance(q['count'], int)
        assert isinstance(q['selectable'], bool)
    # 周色带恒 7 格；`quadrant=None` 是「那天没定档」，不是「没做成」
    assert len(body['week']) == 7
    assert all(d['quadrant'] is None for d in body['week'])
    assert body['week'][-1]['date'] == today().isoformat()


def test_rest_selectable_even_when_count_zero(client):
    """② 风干 `count=0` 但必须可点 —— 它不是「没有活」，是「本来就没有清单」。"""
    payload = client.get(TODAY_URL).json()
    rest = _quad(payload, 'rest')
    assert rest['count'] == 0
    assert rest['has_candidates'] is False
    assert rest['selectable'] is True


def test_no_candidate_quadrant_is_greyed(client):
    """没活的那三格不可点；风干是唯一的例外（上一条已钉）。"""
    payload = client.get(TODAY_URL).json()
    for key in ('sow', 'reap', 'tend'):
        assert _quad(payload, key)['selectable'] is False


def test_all_empty_reason(client):
    """四格全空时给总口径，前端不必自己把四格再判一遍。"""
    payload = client.get(TODAY_URL).json()
    assert payload['empty_reason'] == 'all_empty'


def test_empty_reason_is_null_when_something_to_do(client):
    make_milestone(make_goal(), '写完设计稿')
    assert client.get(TODAY_URL).json()['empty_reason'] is None


# ══════════════════════════════════════════════════════════════
# 风干
# ══════════════════════════════════════════════════════════════

def test_rest_has_no_list_and_no_reason_code(client):
    """风干：没有清单，也**不许**报 `no_candidates`。

    给它 `no_candidates`，页面就会在一格叫「今天不排活」的卡里写
    「这一类没有排着的活」—— 自相矛盾，而且改都改不掉。
    """
    body = pool_of('rest')
    assert body['candidates'] == []
    assert body['total'] == 0
    assert body['empty_reason'] is None
    assert body['no_focus'] is False


def test_rest_label_comes_from_backend(client):
    """标签只在一处定义（`constants.py`），前端不拼。"""
    SelfRunDayCell.objects.create(cell_date=today(), quadrant='rest')
    assert client.get(TODAY_URL).json()['cell']['quadrant_label'] == '风干'


# ══════════════════════════════════════════════════════════════
# 播种
# ══════════════════════════════════════════════════════════════

def test_sow_without_focus_says_no_focus(client):
    """没有「当前这本」且这一格空 ⇒ 理由码是 no_focus（并给出去书库的出口）。"""
    body = pool_of('sow')
    assert body['candidates'] == []
    assert body['empty_reason'] == 'no_focus'


def test_sow_without_focus_still_lists_milestones(client):
    """没书不等于这一格空 —— 无期限的长期里程碑照常出现。"""
    goal = make_goal('三年赎回期')
    make_milestone(goal, '写完今日四格的设计稿', order_num=1)

    body = pool_of('sow')
    assert body['empty_reason'] is None
    assert [c['kind'] for c in body['candidates']] == ['milestone']
    assert body['candidates'][0]['subtitle'] == '三年赎回期 · 第 1 个里程碑'


def test_sow_book_is_first_and_carries_day_count(client):
    """当前这本固定第 1 条，「第 N 天」与书页横条同源（`days_on`）。"""
    book = make_book()
    ReadingFocusService.switch(book, today=today() - dt.timedelta(days=3))
    make_milestone(make_goal(), '没有日期的活', order_num=1)

    body = pool_of('sow')
    first = body['candidates'][0]
    assert first['kind'] == 'book'
    assert first['title'] == book.btitle
    assert first['reason'] == '当前这本，第 4 天'
    # 书没有 done：读完由换书动作触发，不在候选行里做
    assert first['done'] is None
    assert first['open_route'] == '/books'


def test_sow_caps_at_three_including_book(client):
    """书占 1 格 ⇒ 里程碑只再给 2 条（`limit=3` 是总数，不是「每类各 3」）。"""
    ReadingFocusService.switch(make_book(), today=today())
    goal = make_goal()
    for i in range(5):
        make_milestone(goal, f'长期活{i}', order_num=i + 1)

    body = pool_of('sow')
    assert len(body['candidates']) == 3
    assert [c['kind'] for c in body['candidates']] == ['book', 'milestone', 'milestone']
    # 但 `total` 报的是全量（点开后才显示「手上还有 N 件」）
    assert body['total'] == 6


def test_abandoned_goal_milestones_never_show(client):
    """③ 已放弃/已归档目标下的里程碑不出现 —— 不替一个结束的计划讨债。"""
    make_milestone(make_goal('放弃的', status='abandoned'), '不该出现', target_date=today())
    make_milestone(make_goal('归档的', status='archived'), '也不该出现')

    assert pool_of('sow')['candidates'] == []
    assert pool_of('reap')['candidates'] == []


def test_sow_no_focus_is_reported_even_with_milestones(client):
    """有里程碑、但还没指定「当前这本」时，`no_focus` 必须单独给出来。

    🔴 这一条是真实数据逼出来的：播种格有 262 条里程碑（所以格子不为空、
       `empty_reason` 是 None），于是「还没指定当前这本」这条提示永远不出现 ——
       而播种格第一条本该就是那本书（第 1 步书闸门的全部意义）。
       两个事实都真，所以两个字段都要给。
    """
    make_milestone(make_goal(), '没有日期的活')

    body = pool_of('sow')
    assert body['empty_reason'] is None      # 格子不为空
    assert body['no_focus'] is True          # 但没有「当前这本」
    assert body['candidates'][0]['kind'] == 'milestone'


def test_sow_no_focus_is_false_once_book_is_set(client):
    ReadingFocusService.switch(make_book(), today=today())
    assert pool_of('sow')['no_focus'] is False


def test_other_quadrants_never_claim_no_focus(client):
    """书只跟播种格有关 —— 其余三格报 `no_focus=True` 是假话。"""
    for key in ('reap', 'tend', 'rest'):
        assert pool_of(key)['no_focus'] is False


# ══════════════════════════════════════════════════════════════
# 收割
# ══════════════════════════════════════════════════════════════

def test_reap_only_due_milestones(client):
    """收割只认「今天到期或已逾期」，未到期的不进来（那是播种的事）。"""
    goal = make_goal()
    make_milestone(goal, '逾期6天', target_date=today() - dt.timedelta(days=6))
    make_milestone(goal, '今天到期', target_date=today())
    make_milestone(goal, '下周的', target_date=today() + dt.timedelta(days=7))

    body = pool_of('reap')
    titles = [c['title'] for c in body['candidates']]
    assert titles == ['逾期6天', '今天到期']
    assert body['candidates'][0]['reason'] == '逾期 6 天'
    assert body['candidates'][1]['reason'] == '今天到期'


def test_reap_work_fills_the_rest(client):
    """里程碑在前，准备发的作品补足到 3 条。"""
    goal = make_goal()
    make_milestone(goal, '到期的一件', target_date=today())
    Work.objects.create(name='准备发的一篇', status='ready')
    Work.objects.create(name='还在草稿', status='private')

    body = pool_of('reap')
    assert [c['kind'] for c in body['candidates']] == ['milestone', 'work']
    assert body['candidates'][1]['reason'] == '准备发，还没发'
    # 私有的不算「能交出去」的，不进 total
    assert body['total'] == 2


# ══════════════════════════════════════════════════════════════
# 疏苗
# ══════════════════════════════════════════════════════════════

def test_tend_orders_by_priority_not_alphabetically(client):
    """④ 'high'/'medium'/'low' 的字典序是 high → low → medium，必须显式映射。"""
    InboxItem.objects.create(content='低', priority='low')
    InboxItem.objects.create(content='高', priority='high')
    InboxItem.objects.create(content='中', priority='medium')

    body = pool_of('tend')
    assert [c['title'] for c in body['candidates']] == ['高', '中', '低']


def test_tend_hesitating_says_so(client):
    InboxItem.objects.create(content='一直在想的那件', status='hesitating', priority='high')
    InboxItem.objects.create(content='普通的', status='pending', priority='low')

    body = pool_of('tend')
    first = body['candidates'][0]
    assert '一直在犹豫' in first['reason']
    assert '一直在犹豫' not in body['candidates'][1]['reason']


def test_tend_ignores_closed_items(client):
    """已处理/已归档/已废弃的不该再催你「压了 N 天」。"""
    for st in ('processed', 'done', 'archived', 'abandoned'):
        InboxItem.objects.create(content=f'已结束-{st}', status=st)
    assert pool_of('tend')['candidates'] == []


# ══════════════════════════════════════════════════════════════
# 结构约束
# ══════════════════════════════════════════════════════════════

def test_count_is_what_today_gives_not_pool_size(client):
    """① 计数与候选同源，且**格子上的数是「今天给几件」不是池子总量**。

    这条是真实数据逼出来的：无期限里程碑实际有 262 条，格子上写 262
    就等于把「426 件待办」原封不动搬回首屏 —— 而这一页存在的理由
    恰恰是别让人面对那个数。池子规模只在点开后的 `total` 里出现。
    """
    for i in range(7):
        InboxItem.objects.create(content=f'条目{i}')
    SelfRunDayCell.objects.create(cell_date=today(), quadrant='tend')

    payload = client.get(TODAY_URL).json()
    cell = payload['cell']

    assert _quad(payload, 'tend')['count'] == len(cell['candidates']) == 3
    assert cell['total'] == 7          # 池子总量仍然诚实地给，只是不在格子上


def test_done_path_is_relative_to_api_prefix(client):
    """⑤ `done.path` 不含 `/api` —— 前端 baseURL 已经是 `/api`。"""
    make_milestone(make_goal(), '一件')
    done = pool_of('sow')['candidates'][0]['done']
    assert done['method'] == 'PATCH'
    assert done['path'].startswith('/goals/')
    assert not done['path'].startswith('/api/')


def test_done_path_really_works_for_milestone(client):
    """`done` 里给的是**真实可用**的路径 —— 写错了按钮就是个 404。

    ⚠️ `done.path` 是相对 `/api` 的（前端 `request` 的 `baseURL`），
       所以这里手工补前缀 —— 这正是前端解析它的方式。
    🔴 `done.body` 只带状态，**批阅由前端收集后补上**（v3.64.84）。
       这里与 `TodayPanel.finish()` 保持同一种串法，两处一起改才叫同一条契约。
    """
    m = make_milestone(make_goal(), '一件')
    done = pool_of('sow')['candidates'][0]['done']

    r = client.patch(
        '/api' + done['path'],
        {**done['body'], 'self_review': '读完了这一章'},
        format='json',
    )
    assert r.status_code == 200
    m.refresh_from_db()
    assert m.status == 'completed'
    assert m.self_review == '读完了这一章'


def test_milestone_done_body_alone_is_rejected(client):
    """只发 `done.body`（不带批阅）⇒ 400，且库里**没有**被改成完成。

    钉两件事：
      ① `done.body` 不是一个完整的请求 —— 前端必须先问一句；
      ② 不会半写 —— 先写状态再报错的话，这里会看到 `completed`。
    """
    m = make_milestone(make_goal(), '一件')
    done = pool_of('sow')['candidates'][0]['done']

    r = client.patch('/api' + done['path'], done['body'], format='json')

    assert r.status_code == 400
    assert 'self_review' in r.json()
    m.refresh_from_db()
    assert m.status == 'pending'


def test_done_path_really_works_for_inbox(client):
    item = InboxItem.objects.create(content='一件待办')
    done = pool_of('tend')['candidates'][0]['done']

    r = client.post('/api' + done['path'], done['body'], format='json')
    assert r.status_code == 200
    item.refresh_from_db()
    assert item.status == 'done'


def test_get_never_writes(client):
    """⑥ `GET` 不写库：调 5 次不该出现任何 INSERT / UPDATE / DELETE。"""
    make_milestone(make_goal(), '一件', target_date=today())
    InboxItem.objects.create(content='一件')

    with CaptureQueriesContext(connection) as ctx:
        for _ in range(5):
            client.get(TODAY_URL)

    writes = [
        q['sql'] for q in ctx.captured_queries
        if q['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))
    ]
    assert writes == []


# ══════════════════════════════════════════════════════════════
# 补记入口（v3.64.78）
# ══════════════════════════════════════════════════════════════

_WEEKDAY = ('周一', '周二', '周三', '周四', '周五', '周六', '周日')


def test_backfill_lists_empty_days_newest_first(client):
    """空库 → 最近 7 天全在，**最近的一天排在前面**；今天不在。"""
    body = client.get(TODAY_URL).json()
    dates = [d['date'] for d in body['backfill']['days']]
    expected = [(today() - dt.timedelta(days=i)).isoformat() for i in range(1, 8)]
    assert dates == expected
    assert body['backfill']['limit'] == 7


def test_backfill_items_carry_weekday_and_no_count(client):
    """🔴 列表项只有「日期 + 周几」，**不许带 count**。

    格子上的 `count` 是「**今天**这一格给几件」。把它摆进「补 3 天前」的
    对话框里，就是拿今天的池子冒充那天的池子 —— 而且看起来毫无破绽，
    因为两个数字都合法。
    """
    make_milestone(make_goal(), '一件今天该做的事', target_date=today())
    day = client.get(TODAY_URL).json()['backfill']['days'][0]
    assert set(day) == {'date', 'weekday'}
    assert day['weekday'] in _WEEKDAY


def test_backfill_today_is_never_in_the_list(client):
    """今天没定档时，今天**也**不在补记列表里：那四格就是今天的入口。

    同一件事给两个入口，早晚出现「在补记里把今天定了」这种记法，
    而它和正常定档走的是同一个 POST，事后分不出来。
    """
    body = client.get(TODAY_URL).json()
    assert body['cell'] is None
    assert all(d['date'] != body['date'] for d in body['backfill']['days'])


def test_backfill_skips_days_already_marked(client):
    """已有格子的那天从入口里消失 —— 入口与实际可补范围同源，不各算一遍。"""
    marked = today() - dt.timedelta(days=3)
    SelfRunDayCell.objects.create(cell_date=marked, quadrant='tend', is_backfilled=True)

    dates = [d['date'] for d in client.get(TODAY_URL).json()['backfill']['days']]
    assert marked.isoformat() not in dates
    assert len(dates) == 6


def test_backfill_window_is_seven_days_inclusive(client):
    """窗口是 `今-7 … 昨`，与色带 `今-6 … 今` **错开一天**。

    用色带去推补记列表（省一次查询）会让第 7 天永远补不了，
    而它恰好在窗口里、且从界面上看不出是被谁挡住的。
    """
    d7 = today() - dt.timedelta(days=7)
    d8 = today() - dt.timedelta(days=8)
    SelfRunDayCell.objects.create(cell_date=d8, quadrant='reap', is_backfilled=True)

    dates = [d['date'] for d in client.get(TODAY_URL).json()['backfill']['days']]
    assert d7.isoformat() in dates     # 第 7 天在窗口里
    assert len(dates) == 7             # 8 天前那条既不进列表、也不占位


def test_backfill_shrinks_after_writing_a_day(client):
    """补记一天 → 它从入口里消失（入口跟着表走，不是一次性下发就定死）。"""
    target = today() - dt.timedelta(days=2)
    r = client.post(
        '/api/selfrun/day-cells/',
        {'cell_date': target.isoformat(), 'quadrant': 'tend'}, format='json',
    )
    assert r.status_code == 201
    assert r.json()['cell']['is_backfilled'] is True

    dates = [d['date'] for d in client.get(TODAY_URL).json()['backfill']['days']]
    assert target.isoformat() not in dates


def test_backfill_then_settle_prompt_asks_about_it(client):
    """补记只问「走了哪一格」；「成了吗」由结算条接着问。

    一个入口只问一件事 —— 对话框里再塞一组「成了/没成」，
    就成了两张表单叠在一起，而第二张问的还是三天前的事。
    """
    target = today() - dt.timedelta(days=2)
    client.post(
        '/api/selfrun/day-cells/',
        {'cell_date': target.isoformat(), 'quadrant': 'reap'}, format='json',
    )

    prompt = client.get(TODAY_URL).json()['settle_prompt']
    assert prompt is not None
    assert prompt['date'] == target.isoformat()
    assert prompt['days_ago'] == 2


def test_backfill_rest_is_legal_and_not_chased(client):
    """补记「风干」合法，且**不会**被追着问成没成 —— 休了就是休了。"""
    target = today() - dt.timedelta(days=1)
    r = client.post(
        '/api/selfrun/day-cells/',
        {'cell_date': target.isoformat(), 'quadrant': 'rest'}, format='json',
    )
    assert r.status_code == 201

    body = client.get(TODAY_URL).json()
    assert body['settle_prompt'] is None
    assert target.isoformat() not in [d['date'] for d in body['backfill']['days']]

