"""顶部三块与六项比率同源（2026-09-29 合并资产录入链路）

这轮之前：`cashflow_service` 只看旧表 `wealth_cash_flow`，而 `ratio_service`
「有新体系快照就整条切新体系」—— 同一次月末盘点要填两遍，且两块趋势的期数
会分叉（开发库实测：旧表 18 期 / 新体系 1 期），界面上看不出来。

本轮把「取哪一套、取哪几期」收敛到 `ratio_service.resolve_asset_*` 一处，
本文件钉住五条不该退化的性质：

  ① 新体系有快照 ⇒ 顶部三块**整体**用新体系（不再偷偷读旧表）
  ② 新体系没有    ⇒ 回落旧表（回退保险还在）
  ③ 新体系的「金融资产」**含应收借出** —— 与旧表 8 列口径不同，是刻意的
  ④ 趋势与比率取到**同一批期次**
  ⑤ 回填与 `get_snapshot_series()` 用同一套「同月取哪一行」口径

新表由 conftest 的 session 级 DDL 镜像建出（`--no-migrations --reuse-db`
下不会自动出现），故本文件每个测试类都必须带 `django_db` 标记。
"""
from datetime import date

import pytest

from apps.wealth.models import (
    WealthAssetAccount,
    WealthAssetSnapshot,
    WealthAssetSnapshotItem,
    WealthCashFlow,
)
from apps.wealth.services.asset_service import backfill_from_legacy, seed_asset_accounts
from apps.wealth.services.cashflow_service import (
    get_asset_trend,
    get_cashflow_by_yearmon,
    get_cashflow_overview,
    get_snapshot_list,
    get_snapshot_series,
)
from apps.wealth.services.ratio_service import resolve_asset_series, resolve_asset_source

SOURCE_SNAPSHOT = 'asset_snapshot'
SOURCE_LEGACY = 'legacy_cash_flow'


def _legacy(yearmon, btime, **kw) -> WealthCashFlow:
    base = dict(
        zplay=0, wechat=0, cash=0, jianbank=0, gongbank=0,
        zhongbank=0, nongbank=0, accumulationfund=0, lend=0, borrow=0,
    )
    base.update(kw)
    return WealthCashFlow.objects.create(yearmon=yearmon, btime=btime, **base)


def _acct(code, name, category='流动性', is_liquid=True, sort=10) -> WealthAssetAccount:
    return WealthAssetAccount.objects.create(
        code=code, name=name, category=category, account_kind='储蓄卡',
        is_liquid=is_liquid, include_in_balance_sheet=True,
        sort=sort, is_active=True, user_id=1,
    )


def _snap(yearmon, d, items, borrow=0.0, lend=0.0) -> WealthAssetSnapshot:
    snap = WealthAssetSnapshot.objects.create(
        yearmon=yearmon, snapshot_date=d, borrow=borrow, lend=lend, user_id=1,
    )
    for acct, amount in items:
        WealthAssetSnapshotItem.objects.create(snapshot=snap, account=acct, amount=amount)
    return snap


# ══════════════════════════════════════════════════════════════
# ①②③ 顶部三块跟随统一来源
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestOverviewFollowsUnifiedSource:

    def test_snapshot_wins_over_legacy(self):
        """新体系有快照时，顶部三块必须整体用新体系 —— 否则又变成两边各一套"""
        _legacy('2026-06', date(2026, 6, 30), zplay=99999)
        acct = _acct('zplay', '支付宝')
        _snap('2026-06', date(2026, 6, 30), [(acct, 100)])

        assert resolve_asset_source() == SOURCE_SNAPSHOT
        overview = get_cashflow_overview()
        assert overview['yearmon'] == '2026-06'
        assert overview['accounts']['zplay'] == 100      # 不是旧表的 99999

    def test_falls_back_to_legacy_when_no_snapshot(self):
        """回退保险：一条新体系快照都没有时，仍然读旧表"""
        _legacy('2026-06', date(2026, 6, 30), zplay=777)

        assert resolve_asset_source() == SOURCE_LEGACY
        assert get_cashflow_overview()['accounts']['zplay'] == 777

    def test_financial_assets_includes_receivable(self):
        """新体系「金融资产」含应收借出 —— 与旧表 8 列口径不同，是刻意的"""
        cash = _acct('cash', '现金')
        lend = _acct('lend', '借出款', category='应收', is_liquid=False)
        _snap('2026-06', date(2026, 6, 30), [(cash, 1000), (lend, 300)])

        overview = get_cashflow_overview()
        assert overview['summary']['financial_assets'] == 1300
        # 应收借出是「金融资产」的明细拆解，不是并列的另一项
        assert overview['summary']['lend'] == 300
        assert overview['summary']['net_worth'] == 1300

    def test_liquid_excludes_receivable_and_provident_fund(self):
        """应急金分子只认 is_liquid —— 借出款与公积金都不算"""
        cash = _acct('cash', '现金')
        lend = _acct('lend', '借出款', category='应收', is_liquid=False)
        pf = _acct('accumulationfund', '公积金', category='投资性', is_liquid=False)
        _snap('2026-06', date(2026, 6, 30), [(cash, 1000), (lend, 300), (pf, 5000)])

        assert get_cashflow_overview()['summary']['flow_total'] == 1000


