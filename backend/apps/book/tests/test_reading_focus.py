"""阅读 · 一本书闸门（`book_reading_focus`）—— 26 条

这个功能只解决一件事：**「现在读哪本」必须有唯一答案**。

之前的状态词把「读法」也算成「在推进」（精读 / 通读 / 消遣 全算开着），
于是每天早上都要重新从一堆书里挑一本，挑的还总是同一批 —— 选择这件事
本身把「开始读」消耗掉了。闸门把并行压成串行：全库只有一行指针。

🔴 这一组钉住五件最容易静默出错的事：

① **表里永远只有一行** —— 直接 `objects.create()` 就能造出第二行，
   于是「现在读哪本」有两个答案，页面再也不一致。断言：连续换书两次仍 1 行。
② **换书必须先给旧书结论** —— 不给就 400。悄悄切走等于让一本读了半年的书
   无声消失（它既没完成、也没弃读、也没回待读池）。
③ **弃读必须写原因** —— 与单本编辑同口径（`BookCreateUpdateSerializer`）。
   空原因写进库，就是一条「为什么弃」的假话。
④ **无旧书时传 `close_mode` 要报错** —— 忽略它等于「用户以为点完了，
   其实什么也没发生」。
⑤ **切到自己要被拒** —— 放行的话会先给自己写结论（比如「已读完」）
   再把自己设成在读，一次点击把书的状态改坏。

⑥ **候选只含「还能读」的书**（v3.64.81）—— 已读完 / 弃读不进下拉，
   当前这本也不进。原先候选集是「整张书单截 20 条」，93 本「已读完」
   躺在「接下来读哪本」里，看着像随时可以再读一遍。

另有一条只读约束：`GET` 不写库（不 `get_or_create`）。
"""
import datetime as dt

import pytest
from rest_framework.test import APIClient

from apps.book.models import Book, ReadingFocus
from apps.book.services import ReadingFocusService

pytestmark = pytest.mark.django_db

FOCUS_URL = '/api/books/reading-focus/'
SWITCH_URL = '/api/books/reading-focus/switch/'
CANDIDATES_URL = '/api/books/reading-focus/candidates/'


@pytest.fixture
def client():
    return APIClient()


def make_book(title, status='to_read', **kwargs):
    # `setdefault` 而不是写死 `author='某人'`：搜索口径要测「按作者搜」，
    # 写死关键字参数会让 `make_book(..., author='苏轼')` 当场 TypeError。
    kwargs.setdefault('author', '某人')
    return Book.objects.create(
        years='2026', btitle=title, btype='认知提升类',
        status=status, reading_depth=3, recommend=3, **kwargs,
    )


def switch(client, book, close_mode=None, reason=''):
    payload = {'book_id': book.bid}
    if close_mode is not None:
        payload['close_mode'] = close_mode
    if reason:
        payload['reason'] = reason
    return client.post(SWITCH_URL, payload, format='json')


def today():
    from django.utils import timezone
    return timezone.localdate()


# ══════════════════════════════════════════════════════════════
# 一、读：没有指针 / 有指针
# ══════════════════════════════════════════════════════════════

def test_no_focus_returns_three_nulls(client):
    """没有指针时三个字段同时为 null —— 不许出现「有书但没有天数」。"""
    r = client.get(FOCUS_URL)
    assert r.status_code == 200
    assert r.data['book'] is None
    assert r.data['started_on'] is None
    assert r.data['days'] is None


def test_get_does_not_create_row(client):
    """只读接口不写库：调 5 次后表里仍是 0 行。"""
    for _ in range(5):
        assert client.get(FOCUS_URL).status_code == 200
    assert ReadingFocus.objects.count() == 0


def test_focus_days_start_from_one(client):
    """开始当天算第 1 天，不是第 0 天。"""
    book = make_book('书一')
    switch(client, book)

    r = client.get(FOCUS_URL)
    assert r.data['book']['bid'] == book.bid
    assert r.data['started_on'] == today().isoformat()
    assert r.data['days'] == 1


def test_focus_days_counts_calendar_days(client):
    """放到 3 天前开始 ⇒ 第 4 天。"""
    book = make_book('书一')
    switch(client, book)
    ReadingFocus.objects.filter(pk=1).update(started_on=today() - dt.timedelta(days=3))

    assert client.get(FOCUS_URL).data['days'] == 4


def test_focus_book_deleted_pointer_becomes_null(client):
    """书被删时指针自动失效（SET_NULL），不该让删书操作 500。"""
    book = make_book('书一')
    switch(client, book)
    book.delete()

    r = client.get(FOCUS_URL)
    assert r.status_code == 200
    assert r.data['book'] is None
    assert r.data['days'] is None


# ══════════════════════════════════════════════════════════════
# 二、第一次指定（没有旧书）
# ══════════════════════════════════════════════════════════════

