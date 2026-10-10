"""资产科目主数据 / 资产快照（v3.58.21，P1-B）

覆盖：
  ① 种子科目：9 个（旧表 8 个账户列 + 借出款）、幂等、默认不覆盖用户改动
  ② 科目 CRUD：code 唯一（重复 400）、空 code 可多行、被快照引用时删除 400
  ③ 汇总恒等式：total_assets = financial_assets + self_use_total；
     net_worth = total_assets − borrow；available_net_worth 剔除自用资产
  ④ liquid_total 只认 is_liquid；类别合计恒 4 行（缺失补 0）
  ⑤ include_in_balance_sheet=False 不进任何合计，但仍进明细与 excluded_total
  ⑥ 快照按 yearmon 幂等、明细全删重建、不允许改年月
  ⑦ 写校验：负金额 400、停用科目 400、重复科目 400、年月格式 400
  ⑧ 回填：前置检查（科目未建即中止、不写半截数据）+ 幂等（重跑是覆盖不是新建）
  ⑨ 列表返回**裸数组** —— 防被全局分页包成 {count, results} 后前端静默显示为空

（v3.60.7 退役「双跑对账」：回填已执行完毕，两边同源，比对退化成恒等式，
  且它对旧表「同月两行」的期次会选到与回填不同的行、给出假差额 —— 相关用例一并删除。）

三张新表由 conftest 的 session 级 django_db_setup 镜像建表
（--no-migrations --reuse-db 下新表不会自动出现）。
"""
from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.wealth.constants import ASSET_CATEGORIES, LEGACY_ASSET_ACCOUNTS
from apps.wealth.models import (
    WealthAssetAccount,
    WealthAssetSnapshot,
    WealthAssetSnapshotItem,
    WealthCashFlow,
)
from apps.wealth.services.asset_service import (
    backfill_from_legacy,
    get_account_list,
    get_account_summary,
    get_snapshot_by_yearmon,
    list_snapshots,
    rollup_items,
    seed_asset_accounts,
)

ACC_URL = '/api/wealth/asset/accounts/'
SNAP_URL = '/api/wealth/asset/snapshots/'
SEED_CODES = {row[0] for row in LEGACY_ASSET_ACCOUNTS}


def _acct(**kw) -> WealthAssetAccount:
    base = dict(
        name='测试科目', category='流动性', account_kind='储蓄卡',
        is_liquid=True, include_in_balance_sheet=True, sort=0,
        is_active=True, user_id=1,
    )
    base.update(kw)
    return WealthAssetAccount.objects.create(**base)


def _legacy(yearmon='2099-06', **kw) -> WealthCashFlow:
    base = dict(
        yearmon=yearmon, btime=date(2099, 6, 30),
        zplay=0, wechat=0, cash=0, jianbank=0, gongbank=0,
        zhongbank=0, nongbank=0, accumulationfund=0, lend=0, borrow=0,
    )
    base.update(kw)
    return WealthCashFlow.objects.create(**base)


# ══════════════════════════════════════════════════════════════
# ① 种子科目
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestSeedAccounts:

    def test_seed_creates_all_legacy_accounts(self):
        result = seed_asset_accounts()
        assert result['created'] == len(LEGACY_ASSET_ACCOUNTS) == 9
        codes = set(WealthAssetAccount.objects.values_list('code', flat=True))
        assert codes == SEED_CODES

    def test_seed_marks_liquid_flags_correctly(self):
        """公积金与借出款都不是 T+0 可取 —— 不能进应急金分子"""
        seed_asset_accounts()
        by_code = {a.code: a for a in WealthAssetAccount.objects.all()}
        assert by_code['zplay'].is_liquid is True
        assert by_code['cash'].is_liquid is True
        assert by_code['accumulationfund'].is_liquid is False
        assert by_code['lend'].is_liquid is False

    def test_seed_puts_lend_into_receivable_category(self):
        """借出款是资产（应收类），负债不是 —— 负债留在快照头"""
        seed_asset_accounts()
        lend_acct = WealthAssetAccount.objects.get(code='lend')
        assert lend_acct.category == '应收'
        assert not WealthAssetAccount.objects.filter(code='borrow').exists()

    def test_seed_is_idempotent(self):
        first = seed_asset_accounts()
        second = seed_asset_accounts()
        assert first['created'] == 9
        assert second['created'] == 0
        assert second['kept'] == 9
        assert WealthAssetAccount.objects.count() == 9

    def test_seed_does_not_clobber_user_edits(self):
        """默认不覆盖：用户在界面上改过的类别不能被种子定义冲回去"""
        seed_asset_accounts()
        obj = WealthAssetAccount.objects.get(code='cash')
        obj.category = '投资性'
        obj.is_liquid = False
        obj.save()

        seed_asset_accounts()

        obj.refresh_from_db()
        assert obj.category == '投资性'
        assert obj.is_liquid is False

    def test_seed_overwrite_restores_defaults(self):
        seed_asset_accounts()
        obj = WealthAssetAccount.objects.get(code='cash')
        obj.category = '投资性'
        obj.save()

        result = seed_asset_accounts(overwrite=True)

        assert result['updated'] == 9
        assert WealthAssetAccount.objects.get(code='cash').category == '流动性'

    def test_seed_builds_blank_code_beside_seeded(self):
        """种子科目有 code，手工新增的科目 code 为空，两者互不冲突"""
        seed_asset_accounts()
        _acct(name='证券账户', code=None, category='投资性', is_liquid=False)
        assert WealthAssetAccount.objects.count() == 10


