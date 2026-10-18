"""资产科目主数据 / 资产快照（v3.58.21，P1-B）

覆盖：
  ① 种子科目：9 个（旧表 8 个账户列 + 借出款）、幂等、默认不覆盖用户改动
  ② 科目 CRUD：code 唯一（重复 400）、空 code 可多行、被快照引用时删除 400、
     表单字段的校验消息必须中文化（回英文串 = 用户不知道该改哪一格）
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

from apps.wealth.constants import (
    ASSET_CATEGORIES,
    LEGACY_ASSET_ACCOUNTS,
    PROVIDENT_FUND_ACCOUNT_KEY,
)
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
from apps.wealth.services.cashflow_service import get_cashflow_overview
from apps.wealth.services.ratio_service import resolve_asset_position

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

    # ── 校验消息必须说人话（v3.62.18）──

    def test_over_long_code_is_rejected_with_chinese_hint(self):
        """映射码超长：既要拦住，也要说清是哪一格、怎么办。

        2026-10-16 现场：21 个字符的 `accumulationfund_ning` 被拒，
        后端回的是 DRF 默认英文 `Ensure this field has no more than
        20 characters.`，而前端那条链只认 `detail` ⇒ 字段级错误被吞成
        「保存失败」⇒ 用户只能来问「为什么失败」。

        本用例钉两件事：
          ① 超长被拒是 400（不是 IntegrityError 500，也不是放行后
             在 MySQL 严格模式下炸 1406）；
          ② 消息是中文、且带「映射码」三个字 —— 否则用户不知道指哪一格。
        """
        r = APIClient().post(ACC_URL, {
            'name': '公积金福建', 'code': 'accumulationfund_ning',
        }, format='json')
        assert r.status_code == 400
        msg = str(r.data['code'])
        assert '映射码' in msg
        assert 'Ensure this field' not in msg
        assert not WealthAssetAccount.objects.filter(name='公积金福建').exists()

    def test_code_at_exactly_20_chars_is_accepted(self):
        """20 是闭区间上限 —— 边界不许写成「小于 20」"""
        code = 'a' * 20
        r = APIClient().post(ACC_URL, {'name': '恰好20码', 'code': code}, format='json')
        assert r.status_code == 201
        assert WealthAssetAccount.objects.get(id=r.data['id']).code == code

    def test_form_field_errors_are_chinese(self):
        """四个可填字段的校验消息都得是中文（界面里冒英文等于没提示）"""
        c = APIClient()
        for payload, field, expected in [
            ({'name': ''}, 'name', '请填写科目名'),
            ({'name': 'X', 'institution': '浙' * 60}, 'institution', '机构最长 50 个字符'),
            ({'name': 'X', 'note': '浙' * 210}, 'note', '备注最长 200 个字符'),
        ]:
            r = c.post(ACC_URL, payload, format='json')
            assert r.status_code == 400, payload
            assert expected in str(r.data[field]), payload

    def test_two_provident_fund_accounts_can_coexist(self):
        """用户场景：公积金随工作变动会不断开户，要按省份区分余额。

        两条同类别、同账户形态、仅科目名与机构不同的记录必须都能建 ——
        科目名与 account_kind 都没有唯一约束（account_kind 是自由 CharField，
        不受任何枚举限制），区分账户本来就该靠「科目名 + 机构」。
        """
        c = APIClient()
        rows = [
            {'name': '公积金福建', 'institution': '宁德', 'code': 'accfund_fj'},
            {'name': '公积金浙江', 'institution': '浙江', 'code': 'accfund_zj'},
        ]
        for row in rows:
            r = c.post(ACC_URL, {
                'category': '投资性', 'account_kind': '公积金', **row,
            }, format='json')
            assert r.status_code == 201, r.data
        assert WealthAssetAccount.objects.filter(account_kind='公积金').count() == 2

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


# ══════════════════════════════════════════════════════════════
# ⑩ 公积金按**形态**汇总（v3.62.24）
# ══════════════════════════════════════════════════════════════
#
# 用户报的场景：新建一个公积金科目后，资产全景上「公积金」一栏恒显 ¥0.00。
# 根因：资产位置的取数键用的是**旧表列名** `accumulationfund`，而新体系里
# 科目 code 由用户自定（实测 `accfund_zj`）或为空 —— 那个键不存在
# ⇒ 前端读到 undefined ⇒ 显示 0，而且**全程不报错**
# （`accounts.get(key, 0.0)`，缺键和真 0 长得一模一样）。
# 影响面 5 处：汇总列 / 饼图 / 公积金占比 / 趋势线 / 快照历史列。
#
# 判据：**新体系里凡「跨科目的语义量」都必须按形态 / 类别取，不许按 code 取。**
# `code` 只是旧表列名的映射，服务于「初始化科目 + 回填历史快照」这条迁移路径。


@pytest.mark.django_db
class TestProvidentFundAggregation:

    def _snapshot(self, rows, yearmon='2026-10', lend=0.0):
        """rows: [(科目, 金额)] → 建一期快照。"""
        snap = WealthAssetSnapshot.objects.create(
            user_id=1, yearmon=yearmon, snapshot_date=date(2026, 10, 3),
            borrow=0, lend=lend,
        )
        for acct, amount in rows:
            WealthAssetSnapshotItem.objects.create(
                snapshot=snap, account=acct, amount=amount,
            )
        return snap

    def test_two_provident_fund_accounts_are_merged(self):
        """两个省份的公积金账户 → 合并成一条，且**不以各自 code 重复出现**"""
        zj = _acct(name='公积金浙江', code='accfund_zj', category='投资性',
                   account_kind='公积金', is_liquid=False)
        fj = _acct(name='公积金福建', code=None, category='投资性',
                   account_kind='公积金', is_liquid=False)
        self._snapshot([(zj, 48810.2), (fj, 2500)])

        accounts = get_cashflow_overview()['accounts']
        assert accounts[PROVIDENT_FUND_ACCOUNT_KEY] == 51310.2
        # 🔴 不得同时留着 code 键 —— 那会让同一笔钱在两个键里各出现一次（双计）
        assert 'accfund_zj' not in accounts

    def test_financial_assets_decompose_into_four(self):
        """金融资产 = 流动资金 + 非流动资金 + 公积金 + 应收借出（1 + 4 个拆解，不是五项并列）"""
        cash = _acct(name='现金', code='cash', account_kind='现金', is_liquid=True)
        pf = _acct(name='公积金浙江', code='accfund_zj', category='投资性',
                   account_kind='公积金', is_liquid=False)
        lend = _acct(name='借出款', code='lend', category='应收',
                     account_kind='其他', is_liquid=False)
        self._snapshot([(cash, 1000), (pf, 4000), (lend, 500)], lend=500)

        ov = get_cashflow_overview()
        s = ov['summary']
        assert ov['accounts'][PROVIDENT_FUND_ACCOUNT_KEY] == 4000
        assert s['flow_total'] == 1000
        assert s['non_liquid'] == 0
        assert s['lend'] == 500
        assert s['financial_assets'] == 5500
        assert (s['flow_total'] + s['non_liquid']
                + ov['accounts'][PROVIDENT_FUND_ACCOUNT_KEY]
                + s['lend']) == s['financial_assets']

    def test_provident_fund_not_in_emergency_fund(self):
        """另一侧：公积金**绝不**进应急金分子 —— 它撑不了应急"""
        cash = _acct(name='现金', code='cash', account_kind='现金', is_liquid=True)
        pf = _acct(name='公积金浙江', code='accfund_zj', category='投资性',
                   account_kind='公积金', is_liquid=False)
        self._snapshot([(cash, 1000), (pf, 90000)])
        assert get_cashflow_overview()['health_metrics']['emergency_fund'] == 1000

    def test_provident_fund_ratio_shares_the_same_source(self):
        """公积金占比的分子与「公积金」那一栏**同源**（不许做第二把尺子）"""
        pf = _acct(name='公积金浙江', code='accfund_zj', category='投资性',
                   account_kind='公积金', is_liquid=False)
        self._snapshot([(pf, 4000)])
        ov = get_cashflow_overview()
        assert ov['accounts'][PROVIDENT_FUND_ACCOUNT_KEY] == 4000
        assert ov['health_metrics']['provident_fund_ratio'] == 100.0

    def test_account_without_code_is_not_silently_dropped(self):
        """code 为空的普通科目**不许静默丢钱**（回落形态做键）

        旧实现 `if not code: continue` 会让这笔钱从**唯一口径真源**
        `resolve_asset_position()['accounts']` 里消失，而 `financial_assets`
        （走 rollup_items）仍算它 ⇒ 两边对不上且都不报错。

        ⚠️ 断言打在**真源层**，不打 `overview['accounts']` ——
        后者是旧表 8 列的固定形状（展示位写死），本来就不含用户自建科目。
        """
        sec = _acct(name='华泰证券', code=None, category='投资性',
                    account_kind='证券账户', is_liquid=False)
        self._snapshot([(sec, 7000)])

        pos = resolve_asset_position()
        assert pos['accounts'].get('证券账户') == 7000
        assert pos['financial_assets'] == 7000
        # 展示层仍是固定 8 键 —— 这是**已知限制**，不是 bug：
        # 要让新科目上饼图得把展示层改成按科目动态（独立一轮）。
        assert '证券账户' not in get_cashflow_overview()['accounts']

    def test_legacy_path_keeps_the_same_shape(self):
        """旧表路径仍下发 `accumulationfund` —— 两条路径同形状，消费方不必分支"""
        _legacy(yearmon='2099-06', cash=100, accumulationfund=1234)
        accounts = get_cashflow_overview()['accounts']
        assert accounts[PROVIDENT_FUND_ACCOUNT_KEY] == 1234
        assert accounts['cash'] == 100


# ══════════════════════════════════════════════════════════════
# ⑧ 金融资产的四行拆解必须「加得回去」（v3.62.28）
# ══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAssetDecomposition:
    """用户原话：「应该显示固定、不流动的那份资产，否则账面数据对不上」。

    改前界面上只有「流动资金」一行，`T+0 可取 = 否` 的余额
    **不属于任何一行** ⇒ 拆项之和比金融资产少一截，而两边各自都「看着正常」。
    这不是算错，是有一块根本不出现 —— 本项目最忌的静默失败。

    🔴 判据：拆解等式必须是**按定义**成立的（四桶互斥完备），
       而不是「此刻恰好成立」—— 判法见 `test_identity_holds_whatever_is_liquid`。
    """

    def _snapshot(self, rows, yearmon='2026-10', lend=0.0):
        snap = WealthAssetSnapshot.objects.create(
            user_id=1, yearmon=yearmon, snapshot_date=date(2026, 10, 3),
            borrow=0, lend=lend,
        )
        for acct, amount in rows:
            WealthAssetSnapshotItem.objects.create(
                snapshot=snap, account=acct, amount=amount,
            )
        return snap

    def test_non_liquid_bucket_fills_the_gap(self):
        """那 206,752.88 以前不属于任何一行 —— 现在它是「非流动资金」

        金额取自开发库 2026-10 那期的真实形状：三张储蓄卡被标成
        「T+0 可取 = 否」（用户自己拨的开关），于是它们从流动资金里消失，
        但**仍然计入金融资产** —— 中间那一截就是这轮补的那一行。
        """
        rows = [
            (_acct(name='支付宝', code='zplay', account_kind='第三方支付'), 31110.17),
            (_acct(name='微信', code='wechat', account_kind='第三方支付'), 12480.03),
            (_acct(name='现金', code='cash', account_kind='现金'), 3982.00),
            (_acct(name='建设银行', code='jianbank', is_liquid=False), 100624.81),
            (_acct(name='工商银行', code='gongbank', is_liquid=False), 30057.88),
            (_acct(name='中国银行', code='zhongbank', category='投资性', is_liquid=False), 76070.19),
            (_acct(name='农村信用社', code='nongbank'), 28.00),
            (_acct(name='公积金福建', code=None, category='投资性',
                   account_kind='公积金', is_liquid=False), 816.09),
            (_acct(name='公积金浙江', code='accfund_zj', category='投资性',
                   account_kind='公积金', is_liquid=False), 47994.09),
            (_acct(name='借出款', code='lend', category='应收',
                   account_kind='其他', is_liquid=False), 5000.00),
        ]
        self._snapshot(rows, lend=5000)

        ov = get_cashflow_overview()
        s = ov['summary']
        assert s['flow_total'] == 47600.20
        assert s['non_liquid'] == 206752.88      # ← 三张卡，以前界面上根本没有这一格
        assert ov['accounts'][PROVIDENT_FUND_ACCOUNT_KEY] == 48810.18
        assert s['lend'] == 5000
        assert s['financial_assets'] == 308163.26
        assert (s['flow_total'] + s['non_liquid']
                + ov['accounts'][PROVIDENT_FUND_ACCOUNT_KEY]
                + s['lend']) == s['financial_assets']

    def test_identity_holds_whatever_is_liquid(self):
        """把三个开关翻来翻去，等式恒成立 —— 它不依赖用户能改的任何东西

        这条才是「恒等式」的正当性所在：如果某个组合下它破了，
        说明桶没做到互斥完备，那它就只是「此刻恰好成立」的巧合。
        """
        cash = _acct(name='现金', code='cash', account_kind='现金')
        card = _acct(name='建设银行', code='jianbank', is_liquid=False)
        pf = _acct(name='公积金浙江', code='accfund_zj', category='投资性',
                   account_kind='公积金', is_liquid=False)
        lend = _acct(name='借出款', code='lend', category='应收',
                     account_kind='其他', is_liquid=False)
        self._snapshot([(cash, 1000), (card, 20000), (pf, 4000), (lend, 500)], lend=500)

        for card_liquid in (False, True):
            for pf_liquid in (False, True):
                for lend_liquid in (False, True):
                    WealthAssetAccount.objects.filter(id=card.id).update(is_liquid=card_liquid)
                    WealthAssetAccount.objects.filter(id=pf.id).update(is_liquid=pf_liquid)
                    WealthAssetAccount.objects.filter(id=lend.id).update(is_liquid=lend_liquid)

                    ov = get_cashflow_overview()
                    s = ov['summary']
                    parts = (s['flow_total'] + s['non_liquid']
                             + ov['accounts'][PROVIDENT_FUND_ACCOUNT_KEY] + s['lend'])
                    assert parts == s['financial_assets'] == 25500, (
                        f'card_liquid={card_liquid} pf_liquid={pf_liquid} '
                        f'lend_liquid={lend_liquid} → {parts} != {s["financial_assets"]}'
                    )

    def test_receivable_never_counts_as_liquid(self):
        """借出的钱即使被标成 T+0 可取，也不进「流动资金」

        口径收紧（v3.62.28）：旧表路径 `sum_liquid_accounts` 本来就不含借出，
        新体系若含它 ⇒ 切换来源时「流动资金」会凭空跳 5,000。
        """
        lend = _acct(name='借出款', code='lend', category='应收',
                     account_kind='其他', is_liquid=True)
        self._snapshot([(lend, 5000)], lend=5000)

        s = get_cashflow_overview()['summary']
        assert s['flow_total'] == 0
        assert s['lend'] == 5000
        assert s['non_liquid'] == 0
        assert s['financial_assets'] == 5000

    def test_provident_fund_never_counts_as_liquid(self):
        """公积金同理：只进「公积金」那一行，绝不同时出现在流动资金里（否则双计）"""
        pf = _acct(name='公积金浙江', code=None, category='投资性',
                   account_kind='公积金', is_liquid=True)
        self._snapshot([(pf, 4000)])

        ov = get_cashflow_overview()
        assert ov['summary']['flow_total'] == 0
        assert ov['summary']['non_liquid'] == 0
        assert ov['accounts'][PROVIDENT_FUND_ACCOUNT_KEY] == 4000
        assert ov['summary']['financial_assets'] == 4000

    def test_legacy_path_non_liquid_is_zero(self):
        """旧表 8 列装的都是能动的钱（活期 + 公积金）—— 没有非流动项，给 0 而不是省略字段"""
        _legacy(yearmon='2099-06', cash=100, accumulationfund=1000)
        s = get_cashflow_overview()['summary']
        assert s['non_liquid'] == 0
