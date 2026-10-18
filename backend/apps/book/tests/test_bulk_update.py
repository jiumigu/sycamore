"""阅读管理 · 批量改「阅读状态 / 阅读深度」—— 18 条

🔴 这一组钉住四件最容易静默出错的事：

① **「弃读」不许批量** —— 弃读在后端是逐本必填原因的（`BookCreateUpdateSerializer`），
   批量给一个统一原因会把「为什么弃」写成假话。约束在**后端**挡（400），
   不能只靠前端少画一项：越界调用必须失败，而不是写进一条假原因。
② **「请求了几本」和「改了几本」必须分开报** —— 选中的书可能已被别处删掉，
   只回一个命中数，前端就会把「改了 3 本」说成「改了 5 本」。
③ **`updated_at` 要跟着动** —— `QuerySet.update()` 绕过 `Model.save()`，
   而 `auto_now` 钩子挂在 `save()` 上；不手工写就成了「内容改了、更新日期还是旧的」。
④ **只开两个字段** —— 请求里夹带 `btitle` 之类必须被忽略，
   否则「少写一个字段」和「清空一个字段」会静默等价。
"""
import datetime as dt

import pytest
from rest_framework.test import APIClient

from apps.book.models import Book
from apps.book.services import BookService
from apps.works.models import WorkCapture

pytestmark = pytest.mark.django_db

URL = '/api/books/bulk_update/'


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def books():
    """三本书：一本在读、一本计划阅读、一本已完成。"""
    return [
        Book.objects.create(years='2026', btitle='书一', btype='认知提升类', status='在读',
                            reading_depth=3, recommend=3),
        Book.objects.create(years='2026', btitle='书二', btype='认知提升类', status='计划阅读',
                            reading_depth=1, recommend=2),
        Book.objects.create(years='2026', btitle='书三', btype='文学滋养类', status='已完成',
                            reading_depth=5, recommend=5),
    ]


# ══════════════════════════════════════════════════════════════
# 一、批量改状态
# ══════════════════════════════════════════════════════════════

class TestBulkStatus:

    def test_bulk_set_status(self, client, books):
        """选两本改成「通读」—— 只动这两本，第三本一个字不动。"""
        ids = [books[0].bid, books[1].bid]
        res = client.post(URL, {'bids': ids, 'status': '通读'}, format='json')
        assert res.status_code == 200
        assert res.data == {'updated': 2, 'requested': 2}
        assert Book.objects.get(bid=ids[0]).status == '通读'
        assert Book.objects.get(bid=ids[1]).status == '通读'
        assert Book.objects.get(bid=books[2].bid).status == '已完成'

    def test_status_does_not_touch_other_fields(self, client, books):
        """改状态**不该顺手改深度/推荐/书名**。"""
        before = Book.objects.get(bid=books[0].bid)
        client.post(URL, {'bids': [books[0].bid], 'status': '消遣'}, format='json')
        after = Book.objects.get(bid=books[0].bid)
        assert after.reading_depth == before.reading_depth
        assert after.recommend == before.recommend
        assert after.btitle == before.btitle
        assert after.btype == before.btype

    def test_set_status_to_completed_does_not_capture(self, client, books):
        """🔴 批量改成「已完成」**不产生「待提炼」**。

        「值得留下」是编辑弹窗里那个勾的事，捕获必须带 `source_id` 且由人逐本决定。
        批量路径偷偷打勾 = 替用户判断「这本书值得留」。
        """
        client.post(URL, {'bids': [books[0].bid, books[1].bid], 'status': '已完成'}, format='json')
        assert WorkCapture.objects.count() == 0


# ══════════════════════════════════════════════════════════════
# 二、批量改阅读深度
# ══════════════════════════════════════════════════════════════

class TestBulkDepth:

    def test_bulk_set_depth(self, client, books):
        res = client.post(URL, {'bids': [books[0].bid, books[2].bid], 'reading_depth': 4}, format='json')
        assert res.status_code == 200
        assert res.data['updated'] == 2
        assert Book.objects.get(bid=books[0].bid).reading_depth == 4
        assert Book.objects.get(bid=books[2].bid).reading_depth == 4
        assert Book.objects.get(bid=books[1].bid).reading_depth == 1

    def test_depth_does_not_touch_status(self, client, books):
        """只传深度 ⇒ 状态保持原样（不是「清空状态」）。"""
        client.post(URL, {'bids': [books[0].bid], 'reading_depth': 2}, format='json')
        assert Book.objects.get(bid=books[0].bid).status == '在读'

    def test_depth_out_of_range_rejected(self, client, books):
        """1–5 之外一律 400 —— 而且**库里没被改**。"""
        for bad in (0, 6, 99):
            res = client.post(URL, {'bids': [books[0].bid], 'reading_depth': bad}, format='json')
            assert res.status_code == 400, f'depth={bad} 应被拒'
            assert Book.objects.get(bid=books[0].bid).reading_depth == 3

    def test_depth_boundary_ok(self, client, books):
        for good in (1, 5):
            res = client.post(URL, {'bids': [books[0].bid], 'reading_depth': good}, format='json')
            assert res.status_code == 200
            assert Book.objects.get(bid=books[0].bid).reading_depth == good