# ══════════════════════════════════════════════════════════════
# ② 科目 CRUD
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAccountApi:

    def test_list_returns_bare_array(self):
        """裸数组断言 —— 被全局分页包成 {count, results} 会让前端静默显示为空"""
        _acct(name='A')
        r = APIClient().get(ACC_URL)
        assert r.status_code == 200
        assert isinstance(r.data, list)
        assert len(r.data) == 1

    def test_list_excludes_inactive_by_default(self):
        _acct(name='在用')
        _acct(name='停用中', is_active=False)
        c = APIClient()
        assert len(c.get(ACC_URL).data) == 1
        assert len(c.get(ACC_URL + '?include_inactive=1').data) == 2

    def test_list_sorted_by_category_order_then_sort(self):
        _acct(name='自用资产', category='自用', sort=1)
        _acct(name='活期B', category='流动性', sort=20)
        _acct(name='活期A', category='流动性', sort=10)
        names = [a['name'] for a in get_account_list()]
        assert names == ['活期A', '活期B', '自用资产']

    def test_create_returns_full_row(self):
        r = APIClient().post(ACC_URL, {
            'name': '证券账户', 'category': '投资性', 'account_kind': '证券账户',
            'is_liquid': False, 'include_in_balance_sheet': True,
        }, format='json')
        assert r.status_code == 201
        assert r.data['name'] == '证券账户'
        assert r.data['category'] == '投资性'
        assert r.data['used_snapshot_count'] == 0

    def test_create_rejects_unknown_category(self):
        r = APIClient().post(ACC_URL, {'name': 'X', 'category': '不存在'}, format='json')
        assert r.status_code == 400

    def test_duplicate_code_returns_400_not_500(self):
        """(user_id, code) 是唯一键，但模型上没写 unique=True（要允许多行 NULL），
        DRF 不会自动校验 —— 手写的 validate_code 必须拦住，否则是 IntegrityError 500"""
        c = APIClient()
        assert c.post(ACC_URL, {'name': 'A', 'code': 'zplay'}, format='json').status_code == 201
        r = c.post(ACC_URL, {'name': 'B', 'code': 'zplay'}, format='json')
        assert r.status_code == 400
        assert 'zplay' in str(r.data)

    def test_blank_code_can_repeat(self):
        """空 code 归一为 NULL；MySQL 唯一索引允许多个 NULL"""
        c = APIClient()
        assert c.post(ACC_URL, {'name': 'A', 'code': ''}, format='json').status_code == 201
        assert c.post(ACC_URL, {'name': 'B', 'code': ''}, format='json').status_code == 201
        assert WealthAssetAccount.objects.count() == 2
        assert all(a.code is None for a in WealthAssetAccount.objects.all())

    def test_patch_updates_flags(self):
        obj = _acct(name='某卡', is_liquid=True)
        r = APIClient().patch(f'{ACC_URL}{obj.id}/', {
            'is_liquid': False, 'include_in_balance_sheet': False,
        }, format='json')
        assert r.status_code == 200
        obj.refresh_from_db()
        assert obj.is_liquid is False
        assert obj.include_in_balance_sheet is False

    def test_delete_unreferenced_account_ok(self):
        obj = _acct(name='待删')
        r = APIClient().delete(f'{ACC_URL}{obj.id}/')
        assert r.status_code == 200
        assert not WealthAssetAccount.objects.filter(id=obj.id).exists()

    def test_delete_referenced_account_returns_400(self):
        """被历史快照引用即不可删 —— 删掉会把往期净资产悄悄挖空"""
        acct = _acct(name='被引用')
        snapshot = WealthAssetSnapshot.objects.create(yearmon='2099-01', user_id=1)
        WealthAssetSnapshotItem.objects.create(snapshot=snapshot, account=acct, amount=100)

        r = APIClient().delete(f'{ACC_URL}{acct.id}/')

        assert r.status_code == 400
        assert '停用' in str(r.data)
        assert WealthAssetAccount.objects.filter(id=acct.id).exists()

    def test_summary_counts_structure_only(self):
        _acct(name='活期', category='流动性', is_liquid=True)
        _acct(name='自用', category='自用', is_liquid=False, include_in_balance_sheet=False)
        _acct(name='停用', is_active=False)
        s = get_account_summary()
        assert s['total'] == 3
        assert s['active_count'] == 2
        assert s['inactive_count'] == 1
        assert s['liquid_count'] == 1
        assert s['excluded_count'] == 1
        assert len(s['by_category']) == len(ASSET_CATEGORIES)

    def test_seed_endpoint(self):
        r = APIClient().post(ACC_URL + 'seed/', {}, format='json')
        assert r.status_code == 200
        assert r.data['created'] == 9
        assert r.data['overwrite'] is False


