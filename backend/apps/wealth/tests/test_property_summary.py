"""物件资产 · 首屏四卡的合计口径（v3.60.0）

这一份钉的是 `summarize` 的**对外行为**：四个数缺一不可、
报废的算不算、算不出的怎么报。

三个最容易「看着合理其实是错」的取舍，各有用例：
    ① **原值合计含已报废**：那是「一共投进去多少钱」的历史总投入，
       已经淘汰掉的那部分也是花掉的钱 —— 把它排除掉会让数字凭记忆变小。
    ② **在用净值合计不含已报废**：它的价值在报废那天就定格了，
       再算进来等于让一笔已经结束的账继续随日历变化。
    ③ **「算不出」必须单独报出来**：只给总额的话，界面没法把「少算了」摆出来 ——
       总额看着小一点、件数却是全的，两个数都对不上，还没人会去查。
"""

from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.wealth.models import WealthProperty

TODAY = date.today()
CATEGORIES = '/api/wealth/property/categories/'
ITEMS = '/api/wealth/property/items/'
SUMMARY = '/api/wealth/property/summary/'


def _months_ago(months: int) -> date:
    total = TODAY.year * 12 + (TODAY.month - 1) - months
    year, month = divmod(total, 12)
    return date(year, month + 1, min(TODAY.day, 28))


def _category(api, name='家电'):
    return api.post(CATEGORIES, {'name': name}, format='json').json()['id']


def _item(api, category, **overrides):
    payload = {
        'category_id': category,
        'name': '物件',
        'purchase_amount': '4800.00',
        'purchase_date': _months_ago(24).isoformat(),
        'lifespan_months': 120,
        'status': 'in_use',
        'condition': 'normal',
    }
    payload.update(overrides)
    response = api.post(ITEMS, payload, format='json')
    assert response.status_code == 201, response.json()
    return response.json()


def _fixture(api):
    """五种典型家当 —— 覆盖「在用 / 闲置 / 已报废」× 「有价 / 缺金额 / 缺日期」

    预期（对着下面的用例看）：
        冰箱   在用  4800 / 24月前 / 120月 → 净值 3840
        空调   闲置  3000 / 12月前 /  60月 → 净值 2400
        旧手机 报废  2000 / 36月前 /  24月，6月前报废 → 早已折完，定格 0
        旧柜子 在用  没填金额                → 算不出（缺金额）
        台灯   闲置  300 / 没填购买日期       → 算不出（缺日期）
    """
    home = _category(api, '家电')
    _item(api, home, name='冰箱', purchase_amount='4800.00',
          purchase_date=_months_ago(24).isoformat(), lifespan_months=120)
    _item(api, home, name='空调', status='idle', purchase_amount='3000.00',
          purchase_date=_months_ago(12).isoformat(), lifespan_months=60)
    _item(api, home, name='旧手机', status='scrapped', purchase_amount='2000.00',
          purchase_date=_months_ago(36).isoformat(), lifespan_months=24,
          scrapped_date=_months_ago(6).isoformat(), dispose_note='以旧换新')
    _item(api, home, name='旧柜子', purchase_amount=None)
    _item(api, home, name='台灯', status='idle', purchase_amount='300.00',
          purchase_date=None)
    return api.get(SUMMARY).json()


# ══════════════════════════════════════════════════════════════
# ① 四个数缺一不可
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSummaryBlocks:
    def test_every_block_carries_four_numbers(self):
        api = APIClient()
        body = _fixture(api)
        base = {'total', 'counted', 'unpriced_count', 'unvalued_count'}
        assert set(body['total_amount']) == base, '原值合计块少了字段'
        assert set(body['in_use_net_value']) == base | {'broken_count'}, '净值块少了字段'

    def test_only_the_net_block_carries_broken_count(self):
        """🔴 `broken_count` **只属于净值块**。

        原值合计与状况无关（买的时候花了多少钱，不会因为后来坏了就变）——
        给它也挂上 `broken_count` 会多出一个恒为 0 的字段，
        而「一个恒为 0 的字段」最容易让人以为「这个数坏了」（硬坑⑪的反面：
        键名错在界面上看不出来，那多余键就是多了个看不出来的坑）。
        """
        api = APIClient()
        body = _fixture(api)
        assert 'broken_count' in body['in_use_net_value']
        assert 'broken_count' not in body['total_amount']

    def test_counts(self):
        api = APIClient()
        body = _fixture(api)
        # 闲置也算「还在我手上」；已报废的不算
        assert body['in_use_count'] == 4
        assert body['scrapped_count'] == 1