# ══════════════════════════════════════════════════════════════
# ④ 趋势与比率同源同期次
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestTrendAndRatioShareSource:

    def test_trend_and_ratio_share_same_periods(self):
        """趋势与比率必须落在同一批期次上 —— 分叉了界面上看不出来"""
        acct = _acct('cash', '现金')
        _snap('2026-05', date(2026, 5, 31), [(acct, 100)])
        _snap('2026-06', date(2026, 6, 30), [(acct, 200)])

        trend_months = [t['yearmon'] for t in get_asset_trend(months=12)]
        ratio_months = sorted(p['yearmon'] for p in resolve_asset_series().values())
        assert trend_months == ratio_months == ['2026-05', '2026-06']

    def test_trend_has_no_duplicate_months_after_switch(self):
        """切源不能把「一期一条」丢掉 —— 同月重复会让趋势图同一 x 出现两个 y"""
        acct = _acct('cash', '现金')
        _snap('2026-05', date(2026, 5, 31), [(acct, 100)])
        _snap('2026-06', date(2026, 6, 30), [(acct, 200)])

        months = [t['yearmon'] for t in get_asset_trend(months=12)]
        assert len(months) == len(set(months))

    def test_by_yearmon_hits_same_period_as_trend(self):
        acct = _acct('cash', '现金')
        _snap('2026-06', date(2026, 6, 30), [(acct, 200)])

        assert get_cashflow_by_yearmon('2026-06')['accounts']['cash'] == 200
        # 这一期真没有 → None（不是 0，也不是上一期的数）
        assert get_cashflow_by_yearmon('2026-05') is None

    def test_snapshot_list_follows_new_source(self):
        acct = _acct('cash', '现金')
        _snap('2026-05', date(2026, 5, 31), [(acct, 100)])
        _snap('2026-06', date(2026, 6, 30), [(acct, 200)])

        data = get_snapshot_list(page=1, page_size=12)
        assert data['total'] == 2
        assert [i['yearmon'] for i in data['items']] == ['2026-06', '2026-05']


# ══════════════════════════════════════════════════════════════
# ⑤ 回填与趋势线用同一套去重口径
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestBackfillDedupe:

    def test_backfill_uses_snapshot_series_dedupe(self):
        """同月两行时，回填取的必须是 `get_snapshot_series()` 认的那一行。

        回填原先自己 `order_by('yearmon')`，而 MySQL 对同月行的返回顺序
        **不保证** —— 一旦它选中的行与趋势线选中的不是同一行，回填出来的
        期次就和顶部趋势对不上，且两边都「看着正常」。
        """
        seed_asset_accounts()
        _legacy('2026-06', date(2026, 6, 3), zplay=100)
        _legacy('2026-06', date(2026, 6, 29), zplay=200)

        # 前置：去重口径认的是 btime 更晚的那一行
        assert get_snapshot_series()[0].zplay == 200

        result = backfill_from_legacy()
        assert result['ok'] is True
        assert WealthAssetSnapshot.objects.filter(yearmon='2026-06').count() == 1
        assert get_cashflow_overview()['accounts']['zplay'] == 200

    def test_backfill_single_month_filter(self):
        """--yearmon 只回填指定期"""
        seed_asset_accounts()
        _legacy('2026-05', date(2026, 5, 31), zplay=100)
        _legacy('2026-06', date(2026, 6, 30), zplay=200)

        backfill_from_legacy(yearmon='2026-06')
        assert set(WealthAssetSnapshot.objects.values_list('yearmon', flat=True)) == {'2026-06'}
