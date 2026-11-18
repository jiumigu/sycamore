"""收件箱 · 排序与「完成时间」（v3.64.82）—— 10 条

起点是一句体感抱怨：「已完成列表的倒序，不应该按待办建立的时间，
应该按这待办完成的时间去倒序」。

它牵出两件事，各自的失败长相都是**不报错、数看着合理**：

① **排序键装错** —— 列表一直是 `-created_at`，而「已完成」这一页
   问的是「我最近完成了什么」。9 月记下、昨天才做完的那条，按创建时间
   沉在中间，用户只会觉得「顺序不对」，说不出哪里不对。
② **排序键没有落点** —— 编辑表单能把状态直接改成 `done`（走 PATCH），
   这条路径以前**不写** `processed_at`。于是「按完成时间排」这件事，
   对一部分行根本没有事实可用；写成了也只是排了个寂寞。

所以这一组同时钉住「怎么排」和「时间从哪来」：

🔴 **排序键与显示键必须是同一个**。后端按 `processed_at` 排、行上却印
   `created_at`，用户看到的就是一串没有规律的日期 —— 这比不改更糟。
   前端因此也换成了「完成于」（见 `InboxItem.vue`）。
"""
import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.inbox.models import InboxItem

pytestmark = pytest.mark.django_db

URL = '/api/inbox/items/'


def make(content, status='pending', created=None, processed=None):
    """造一条并**改写** `created_at` / `processed_at`。

    `created_at` 是 `auto_now_add`，`create()` 传不进去 ⇒ 只能建完再 `update()`。
    （顺带说明：`update()` 绕开 `auto_now`，`processed_at` 也就不会被抹。）
    """
    item = InboxItem.objects.create(content=content, status=status)
    InboxItem.objects.filter(pk=item.pk).update(
        created_at=created or timezone.now(), processed_at=processed,
    )
    item.refresh_from_db()
    return item


def ids(res):
    return [row['id'] for row in res.data['results']]


# ══════════════════════════════════════════════════════════════
# 一、排序：已完成按完成时间
# ══════════════════════════════════════════════════════════════

class TestDoneOrdering:

    def test_done_sorts_by_completion_not_creation(self):
        """三条的「创建顺序」与「完成顺序」**正好相反** —— 只有按完成时间排才对。

        用相反的顺序造，是为了让「其实还是按创建时间排」的实现当场红：
        同向数据下两种实现结果一样，那种用例等于没写。
        """
        now = timezone.now()
        old_but_late = make('九月记下、昨天才做完', 'done',
                            created=now - dt.timedelta(days=60), processed=now - dt.timedelta(days=1))
        mid = make('十月记下、前天做完', 'done',
                   created=now - dt.timedelta(days=30), processed=now - dt.timedelta(days=2))
        new_but_early = make('昨天记下、昨天就做完', 'done',
                             created=now - dt.timedelta(days=1), processed=now - dt.timedelta(days=5))

        res = APIClient().get(URL, {'status': 'done'})

        assert ids(res) == [old_but_late.id, mid.id, new_but_early.id]

    def test_done_without_completion_time_uses_recorded_time(self):
        """历史空值（早期 PATCH 改成完成、没记时间）按「记下的时间」排，不沉底。

        这是**兜底**，不是口径：`Coalesce(processed_at, created_at)`。
        断言的是它落在「按创建时间该在的位置」，而不是跑到最末尾 ——
        沉底会让一条其实是最近完成的书永远看不见。
        """
        now = timezone.now()
        done_long_ago = make('早就做完的', 'done',
                             created=now - dt.timedelta(days=90), processed=now - dt.timedelta(days=80))
        legacy = make('没有完成时间的', 'done', created=now - dt.timedelta(days=2), processed=None)

        res = APIClient().get(URL, {'status': 'done'})

        assert ids(res) == [legacy.id, done_long_ago.id]

    def test_pending_still_sorts_by_creation(self):
        """待办列表**没被顺带改掉** —— 它问的是「我最近记了什么」。"""
        now = timezone.now()
        old = make('前天记的', created=now - dt.timedelta(days=2))
        new = make('今天记的', created=now)

        res = APIClient().get(URL, {'status': 'pending'})

        assert ids(res) == [new.id, old.id]

    def test_processed_is_not_reordered(self):
        """「已处理」仍按创建时间 —— 它有 61/87 条历史空值，按完成时间排会更乱。

        这条钉的是**边界**：`done` 的口径不许顺手套到隔壁状态上。
        """
        now = timezone.now()
        created_early_converted_late = make(
            '早记下、晚转出', 'processed',
            created=now - dt.timedelta(days=10), processed=now - dt.timedelta(days=1))
        created_late_converted_early = make(
            '晚记下、早转出', 'processed',
            created=now - dt.timedelta(days=5), processed=now - dt.timedelta(days=9))

        res = APIClient().get(URL, {'status': 'processed'})

        assert ids(res) == [created_late_converted_early.id, created_early_converted_late.id]

    def test_explicit_ordering_wins(self):
        """显式 `?ordering=` 一律听调用方（排序控件/调试不能被默认值挡回去）。"""
        now = timezone.now()
        a = make('甲', 'done', created=now - dt.timedelta(days=1), processed=now - dt.timedelta(days=2))
        b = make('乙', 'done', created=now - dt.timedelta(days=2), processed=now - dt.timedelta(days=1))

        by_created = APIClient().get(URL, {'status': 'done', 'ordering': '-created_at'})
        by_created_asc = APIClient().get(URL, {'status': 'done', 'ordering': 'created_at'})

        assert ids(by_created) == [a.id, b.id]
        assert ids(by_created_asc) == [b.id, a.id]

    def test_ordering_by_processed_at_is_allowed(self):
        """`processed_at` 在 `ordering_fields` 里 —— 前端要自己排也不会 400。"""
        now = timezone.now()
        a = make('甲', 'done', processed=now - dt.timedelta(days=2))
        b = make('乙', 'done', processed=now - dt.timedelta(days=1))

        res = APIClient().get(URL, {'status': 'done', 'ordering': 'processed_at'})

        assert res.status_code == 200
        assert ids(res) == [a.id, b.id]


