"""通知接口：**列表本身**必须能取到（v3.62.37）

🔴 上一版给 `NotificationViewSet` 加了 `generate` / `read` / `read_all` 三个 action，
   却漏了 `serializer_class` —— `ReadOnlyModelViewSet.list` 在
   `get_serializer_class()` 里会断言它非空，于是 `GET /core/notifications/`
   恒 **500**。三个新 action 都自己 `Response(...)`，因此测试全绿，
   只有真的去列表才会炸：前端表现是「通知中心永远空着」。

   所以这组测试的第一条就是「列表能取到」，剩下的守 action 契约。
"""
import pytest
from rest_framework.test import APIClient

from apps.core.models import Notification

URL = '/api/core/notifications/'


def _client():
    return APIClient()


def _make(**kw):
    data = dict(
        source_module='core',
        category='info',
        title='测试通知',
        body='正文',
        action_url='',
    )
    data.update(kw)
    return Notification.objects.create(**data)


# ══════════════════════════════════════════════════════════
# 列表
# ══════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_list_returns_200_and_paginated_shape():
    _make()
    r = _client().get(URL, {'page_size': 20})
    assert r.status_code == 200, r.content[:300]
    body = r.json()
    assert set(['count', 'results']).issubset(body.keys())
    assert body['count'] == 1


@pytest.mark.django_db
def test_list_item_has_all_frontend_keys():
    """前端 `NotificationItem` 的 9 个键一个都不能少 —— 少声明 = 静默丢键"""
    _make(source_object_id=7)
    item = _client().get(URL).json()['results'][0]
    assert set(item.keys()) == {
        'id', 'source_module', 'source_object_id', 'category',
        'title', 'body', 'action_url', 'is_read', 'created_at',
    }


@pytest.mark.django_db
def test_list_orders_newest_first():
    _make(title='旧')
    _make(title='新')
    titles = [x['title'] for x in _client().get(URL).json()['results']]
    assert titles == ['新', '旧']


@pytest.mark.django_db
def test_list_empty_is_200_not_500():
    r = _client().get(URL)
    assert r.status_code == 200
    assert r.json()['count'] == 0


# ══════════════════════════════════════════════════════════
# action 契约
# ══════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_unread_count():
    _make()
    n = _make()
    n.is_read = True
    n.save(update_fields=['is_read'])
    assert _client().get(f'{URL}unread_count/').json() == {'count': 1}


@pytest.mark.django_db
def test_mark_read_is_idempotent():
    n = _make()
    c = _client()
    assert c.post(f'{URL}{n.id}/read/').status_code == 200
    assert c.post(f'{URL}{n.id}/read/').status_code == 200
    n.refresh_from_db()
    assert n.is_read is True


@pytest.mark.django_db
def test_mark_read_missing_id_404():
    assert _client().post(f'{URL}999999/read/').status_code == 404


@pytest.mark.django_db
def test_read_all_reports_actually_updated():
    _make()
    a = _make()
    b = _make()
    a.is_read = True
    a.save(update_fields=['is_read'])
    body = _client().post(f'{URL}read_all/').json()
    assert body['updated'] == 2  # 只数真正被改动的（a 已是已读）
    assert Notification.objects.filter(is_read=False).count() == 0
    assert b.id


@pytest.mark.django_db
def test_generate_is_post_only():
    r = _client().get(f'{URL}generate/')
    assert r.status_code == 405
