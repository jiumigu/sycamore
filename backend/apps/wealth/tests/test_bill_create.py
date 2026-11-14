"""`POST /wealth/bill/create/` —— 页头「记一笔」的落库契约。

页头只送五个字段：金额 / 分类 / 子分类 / 日期 / 类型（v3.64.49）。这个接口原本只有
`DayDetailModal` 在用，行为没被测试钉住过；现在它成了每天的录入口，
下面几条一旦破了，账目会「看着记成功了、实际上错位」。
"""
import pytest
from django.db import connection
from rest_framework.test import APIClient

URL = '/api/wealth/bill/create/'


def _post(**payload):
    return APIClient().post(URL, payload, format='json')


def _fetch_one():
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT transaction_type, category, subcategory, amount, date,
                   year, month, day, IFNULL(period_tag, ''), IFNULL(necessity, '')
            FROM wealth_bill_list
        """)
        return cursor.fetchone()


@pytest.mark.django_db
def test_minimal_four_fields_are_enough() -> None:
    """金额 + 分类 + 日期 + 类型就能记一笔，其余字段全部可空。"""
    resp = _post(
        transaction_type='支出',
        amount='12.34',
        category='食品酒水',
        date='2026-11-11',
    )
    assert resp.status_code == 201

    row = _fetch_one()
    assert row[0] == '支出'
    assert row[1] == '食品酒水'
    assert str(row[3]) == '12.34'
    # 🔴 存的是**本地** 00:00。若哪天变成前一天的 16:00，就是被当 UTC 转了 ——
    #    界面上完全看不出来，只有月底对账时才发现账落错了一天。
    assert row[4].strftime('%Y-%m-%d %H:%M:%S') == '2026-11-11 00:00:00'
    # 冗余列必须与 date 同源，否则按 year/month 聚合与按 date 过滤会各算各的
    assert (row[5], row[6], row[7]) == (2026, 11, 11)


@pytest.mark.django_db
def test_category_can_be_blank() -> None:
    """分类可以先不填 —— 它是后置归类，不该堵在录入口。"""
    resp = _post(
        transaction_type='支出',
        amount='5',
        category='',
        date='2026-11-11',
    )
    assert resp.status_code == 201
    assert _fetch_one()[1] == ''


@pytest.mark.django_db
def test_subcategory_is_persisted() -> None:
    """子分类必须原样落库（v3.64.49）。

    🔴 它不是「描述性字段」，而是**口径的一部分**：`CLASSIFY_RULE` 的匹配字段是
       category / subcategory / merchant，且同优先级时更具体的字段胜
       （subcategory > category）。子分类一丢，「早午晚餐 → 品质支出」这类规则
       就永远打不中；未归类候选按 `(category, subcategory)` 聚合，也只能退化成
       按大类给建议 —— 全都不会报错，只是口径悄悄变粗。
    """
    resp = _post(
        transaction_type='支出',
        amount='23.5',
        category='食品酒水',
        subcategory='早午晚餐',
        date='2026-11-11',
    )
    assert resp.status_code == 201
    assert _fetch_one()[2] == '早午晚餐'


@pytest.mark.django_db
def test_subcategory_omitted_falls_back_to_blank() -> None:
    """不传子分类 = 空串，不是 NULL：前端不清空、报表里也不会变成 `None` 字样。"""
    _post(transaction_type='支出', amount='5', category='食品酒水', date='2026-11-11')
    assert _fetch_one()[2] == ''


@pytest.mark.django_db
def test_period_tag_left_empty_on_purpose() -> None:
    """归属留空是**故意的**：`BillCreateView` 那条 SQL 根本没有 period_tag 列。"""
    _post(transaction_type='支出', amount='9.9', category='日常生活', date='2026-11-11')
    row = _fetch_one()
    assert row[8] == ''
    assert row[9] == ''


@pytest.mark.django_db
@pytest.mark.parametrize('amount', ['0', '-1', 'abc'])
def test_invalid_amount_is_rejected(amount: str) -> None:
    resp = _post(
        transaction_type='支出',
        amount=amount,
        category='食品酒水',
        date='2026-11-11',
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_invalid_type_is_rejected() -> None:
    resp = _post(
        transaction_type='转账',
        amount='10',
        category='食品酒水',
        date='2026-11-11',
    )
    assert resp.status_code == 400
