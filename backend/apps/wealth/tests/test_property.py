"""物件资产 · 接口测试（v3.60.0）

覆盖范围：类别的增删改查与「有引用不许删」、物件的增删改查、
状态与报废字段的耦合、表单校验、保存前试算、筛选与「裸数组」形状。

刻意**不重复** `test_property_calc.py` 的算法用例 —— 那边钉的是「数算得对不对」，
这边钉的是「接口有没有把该拦的拦住、该置空的置空、该原样返回的原样返回」。

三条最容易静默失效的纪律，各有专门用例：
    ① **裸数组**：被 DRF 全局分页包成 `{count, results}` 后，前端按数组消费
       会静默显示为空（项目硬坑③）—— 界面上看起来就是「一件家当都没有」。
    ② **服务端置空**：状态从「已报废」改回来时，报废日期与处置备注必须由
       **服务端**清掉，不指望客户端记得送 null。否则会出现「状态是在用、
       却带着报废日期」的自相矛盾行，而那种行在列表里看起来完全正常。
    ③ **派生值不落库**：接口不提供 `?ordering=`。一旦提供，`current_value`
       就会被逼着落库，撕开「派生值不落库」这条口子。
"""

from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.wealth.models import WealthProperty, WealthPropertyCategory

TODAY = date.today()
CATEGORIES = '/api/wealth/property/categories/'
SEED = '/api/wealth/property/categories/seed/'
ITEMS = '/api/wealth/property/items/'
PREVIEW = '/api/wealth/property/items/preview/'
SUMMARY = '/api/wealth/property/summary/'


# ──────────────────────────────────────────────────────────────
# 造数
# ──────────────────────────────────────────────────────────────

def _months_ago(months: int) -> date:
    """距今「整几个月」的日期 —— 让 age_months 恰好等于 months。

    日取 `min(TODAY.day, 28)` 是为了绕开 2 月没有 31 日的坑；
    这样 `months_between` 的两步（月份差 / 日数回退）都不会触发回退，
    用例的期望值可以直接写整数。
    """
    total = TODAY.year * 12 + (TODAY.month - 1) - months
    year, month = divmod(total, 12)
    return date(year, month + 1, min(TODAY.day, 28))


def _category(api, name='家电'):
    response = api.post(CATEGORIES, {'name': name}, format='json')
    assert response.status_code == 201, response.json()
    return response.json()['id']


def _payload(category_id, **overrides):
    """一台「什么都有」的冰箱 —— 前提齐全，所以净值一定算得出。

    用例要验「某个字段缺了会怎样」时，用 overrides 单独把它抹成 None，
    这样「缺了这个字段」是唯一的变量。
    """
    data = {
        'category_id': category_id,
        'name': '冰箱',
        'spec': '海尔 BCD-216',
        'location': '厨房',
        'purchase_amount': '4800.00',
        'purchase_date': _months_ago(24).isoformat(),
        'lifespan_months': 120,
        'status': 'in_use',
        'condition': 'normal',
    }
    data.update(overrides)
    return data


def _create(api, category_id, **overrides):
    response = api.post(ITEMS, _payload(category_id, **overrides), format='json')
    assert response.status_code == 201, response.json()
    return response.json()


def _dec(value):
    """响应里的 Decimal 是字符串 —— 比数之前先转回来，别拿字符串比。"""
    return Decimal(str(value))


