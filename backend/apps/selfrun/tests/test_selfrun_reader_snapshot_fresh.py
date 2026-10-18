"""自我运转 · `wealth.snapshot_fresh`（资产盘点）取数器 —— 6 条（v3.62.34）

🔴 这一组钉住的是**「溯源没有信息量」**这一类问题：

① **一条溯源只给日期 + 次数**
   `breakdown` 原来只有 `{'label': 日期, 'value': 1}`，界面上就是
   「2026-10-03 ……… 1」。对「本月盘过 1 次」这个 KPI，那个 `1` 不是信息，
   是复述它自己；用户想确认的是**这一期盘成了什么样**
   （几个科目、总资产多少、负债多少、净资产多少）。

② **备注键名对不上**（同一类错第二次）
   后端给 `extra.remarks`，前端 `ReadingCard` 读 `extra.note`
   ⇒ 备注（「猫咪承诺的6000到账」）一次都没显示过。两个键名都「看着合理」。

③ **汇总必须复用 `rollup_items`**（唯一实现）
   资产盘点页已经有一份汇总，这里再手写一遍求和 = 第二把尺子。
   两处一旦在「自用资产 / `include_in_balance_sheet`」这类边界上分叉，
   分叉是静默的：两个数都「看着合理」，但永远对不上。

④ **`value` 不许拿来装金额**
   溯源行的 `value` 之和必须等于「自动取到的值」，否则「溯源」二字不成立。
   金额放进 `extra.facts`，与次数并列而不挤占它。
"""
import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.selfrun.models import SelfRunMetric, SelfRunStage
from apps.selfrun.services import compute_metric_reading
from apps.wealth.models import (
    WealthAssetAccount, WealthAssetSnapshot, WealthAssetSnapshotItem,
)
from apps.wealth.services.asset_service import rollup_items

pytestmark = pytest.mark.django_db

URL = '/api/selfrun'


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def asset_metric(client):
    """建一个只含「资产盘点」的阶段，返回那条 metric。"""
    today = timezone.localdate()
    resp = client.post(f'{URL}/stages/', {
        'name': '资产测试阶段',
        'start_date': str(today - dt.timedelta(days=40)),
        'metrics': [{'template_key': 'asset_checkup'}],
    }, format='json')
    assert resp.status_code == 201, resp.data
    stage = SelfRunStage.objects.get()
    return stage.metrics.get(template_key='asset_checkup')


def _acct(name, *, category='流动性', kind='储蓄卡', liquid=True, in_sheet=True):
    return WealthAssetAccount.objects.create(
        name=name, category=category, account_kind=kind,
        is_liquid=liquid, include_in_balance_sheet=in_sheet,
        sort=0, is_active=True, user_id=1,
    )


def _snapshot(items, *, borrow=0.0, remarks='', day=None):
    """造一期快照 + 若干明细行。`day` 缺省取今天（必落在本月区间内）。"""
    day = day or timezone.localdate()
    snap = WealthAssetSnapshot.objects.create(
        yearmon=f'{day:%Y-%m}', snapshot_date=day,
        borrow=borrow, lend=0.0, remarks=remarks, user_id=1,
    )
    for acct, amt in items:
        WealthAssetSnapshotItem.objects.create(snapshot=snap, account=acct, amount=amt)
    return snap


def _facts(reading):
    """`extra.facts` → `{label: 项}`，方便按语义取值而不是按下标。"""
    return {f['label']: f for f in reading['breakdown'][0]['extra']['facts']}


def _month_range():
    today = timezone.localdate()
    return today.replace(day=1), today.replace(day=1) + dt.timedelta(days=31)


