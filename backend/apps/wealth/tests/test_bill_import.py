"""CSV 账单导入去重测试 — apps.wealth.views.wealth_views.BillImportView"""
from datetime import datetime

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from rest_framework.test import APIClient

IMPORT_URL = '/api/wealth/import/csv/'

CSV_HEADER = '交易类型,日期,分类,子分类,项目,账户,币种,金额,成员,商家,备注\n'
CSV_HEADER2 = '交易类型,日期,分类,子分类,项目,账户,币种,金额,成员,商家,备注\n'


def _upload(content: str, filename: str = 'bills.csv') -> dict:
    client = APIClient()
    resp = client.post(
        IMPORT_URL,
        {
            'file': SimpleUploadedFile(filename, content.encode('utf-8-sig')),
            'user_id': 1,
        },
        format='multipart',
    )
    return resp.data


def _bill_count() -> int:
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) FROM wealth_bill_list')
        return cursor.fetchone()[0]


@pytest.mark.django_db
def test_import_creates_new_bills() -> None:
    """核心：有效行全部创建"""
    content = (
        CSV_HEADER + CSV_HEADER2 +
        '支出,2025-01-07 12:00:00,餐饮,午餐,,支付宝,CNY,30.00,,麦当劳,午饭\n'
        '收入,2025-01-08 09:00:00,工资,,,银行卡,CNY,5000,,,月薪\n'
    )
    result = _upload(content)
    assert result['created'] == 2
    assert result['duplicated'] == 0
    assert _bill_count() == 2


@pytest.mark.django_db
def test_import_duplicate_date_amount_type_skipped() -> None:
    """核心：同 (日期, 金额, 类型) 的重复行不重复创建"""
    content = (
        CSV_HEADER + CSV_HEADER2 +
        '支出,2025-01-07 12:00:00,餐饮,午餐,,支付宝,CNY,30.00,,麦当劳,午饭\n'
    )
    first = _upload(content)
    second = _upload(content)
    assert first['created'] == 1
    assert second['created'] == 0
    assert second['duplicated'] == 1
    assert _bill_count() == 1


@pytest.mark.django_db
def test_import_negative_amount_stored_as_abs() -> None:
    """边界：负数金额取绝对值入库"""
    content = (
        CSV_HEADER + CSV_HEADER2 +
        '支出,2025-01-07 12:00:00,餐饮,午餐,,支付宝,CNY,-30.00,,麦当劳,午饭\n'
    )
    _upload(content)
    with connection.cursor() as cursor:
        cursor.execute('SELECT amount, transaction_type FROM wealth_bill_list')
        row = cursor.fetchone()
    assert float(row[0]) == 30.00
    assert row[1] == '支出'


@pytest.mark.django_db
def test_import_skips_rows_with_insufficient_columns() -> None:
    """边界：列数不足 8 的行跳过"""
    content = (
        CSV_HEADER + CSV_HEADER2 +
        '支出,2025-01-07,餐饮\n'
        '收入,2025-01-08 09:00:00,工资,,,银行卡,CNY,5000\n'
    )
    result = _upload(content)
    assert result['skipped'] == 1
    assert result['created'] == 1


@pytest.mark.django_db
def test_import_skips_row_without_date_or_amount() -> None:
    """边界：缺日期或缺金额的行跳过"""
    content = (
        CSV_HEADER + CSV_HEADER2 +
        '支出,,餐饮,午餐,,支付宝,CNY,30.00,,麦当劳,午饭\n'
        '支出,2025-01-08 09:00:00,餐饮,午餐,,支付宝,CNY,,,麦当劳,午饭\n'
    )
    result = _upload(content)
    assert result['skipped'] == 2
    assert result['created'] == 0