# ══════════════════════════════════════════════════════════════
# ③④⑤ 汇总口径（roll-up）
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestRollup:

    def test_identity_two_equations(self):
        """total_assets = financial_assets + self_use_total
           net_worth   = total_assets − borrow"""
        rows = [
            (10000, _acct(name='活期', category='流动性', is_liquid=True)),
            (50000, _acct(name='公积金', category='流动性', is_liquid=False)),
            (200000, _acct(name='房', category='自用', is_liquid=False,
                           include_in_balance_sheet=True)),
        ]
        r = rollup_items(rows, borrow=30000)
        assert r['financial_assets'] == 60000
        assert r['self_use_total'] == 200000
        assert r['total_assets'] == 260000
        assert r['total_assets'] == r['financial_assets'] + r['self_use_total']
        assert r['net_worth'] == 230000
        assert r['net_worth'] == r['total_assets'] - r['borrow']

    def test_available_net_worth_excludes_self_use(self):
        """「能变成钱的净值」—— 自用资产计进去会让净资产看着漂亮却无法变现"""
        rows = [
            (10000, _acct(name='活期', category='流动性')),
            (200000, _acct(name='房', category='自用', is_liquid=False,
                           include_in_balance_sheet=True)),
        ]
        r = rollup_items(rows, borrow=5000)
        assert r['net_worth'] == 205000
        assert r['available_net_worth'] == 5000

    def test_liquid_total_only_counts_is_liquid(self):
        """公积金是「类别=流动性 但不可随时取」的典型，不能进应急金分子"""
        rows = [
            (10000, _acct(name='活期', category='流动性', is_liquid=True)),
            (50000, _acct(name='公积金', category='流动性', is_liquid=False)),
        ]
        r = rollup_items(rows)
        assert r['liquid_total'] == 10000
        assert r['category_totals']['流动性'] == 60000

    def test_category_totals_always_four_keys(self):
        """类别合计恒返回全部键（缺失补 0）—— 前端按固定顺序渲染，不必自己补空行"""
        r = rollup_items([(100, _acct(name='A', category='流动性'))])
        assert set(r['category_totals']) == set(ASSET_CATEGORIES)
        assert r['category_totals']['自用'] == 0

    def test_excluded_account_out_of_totals_but_in_detail(self):
        rows = [
            (10000, _acct(name='活期', category='流动性')),
            (200000, _acct(name='房', category='自用', is_liquid=False,
                           include_in_balance_sheet=False)),
        ]
        r = rollup_items(rows)
        assert r['total_assets'] == 10000
        assert r['self_use_total'] == 0
        assert r['excluded_total'] == 200000      # 不静默吞掉，单独提示
        assert r['item_count'] == 2               # 明细仍完整保留
        assert r['counted_count'] == 1

    def test_empty_snapshot_no_division_by_zero(self):
        r = rollup_items([], borrow=0)
        assert r['total_assets'] == 0
        assert r['net_worth'] == 0
        assert r['available_net_worth'] == 0
        assert r['liquid_total'] == 0

    def test_negative_net_worth_not_absolutised(self):
        """负债大于资产时净资产必须为负 —— 不得取绝对值或截断为 0"""
        r = rollup_items([(1000, _acct(name='活期', category='流动性'))], borrow=50000)
        assert r['net_worth'] == -49000
        assert r['available_net_worth'] == -49000