# ══════════════════════════════════════════════════════════════
# 三、状态 + 深度一起改
# ══════════════════════════════════════════════════════════════

class TestBulkBoth:

    def test_status_and_depth_together(self, client, books):
        res = client.post(URL, {'bids': [books[1].bid], 'status': '精读', 'reading_depth': 5}, format='json')
        assert res.status_code == 200
        row = Book.objects.get(bid=books[1].bid)
        assert (row.status, row.reading_depth) == ('精读', 5)


# ══════════════════════════════════════════════════════════════
# 四、「弃读」与形状校验
# ══════════════════════════════════════════════════════════════

class TestRejectGuard:

    def test_abandon_is_not_bulkable(self, client, books):
        """🔴 批量改「弃读」→ 400，且**状态一个字没动**。

        弃读在单本编辑里必须同时给原因；批量做不到逐本给，
        所以这里必须**失败**，而不是写进一条没有原因的弃读。
        """
        res = client.post(URL, {'bids': [books[0].bid, books[1].bid], 'status': '弃读'}, format='json')
        assert res.status_code == 400
        assert Book.objects.get(bid=books[0].bid).status == '在读'
        assert Book.objects.get(bid=books[1].bid).status == '计划阅读'

    def test_abandon_with_reason_still_rejected(self, client, books):
        """就算把原因一起传进来，也不认 —— 原因必须逐本填，这一条避免「以后有人顺手放开」。"""
        res = client.post(
            URL,
            {'bids': [books[0].bid], 'status': '弃读', 'abandon_reason': '不好看'},
            format='json',
        )
        assert res.status_code == 400

    def test_empty_bids_rejected(self, client):
        res = client.post(URL, {'bids': [], 'status': '在读'}, format='json')
        assert res.status_code == 400

    def test_no_field_given_rejected(self, client, books):
        """两个字段都不给 ⇒ 400（而不是回一个「改了 0 本」装成功）。"""
        res = client.post(URL, {'bids': [books[0].bid]}, format='json')
        assert res.status_code == 400

    def test_unknown_field_ignored(self, client, books):
        """夹带别的字段（`btitle`）不生效 —— 否则「少写」和「清空」会静默等价。"""
        res = client.post(
            URL,
            {'bids': [books[0].bid], 'status': '在读', 'btitle': '被改掉了', 'recommend': 0},
            format='json',
        )
        assert res.status_code == 200
        row = Book.objects.get(bid=books[0].bid)
        assert row.btitle == '书一'
        assert row.recommend == 3

    def test_missing_ids_reported_honestly(self, client, books):
        """不存在的编号：`requested` 照实报 3、`updated` 报 1 —— 不谎报。"""
        bogus = 999999
        assert not Book.objects.filter(bid=bogus).exists()
        res = client.post(URL, {'bids': [books[0].bid, bogus, bogus + 1], 'status': '待重读'}, format='json')
        assert res.status_code == 200
        assert res.data == {'updated': 1, 'requested': 3}

    def test_no_match_updates_nothing(self, client):
        res = client.post(URL, {'bids': [999999], 'status': '在读'}, format='json')
        assert res.status_code == 200
        assert res.data == {'updated': 0, 'requested': 1}


# ══════════════════════════════════════════════════════════════
# 五、服务层：`updated_at` 必须跟着动
# ══════════════════════════════════════════════════════════════

class TestServiceLayer:

    def test_bulk_update_refreshes_updated_at(self, books):
        """🔴 `QuerySet.update()` 不触发 `auto_now` —— 不手工带就停在旧日期。

        这里先把 `updated_at` 按到 2020 年（同样用 `.update()` 绕过钩子），
        再走批量改：如果服务层忘了带 `updated_at`，这一条会红。
        """
        old = dt.date(2020, 1, 1)
        Book.objects.filter(bid=books[0].bid).update(updated_at=old)
        assert Book.objects.get(bid=books[0].bid).updated_at == old

        changed = BookService.bulk_update([books[0].bid], status='待重读')

        assert changed == 1
        row = Book.objects.get(bid=books[0].bid)
        assert row.status == '待重读'
        assert row.updated_at == dt.date.today()

    def test_bulk_update_without_fields_is_noop(self, books):
        """一个字段都不给 ⇒ 直接返回 0，不发 UPDATE（也不顺手刷 `updated_at`）。"""
        old = dt.date(2020, 1, 1)
        Book.objects.filter(bid=books[0].bid).update(updated_at=old)
        assert BookService.bulk_update([books[0].bid]) == 0
        assert Book.objects.get(bid=books[0].bid).updated_at == old

    def test_status_none_is_not_written(self, books):
        """`status=None` 表示「这次不改状态」，**不是**「把状态清空」。"""
        BookService.bulk_update([books[0].bid], status=None, reading_depth=2)
        row = Book.objects.get(bid=books[0].bid)
        assert row.status == '在读'
        assert row.reading_depth == 2
