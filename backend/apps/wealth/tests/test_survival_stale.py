"""生存资源 · 库存新鲜度 `_stock_stale_days`（v3.64.89）

钉住一个口径决策：结论条标黄的「多久没盘」取**盘点**（stocktake）的创建时间，
不是库存流水（flow）—— 流水只改单件（实测 11/9 两条流水只动了 2 件），
用它当整体新鲜度会高估：那 2 件新鲜 ≠ 57 件都新鲜。

新表由 conftest 的 session 级 django_db_setup 补齐（--no-migrations --reuse-db 下
新表不会自动出现）。
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.wealth.models import SurvivalStocktake
from apps.wealth.services.survival_service import _stock_stale_days

pytestmark = pytest.mark.django_db

# 🔴 不能写死某一天当「今天」：`created_at` 是用 `timezone.now()` 往回推的，
#    写死日期后测试只在那一天成立 —— 第二天跑就 1 == 3 挂掉（真实踩过）。
#    两处必须用同一个基准，所以取一次 `localdate()` 供造数与断言共用。
TODAY = timezone.localdate()


def _make_stocktake(days_ago: int) -> SurvivalStocktake:
    """造一条 N 天前创建的盘点单。

    `created_at` 是 `auto_now_add`，只能先 create 再用 `update()` 改回过去
    （`update()` 不触发 auto_now_add，`save()` 会）。
    """
    row = SurvivalStocktake.objects.create(stocktake_date=TODAY)
    SurvivalStocktake.objects.filter(pk=row.pk).update(
        created_at=timezone.now() - timedelta(days=days_ago),
    )
    return row


def test_no_stocktake_returns_none():
    """从未盘点 → None：没有「盘过」的基线，「很久没盘」无从谈起"""
    assert _stock_stale_days(TODAY) is None


def test_stale_days_counts_from_latest_stocktake():
    """取最近一次盘点（不求和、不看最旧那一单）"""
    _make_stocktake(days_ago=10)
    _make_stocktake(days_ago=3)
    assert _stock_stale_days(TODAY) == 3


def test_stale_days_uses_created_at_not_stocktake_date():
    """新鲜度看「哪天动手盘的」（created_at），不是「盘的是哪一天」（stocktake_date）"""
    _make_stocktake(days_ago=0)
    assert _stock_stale_days(TODAY) == 0
