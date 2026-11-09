"""净资产变动归因（v3.62.42，第 5 条）

守六件事：
1. **恒等式**：Δ净资产 = 账本净流量 + 未解释差额 − Δ负债，每期都成立
2. 🔴 **还债不该报成漏记**：差额只算**资产端**，Δ负债 只作为独立一行
   （若把 Δ负债 减进差额，还债会被算成「账本漏记」、而真漏记反而静默放过 —— 正好反了）
3. **窗口 = (上期盘点日, 本期盘点日]**：起点日整天排除、终点日整天纳入
4. **无盘点日期 ⇒ 不下结论**（`no_window`），不拿 0 假装算过
5. **门槛只在后端**：500 元以下算噪声，前端不自己比大小
6. **缺月不静默**：跳过 2025-10 这类不连续盘点要显式列出
"""
import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.wealth.models import (
    WealthAssetAccount,
    WealthAssetSnapshot,
    WealthAssetSnapshotItem,
    WealthBillList,
)
from apps.wealth.services.networth_bridge import build_networth_bridge

D = dt.date


def _account(name='银行卡', category='流动性', is_liquid=True, sort=10):
    return WealthAssetAccount.objects.create(
        name=name, category=category, account_kind='储蓄卡',
        is_liquid=is_liquid, include_in_balance_sheet=True, sort=sort, user_id=1,
    )


def _snapshot(yearmon, snapshot_date, amount, borrow=0.0, account=None):
    snap = WealthAssetSnapshot.objects.create(
        yearmon=yearmon, snapshot_date=snapshot_date, borrow=borrow, user_id=1,
    )
    WealthAssetSnapshotItem.objects.create(
        snapshot=snap, account=account or _account(), amount=amount,
    )
    return snap


def _bill(day, ttype, amount, user_id=1):
    """账单是 managed=False 外部表，但测试库有镜像，可直接写

    ⚠️ `created_at` / `updated_at` 在模型里是 `null=True`，而库 DDL 是
    `NOT NULL DEFAULT CURRENT_TIMESTAMP` —— 不显式传会以 NULL 插入而报 1048。
    """
    stamp = timezone.make_aware(dt.datetime.combine(day, dt.time(12, 0)))
    return WealthBillList.objects.create(
        transaction_type=ttype,
        date=stamp,
        amount=Decimal(str(amount)),
        user_id=user_id,
        created_at=stamp,
        updated_at=stamp,
    )


def _latest(periods=2):
    """造两期快照后取最后一期归因"""
    return build_networth_bridge(limit=12)['periods'][-1]


@pytest.mark.django_db
class TestIdentity:
    def test_identity_holds(self):
        acc = _account()
        _snapshot('2026-08', D(2026, 8, 1), 10000, borrow=2000, account=acc)
        _snapshot('2026-09', D(2026, 9, 1), 13000, borrow=2000, account=acc)
        _bill(D(2026, 8, 10), '收入', 5000)
        _bill(D(2026, 8, 20), '支出', 2000)

        p = _latest()
        rebuilt = p['flow_net'] + p['unexplained'] - p['borrow_change']
        assert abs(rebuilt - p['net_worth_change']) < 0.02
        assert p['level'] == 'ok'
        assert build_networth_bridge()['summary']['identity_ok'] is True


@pytest.mark.django_db
class TestDebtIsNotUnexplained:
    """这条是本模块最容易被写反的地方"""

    def test_recorded_repayment_does_not_warn(self):
        """还债记进了账本（支出）⇒ 资产端差额 0，不该报警"""
        acc = _account()
        _snapshot('2026-08', D(2026, 8, 1), 20000, borrow=10000, account=acc)
        _snapshot('2026-09', D(2026, 9, 1), 12000, borrow=2000, account=acc)
        _bill(D(2026, 8, 15), '支出', 8000)   # 还款 8000 记成支出

        p = _latest()
        assert p['assets_change'] == -8000
        assert p['flow_net'] == -8000
        assert p['unexplained'] == 0
        assert p['borrow_change'] == -8000
        assert p['net_worth_change'] == 0     # 还债不改变净资产
        assert p['level'] == 'ok'

    def test_unrecorded_repayment_is_flagged(self):
        """还债**没记**进账本 ⇒ 差额 = −8000，报「现金流出没有账」"""
        acc = _account()
        _snapshot('2026-08', D(2026, 8, 1), 20000, borrow=10000, account=acc)
        _snapshot('2026-09', D(2026, 9, 1), 12000, borrow=2000, account=acc)

        p = _latest()
        assert p['unexplained'] == -8000
        assert p['unexplained_side'] == 'less_than_recorded'
        assert p['level'] == 'material'