def test_first_switch_needs_no_close_mode(client):
    """第一次指定不需要 close_mode。"""
    book = make_book('书一')
    r = switch(client, book)

    assert r.status_code == 200
    assert r.data['book']['bid'] == book.bid
    assert r.data['written']['book_reading_focus'] == 1
    # 待读 → 在读
    book.refresh_from_db()
    assert book.status == 'reading'


def test_first_switch_with_close_mode_is_rejected(client):
    """没有旧书却传了结论 ⇒ 400。静默忽略 = 用户以为关掉了一本书。"""
    book = make_book('书一')
    r = switch(client, book, close_mode='finished')

    assert r.status_code == 400
    assert r.data['code'] == 'no_current_book'
    assert ReadingFocus.objects.count() == 0


def test_new_book_other_status_is_kept(client):
    """新书已经是「二刷」就保持「二刷」—— 被选中不等于被降级（降级会抹掉第几遍）。"""
    book = make_book('书一', status='rereading')
    assert switch(client, book).status_code == 200

    book.refresh_from_db()
    assert book.status == 'rereading'


def test_switch_to_missing_book_404(client):
    r = client.post(SWITCH_URL, {'book_id': 999999}, format='json')
    assert r.status_code == 404
    assert r.data['code'] == 'book_not_found'


# ══════════════════════════════════════════════════════════════
# 三、换书：三种结论
# ══════════════════════════════════════════════════════════════

def test_switch_twice_keeps_one_row(client):
    """连续换书两次：表里仍 1 行，指针指向第二本。"""
    first = make_book('书一', status='reading')
    second = make_book('书二', status='reading')

    switch(client, first)
    switch(client, second, close_mode='later')

    assert ReadingFocus.objects.count() == 1
    assert ReadingFocus.objects.get(pk=1).book_id == second.bid


def test_close_finished_sets_status_and_read_date(client):
    old = make_book('书一', status='reading')
    new = make_book('书二')

    switch(client, old)
    r = switch(client, new, close_mode='finished')

    assert r.status_code == 200
    old.refresh_from_db()
    assert old.status == 'finished'
    assert old.readDate == today()
    assert r.data['written']['book_read_list'] == 2   # 旧书结案 + 新书升「在读」


def test_close_finished_on_already_finished_keeps_read_date(client):
    """已经「已读完」的书再点一次「读完」：**不许把完成日期改成今天**。

    真实路径：书页编辑弹窗先把状态改成「已读完」，之后再换书 → 走的正是这里。
    """
    older = today() - dt.timedelta(days=30)
    old = make_book('书一', status='finished', readDate=older)
    new = make_book('书二', status='reading')

    switch(client, old)
    r = switch(client, new, close_mode='finished')

    assert r.status_code == 200
    old.refresh_from_db()
    assert old.status == 'finished'
    assert old.readDate == older
    # 一个字都没写 ⇒ 不能报「改了 1 行」
    assert r.data['written']['book_read_list'] == 0


def test_close_abandoned_requires_reason(client):
    old = make_book('书一', status='reading')
    new = make_book('书二')

    switch(client, old)
    r = switch(client, new, close_mode='abandoned')

    assert r.status_code == 400
    assert r.data['code'] == 'reason_required'
    old.refresh_from_db()
    assert old.status == 'reading'                  # 没写原因 ⇒ 一个字也没改
    assert ReadingFocus.objects.get(pk=1).book_id == old.bid


def test_close_abandoned_writes_reason(client):
    old = make_book('书一', status='reading')
    new = make_book('书二')

    switch(client, old)
    r = switch(client, new, close_mode='abandoned', reason='  读不下去  ')

    assert r.status_code == 200
    old.refresh_from_db()
    assert old.status == 'abandoned'
    assert old.abandon_reason == '读不下去'       # 去首尾空白，不写空格进库


def test_close_later_keeps_abandon_reason(client):
    """「先放回」只改状态，之前写过的弃读原因原样保留。"""
    old = make_book('书一', status='reading', abandon_reason='之前想弃，后来又读了')
    new = make_book('书二')

    switch(client, old)
    r = switch(client, new, close_mode='later')

    assert r.status_code == 200
    old.refresh_from_db()
    assert old.status == 'to_read'
    assert old.abandon_reason == '之前想弃，后来又读了'


def test_close_mode_required_when_old_book_exists(client):
    old = make_book('书一', status='reading')
    new = make_book('书二')

    switch(client, old)
    r = switch(client, new)

    assert r.status_code == 400
    assert r.data['code'] == 'close_mode_required'
    assert ReadingFocus.objects.get(pk=1).book_id == old.bid


