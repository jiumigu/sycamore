"""月度复盘「余额类字段」退役（v3.60.14，2026-10-03）

背景：`wealth_balance_list` 的 6 个存量列（`balance` / `accumulationfund` /
`distance` / `borrow` / `lend` / `realnum`）自 2026-06 起无人填写 —— 复盘录入
弹窗从来没送过它们。它们的语义已由「资产盘点」接管，本轮把写入面正式封掉、
读取面收口到唯一取数口。决策稿：
`docs/wealth_balance_list-字段退役决策稿-20261003.md`

覆盖：
  ① 存款余额**三态取数**：有资产盘点快照 → 取该月净资产 + `asset_snapshot`；
     无快照有手填 → 回落 `legacy`；两者都无 → `None`（**不是 0**）
  ② **取数口唯一**：`_parse_balance_list` 只吐「流」，不吐存款 ——
     否则会绕过 `_deposit_payload()`，来源标注跟着丢
  ③ 序列化器**收口**：送退役列一律被忽略；`total` 只读（历史值照常能读）
  ④ `reconcile` 已**退役**（端点 404 + 服务层无该符号），且不误伤
     生存资源的同名 `get_reconcile`
  ⑤ `net_worth_by_yearmon` 与 `rollup_items` **同源**，不是第二份汇总实现
  ⑥ 趋势接口不因切源而炸

⚠️ 四个受测表（`wealth_balance_list` / `wealth_asset_account` /
   `wealth_asset_snapshot` / `wealth_asset_snapshot_item`）都在 `conftest.py`
   的 session 级镜像建表里 —— `--no-migrations --reuse-db` 下新表不会自动出现，
   所以本文件**不需要**再动 conftest；反过来说，谁要新加表，得先补那里。
"""
from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.wealth.models import (
    WealthAssetAccount,
    WealthAssetSnapshot,
    WealthAssetSnapshotItem,
    WealthBalanceList,
)
from apps.wealth.services.asset_service import net_worth_by_yearmon, rollup_items
from apps.wealth.services.review_service import (
    _parse_balance_list,
    get_monthly_review,
    get_trend_data,
)

BALANCE_URL = '/api/wealth/review/balance_list/'
LIST_URL = '/api/wealth/review/monthly_list/'


# ══════════════════════════════════════════════════════════════
# 造数工具
# ══════════════════════════════════════════════════════════════


def _balance(yearmon, total=None, income=0.0, expense=0.0, **extra):
    """一期复盘记录。`total` = 历史手填的「存款余额」（已退役，只读）。"""
    return WealthBalanceList.objects.create(
        yearmon=yearmon,
        wageincome=income, otherincome=0.0,
        outmoney=expense, mbalance=income - expense,
        total=total, **extra
    )


def _account(name='支付宝', category='流动性', is_liquid=True, sort=10):
    return WealthAssetAccount.objects.create(
        name=name, category=category, account_kind='储蓄卡',
        is_liquid=is_liquid, include_in_balance_sheet=True,
        sort=sort, user_id=1,
    )


def _snapshot(yearmon, snapshot_date, borrow=0.0, items=()):
    snap = WealthAssetSnapshot.objects.create(
        yearmon=yearmon, snapshot_date=snapshot_date, borrow=borrow, user_id=1,
    )
    for account, amount in items:
        WealthAssetSnapshotItem.objects.create(
            snapshot=snap, account=account, amount=amount,
        )
    return snap


# ══════════════════════════════════════════════════════════════
# ① 存款余额三态取数
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_deposit_prefers_asset_snapshot():
    """有快照时取该月**净资产**，并下发来源与盘点日 —— 完全不看手填的 total"""
    acc = _account()
    _snapshot('2026-09', date(2026, 9, 23), borrow=3000.0, items=[(acc, 50000.0)])
    _balance('2026-09', total=99999.0)

    result = get_monthly_review(1, 2026, 9)

    assert result['deposit'] == 47000.0          # 50000 − 3000，不是手填的 99999
    assert result['deposit_source'] == 'asset_snapshot'
    assert result['deposit_as_of'] == '2026-09-23'


