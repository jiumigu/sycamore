"""落库回归：换解析器之后，真实导出文件的三项计数必须与旧实现逐字一致。

为什么单开一份
==============
`test_bill_import.py` 测的是行为细节（判重、负数、缺列），会随口径调整而变化。
这份测的是**一次真实迁移的回归基线**：拿 15 行「随手记原格式」CSV，
`created / skipped / duplicated` 必须是 13 / 2 / 0。

这三个数是在 v3.65 改造**之前**跑旧接口实测记录的，不是推算的。
不同就是改坏了 —— 说明新的按列名解析与旧的按位置解析在真实数据上分了叉。

🔴 里含 `转入` / `转出` 行：它们是随手记真实存在的值（开发库 67 + 67 条），
   必须原样入库。判成 error 就等于「以前导得进、以后导不进」，而且没提示。
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from rest_framework.test import APIClient

IMPORT_URL = '/api/wealth/import/csv/'

HEADER = '交易类型,日期,分类,子分类,项目,账户,币种,金额,成员,商家,备注\n'

REAL_ROWS = """支出,2026-06-01 06:44:05,日常生活,日常用品,,叶子,CNY,9.86,,淘宝,临时马桶
支出,2026-06-01 12:36:02,日常生活,日常用品,,叶子,CNY,8.64,,淘宝,修眉刀
支出,2026-06-01 12:36:22,食品酒水,早午晚餐,,叶子,CNY,6.00,,,店下炒米粉
支出,2026-06-02 11:57:51,食品酒水,早午晚餐,,叶子,CNY,6.00,,,寿宁米糕
支出,2026-06-03 06:58:54,日常生活,话费,,叶子,CNY,50.00,,,
支出,2026-06-03 07:05:29,日常生活,日常用品,,叶子,CNY,18.87,,淘宝,蚊香盘
支出,2026-06-03 07:24:01,日常生活,家居装饰,,叶子,CNY,228.54,,淘宝,外墙防水涂料
支出,2026-06-03 07:44:17,日常生活,日常用品,,叶子,CNY,284.86,,淘宝,"书包，雨伞，干燥剂"
转入,2026-06-03 12:23:56,,,,应收款项,CNY,199.50,,,#代付: 猫咪# 话费
转出,2026-06-03 12:23:56,,,,叶子,CNY,199.50,,,#代付: 猫咪# 话费
转入,2026-06-03 12:23:56,,,,应收款项,CNY,0.00,,,#代付: 猫咪#
转出,2026-06-03 12:23:56,,,,叶子,CNY,0.00,,,#代付: 猫咪#
支出,2026-06-01 06:44:05,日常生活,日常用品,,叶子,CNY,9.86,,淘宝,临时马桶
支出,坏日期,日常生活,日常用品,,叶子,CNY,9.86,,淘宝,x
支出,9.86
"""

#: 两行表头 + 15 行数据，与随手记导出的物理结构一致
REAL_CSV = HEADER + HEADER + REAL_ROWS


def _upload(content: str, **extra) -> dict:
    client = APIClient()
    payload = {
        'file': SimpleUploadedFile('real.csv', content.encode('utf-8-sig')),
        'user_id': 1,
    }
    payload.update(extra)
    return client.post(IMPORT_URL, payload, format='multipart').data


def _bill_count() -> int:
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) FROM wealth_bill_list')
        return cursor.fetchone()[0]


@pytest.mark.django_db
def test_legacy_baseline_numbers_unchanged() -> None:
    """旧实现实测：created 13 / skipped 2 / duplicated 0 / total 15。"""
    result = _upload(REAL_CSV)
    assert result['created'] == 13
    assert result['skipped'] == 2
    assert result['duplicated'] == 0
    assert result['total'] == 15
    assert _bill_count() == 13


@pytest.mark.django_db
def test_reimport_same_file_creates_nothing() -> None:
    """同一份文件导第二次：一条都不新增，全部判重。"""
    assert _upload(REAL_CSV)['created'] == 13
    second = _upload(REAL_CSV)
    assert second['created'] == 0
    assert second['duplicated'] == 13
    assert _bill_count() == 13


@pytest.mark.django_db
def test_transfer_rows_are_kept_verbatim() -> None:
    """转入/转出不是收支，但是代付凭据 —— 原样入库，不判成错误行。"""
    _upload(REAL_CSV)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT transaction_type, COUNT(*) FROM wealth_bill_list "
            "WHERE transaction_type IN ('转入', '转出') GROUP BY transaction_type"
        )
        counts = dict(cursor.fetchall())
    assert counts == {'转入': 2, '转出': 2}


@pytest.mark.django_db
def test_project_member_currency_are_written() -> None:
    """旧实现手写 15 列，静默漏掉这三列 ⇒ 导进去永远为空。"""
    content = (
        '交易类型,日期,分类,子分类,项目,账户,币种,金额,成员,商家,备注\n'
        '支出,2026-05-01 12:00:00,餐饮,午餐,自建项目,支付宝,USD,30.00,叶子,麦当劳,午饭\n'
    )
    assert _upload(content)['created'] == 1
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT project, member, account_currency, year, month, day '
            'FROM wealth_bill_list'
        )
        row = cursor.fetchone()
    assert row[0] == '自建项目'
    assert row[1] == '叶子'
    assert row[2] == 'USD'
    assert row[3:] == (2026, 5, 1), 'year/month/day 必须落，月历按这三列分组'


@pytest.mark.django_db
def test_skip_rows_counts_separately_from_errors() -> None:
    """预览里勾掉的行单独计数，不混进「出错」。"""
    content = (
        '交易类型,日期,分类,子分类,项目,账户,币种,金额,成员,商家,备注\n'
        '支出,2026-05-01 12:00:00,餐饮,午餐,,支付宝,CNY,30.00,,麦当劳,午饭\n'
        '支出,2026-05-02 12:00:00,餐饮,午餐,,支付宝,CNY,40.00,,麦当劳,午饭\n'
    )
    result = _upload(content, skip_rows='[2]')
    assert result['created'] == 1
    assert result['skipped_by_user'] == 1
    assert result['skipped'] == 0
    assert result['total'] == 2


@pytest.mark.django_db
def test_user_mapping_overrides_auto_detection() -> None:
    """列名认不出时，用户手选的映射整份取代自动识别。"""
    content = (
        '花销日,花销钱,方向\n'
        '2026-05-01 12:00:00,30.00,支出\n'
    )
    # 先确认：不传映射 ⇒ 400，且把列名列出来给用户指认
    client = APIClient()
    resp = client.post(
        IMPORT_URL,
        {'file': SimpleUploadedFile('x.csv', content.encode('utf-8-sig'))},
        format='multipart',
    )
    assert resp.status_code == 400
    assert resp.json()['code'] == 'missing_required'
    assert [c['raw'] for c in resp.json()['columns']] == ['花销日', '花销钱', '方向']

    # 传了映射 ⇒ 导得进来
    result = _upload(
        content,
        mapping='{"花销日": "date", "花销钱": "amount", "方向": "transaction_type"}',
    )
    assert result['created'] == 1
    with connection.cursor() as cursor:
        cursor.execute('SELECT amount, transaction_type, category FROM wealth_bill_list')
        amount, ttype, category = cursor.fetchone()
    assert float(amount) == 30.0
    assert ttype == '支出'
    assert category in (None, ''), '没映射的列必须留空，不能从别的列借值'


@pytest.mark.django_db
def test_missing_type_column_without_default_returns_400() -> None:
    """没有类型列又没指定方向 ⇒ 400。猜方向等于替用户决定钱的流向。"""
    content = '日期,金额,分类\n2026-05-01 12:00:00,30.00,餐饮\n'
    client = APIClient()
    resp = client.post(
        IMPORT_URL,
        {'file': SimpleUploadedFile('x.csv', content.encode('utf-8-sig'))},
        format='multipart',
    )
    assert resp.status_code == 400
    assert resp.json()['code'] == 'needs_default_type'
    assert _bill_count() == 0


@pytest.mark.django_db
def test_missing_type_column_with_default_imports() -> None:
    content = '日期,金额,分类\n2026-05-01 12:00:00,30.00,餐饮\n'
    result = _upload(content, default_type='支出')
    assert result['created'] == 1
    with connection.cursor() as cursor:
        cursor.execute('SELECT transaction_type FROM wealth_bill_list')
        assert cursor.fetchone()[0] == '支出'