# ══════════════════════════════════════════════════════════════
# ① 类别
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestCategoryCrud:
    def test_create_and_list(self):
        api = APIClient()
        _category(api, '家电')
        _category(api, '家具')
        rows = api.get(CATEGORIES).json()
        assert isinstance(rows, list)
        assert [r['name'] for r in rows] == ['家电', '家具']
        # 新建的类别还没有任何物件 —— 这个数就是「为什么它删得掉」
        assert all(r['property_count'] == 0 for r in rows)

    def test_duplicate_name_is_rejected(self):
        """同名类别必须 400 —— 唯一约束在 Meta.constraints 里，
        DRF 不会自动替我验（项目已踩三次），所以服务层手写了这条检查。"""
        api = APIClient()
        _category(api, '家电')
        response = api.post(CATEGORIES, {'name': '家电'}, format='json')
        assert response.status_code == 400
        assert '家电' in response.json()['detail']

    def test_blank_name_is_rejected(self):
        api = APIClient()
        assert api.post(CATEGORIES, {'name': ''}, format='json').status_code == 400

    def test_update_and_rename(self):
        api = APIClient()
        pk = _category(api, '家电')
        response = api.patch(f'{CATEGORIES}{pk}/', {'note': '冰箱空调洗衣机'}, format='json')
        assert response.status_code == 200
        assert response.json()['note'] == '冰箱空调洗衣机'

    def test_default_lifespan_can_be_cleared(self):
        """默认年限是**可清空**的 —— 用户可以把预填值撤掉。
        写成 `if value is not None` 就永远撤不掉，而且界面上看不出为什么。"""
        api = APIClient()
        pk = _category(api, '家电')
        api.patch(f'{CATEGORIES}{pk}/', {'default_lifespan_months': 120}, format='json')
        response = api.patch(
            f'{CATEGORIES}{pk}/', {'default_lifespan_months': None}, format='json',
        )
        assert response.status_code == 200
        assert response.json()['default_lifespan_months'] is None

    def test_delete_empty_category(self):
        api = APIClient()
        pk = _category(api, '家电')
        assert api.delete(f'{CATEGORIES}{pk}/').status_code == 200
        assert WealthPropertyCategory.objects.filter(id=pk).count() == 0

    def test_delete_category_with_items_is_refused(self):
        """🔴 不级联删除 —— 并把「还有几件」报出来让人能照做。

        级联删除会让「删掉一个建错的空类别」与「删掉整柜家当」
        走同一个按钮，代价完全不对称且不可逆。"""
        api = APIClient()
        pk = _category(api, '家电')
        _create(api, pk, name='冰箱')
        _create(api, pk, name='空调')
        response = api.delete(f'{CATEGORIES}{pk}/')
        assert response.status_code == 400
        assert '2 件' in response.json()['detail']
        # 拒绝之后，类别与物件都还在
        assert WealthPropertyCategory.objects.filter(id=pk).exists()
        assert WealthProperty.objects.filter(category_id=pk).count() == 2

    def test_seed_is_idempotent_and_creates_no_items(self):
        """初始化默认类别：只建类别，**绝不预设任何物件**。
        物件是用户自己的数据，代猜就是编数据。"""
        api = APIClient()
        first = api.post(SEED, {}, format='json').json()
        assert first['created'] == 6
        assert first['skipped'] == 0
        second = api.post(SEED, {}, format='json').json()
        assert second['created'] == 0
        assert second['skipped'] == 6
        assert WealthPropertyCategory.objects.count() == 6
        assert WealthProperty.objects.count() == 0
        # 种子里**没有**默认使用年限 —— 那是用户自己的判断
        assert all(row['default_lifespan_months'] is None for row in second['categories'])


