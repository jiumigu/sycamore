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
def test_import_invalid_date_format_counts_as_skipped() -> None:
    """边界：非法日期格式的行跳过且不中断"""
    content = (
        CSV_HEADER + CSV_HEADER2 +
        '支出,2025/01/07,餐饮,午餐,,支付宝,CNY,30.00,,麦当劳,午饭\n'
        '收入,2025-01-08 09:00:00,工资,,,银行卡,CNY,5000,,,月薪\n'
    )
    result = _upload(content)
    assert result['skipped'] == 1
    assert result['created'] == 1
