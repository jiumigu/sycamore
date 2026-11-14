"""`/core/quick-record/` 的模块分派。

起因（2026-11-11）：`module` 不认识时落到函数末尾，直接返回
`{'success': True, 'message': '记录成功'}` —— **什么都没写**。
前端把模块名拼错一次，用户看到「已记录」，事后查不到任何东西。
这组测试钉住「不认识的类型必须报错、且不能写库」。
"""
import pytest
from django.db import connection
from rest_framework.test import APIClient

URL = '/api/core/quick-record/'


def _post(**payload):
    return APIClient().post(URL, payload, format='json')


def _count(table: str) -> int:
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT COUNT(*) FROM {table}')
        return cursor.fetchone()[0]


@pytest.mark.django_db
def test_unknown_module_is_rejected() -> None:
    """拼错模块名 ⇒ 400，且三张表都不得新增行。"""
    before = (
        _count('temporal_oneday_page_list'),
        _count('sugar_record'),
        _count('inbox_item'),
    )
    resp = _post(module='diray', content='今天心情不错')

    assert resp.status_code == 400
    assert resp.json()['code'] == 'unknown_module'
    assert 'diray' in resp.json()['error']

    after = (
        _count('temporal_oneday_page_list'),
        _count('sugar_record'),
        _count('inbox_item'),
    )
    assert after == before, '未知 module 竟然写了库'


@pytest.mark.django_db
def test_known_modules_still_work() -> None:
    """三个纯文本类型照旧可用 —— 修静默失败不能顺手把正常路径也关掉。"""
    assert _post(module='temporal', content='日记一条').status_code == 200
    assert _post(module='sugar', content='小确幸一条').status_code == 200
    assert _post(module='goals', content='待办一条').status_code == 200

    assert _count('temporal_oneday_page_list') == 1
    assert _count('sugar_record') == 1
    assert _count('inbox_item') == 1


@pytest.mark.django_db
def test_empty_content_still_rejected() -> None:
    resp = _post(module='temporal', content='   ')
    assert resp.status_code == 400