@pytest.mark.django_db
def test_deposit_falls_back_to_legacy_total():
    """没有盘点快照的月份，才回落到历史手填值，并**如实标注** legacy"""
    _balance('2020-07', total=480.0)

    result = get_monthly_review(1, 2020, 7)

    assert result['deposit'] == 480.0
    assert result['deposit_source'] == 'legacy'
    assert result['deposit_as_of'] is None


@pytest.mark.django_db
def test_deposit_is_none_when_neither_source_exists():
    """两处都没有 → `None`，**不是 0**（0 是一个结论，None 是没数据）

    前端据此占位 `—`；若这里返回 0，界面会把「没盘过」画成「余额为零」。
    """
    _balance('2020-01')          # 没有 total

    result = get_monthly_review(1, 2020, 1)

    assert result['deposit'] is None
    assert result['deposit_source'] is None
    assert result['deposit_as_of'] is None


@pytest.mark.django_db
def test_zero_total_is_kept_as_zero_not_treated_as_missing():
    """手填 `total = 0` 是**一个值**，不是「没填」—— 别用 `if total:` 判空"""
    _balance('2020-02', total=0.0)

    result = get_monthly_review(1, 2020, 2)

    assert result['deposit'] == 0.0
    assert result['deposit_source'] == 'legacy'


# ══════════════════════════════════════════════════════════════
# ② 取数口唯一
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_parse_balance_list_only_emits_flow():
    """`_parse_balance_list` 只吐「流」。

    往它里面加 `deposit` 会**绕过** `_deposit_payload()`：金额还有，
    但「这个数是从哪来的」那句话丢了 —— 前端只能按值猜。
    """
    bi = _balance('2026-09', total=99999.0, income=1000.0, expense=400.0)

    data = _parse_balance_list(bi)

    assert 'deposit' not in data
    assert 'deposit_balance' not in data
    assert data['income'] == 1000.0
    assert data['expense'] == 400.0
    assert data['balance'] == 600.0
    assert data['from_balance_list'] is True


# ══════════════════════════════════════════════════════════════
# ③ 序列化器收口
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_retired_columns_are_not_writable_via_api():
    """PUT 送退役列一律被忽略 —— 否则等于又开出一个录入口"""
    _balance('2026-09', total=500.0, income=100.0, expense=10.0)

    resp = APIClient().put(BALANCE_URL, {
        'yearmon': '2026-09',
        # `income` / `expense` 是算出来的只读字段 —— 送什么都被忽略，
        # 真正落库的是 wageincome / outmoney（前端 payload 也是这么映射的）
        'income': 999.0, 'expense': 999.0,
        'wageincome': 200.0, 'outmoney': 20.0, 'mbalance': 180.0,
        # 六个退役列
        'accumulationfund': 12345.0, 'distance': 7.0,
        'borrow': 888.0, 'lend': 999.0, 'realnum': 111.0,
        # DB 的 balance 列（与序列化器里那个同名的只读「结余」字段是两回事）
        'balance': 4321.0,
        # 一并摘掉的元信息
        'btime': '2026-10-03T10:00:00+08:00', 'user_id': 9,
    }, format='json')

    assert resp.status_code == 200
    after = WealthBalanceList.objects.get(yearmon='2026-09')
    for column in ('accumulationfund', 'distance', 'borrow', 'lend', 'realnum',
                   'balance', 'btime', 'user_id'):
        assert getattr(after, column) is None, column
    # 「流」照常可写
    assert after.wageincome == 200.0
    assert after.outmoney == 20.0
    assert after.mbalance == 180.0


@pytest.mark.django_db
def test_total_is_read_only_but_still_readable():
    """`total` = 历史手填值：**读得到、写不进**。

    展示走 `review_service`（余额以资产盘点为准）。封掉写入面是为了不让
    它变成第二个录入口；修正历史请补一期资产盘点快照。
    """
    _balance('2026-09', total=500.0, income=100.0, expense=10.0)

    resp = APIClient().put(BALANCE_URL, {
        'yearmon': '2026-09', 'income': 100.0, 'expense': 10.0, 'total': 77777.0,
    }, format='json')

    assert resp.status_code == 200
    assert resp.json()['total'] == 500.0                                  # 读得到（旧值）
    assert WealthBalanceList.objects.get(yearmon='2026-09').total == 500.0  # 没被改