# ══════════════════════════════════════════════════════════════
# ⑥⑦ 快照读写与校验
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestSnapshotApi:

    def _two_accounts(self):
        return _acct(name='活期', category='流动性', is_liquid=True, sort=10), \
               _acct(name='公积金', category='流动性', is_liquid=False, sort=20)

    def test_list_returns_bare_array(self):
        r = APIClient().get(SNAP_URL)
        assert r.status_code == 200
        assert isinstance(r.data, list)

    def test_save_is_idempotent_by_yearmon(self):
        a, _ = self._two_accounts()
        c = APIClient()
        c.post(SNAP_URL, {
            'yearmon': '2099-06', 'borrow': 0, 'items': [{'account_id': a.id, 'amount': 100}],
        }, format='json')
        c.post(SNAP_URL, {
            'yearmon': '2099-06', 'borrow': 0, 'items': [{'account_id': a.id, 'amount': 300}],
        }, format='json')
        assert WealthAssetSnapshot.objects.filter(yearmon='2099-06').count() == 1
        row = get_snapshot_by_yearmon('2099-06')
        assert row['items'][0]['amount'] == 300

    def test_items_are_fully_replaced(self):
        """明细全删重建 —— 逐行 diff 的收益很小，漏删一行的代价是钱被算两遍"""
        a, b = self._two_accounts()
        c = APIClient()
        c.post(SNAP_URL, {
            'yearmon': '2099-07',
            'items': [{'account_id': a.id, 'amount': 100}, {'account_id': b.id, 'amount': 200}],
        }, format='json')
        c.post(SNAP_URL, {
            'yearmon': '2099-07', 'items': [{'account_id': a.id, 'amount': 100}],
        }, format='json')
        row = get_snapshot_by_yearmon('2099-07')
        assert row['item_count'] == 1
        assert WealthAssetSnapshotItem.objects.count() == 1

    def test_snapshot_list_carries_rollup(self):
        a, _ = self._two_accounts()
        APIClient().post(SNAP_URL, {
            'yearmon': '2099-08', 'borrow': 5000,
            'items': [{'account_id': a.id, 'amount': 8000}],
        }, format='json')
        rows = list_snapshots()
        assert len(rows) == 1
        assert rows[0]['liquid_total'] == 8000
        assert rows[0]['total_assets'] == 8000
        assert rows[0]['net_worth'] == 3000
        # 列表刻意不带明细（省流量），详情接口才有
        assert 'items' not in rows[0]

    def test_detail_includes_items_with_account_attrs(self):
        a, _ = self._two_accounts()
        r = APIClient().post(SNAP_URL, {
            'yearmon': '2099-09', 'items': [{'account_id': a.id, 'amount': 1234}],
        }, format='json')
        assert r.status_code == 201
        detail = APIClient().get(f"{SNAP_URL}{r.data['id']}/").data
        assert detail['item_count'] == 1
        assert detail['items'][0]['name'] == '活期'
        assert detail['items'][0]['is_liquid'] is True
        assert detail['items'][0]['amount'] == 1234

    def test_rejects_negative_amount(self):
        a, _ = self._two_accounts()
        r = APIClient().post(SNAP_URL, {
            'yearmon': '2099-10', 'items': [{'account_id': a.id, 'amount': -1}],
        }, format='json')
        assert r.status_code == 400

    def test_rejects_inactive_account(self):
        a = _acct(name='已停用', is_active=False)
        r = APIClient().post(SNAP_URL, {
            'yearmon': '2099-10', 'items': [{'account_id': a.id, 'amount': 100}],
        }, format='json')
        assert r.status_code == 400
        assert '停用' in str(r.data)

    def test_rejects_duplicate_account_in_one_snapshot(self):
        a, _ = self._two_accounts()
        r = APIClient().post(SNAP_URL, {
            'yearmon': '2099-10',
            'items': [{'account_id': a.id, 'amount': 1}, {'account_id': a.id, 'amount': 2}],
        }, format='json')
        assert r.status_code == 400

    def test_rejects_unknown_account(self):
        r = APIClient().post(SNAP_URL, {
            'yearmon': '2099-10', 'items': [{'account_id': 999999, 'amount': 1}],
        }, format='json')
        assert r.status_code == 400

    def test_rejects_bad_yearmon_format(self):
        a, _ = self._two_accounts()
        r = APIClient().post(SNAP_URL, {
            'yearmon': '2099/10', 'items': [{'account_id': a.id, 'amount': 1}],
        }, format='json')
        assert r.status_code == 400

    def test_update_rejects_yearmon_change(self):
        """年月是这一期的身份；改年月等于换一期，必须删除重建"""
        a, _ = self._two_accounts()
        created = APIClient().post(SNAP_URL, {
            'yearmon': '2099-11', 'items': [{'account_id': a.id, 'amount': 100}],
        }, format='json').data
        r = APIClient().put(f"{SNAP_URL}{created['id']}/", {
            'yearmon': '2099-12', 'items': [{'account_id': a.id, 'amount': 100}],
        }, format='json')
        assert r.status_code == 400
        assert '年月' in str(r.data)

    def test_update_same_yearmon_ok(self):
        a, _ = self._two_accounts()
        created = APIClient().post(SNAP_URL, {
            'yearmon': '2099-11', 'items': [{'account_id': a.id, 'amount': 100}],
        }, format='json').data
        r = APIClient().put(f"{SNAP_URL}{created['id']}/", {
            'yearmon': '2099-11', 'borrow': 20,
            'items': [{'account_id': a.id, 'amount': 500}],
        }, format='json')
        assert r.status_code == 200
        assert r.data['borrow'] == 20
        assert r.data['net_worth'] == 480

    def test_delete_snapshot_cascades_items(self):
        a, _ = self._two_accounts()
        created = APIClient().post(SNAP_URL, {
            'yearmon': '2099-11', 'items': [{'account_id': a.id, 'amount': 100}],
        }, format='json').data
        assert APIClient().delete(f"{SNAP_URL}{created['id']}/").status_code == 200
        assert WealthAssetSnapshot.objects.count() == 0
        assert WealthAssetSnapshotItem.objects.count() == 0

    def test_receivable_gap_flagged(self):
        """应收类科目合计与快照头 lend 不一致时给差额（只报差额，不改数据）"""
        acct = _acct(name='借出款', category='应收', is_liquid=False)
        r = APIClient().post(SNAP_URL, {
            'yearmon': '2099-11', 'lend': 30000,
            'items': [{'account_id': acct.id, 'amount': 25000}],
        }, format='json')
        assert r.data['receivable_gap'] == -5000

    def test_by_yearmon_endpoint(self):
        a, _ = self._two_accounts()
        APIClient().post(SNAP_URL, {
            'yearmon': '2099-05', 'items': [{'account_id': a.id, 'amount': 100}],
        }, format='json')
        assert APIClient().get(SNAP_URL + 'by_yearmon/?yearmon=2099-05').status_code == 200
        assert APIClient().get(SNAP_URL + 'by_yearmon/').status_code == 400
        assert APIClient().get(SNAP_URL + 'by_yearmon/?yearmon=2000-01').status_code == 404

    def test_list_limit(self):
        a, _ = self._two_accounts()
        c = APIClient()
        for ym in ('2099-01', '2099-02', '2099-03'):
            c.post(SNAP_URL, {
                'yearmon': ym, 'items': [{'account_id': a.id, 'amount': 1}],
            }, format='json')
        assert len(c.get(SNAP_URL + '?limit=2').data) == 2
        # 倒序：最近的在前
        assert c.get(SNAP_URL + '?limit=2').data[0]['yearmon'] == '2099-03'