def test_switch_to_same_book_is_rejected(client):
    """切到自己：拒绝，且不能顺手把自己的状态改成「已读完」。"""
    book = make_book('书一', status='reading')
    switch(client, book)

    r = switch(client, book, close_mode='finished')

    assert r.status_code == 400
    assert r.data['code'] == 'same_book'
    book.refresh_from_db()
    assert book.status == 'reading'
    assert book.readDate is None


def test_bad_close_mode_is_rejected_by_serializer(client):
    old = make_book('书一', status='reading')
    new = make_book('书二')
    switch(client, old)

    r = client.post(
        SWITCH_URL, {'book_id': new.bid, 'close_mode': 'whatever'}, format='json',
    )
    assert r.status_code == 400
    assert 'close_mode' in r.data
    assert ReadingFocus.objects.get(pk=1).book_id == old.bid


# ══════════════════════════════════════════════════════════════
# 六、换书的候选（v3.64.81）—— 只给「还能读」的书
# ══════════════════════════════════════════════════════════════

def test_candidates_exclude_finished_and_abandoned(client):
    """已读完 / 弃读**不在**候选里。

    用户报的就是这条：93 本「已读完」躺在「接下来读哪本」的下拉里。
    成因是候选集原来是「整张书单按更新时间截 20 条」—— 一个没写过滤的列表。
    """
    for title, status in [
        ('待读的', 'to_read'), ('在读的', 'reading'),
        ('二刷的', 'rereading'), ('搁置的', 'shelved'),
    ]:
        make_book(title, status=status)
    make_book('读完的', status='finished')
    make_book('弃掉的', status='abandoned')

    r = client.get(CANDIDATES_URL)

    assert r.status_code == 200
    titles = {b['btitle'] for b in r.data['results']}
    assert titles == {'待读的', '在读的', '二刷的', '搁置的'}


def test_candidates_exclude_current_focus(client):
    """当前这本不在候选里 —— 换书弹窗里选「正在读的这本」是被后端拒掉的（400），
    摆在下拉里就是让人点一个必然失败的选项。"""
    current = make_book('当前这本', status='reading')
    other = make_book('另一本')
    assert switch(client, current).status_code == 200

    r = client.get(CANDIDATES_URL)

    bids = [b['bid'] for b in r.data['results']]
    assert bids == [other.bid]


def test_candidates_search_matches_title_and_author(client):
    """搜索口径 = 书名 + 作者（下拉框写的就是「搜书名或作者」）。"""
    make_book('东坡词', author='苏轼')
    make_book('无关的书', author='别人')

    by_title = client.get(CANDIDATES_URL, {'search': '东坡'})
    by_author = client.get(CANDIDATES_URL, {'search': '苏轼'})
    none = client.get(CANDIDATES_URL, {'search': '不存在'})

    assert [b['btitle'] for b in by_title.data['results']] == ['东坡词']
    assert [b['btitle'] for b in by_author.data['results']] == ['东坡词']
    assert none.data['results'] == []


def test_candidates_search_does_not_widen_the_status_filter(client):
    """搜索**不许**把已读完的书捞回来 —— 两个条件是「且」，不是「或」。"""
    make_book('读完的东坡词', status='finished')

    r = client.get(CANDIDATES_URL, {'search': '东坡'})

    assert r.data['results'] == []


def test_candidates_count_matches_results(client):
    """`count` 与 `results` 同源：前端若拿它显示条数，不能与列表打架。"""
    make_book('书一')
    make_book('书二', status='finished')

    r = client.get(CANDIDATES_URL)

    assert r.data['count'] == len(r.data['results']) == 1


def test_candidates_carry_status_display(client):
    """候选要带 `status_display` —— 下拉里那一行写的是「作者 · 状态」，
    缺这个键会静默显示成「—」。"""
    make_book('书一', status='shelved')

    row = client.get(CANDIDATES_URL).data['results'][0]

    assert row['status'] == 'shelved'
    assert row['status_display'] == '搁置'


def test_candidates_are_capped(client):
    """条数上限 = `ReadingFocusService.CANDIDATE_LIMIT`（不写死 20）。

    ⚠️ 这里断言「等于上限」是安全的：25 本全部可读，必然被截。
       但数字要读常量 —— 写成 20 的话，将来调上限会红在一条与它无关的用例上。
    """
    for i in range(25):
        make_book(f'书{i:02d}')

    r = client.get(CANDIDATES_URL)

    assert len(r.data['results']) == ReadingFocusService.CANDIDATE_LIMIT


def test_switch_shelved_book_promotes_to_reading(client):
    """搁置的书被选中 ⇒ 升成「在读」。

    搁置的定义是「暂停但没弃、能捡回来」，而捡回来的动作就是换书。
    留在「搁置」里的话，页头写「现在读这本」、列表标签写「搁置」，同一行书两个说法。
    """
    book = make_book('搁置的', status='shelved')
    assert switch(client, book).status_code == 200

    book.refresh_from_db()
    assert book.status == 'reading'