class TestBreakdownCarriesTheSnapshot:

    def test_facts_describe_what_was_counted(self, asset_metric):
        """一次盘点 = 一行溯源，但这一行要说得清盘成了什么样。"""
        _snapshot([
            (_acct('支付宝'), 10000.0),
            (_acct('微信'), 300.0),
        ], borrow=300.0, remarks='猫咪承诺的6000到账')

        r = compute_metric_reading(asset_metric, *_month_range())
        facts = _facts(r)

        assert facts['科目']['value'] == 2
        assert facts['总资产']['value'] == 10300.0
        assert facts['负债']['value'] == 300.0
        assert facts['净资产']['value'] == 10000.0

    def test_facts_match_rollup_items_exactly(self, asset_metric):
        """🔴 与资产盘点页的汇总**同一个函数**算出来 —— 不允许第二把尺子。

        这条不写死数字：直接拿 `rollup_items` 对同一批明细求值再比。
        若以后谁在这里手写一遍求和，自用资产 / 不计表科目那类边界
        就会先在这条用例上红。
        """
        a1, a2 = _acct('支付宝'), _acct('建设银行', liquid=False)
        _snapshot([(a1, 10000.0), (a2, 206752.88)], borrow=11500.0)

        r = compute_metric_reading(asset_metric, *_month_range())
        facts = _facts(r)
        roll = rollup_items([(10000.0, a1), (206752.88, a2)], borrow=11500.0)

        assert facts['总资产']['value'] == roll['total_assets']
        assert facts['负债']['value'] == roll['borrow']
        assert facts['净资产']['value'] == roll['net_worth']
        assert facts['科目']['value'] == roll['counted_count']

    def test_note_key_is_the_one_frontend_reads(self, asset_metric):
        """🔴 备注键名只能是 `note`。

        前端 `ReadingCard` 读 `extra.note`；写成 `remarks` / `notes`
        既不报错也不影响判定 —— 备注就是**永远不显示**。
        """
        _snapshot([(_acct('支付宝'), 1.0)], remarks='猫咪承诺的6000到账')

        r = compute_metric_reading(asset_metric, *_month_range())
        extra = r['breakdown'][0]['extra']

        assert extra['note'] == '猫咪承诺的6000到账'
        assert 'remarks' not in extra
        assert 'notes' not in extra

    def test_l2_is_the_period_not_the_snapshot_date(self, asset_metric):
        """盘点日 ≠ 所属期：10-03 盘的是 10 月这一期，光有日期说明不了是哪一期。"""
        _snapshot([(_acct('支付宝'), 1.0)])

        r = compute_metric_reading(asset_metric, *_month_range())
        b = r['breakdown'][0]

        assert b['l2'] == f'{timezone.localdate():%Y-%m}'
        assert b['label'] == str(timezone.localdate())

    def test_self_use_asset_is_reported_but_not_in_net_worth(self, asset_metric):
        """自用资产（房/车）`include_in_balance_sheet=False`：
        净资产里不该有它，但**必须说出来它在**（否则净资产看着少一块却不知道为什么）。"""
        _snapshot([
            (_acct('支付宝'), 10000.0),
            (_acct('房子', category='自用', kind='房产', liquid=False, in_sheet=False), 500000.0),
        ], borrow=0.0)

        r = compute_metric_reading(asset_metric, *_month_range())
        facts = _facts(r)

        assert facts['净资产']['value'] == 10000.0          # 房子不进净资产
        assert facts['未计表']['value'] == 500000.0         # 但要说出来
        assert facts['科目']['value'] == 1                  # 计表科目数也不含它

    def test_value_stays_one_per_snapshot(self, asset_metric):
        """🔴 `value` 是「盘了 1 次」，不是金额。

        溯源的恒等式：`sum(breakdown[].value) == auto_value`。
        把金额塞进 `value` 会让「溯源 N 条」下面加起来是个几万块，
        和上面「1 次」对不上 —— 那种不一致最容易被当成「口径不同」放过。
        """
        _snapshot([(_acct('支付宝'), 10000.0), (_acct('微信'), 300.0)])

        r = compute_metric_reading(asset_metric, *_month_range())

        assert r['auto_value'] == 1.0
        assert sum(b['value'] for b in r['breakdown']) == r['auto_value']