# ══════════════════════════════════════════════════════════════
# ② 原值合计：含已报废
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestTotalAmount:
    def test_includes_scrapped(self):
        api = APIClient()
        body = _fixture(api)
        block = body['total_amount']
        # 4800 + 3000 + 2000(已报废) + 300 = 10100
        assert float(block['total']) == pytest.approx(10100.0)
        assert block['counted'] == 4
        # 5 件里 1 件没填金额 —— 报出来，不静默少算
        assert block['unpriced_count'] == 1
        assert block['unvalued_count'] == 0

    def test_scrapped_amount_survives_its_own_scrapping(self):
        """报废前后，原值合计**不变** —— 那是历史投入，不是现值"""
        api = APIClient()
        home = _category(api)
        row = _item(api, home, name='洗衣机', purchase_amount='2000.00')
        before = float(api.get(SUMMARY).json()['total_amount']['total'])
        api.patch(f'{ITEMS}{row["id"]}/', {
            'status': 'scrapped', 'scrapped_date': TODAY.isoformat(),
        }, format='json')
        after = float(api.get(SUMMARY).json()['total_amount']['total'])
        assert before == after == pytest.approx(2000.0)


# ══════════════════════════════════════════════════════════════
# ③ 在用净值合计：不含已报废
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestInUseNetValue:
    def test_excludes_scrapped_and_reports_what_it_could_not_count(self):
        api = APIClient()
        block = _fixture(api)['in_use_net_value']
        # 冰箱 3840 + 空调 2400 = 6240；旧手机已报废，不入账
        assert float(block['total']) == pytest.approx(6240.0)
        assert block['counted'] == 2
        # 旧柜子连原值都没有 → 算「未填金额」
        assert block['unpriced_count'] == 1
        # 台灯填了金额却算不出净值（缺日期）→ 与「未填金额」分开报
        assert block['unvalued_count'] == 1

    def test_the_two_reasons_are_reported_separately(self):
        """🔴「没填金额」与「填了但算不出」必须分开 —— 两件事该采取的行动不同：
        一个是去补价格，一个是去补日期/年限。合并成一个数就看不出去补哪个。"""
        api = APIClient()
        block = _fixture(api)['in_use_net_value']
        assert block['unpriced_count'] != 0
        assert block['unvalued_count'] != 0

    def test_scrapping_removes_the_value_from_the_in_use_block(self):
        api = APIClient()
        home = _category(api)
        row = _item(api, home, name='洗衣机', purchase_amount='2400.00',
                    purchase_date=_months_ago(0).isoformat(), lifespan_months=24)
        before = float(api.get(SUMMARY).json()['in_use_net_value']['total'])
        assert before == pytest.approx(2400.0)
        api.patch(f'{ITEMS}{row["id"]}/', {
            'status': 'scrapped', 'scrapped_date': TODAY.isoformat(),
        }, format='json')
        after = api.get(SUMMARY).json()
        assert float(after['in_use_net_value']['total']) == pytest.approx(0.0)
        assert after['in_use_net_value']['counted'] == 0
        assert after['in_use_count'] == 0

    def test_empty_ledger_is_all_zeros_not_an_error(self):
        """一件物件都没有时是 0，不是报错 —— 这里 0 是**正确**的答案"""
        api = APIClient()
        body = api.get(SUMMARY).json()
        assert body['in_use_count'] == 0
        assert body['scrapped_count'] == 0
        assert float(body['total_amount']['total']) == 0.0
        assert float(body['in_use_net_value']['total']) == 0.0