@pytest.mark.django_db
class TestDirection:
    def test_more_than_recorded(self):
        """资产涨得比账本记的多 ⇒ 漏记收入 / 余额抄少"""
        acc = _account()
        _snapshot('2026-08', D(2026, 8, 1), 10000, account=acc)
        _snapshot('2026-09', D(2026, 9, 1), 20000, account=acc)

        p = _latest()
        assert p['unexplained'] == 10000
        assert p['unexplained_side'] == 'more_than_recorded'

    def test_adjustment_counts_as_flow(self):
        """「余额变更」是账本的一部分，不是差额"""
        acc = _account()
        _snapshot('2026-08', D(2026, 8, 1), 10000, account=acc)
        _snapshot('2026-09', D(2026, 9, 1), 10500, account=acc)
        _bill(D(2026, 8, 5), '余额变更', 500)

        p = _latest()
        assert p['adjustment'] == 500
        assert p['flow_net'] == 500
        assert p['unexplained'] == 0


@pytest.mark.django_db
class TestWindow:
    def test_window_excludes_start_day_includes_end_day(self):
        """(上期日, 本期日]：上期当天记的单据不算进本期"""
        acc = _account()
        _snapshot('2026-08', D(2026, 8, 10), 10000, account=acc)
        _snapshot('2026-09', D(2026, 9, 10), 10500, account=acc)
        _bill(D(2026, 8, 10), '收入', 9999)   # 起点日 ⇒ 不计
        _bill(D(2026, 9, 10), '收入', 500)    # 终点日 ⇒ 计入

        p = _latest()
        assert p['income'] == 500
        assert p['unexplained'] == 0
        assert p['days'] == 31

    def test_missing_date_yields_no_window(self):
        acc = _account()
        _snapshot('2026-08', None, 10000, account=acc)
        _snapshot('2026-09', D(2026, 9, 1), 12000, account=acc)

        p = _latest()
        assert p['window_reason'] == 'undated'
        assert p['level'] == 'no_window'
        assert p['unexplained'] is None       # null 不是 0
        assert p['income'] is None

    def test_invalid_span_yields_no_window(self):
        acc = _account()
        _snapshot('2026-08', D(2026, 9, 5), 10000, account=acc)
        _snapshot('2026-09', D(2026, 9, 5), 12000, account=acc)

        p = _latest()
        assert p['window_reason'] == 'invalid_span'
        assert p['unexplained'] is None


@pytest.mark.django_db
class TestThreshold:
    def test_small_gap_is_noise(self):
        acc = _account()
        _snapshot('2026-08', D(2026, 8, 1), 100000, account=acc)
        _snapshot('2026-09', D(2026, 9, 1), 100300, account=acc)

        p = _latest()
        assert p['unexplained'] == 300
        assert p['level'] == 'ok'

    def test_threshold_is_inclusive(self):
        acc = _account()
        _snapshot('2026-08', D(2026, 8, 1), 100000, account=acc)
        _snapshot('2026-09', D(2026, 9, 1), 100500, account=acc)

        data = build_networth_bridge()
        assert data['periods'][-1]['level'] == 'material'
        assert data['thresholds']['material_amount'] == 500.0


@pytest.mark.django_db
class TestContinuity:
    def test_missing_month_is_reported(self):
        acc = _account()
        _snapshot('2026-07', D(2026, 7, 1), 10000, account=acc)
        _snapshot('2026-09', D(2026, 9, 1), 10000, account=acc)

        s = build_networth_bridge()['summary']
        assert s['missing_months'] == ['2026-08']
        assert s['missing_count'] == 1
        assert s['snapshot_count'] == 2

    def test_continuous_periods_have_no_gap(self):
        acc = _account()
        for i in (7, 8, 9):
            _snapshot(f'2026-{i:02d}', D(2026, i, 1), 10000, account=acc)

        assert build_networth_bridge()['summary']['missing_count'] == 0

    def test_stale_days_from_last_snapshot(self):
        acc = _account()
        _snapshot('2026-08', timezone.localdate() - dt.timedelta(days=40), 10000, account=acc)
        _snapshot('2026-09', timezone.localdate() - dt.timedelta(days=3), 12000, account=acc)

        assert build_networth_bridge()['summary']['stale_days'] == 3


@pytest.mark.django_db
class TestScope:
    def test_other_user_bills_are_excluded(self):
        acc = _account()
        _snapshot('2026-08', D(2026, 8, 1), 10000, account=acc)
        _snapshot('2026-09', D(2026, 9, 1), 10000, account=acc)
        _bill(D(2026, 8, 10), '收入', 8888, user_id=2)

        p = _latest()
        assert p['income'] == 0
        assert p['unexplained'] == 0

    def test_empty_dataset_returns_empty(self):
        data = build_networth_bridge()
        assert data['periods'] == []
        assert data['latest'] is None
        assert data['as_of'] is None
        assert data['summary']['identity_ok'] is True

    def test_single_snapshot_has_no_period(self):
        _snapshot('2026-09', D(2026, 9, 1), 10000, account=_account())

        data = build_networth_bridge()
        assert data['periods'] == []
        assert data['as_of'] == '2026-09'