def test_import_rejects_file_with_less_than_3_rows() -> None:
    """边界：文件不足 3 行直接 400"""
    client = APIClient()
    resp = client.post(
        IMPORT_URL,
        {'file': SimpleUploadedFile('bad.csv', b'a,b\n')},
        format='multipart',
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_import_slash_date_format_accepted() -> None:
    """口径放宽：`2025/01/07` 也是合法日期（随手记换版本会这么导）。

    v3.65 之前只认 `%Y-%m-%d %H:%M:%S`，斜杠格式整行被判 skipped ——
    用户看到「导 0 条」，却不知道为什么。
    """
    content = (
        CSV_HEADER + CSV_HEADER2 +
        '支出,2025/01/07,餐饮,午餐,,支付宝,CNY,30.00,,麦当劳,午饭\n'
        '收入,2025-01-08 09:00:00,工资,,,银行卡,CNY,5000,,,月薪\n'
    )
    result = _upload(content)
    assert result['skipped'] == 0
    assert result['created'] == 2


@pytest.mark.django_db
def test_import_unparsable_date_counts_as_skipped() -> None:
    """边界：真正认不出的日期仍是 skipped，且理由带行号"""
    content = (
        CSV_HEADER + CSV_HEADER2 +
        '支出,2025年1月7日,餐饮,午餐,,支付宝,CNY,30.00,,麦当劳,午饭\n'
        '收入,2025-01-08 09:00:00,工资,,,银行卡,CNY,5000,,,月薪\n'
    )
    result = _upload(content)
    assert result['skipped'] == 1
    assert result['created'] == 1
    assert '第3行' in result['errors'][0]


# ══════════════════════════════════════════════════════════
# DQ-1：判重口径从「秒级」改成「按天半开区间 + 计重数」
# ══════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_import_same_transaction_different_second_is_duplicate() -> None:
    """同一笔账，导出时秒数抖了 7 秒 —— 旧口径会重复入库，现在必须判重。

    这是 DQ-1 的原始症状：`WHERE date = %s` 是秒级比对，
    换个导出时间就对不上，支出被记两遍而不报错。
    """
    first = CSV_HEADER + CSV_HEADER2 + \
        '支出,2025-01-07 12:00:00,餐饮,午餐,,支付宝,CNY,30.00,,麦当劳,午饭\n'
    second = CSV_HEADER + CSV_HEADER2 + \
        '支出,2025-01-07 12:00:07,餐饮,午餐,,支付宝,CNY,30.00,,麦当劳,午饭\n'

    assert _upload(first)['created'] == 1
    result = _upload(second)

    assert result['created'] == 0, '同一天同一笔不该再插一条'
    assert result['duplicated'] == 1
    assert _bill_count() == 1


@pytest.mark.django_db
def test_import_two_identical_rows_in_one_file_both_created() -> None:
    """反证：同一天两笔真的一模一样的消费，**不能被判成重复**。

    按天判重最容易犯的错是「这一天有一笔 15 元了 ⇒ 后面的 15 元都算重复」。
    这里用计重数（Counter）防止那种误杀：库里 0 条、文件里 2 条 ⇒ 建 2 条。
    """
    content = (
        CSV_HEADER + CSV_HEADER2 +
        '支出,2025-01-07 09:00:00,餐饮,咖啡,,支付宝,CNY,15.00,,Manner,早咖啡\n'
        '支出,2025-01-07 15:30:00,餐饮,咖啡,,支付宝,CNY,15.00,,Manner,下午咖啡\n'
    )
    result = _upload(content)

    assert result['created'] == 2
    assert result['duplicated'] == 0
    assert _bill_count() == 2


@pytest.mark.django_db
def test_import_same_day_different_amount_not_duplicate() -> None:
    """同一天、同类型、金额不同 ⇒ 是两笔，不能判重。"""
    content = (
        CSV_HEADER + CSV_HEADER2 +
        '支出,2025-01-07 12:00:00,餐饮,午餐,,支付宝,CNY,30.00,,麦当劳,午饭\n'
        '支出,2025-01-07 19:00:00,餐饮,晚餐,,支付宝,CNY,45.00,,真功夫,晚饭\n'
    )
    result = _upload(content)

    assert result['created'] == 2
    assert result['duplicated'] == 0


@pytest.mark.django_db
def test_import_multiset_dedup_against_existing_day() -> None:
    """库里已有 1 条 15 元；新文件里 2 条 15 元 ⇒ 只补插 1 条。"""
    base = '支出,2025-01-07 09:00:00,餐饮,咖啡,,支付宝,CNY,15.00,,Manner,早咖啡\n'
    assert _upload(CSV_HEADER + CSV_HEADER2 + base)['created'] == 1

    two_rows = (
        CSV_HEADER + CSV_HEADER2 +
        '支出,2025-01-07 09:00:00,餐饮,咖啡,,支付宝,CNY,15.00,,Manner,早咖啡\n'
        '支出,2025-01-07 15:30:00,餐饮,咖啡,,支付宝,CNY,15.00,,Manner,下午咖啡\n'
    )
    result = _upload(two_rows)

    assert result['duplicated'] == 1, '库里那 1 条要判重'
    assert result['created'] == 1, '多出来的那 1 条要补插'
    assert _bill_count() == 2


@pytest.mark.django_db
def test_import_different_day_not_duplicate() -> None:
    """跨天同金额同类型 ⇒ 两笔。半开区间不能把边界日吞掉。"""
    content = (
        CSV_HEADER + CSV_HEADER2 +
        '支出,2025-01-07 12:00:00,餐饮,午餐,,支付宝,CNY,30.00,,麦当劳,午饭\n'
        '支出,2025-01-08 12:00:00,餐饮,午餐,,支付宝,CNY,30.00,,麦当劳,午饭\n'
    )
    result = _upload(content)

    assert result['created'] == 2
    assert result['duplicated'] == 0