# ══════════════════════════════════════════════════════════════
# ② 物件：增删改查
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestItemCrud:
    def test_create_returns_the_full_row(self):
        api = APIClient()
        row = _create(api, _category(api))
        assert row['id'] is not None
        assert row['category_name'] == '家电'
        assert row['age_months'] == 24
        assert row['remaining_months'] == 96
        assert _dec(row['current_value']) == Decimal('3840.00')
        assert row['issues'] == []

    def test_list_is_a_bare_array(self):
        """🔴 前端按数组消费 —— 包成 `{count, results}` 就是「一件家当都没有」"""
        api = APIClient()
        category = _category(api)
        _create(api, category, name='冰箱')
        body = api.get(ITEMS).json()
        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]['name'] == '冰箱'

    def test_retrieve_update_delete(self):
        api = APIClient()
        row = _create(api, _category(api))
        url = f'{ITEMS}{row["id"]}/'
        assert api.get(url).json()['name'] == '冰箱'
        updated = api.patch(url, {'location': '老家'}, format='json').json()
        assert updated['location'] == '老家'
        assert api.delete(url).status_code == 200
        assert not WealthProperty.objects.filter(id=row['id']).exists()

    def test_moving_between_categories(self):
        api = APIClient()
        home = _category(api, '家电')
        other = _category(api, '数码')
        row = _create(api, home)
        moved = api.patch(
            f'{ITEMS}{row["id"]}/', {'category_id': other}, format='json',
        ).json()
        assert moved['category_name'] == '数码'

    def test_unknown_category_is_rejected(self):
        """挂到一个不存在的类别上 ⇒ 400，而不是静默落到别的类别"""
        api = APIClient()
        response = api.post(ITEMS, _payload(999999), format='json')
        assert response.status_code == 400
        assert '不存在' in response.json()['detail']

    def test_filters(self):
        api = APIClient()
        home = _category(api, '家电')
        digital = _category(api, '数码')
        _create(api, home, name='冰箱')
        _create(api, home, name='空调', status='scrapped',
                scrapped_date=TODAY.isoformat(), condition='broken')
        _create(api, digital, name='笔记本')

        assert len(api.get(f'{ITEMS}?category={home}').json()) == 2
        assert len(api.get(f'{ITEMS}?status=scrapped').json()) == 1
        assert len(api.get(f'{ITEMS}?condition=broken').json()) == 1
        assert [r['name'] for r in api.get(f'{ITEMS}?search=冰').json()] == ['冰箱']

    def test_ordering_param_is_not_honoured(self):
        """🔴 本模块**不提供** `?ordering=` —— 排序是前端的事。

        一旦开到后端，`current_value`（派生值、不落库）就会被逼着落库。
        这里传一个最诱人的排序键，断言它被**原样忽略**（既不排序、也不报错）。
        """
        api = APIClient()
        category = _category(api)
        _create(api, category, name='便宜的先建', purchase_amount='100.00')
        _create(api, category, name='贵的后建', purchase_amount='9000.00')
        default_order = [r['name'] for r in api.get(ITEMS).json()]
        asked_order = [
            r['name']
            for r in api.get(f'{ITEMS}?ordering=-current_value&ordering=purchase_amount').json()
        ]
        assert asked_order == default_order
        # 最近录入的在前
        assert default_order == ['贵的后建', '便宜的先建']