# ══════════════════════════════════════════════════════════════
# ④ 状况=损坏 ⇒ 净值归 0（2026-09-26 订正口径）
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestBrokenZeroesTheNetValue:
    """🔴 损坏只改一件事：净值按 0 计。

    原口径是「状况完全不参与任何数字」，被用户这次的要求推翻了
    （两副已报废的眼镜还挂着 ¥151.48 的净值）。
    订正后仍然**只动净值这一项**：件数不变、原值不变、时间事实一概不变。
    """

    def test_broken_zeroes_only_the_value(self):
        api = APIClient()
        home = _category(api)
        normal = _item(api, home, name='好的', condition='normal')
        broken = _item(api, home, name='坏的', condition='broken')

        assert normal['current_value'] == '3840.00'
        assert normal['zero_reason'] is None
        assert broken['current_value'] == '0.00'
        assert broken['zero_reason'] == 'broken'

        # 时间事实一个都不许动 —— 它们与「好不好使」无关
        assert broken['age_months'] == normal['age_months']
        assert broken['remaining_months'] == normal['remaining_months']
        assert broken['monthly_depreciation'] == normal['monthly_depreciation']
        assert broken['is_overdue'] == normal['is_overdue']
        assert broken['issues'] == normal['issues'] == []

    def test_broken_lowers_the_total_but_keeps_the_count(self):
        """🔴 勾一下「损坏」：合计掉一截、件数纹丝不动 —— 所以必须有个数能解释它。

        这里复现的正是那种「看着合理其实是错」的形态：总数小了、
        「计入 N 件」还是全的，两个数对不上还没人会去查 ⇒ broken_count 就是解药。
        """
        api = APIClient()
        home = _category(api)
        _item(api, home, name='好的', purchase_amount='1000.00')
        before = api.get(SUMMARY).json()
        _item(api, home, name='坏的', purchase_amount='1000.00', condition='broken')
        after = api.get(SUMMARY).json()

        # 件数与原值照常 +1（它还在，只是不值钱了）
        assert after['in_use_count'] == before['in_use_count'] + 1
        assert float(after['total_amount']['total']) == pytest.approx(
            float(before['total_amount']['total']) + 1000.0,
        )
        # 净值：+1 件、+0 元
        assert float(after['in_use_net_value']['total']) == pytest.approx(
            float(before['in_use_net_value']['total']),
        )
        assert after['in_use_net_value']['counted'] == before['in_use_net_value']['counted'] + 1
        assert after['in_use_net_value']['broken_count'] == 1
        # 它既不是「算不出」（unvalued）也不是「没填金额」（unpriced）——
        # 三个桶不许串，否则界面会指着一个不存在的毛病让人去补数据
        assert after['in_use_net_value']['unvalued_count'] == 0
        assert after['in_use_net_value']['unpriced_count'] == 0

    def test_broken_count_only_covers_the_in_use_side(self):
        """`broken_count` 只数在用 / 闲置的 —— 报废件本来就不进这个合计。"""
        api = APIClient()
        home = _category(api)
        _item(api, home, name='坏在用件', condition='broken')
        _item(api, home, name='坏报废件', condition='broken', status='scrapped',
              scrapped_date=TODAY.isoformat())
        block = api.get(SUMMARY).json()['in_use_net_value']
        assert block['broken_count'] == 1

    def test_broken_is_still_filterable_by_the_list(self):
        """进了算法 ≠ 不能再筛 —— 它同时是标记，也是净值口径。"""
        api = APIClient()
        home = _category(api)
        _item(api, home, name='好的', condition='normal')
        _item(api, home, name='坏的', condition='broken')
        rows = api.get(f'{ITEMS}?condition=broken').json()
        assert [r['name'] for r in rows] == ['坏的']


# ══════════════════════════════════════════════════════════════
# ⑤ 合计口径 == 明细行
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSummaryAgreesWithTheRows:
    """合计必须与列表里那些行**加起来对得上** —— 对不上的合计没人会去查"""

    def test_net_value_total_equals_the_sum_of_visible_rows(self):
        api = APIClient()
        _fixture(api)
        rows = api.get(ITEMS).json()
        visible = [
            float(r['current_value']) for r in rows
            if r['status'] != 'scrapped' and r['current_value'] is not None
        ]
        block = api.get(SUMMARY).json()['in_use_net_value']
        assert float(block['total']) == pytest.approx(sum(visible))
        assert block['counted'] == len(visible)

    def test_total_amount_equals_the_sum_of_every_priced_row(self):
        api = APIClient()
        _fixture(api)
        rows = api.get(ITEMS).json()
        priced = [
            float(r['purchase_amount']) for r in rows
            if r['purchase_amount'] is not None
        ]
        block = api.get(SUMMARY).json()['total_amount']
        assert float(block['total']) == pytest.approx(sum(priced))
        assert block['counted'] == len(priced)

    def test_deleting_an_item_removes_it_from_the_totals(self):
        api = APIClient()
        home = _category(api)
        row = _item(api, home, name='录错的', purchase_amount='9999.00')
        assert float(api.get(SUMMARY).json()['total_amount']['total']) == pytest.approx(9999.0)
        api.delete(f'{ITEMS}{row["id"]}/')
        assert float(api.get(SUMMARY).json()['total_amount']['total']) == pytest.approx(0.0)
        assert WealthProperty.objects.count() == 0