# ══════════════════════════════════════════════════════════════
# ⑧⑨ 与旧口径的双跑校验 / 回填
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestLegacyBackfill:

    def _legacy_row(self, yearmon='2099-06'):
        return _legacy(
            yearmon=yearmon, btime=date(2099, 6, 30),
            zplay=1000, wechat=2000, cash=500, jianbank=30000,
            accumulationfund=50000, lend=30000, borrow=50000,
        )

    def test_backfill_aborts_without_seeded_accounts(self):
        """半途而废的回填比不回填更糟：缺科目的快照看着"成功了"，总额却少一截"""
        self._legacy_row()
        result = backfill_from_legacy(yearmon='2099-06')
        assert result['ok'] is False
        assert result['reason'] == 'missing_accounts'
        assert WealthAssetSnapshot.objects.count() == 0

    def test_backfill_creates_snapshot_then_is_idempotent(self):
        seed_asset_accounts()
        self._legacy_row()

        first = backfill_from_legacy(yearmon='2099-06')
        assert first['ok'] is True
        assert first['created'] == 1
        assert first['scanned'] == 1

        second = backfill_from_legacy(yearmon='2099-06')
        assert second['created'] == 0
        assert second['updated'] == 1
        assert WealthAssetSnapshot.objects.count() == 1