# ══════════════════════════════════════════════════════════════
# ③ 状态 × 报废字段（服务端置空）
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestScrapFieldsFollowStatus:
    """🔴 置空必须由**服务端**保证，不指望客户端记得送 null。

    漏了它就会出现「状态是在用、却带着报废日期」的自相矛盾行 ——
    而那种行在列表里看起来完全正常（少一个字段没人会发现）。
    """

    def test_scrapped_keeps_the_fields(self):
        api = APIClient()
        row = _create(
            api, _category(api), status='scrapped',
            scrapped_date=TODAY.isoformat(), dispose_note='以旧换新',
        )
        assert row['scrapped_date'] == TODAY.isoformat()
        assert row['dispose_note'] == '以旧换新'

    def test_reverting_to_in_use_clears_them_server_side(self):
        """从「已报废」改回「在用」—— 客户端**什么字段都没送**，
        服务端也必须把那两个格子清掉。"""
        api = APIClient()
        row = _create(
            api, _category(api), status='scrapped',
            scrapped_date=TODAY.isoformat(), dispose_note='送人了',
        )
        updated = api.patch(f'{ITEMS}{row["id"]}/', {'status': 'in_use'}, format='json').json()
        assert updated['status'] == 'in_use'
        assert updated['scrapped_date'] is None
        assert updated['dispose_note'] == ''
        # 库里也真的清掉了（不是只在响应里清）
        stored = WealthProperty.objects.get(id=row['id'])
        assert stored.scrapped_date is None and stored.dispose_note == ''

    def test_client_sent_values_are_also_cleared(self):
        """客户端**送了**报废字段但状态不是在用 —— 照样归零。

        只拦「没送」是不够的：前端表单残留、脚本调用都可能把值带过来。
        """
        api = APIClient()
        row = _create(api, _category(api), name='空调')
        updated = api.patch(
            f'{ITEMS}{row["id"]}/',
            {'status': 'idle', 'scrapped_date': TODAY.isoformat(), 'dispose_note': '送人'},
            format='json',
        ).json()
        assert updated['scrapped_date'] is None
        assert updated['dispose_note'] == ''

    def test_reverting_does_not_freeze_the_value(self):
        """改回在用之后，净值重新按**今天**算（不再是报废那天的定格值）

        注意「报废那天」算的是**从购买日到报废日**：
        24 个月前买的、6 个月前报废 ⇒ 那时已用了 18 个月，不是 6 个月。
        """
        api = APIClient()
        category = _category(api)
        row = _create(
            api, category, status='scrapped', scrapped_date=_months_ago(6).isoformat(),
        )
        assert row['age_months'] == 18
        assert _dec(row['current_value']) == Decimal('4080.00')   # 4800 − 18×40
        back = api.patch(f'{ITEMS}{row["id"]}/', {'status': 'in_use'}, format='json').json()
        assert back['ref_date'] == TODAY.isoformat()
        assert back['age_months'] == 24
        assert _dec(back['current_value']) == Decimal('3840.00')  # 4800 − 24×40


# ══════════════════════════════════════════════════════════════
# ④ 表单校验
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestFormValidation:
    def test_negative_amount_is_rejected(self):
        api = APIClient()
        response = api.post(
            ITEMS, _payload(_category(api), purchase_amount='-1.00'), format='json',
        )
        assert response.status_code == 400
        assert 'purchase_amount' in response.json()

    def test_zero_lifespan_is_rejected(self):
        """0 会让「月折旧 = 金额 ÷ 年限」除零 —— 在入口拦，不在计算层兜"""
        api = APIClient()
        response = api.post(ITEMS, _payload(_category(api), lifespan_months=0), format='json')
        assert response.status_code == 400
        assert 'lifespan_months' in response.json()

    def test_scrap_date_before_purchase_date_is_rejected(self):
        api = APIClient()
        response = api.post(
            ITEMS,
            _payload(
                _category(api), status='scrapped',
                scrapped_date=_months_ago(30).isoformat(),
            ),
            format='json',
        )
        assert response.status_code == 400
        assert 'scrapped_date' in response.json()

    def test_scrap_date_is_not_checked_when_not_scrapped(self):
        """不是报废态时那个字段会被清掉，所以「报废日早于购买日」不该拦 ——
        拦了就会出现「填了一格没人看的字段，保存却报错」。"""
        api = APIClient()
        response = api.post(
            ITEMS,
            _payload(
                _category(api), status='in_use',
                scrapped_date=_months_ago(30).isoformat(),
            ),
            format='json',
        )
        assert response.status_code == 201
        assert response.json()['scrapped_date'] is None

    def test_empty_fields_are_allowed(self):
        """盘家当必然有「想不起来多少钱了」的东西 —— 只填名称也存得下"""
        api = APIClient()
        row = _create(
            api, _category(api), name='不知道多少钱的旧柜子',
            purchase_amount=None, purchase_date=None, lifespan_months=None,
        )
        assert row['current_value'] is None          # 算不出
        assert row['issues']                          # 但**说得出为什么**
        codes = {issue['code'] for issue in row['issues']}
        assert codes == {'NO_AMOUNT', 'NO_PURCHASE_DATE', 'NO_LIFESPAN'}

    def test_uncomputable_is_null_not_zero(self):
        """🔴 缺字段 ⇒ null，**不是 0**。
        0 是「真的折完了」的结论，跟「算不出来」不是一回事 ——
        它们该采取的行动相反（一个该换新，一个该补数据）。"""
        api = APIClient()
        row = _create(api, _category(api), purchase_amount=None)
        assert row['current_value'] is None
        assert row['monthly_depreciation'] is None
        assert row['age_months'] == 24               # 这个算得出，就照给


