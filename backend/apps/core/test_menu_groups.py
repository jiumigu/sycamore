"""core app 测试 — 侧边栏分组的惰性补齐（`ensure_default_menu_groups`）

对应 v3.61.0：新增「自我运转」独立分组（原先挂在「目标与项目」下）。

⚠️ 为什么这条要单独钉住：`DEFAULT_MENU_GROUPS` 的 sort 值**只有新库吃得到** ——
老库（分组表里已经躺着 9 行）不会重跑 seed。旧实现是「表空才写入」
（`if MenuGroup.objects.exists(): return`），于是改常量只对新库生效，
老库**静默拿不到新分组**（不报错、不提示，就是不出现）。

改成「补齐缺失项」之后，两条原本藏在注释里的约束必须有用例守着，
否则以后有人顺手改一下就静默失效：

1. **只 INSERT 缺失项，绝不 UPDATE 已有行** —— 用户会在「菜单管理」里
   上下拖分组（这个库就是：`wealth` 被拖到了第 2 位），覆盖 `sort_order`
   等于把他的排序弄乱；
2. 新分组的 `sort_order` 注定和老库已有分组**撞号**（1..9 已被占满，插不进空位），
   落位依赖 `MenuGroup.Meta.ordering = ['sort_order', 'group_key']` 里的
   `group_key` 字母序 —— 这是个**隐式依赖**：谁把 ordering 改了都不会报错，
   只会让分组默默飘到别的地方去。

⚠️ 这里的 `delete()` 清的是**测试库**（test_sycamore）+ 每个用例包在事务里回滚，
不碰开发库。
"""
import pytest
from rest_framework.test import APIClient

from apps.core.models import MenuGroup
from apps.core.views import DEFAULT_MENU_GROUPS, ensure_default_menu_groups

_DEFAULT_KEYS = {g['key'] for g in DEFAULT_MENU_GROUPS}


def _wipe() -> None:
    """把分组表清空，好摆出「老库」的样子"""
    MenuGroup.objects.all().delete()


@pytest.mark.django_db
def test_backfills_missing_group_without_touching_user_order() -> None:
    """老库升级：补上缺失的 selfrun，**用户拖过的顺序原样不动**"""
    _wipe()
    MenuGroup.objects.create(group_key='overview', group_name='总览', sort_order=1)
    MenuGroup.objects.create(group_key='wealth', group_name='财富管理', sort_order=2)  # 用户拖到第 2
    MenuGroup.objects.create(group_key='goals', group_name='目标与项目', sort_order=3)

    ensure_default_menu_groups()

    assert set(MenuGroup.objects.values_list('group_key', flat=True)) == _DEFAULT_KEYS
    # 已被用户持有的行：一个字都不许动
    assert MenuGroup.objects.get(group_key='wealth').sort_order == 2
    assert MenuGroup.objects.get(group_key='goals').sort_order == 3


@pytest.mark.django_db
def test_backfill_is_idempotent() -> None:
    """重复调用不产生重复行 —— 这函数挂在每个 `GET /core/menu-groups/` 上"""
    _wipe()

    ensure_default_menu_groups()
    ensure_default_menu_groups()

    assert MenuGroup.objects.filter(group_key='selfrun').count() == 1
    assert MenuGroup.objects.count() == len(DEFAULT_MENU_GROUPS)


@pytest.mark.django_db
def test_selfrun_sits_right_after_goals_even_when_sort_collides() -> None:
    """撞号时按 `group_key` 字母序落位：selfrun 紧跟「目标与项目」，不被挤到末尾

    ⚠️ 老库的 sort_order 是 1..9 连续占满的，新分组**只能撞号**
    （`selfrun` 拿到默认的 4，而 4 已经被 `temporal` 占着）。
    这条用例钉的就是：撞号之后它仍落在 goals 之后、temporal 之前
    —— 即 `'goals' < 'selfrun' < 'temporal'`。
    """
    _wipe()
    MenuGroup.objects.create(group_key='goals', group_name='目标与项目', sort_order=3)
    MenuGroup.objects.create(group_key='temporal', group_name='时间感知', sort_order=4)

    ensure_default_menu_groups()

    ordered = list(MenuGroup.objects.values_list('group_key', flat=True))
    assert ordered.index('goals') < ordered.index('selfrun') < ordered.index('temporal')


@pytest.mark.django_db
def test_menu_groups_endpoint_returns_bare_array_with_all_groups():
    """分组接口必须裸数组返回**全量**，绝不能走 DRF 全局分页。

    v3.64.0 踩坑：showroom 补进库后分组总数 11 > 全局 page_size 10，
    分页把排最末的 showroom 截到第 2 页，前端只读第一页 results ⇒ 侧边栏静默少一组。
    """
    _wipe()
    resp = APIClient().get('/api/core/menu-groups/')
    data = resp.json()

    assert resp.status_code == 200
    assert isinstance(data, list), '分组接口必须是裸数组（不是 {count,results}）'
    assert len(data) == len(DEFAULT_MENU_GROUPS)
    keys = {g['group_key'] for g in data}
    assert keys == _DEFAULT_KEYS
    assert 'showroom' in keys