# ══════════════════════════════════════════════════════════════
# ④ reconcile 退役
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_reconcile_endpoint_is_gone():
    """端点 404。它两侧的输入源都已退役（左 `balance` 恒 NULL、右旧表存档），
    留着只会对 2026-06 之后的期次**恒报假差额**。"""
    assert APIClient().get('/api/wealth/cashflow/reconcile/').status_code == 404


def test_reconcile_symbol_removed_from_service_layer():
    """服务层也已无 `reconcile` —— 只删路由不删函数，等于留了个半开的门"""
    import apps.wealth.services.cashflow_service as cashflow_service

    assert not hasattr(cashflow_service, 'reconcile')


def test_survival_reconcile_is_untouched():
    """⚠️ 同名不同物：生存资源的缺口对账 `get_reconcile` **必须还在**。

    退役时最容易连带删掉的就是它（两处都叫 reconcile）。
    """
    from apps.wealth.services import get_survival_reconcile

    assert callable(get_survival_reconcile)


# ══════════════════════════════════════════════════════════════
# ⑤ 单一真源
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_net_worth_by_yearmon_shares_the_single_source():
    """索引值与 `rollup_items()` 同源 —— 不是第二份汇总实现"""
    acc_a = _account('支付宝', category='流动性', sort=10)
    acc_b = _account('公积金', category='投资性', is_liquid=False, sort=20)
    snap = _snapshot('2026-09', date(2026, 9, 23), borrow=1000.0,
                     items=[(acc_a, 5000.0), (acc_b, 3000.0)])

    index = net_worth_by_yearmon(1)

    expected = rollup_items([(5000.0, acc_a), (3000.0, acc_b)], snap.borrow)['net_worth']
    assert index['2026-09']['net_worth'] == expected
    assert index['2026-09']['net_worth'] == 7000.0          # 8000 − 1000
    assert index['2026-09']['snapshot_date'] == '2026-09-23'


@pytest.mark.django_db
def test_net_worth_by_yearmon_ignores_other_users():
    """user_id 要真起作用 —— 别人的快照不该混进本用户的月度复盘"""
    acc = _account()
    snap = _snapshot('2026-09', date(2026, 9, 23), items=[(acc, 1000.0)])
    snap.user_id = 2
    snap.save(update_fields=['user_id'])

    assert net_worth_by_yearmon(1) == {}


# ══════════════════════════════════════════════════════════════
# ⑥ 切源不影响既有接口
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_trend_data_still_works_with_the_new_source():
    """趋势接口不因切源而炸（`asset_index` 可选入参只是省查询，不改结果）"""
    acc = _account()
    _snapshot('2026-09', date(2026, 9, 23), items=[(acc, 1000.0)])
    _balance('2026-09', total=1.0, income=100.0, expense=10.0)

    trend = get_trend_data(1, months=3)

    assert len(trend) == 3
    assert all('deposit' in point for point in trend)


@pytest.mark.django_db
def test_monthly_list_carries_source_keys():
    """列表每条都带来源键，前端据它决定标不标「手填」

    同时钉住三态在同一份响应里并存 —— 这是前端标注逻辑的前提。
    """
    acc = _account()
    _snapshot('2026-09', date(2026, 9, 23), items=[(acc, 1000.0)])
    _balance('2026-09', total=1.0, income=100.0, expense=10.0)
    _balance('2020-07', total=480.0)
    _balance('2020-01')

    body = APIClient().get(f'{LIST_URL}?page=1&page_size=10').json()
    by_yearmon = {item['yearmon']: item for item in body['items']}

    assert by_yearmon['2026-09']['deposit_source'] == 'asset_snapshot'
    assert by_yearmon['2026-09']['deposit'] == 1000.0
    assert by_yearmon['2026-09']['deposit_as_of'] == '2026-09-23'
    assert by_yearmon['2020-07']['deposit_source'] == 'legacy'
    assert by_yearmon['2020-07']['deposit'] == 480.0
    assert by_yearmon['2020-01']['deposit_source'] is None
    assert by_yearmon['2020-01']['deposit'] is None