# ══════════════════════════════════════════════════════════════
# ⑤ 保存前试算
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPreview:
    """试算的存在理由就是「说对了」—— 说得不一样比没有更糟"""

    def test_preview_equals_the_saved_row(self):
        api = APIClient()
        category = _category(api)
        payload = _payload(category)
        preview = api.post(PREVIEW, payload, format='json').json()
        saved = _create(api, category)
        for field in ('age_months', 'remaining_months', 'current_value', 'zero_reason',
                      'monthly_depreciation', 'ref_date', 'is_overdue', 'overdue_months'):
            assert preview[field] == saved[field], f'{field} 两条路径不一致'

    def test_preview_does_not_write(self):
        api = APIClient()
        before = WealthProperty.objects.count()
        api.post(PREVIEW, _payload(_category(api)), format='json')
        assert WealthProperty.objects.count() == before

    def test_preview_row_has_no_id(self):
        api = APIClient()
        row = api.post(PREVIEW, _payload(_category(api)), format='json').json()
        assert row['id'] is None

    def test_preview_uses_the_same_validation(self):
        """「试算放行、一按保存报 400」是最糟的组合 —— 它先把人哄住了"""
        api = APIClient()
        category = _category(api)
        payload = _payload(category, lifespan_months=0)
        assert api.post(PREVIEW, payload, format='json').status_code == 400
        assert api.post(ITEMS, payload, format='json').status_code == 400

    def test_preview_ignores_scrap_fields_when_not_scrapped(self):
        """试算体现的是「保存之后会变成什么样」——
        状态不是在用，那两个字段就不该参与计算。"""
        api = APIClient()
        row = api.post(
            PREVIEW,
            _payload(
                _category(api), status='in_use',
                scrapped_date=_months_ago(6).isoformat(),
            ),
            format='json',
        ).json()
        assert row['ref_date'] == TODAY.isoformat()
        assert row['age_months'] == 24

    def test_preview_shows_zero_the_moment_broken_is_ticked(self):
        """🔴 勾上「损坏」，逐算里那一行数字必须**当场**变成 ¥0.00。

        这条是口径订正（2026-09-26）的核心价值所在：
        人是在表单里决定「它坏了」的，那就该在人还看着这一屏时把结论摆出来 ——
        而不是等他保存、关掉表单、回到列表，才发现四卡的合计已经掉了一截。
        """
        api = APIClient()
        category = _category(api)
        before = api.post(PREVIEW, _payload(category), format='json').json()
        after = api.post(
            PREVIEW, _payload(category, condition='broken'), format='json',
        ).json()

        assert float(before['current_value']) > 0
        assert after['current_value'] == '0.00'
        assert after['zero_reason'] == 'broken'
        # 时间事实与它无关 —— 别让一次「标记」顺手改掉「用了多久」
        assert after['age_months'] == before['age_months']
        assert after['remaining_months'] == before['remaining_months']

    def test_broken_survives_the_round_trip(self):
        """试算与保存必须一模一样 —— 坏消息（净值归 0）也不能只在其中一条路径上出现。"""
        api = APIClient()
        category = _category(api)
        preview = api.post(
            PREVIEW, _payload(category, condition='broken'), format='json',
        ).json()
        saved = _create(api, category, condition='broken')
        assert preview['current_value'] == saved['current_value'] == '0.00'
        assert preview['zero_reason'] == saved['zero_reason'] == 'broken'