# ══════════════════════════════════════════════════════════════
# 二、时间从哪来：`processed_at` 跟着状态走
# ══════════════════════════════════════════════════════════════

class TestCompletionTime:

    def test_patch_status_to_done_stamps_time(self):
        """编辑表单把状态改成「已完成」⇒ 补上完成时间（这就是排序键的来源）。"""
        item = make('一条待办')
        assert item.processed_at is None

        res = APIClient().patch(f'{URL}{item.id}/', {'status': 'done'}, format='json')

        assert res.status_code == 200
        item.refresh_from_db()
        assert item.processed_at is not None
        assert res.data['processed_at'] is not None

    def test_patch_from_done_back_to_pending_clears_time(self):
        """退回待办 ⇒ 清空。一条待办带着完成时间，是「说不清它是什么意思」的字段。"""
        item = make('做完了又发现没做完', 'done', processed=timezone.now() - dt.timedelta(days=1))

        APIClient().patch(f'{URL}{item.id}/', {'status': 'pending'}, format='json')

        item.refresh_from_db()
        assert item.processed_at is None

    def test_complete_twice_keeps_first_time(self):
        """再点一次「完成」**不改**完成日期 —— 完成是既成事实。

        与「已读完不再改 `readDate`」同一条口径：二次点击不该把 9 月 30 日
        改写成今天，否则「上周完成了什么」这个问题的答案每天都在变。
        """
        first = timezone.now() - dt.timedelta(days=3)
        item = make('早就做完的', 'done', processed=first)

        APIClient().post(f'{URL}{item.id}/complete/', {}, format='json')

        item.refresh_from_db()
        assert item.processed_at == first

    def test_editing_a_legacy_done_item_does_not_stamp_now(self):
        """改个标题**不许**把「完成时间」补成今天。

        历史空值（早期用 PATCH 改成完成、没记时间）一旦被这样补，
        它就变成一条「今天完成的」—— 日期是假的，而且看不出是假的。
        """
        item = make('历史条目', 'done', created=timezone.now() - dt.timedelta(days=90), processed=None)

        APIClient().patch(f'{URL}{item.id}/', {'content': '历史条目（改个标题）'}, format='json')

        item.refresh_from_db()
        assert item.processed_at is None

    def test_archiving_a_done_item_keeps_its_completion_time(self):
        """归档一条已完成的条目 ⇒ 完成时间原样保留（收尾态不碰这个字段）。"""
        first = timezone.now() - dt.timedelta(days=3)
        item = make('完成后归档', 'done', processed=first)

        APIClient().post(URL + 'batch/', {'ids': [item.id], 'action': 'archive'}, format='json')

        item.refresh_from_db()
        assert item.status == 'archived'
        assert item.processed_at == first


# ══════════════════════════════════════════════════════════════
# 三、三组状态铺满枚举（不留「没想过」的第三种）
# ══════════════════════════════════════════════════════════════

def test_status_groups_partition_choices():
    """`STATUS_CLOSED` / `STATUS_OPEN` / 收尾态 三组**正好铺满**六种状态。

    将来加一个状态却忘了想「它的 `processed_at` 该不该有」，这条会当场红；
    不红的话，新状态会静默落进「不碰」那一组 —— 而「不碰」是所有分支里
    最容易看着正常的一个。
    """
    all_status = {value for value, _ in InboxItem.STATUS_CHOICES}
    closed = set(InboxItem.STATUS_CLOSED)
    opened = set(InboxItem.STATUS_OPEN)
    terminal = {'archived', 'abandoned'}

    assert closed | opened | terminal == all_status
    assert closed & opened == set()
    assert closed & terminal == set()
    assert opened & terminal == set()
