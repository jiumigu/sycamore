"""收件箱 · 完成备注的读写（v3.64.83）—— 2 条

起点是一条体感抱怨：「已完成待办，点击编辑时完全看不到完成备注项」。

`completion_note` 在「标记完成」弹窗里能填、在列表里能显示，唯独**编辑弹窗里
没有这一项** —— 于是填过的看不到、想补的没地方补。这类「能存不能看」的字段，
接口层一直是通的（列表序列化器可写），缺的是界面与一条钉住它的用例。
"""
import pytest
from rest_framework.test import APIClient

from apps.inbox.models import InboxItem

pytestmark = pytest.mark.django_db

URL = '/api/inbox/items/'


def test_patch_completion_note_persists():
    """编辑弹窗保存备注 ⇒ 落库，且回读拿得到（不是只回显在表单里）。"""
    item = InboxItem.objects.create(content='一条待办', status='pending')

    res = APIClient().patch(f'{URL}{item.id}/', {'completion_note': '做完了，比想象中简单'}, format='json')

    assert res.status_code == 200
    assert res.data['completion_note'] == '做完了，比想象中简单'
    item.refresh_from_db()
    assert item.completion_note == '做完了，比想象中简单'


def test_patch_to_done_with_note_keeps_both():
    """一次 PATCH 同时给「状态=已完成」和备注 ⇒ 两样都要落。

    界面上的真实动作就是这个：打开一条待办，把状态改成已完成，顺手写一句备注。
    只落其中一样的话，另一项会静默消失 —— 而两种「消失」在接口返回里都长得正常。
    """
    item = InboxItem.objects.create(content='一条待办', status='pending')

    res = APIClient().patch(
        f'{URL}{item.id}/', {'status': 'done', 'completion_note': '花了三个小时'}, format='json',
    )

    assert res.status_code == 200
    item.refresh_from_db()
    assert item.status == 'done'
    assert item.completion_note == '花了三个小时'
    # 状态走到 done ⇒ 完成时间必须同时落下（排序键的来源，见 test_order_and_time.py）
    assert item.processed_at is not None
