"""core app 测试 — 用户配置（`/core/profile/`）的读写、区间校验与区间下发

对应 v3.60.12：金句池长度上限由硬编码常量（200）改为 `UserProfile.quote_pool_max_len`，
在「系统管理 → 系统设置」里可调。

⚠️ 文件位置的由来（别顺手搬进 `tests/` 或改名回去）：
core 目录下已有 Django 默认的 `tests.py`，而 `pytest.ini` 只收集 `test_*.py`
（见 pytest.ini 里的注释：历史 `tests.py` 是 Django TestCase，pytest 下 app_label 解析不兼容）。
其他 app 的用例放在 `tests/` 目录里，但 core 没有那个目录、本轮也不新建目录（新建目录需用户决策），
所以这个文件就落在 app 根目录 —— 它是 `test_*.py`，会被正常收集。

⚠️ 本文件是 core app 的**第一个**自动化测试。在此之前 core 长期零测试，
所以 `core_user_profile` 也没进 `conftest.py`（`--reuse-db` 一直在复用旧测试库里那张表「蒙着」）。
本轮一并补上：见 conftest.py 的 `_CREATE_CORE_USER_PROFILE_SQL`
与 `_patch_core_user_profile_columns`。
"""
import pytest
from rest_framework.test import APIClient

from apps.core.models import (
    DEFAULT_QUOTE_POOL_MAX_LEN,
    QUOTE_POOL_LEN_RANGE,
    UserProfile,
)

PROFILE_URL = '/api/core/profile/'


@pytest.mark.django_db
def test_profile_exposes_all_config_keys() -> None:
    """键名清单：`/core/profile/` 下发的每一个键都要能被断言到

    ⚠️ 前端对配置项是「取不到就静默不渲染」—— 键名写错在界面上看不出来，
    所以凡新增配置键，同轮补一条键名断言。
    """
    data = APIClient().get(PROFILE_URL).data
    assert {'user_id', 'privacy_mode', 'logseq_path', 'quote_pool_max_len'} <= set(data)


@pytest.mark.django_db
def test_profile_returns_model_default_when_unset() -> None:
    """还没有配置行时下发**模型字段的默认值**（前端输入框要有个初始值）"""
    assert not UserProfile.objects.filter(user_id=1).exists()
    data = APIClient().get(PROFILE_URL).data
    assert data['quote_pool_max_len'] == DEFAULT_QUOTE_POOL_MAX_LEN


@pytest.mark.django_db
def test_profile_delivers_len_range_for_frontend() -> None:
    """合法区间由后端下发（前端不硬编码阈值，只负责显示）

    同 `RATIO_BANDS` 的判据：阈值只该有一份。前端输入框的 min/max 与文案
    都读这个键，改区间时只改后端一处。
    """
    data = APIClient().get(PROFILE_URL).data
    assert data['quote_pool_len_range'] == list(QUOTE_POOL_LEN_RANGE)


@pytest.mark.django_db
def test_profile_patch_updates_quote_pool_len() -> None:
    """改配置能落库并回读；PATCH 是部分更新，不动别的键"""
    c = APIClient()
    resp = c.patch(PROFILE_URL, {'quote_pool_max_len': 800}, format='json')
    assert resp.status_code == 200
    assert resp.data['quote_pool_max_len'] == 800
    assert c.get(PROFILE_URL).data['quote_pool_max_len'] == 800
    assert UserProfile.objects.get(user_id=1).quote_pool_max_len == 800
    # 隐私模式没被这次 PATCH 顺手改掉
    assert UserProfile.objects.get(user_id=1).privacy_mode is False


@pytest.mark.django_db
@pytest.mark.parametrize('bad', [0, 10, 49, 5001, 99999])
def test_profile_rejects_out_of_range_quote_pool_len(bad: int) -> None:
    """越界值返回 400，**不静默夹取**

    静默把 5001 改成 5000 更「友好」，但用户会以为自己填的值生效了 ——
    配置项要么按你说的存，要么明确报错。
    """
    resp = APIClient().patch(PROFILE_URL, {'quote_pool_max_len': bad}, format='json')
    assert resp.status_code == 400
    assert 'quote_pool_max_len' in resp.data


@pytest.mark.django_db
def test_profile_accepts_range_endpoints() -> None:
    """区间**端点本身**合法（防把校验写成左开右闭）"""
    low, high = QUOTE_POOL_LEN_RANGE
    c = APIClient()
    assert c.patch(PROFILE_URL, {'quote_pool_max_len': low}, format='json').status_code == 200
    assert c.patch(PROFILE_URL, {'quote_pool_max_len': high}, format='json').status_code == 200
