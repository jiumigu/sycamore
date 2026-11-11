"""账单 CSV 预演（v3.65）—— 按列名映射的解析器

与 `test_bill_import.py` 分开：那份测的是**落库**（第 2 步会换成同一份解析器），
这份测的是「认列 + 逐行校验 + 判重汇总」，且必须证明**预演不写库**。
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from rest_framework.test import APIClient

PREVIEW_URL = '/api/wealth/import/preview/'

SHOUJI_HEADER = '交易类型,日期,分类,子分类,项目,账户,币种,金额,成员,商家,备注'


def _preview(content: str, default_type: str = '') -> dict:
    client = APIClient()
    payload = {'file': SimpleUploadedFile('bills.csv', content.encode('utf-8-sig'))}
    if default_type:
        payload['default_type'] = default_type
    return client.post(PREVIEW_URL, payload, format='multipart').json()


def _preview_status(content: str) -> int:
    client = APIClient()
    return client.post(
        PREVIEW_URL,
        {'file': SimpleUploadedFile('bills.csv', content.encode('utf-8-sig'))},
        format='multipart',
    ).status_code


def _bill_count() -> int:
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) FROM wealth_bill_list')
        return cursor.fetchone()[0]


def _seed_bill(date_str: str, amount: str, ttype: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO wealth_bill_list "
            "(transaction_type, category, amount, date, user_id, year, month, day, created_at, updated_at) "
            "VALUES (%s, '', %s, %s, 1, %s, %s, %s, NOW(), NOW())",
            [ttype, amount, date_str, date_str[:4], date_str[5:7], date_str[8:10]],
        )


# ── 认列：这是整份文件的立身之本 ──────────────────────────

@pytest.mark.django_db
def test_header_recognized_by_name() -> None:
    """按列名认，不按位置：把「金额」挪到第 2 列也必须认对。"""
    content = (
        '日期,金额,交易类型,分类\n'
        '2025-01-07 12:00:00,30.00,支出,餐饮\n'
    )
    resp = _preview(content)
    assert resp['summary']['total'] == 1
    assert resp['summary']['new'] == 1
    mapped = {c['mapped'] for c in resp['columns'] if c['mapped']}
    assert mapped == {'date', 'amount', 'transaction_type', 'category'}


@pytest.mark.django_db
def test_english_column_names() -> None:
    """英文列名同样认（将来从多维表/自建 Excel 导出时用得上）。"""
    content = 'date,amount,type,category\n2025-01-07 12:00:00,30.00,支出,餐饮\n'
    resp = _preview(content)
    assert resp['summary']['new'] == 1


@pytest.mark.django_db
def test_column_name_with_spaces_is_normalized() -> None:
    """「账户 」「金额」这种带空格/全角空格的列名不该让用户手动去指。"""
    content = '日期,金额 ,　交易类型\n2025-01-07 12:00:00,30.00,支出\n'
    resp = _preview(content)
    assert resp['summary']['new'] == 1


@pytest.mark.django_db
def test_header_found_below_title_row() -> None:
    """表头前有标题行时也能定位（旧实现固定 `rows[2:]`，多一行就全错位）。"""
    content = (
        '随手记账单导出\n'
        + SHOUJI_HEADER + '\n'
        '支出,2025-01-07 12:00:00,餐饮,午餐,,支付宝,CNY,30.00,,麦当劳,午饭\n'
    )
    resp = _preview(content)
    assert resp['header_row'] == 2
    assert resp['summary']['new'] == 1


@pytest.mark.django_db
def test_duplicate_header_rows_are_skipped() -> None:
    """随手记的导出是两行列名 —— 第二行表头不能被当成数据行报错。"""
    content = (
        SHOUJI_HEADER + '\n' + SHOUJI_HEADER + '\n'
        '支出,2025-01-07 12:00:00,餐饮,午餐,,支付宝,CNY,30.00,,麦当劳,午饭\n'
    )
    resp = _preview(content)
    assert resp['summary']['total'] == 1
    assert resp['summary']['error'] == 0
    assert resp['summary']['new'] == 1


# ── 整份文件不可用：400 里必须说清缺哪列 ──────────────────

def test_missing_amount_column_returns_400_with_column_name() -> None:
    """缺金额列 ⇒ 400，且指名缺哪列。不许「导入 0 条但显示成功」。"""
    client = APIClient()
    resp = client.post(
        PREVIEW_URL,
        {'file': SimpleUploadedFile('bad.csv', '日期,分类\n2025-01-07,餐饮\n'.encode('utf-8-sig'))},
        format='multipart',
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body['code'] == 'missing_required'
    assert body['missing_required'] == ['amount']
    assert '金额' in body['error']


def test_header_only_file_returns_400() -> None:
    """只有表头没有数据行 ⇒ 400，不是「成功导入 0 条」。"""
    assert _preview_status(SHOUJI_HEADER + '\n') == 400


def test_garbage_file_returns_400() -> None:
    """认不出表头 ⇒ 400。"""
    assert _preview_status('a,b\n1,2\n') == 400


def test_unknown_columns_are_listed_for_manual_mapping() -> None:
    """列名全不认识时，400 里必须带列清单 —— 否则那份文件永远导不进来。

    只回「没找到表头」的话，用户手上没有任何可操作的东西。
    """
    client = APIClient()
    resp = client.post(
        PREVIEW_URL,
        {'file': SimpleUploadedFile('x.csv', '花销日,花销钱\n2026-05-01,30\n'.encode('utf-8-sig'))},
        format='multipart',
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body['code'] == 'missing_required'
    assert [c['raw'] for c in body['columns']] == ['花销日', '花销钱']


@pytest.mark.django_db
def test_user_mapping_makes_unknown_file_readable() -> None:
    """手工指认列之后，同一份文件就能预演。"""
    content = '花销日,花销钱,方向\n2026-05-01 12:00:00,30.00,支出\n'
    client = APIClient()
    resp = client.post(
        PREVIEW_URL,
        {
            'file': SimpleUploadedFile('x.csv', content.encode('utf-8-sig')),
            'mapping': '{"花销日": "date", "花销钱": "amount", "方向": "transaction_type"}',
        },
        format='multipart',
    )
    assert resp.status_code == 200
    assert resp.json()['summary']['new'] == 1


@pytest.mark.django_db
def test_user_mapping_replaces_auto_detection() -> None:
    """用户把某列清空 ⇒ 那一列就是没认出来，不许偷偷沿用自动识别的结果。"""
    content = '日期,金额,交易类型\n2026-05-01 12:00:00,30.00,支出\n'
    client = APIClient()
    resp = client.post(
        PREVIEW_URL,
        {
            'file': SimpleUploadedFile('x.csv', content.encode('utf-8-sig')),
            'mapping': '{"日期": "date", "金额": "amount", "交易类型": ""}',
        },
        format='multipart',
    )
    body = resp.json()
    assert body['needs_default_type'] is True, '清空了类型列 ⇒ 应要求指定方向'
    assert body['rows'][0]['type'] == ''


# ── 收支类型 ──────────────────────────────────────────────

@pytest.mark.django_db
def test_missing_type_column_needs_default_type() -> None:
    """没有类型列时，预演照常返回（先让人看见数据），但要求落库时指定方向。"""
    content = '日期,金额,分类\n2025-01-07 12:00:00,30.00,餐饮\n'
    resp = _preview(content)
    assert resp['needs_default_type'] is True
    assert resp['summary']['new'] == 1
    assert resp['rows'][0]['type'] == ''


@pytest.mark.django_db
def test_default_type_fills_missing_type() -> None:
    content = '日期,金额,分类\n2025-01-07 12:00:00,30.00,餐饮\n'
    resp = _preview(content, default_type='支出')
    assert resp['needs_default_type'] is True
    assert resp['rows'][0]['type'] == '支出'


@pytest.mark.django_db
def test_unknown_type_value_is_error_row_not_silent() -> None:
    """「转账」不认识 ⇒ 该行 error。旧实现会原样入库，收支统计悄悄少算。"""
    content = (
        '日期,金额,交易类型\n'
        '2025-01-07 12:00:00,30.00,转账\n'
        '2025-01-08 12:00:00,20.00,支出\n'
    )
    resp = _preview(content)
    assert resp['summary']['error'] == 1
    assert resp['summary']['new'] == 1
    err = [r for r in resp['rows'] if r['verdict'] == 'error'][0]
    assert err['row_no'] == 2
    assert '转账' in err['reason']


@pytest.mark.django_db
def test_transfer_types_are_accepted() -> None:
    """转入/转出/余额变更 是随手记真实存在的值（开发库 67/67/3 条）。

    它们不是收支、不进收支统计，但判成 error 就等于「以前导得进、以后导不进」。
    """
    content = (
        '日期,金额,交易类型\n'
        '2026-06-03 12:23:56,199.50,转入\n'
        '2026-06-03 12:23:56,199.50,转出\n'
        '2026-06-04 12:23:56,1.00,余额变更\n'
    )
    resp = _preview(content)
    assert resp['summary']['error'] == 0
    assert resp['summary']['new'] == 3
    assert {r['type'] for r in resp['rows']} == {'转入', '转出', '余额变更'}


# ── 逐行校验 ──────────────────────────────────────────────

@pytest.mark.django_db
def test_supported_date_formats() -> None:
    """四种日期格式都要认（旧实现只认到秒的一种）。"""
    content = (
        '日期,金额,交易类型\n'
        '2025-01-07 12:00:00,1.00,支出\n'
        '2025-01-08 12:00,1.00,支出\n'
        '2025-01-09,1.00,支出\n'
        '2025/01/10,1.00,支出\n'
    )
    resp = _preview(content)
    assert resp['summary']['error'] == 0
    assert resp['summary']['new'] == 4


@pytest.mark.django_db
def test_bad_date_is_error_with_row_number() -> None:
    """日期认不出 ⇒ 该行 error 且带物理行号，不是静默 skip。"""
    content = (
        '日期,金额,交易类型\n'
        '2025-01-07 12:00:00,1.00,支出\n'
        '昨天,2.00,支出\n'
    )
    resp = _preview(content)
    assert resp['summary']['error'] == 1
    err = [r for r in resp['rows'] if r['verdict'] == 'error'][0]
    assert err['row_no'] == 3


@pytest.mark.django_db
def test_negative_amount_takes_abs_and_says_so() -> None:
    content = '日期,金额,交易类型\n2025-01-07 12:00:00,-30.00,支出\n'
    resp = _preview(content)
    assert resp['summary']['new'] == 1
    assert '绝对值' in resp['rows'][0]['reason']


@pytest.mark.django_db
def test_blank_rows_are_ignored() -> None:
    content = '日期,金额,交易类型\n2025-01-07 12:00:00,1.00,支出\n,,,\n'
    resp = _preview(content)
    assert resp['summary']['total'] == 1
    assert resp['summary']['error'] == 0


@pytest.mark.django_db
def test_field_options_are_served_for_the_mapping_dropdown() -> None:
    """映射下拉的候选由后端给：成功与 400 两条路径都要带。

    前端不持有字段名常量 —— 缺了这份候选，界面上就选不到字段，
    而报错是「下拉是空的」，看不出是接口少了一个字段。
    """
    ok = _preview('日期,金额,交易类型\n2025-01-07 12:00:00,30.00,支出\n')
    options = {o['value']: o for o in ok['field_options']}
    assert set(options) == {
        'date', 'amount', 'transaction_type', 'category', 'subcategory',
        'project', 'account', 'account_currency', 'member', 'merchant', 'notes',
    }
    assert options['date']['label'] == '日期'
    assert options['date']['required'] is True
    assert options['notes']['required'] is False

    # 400 也要带：认不出列名的文件正是最需要这份候选的时候
    client = APIClient()
    bad = client.post(
        PREVIEW_URL,
        {'file': SimpleUploadedFile('x.csv', '花销日,花销钱\n2026-05-01,30\n'.encode('utf-8-sig'))},
        format='multipart',
    )
    assert bad.status_code == 400
    assert len(bad.json()['field_options']) == 11


# ── 判重：口径必须与落库一致 ──────────────────────────────

@pytest.mark.django_db
def test_existing_bill_is_duplicate() -> None:
    _seed_bill('2025-01-07 12:00:00', '30.00', '支出')
    content = '日期,金额,交易类型\n2025-01-07 19:00:00,30.00,支出\n'
    resp = _preview(content)
    assert resp['summary']['duplicate'] == 1
    assert resp['summary']['new'] == 0


@pytest.mark.django_db
def test_two_identical_rows_in_one_file_are_both_new() -> None:
    """同一天两杯 15 元咖啡是真的两笔 —— 文件内重复**不丢**，只提示。"""
    content = (
        '日期,金额,交易类型\n'
        '2025-01-07 09:00:00,15.00,支出\n'
        '2025-01-07 15:30:00,15.00,支出\n'
    )
    resp = _preview(content)
    assert resp['summary']['new'] == 2
    assert resp['summary']['duplicate'] == 0
    assert resp['summary']['inner_duplicate'] == 1


@pytest.mark.django_db
def test_same_day_different_amount_not_duplicate() -> None:
    _seed_bill('2025-01-07 12:00:00', '30.00', '支出')
    content = '日期,金额,交易类型\n2025-01-07 19:00:00,45.00,支出\n'
    assert _preview(content)['summary']['duplicate'] == 0


@pytest.mark.django_db
def test_same_amount_different_type_not_duplicate() -> None:
    """同一天同金额但一收一支 ⇒ 两笔，不能互相判重。"""
    _seed_bill('2025-01-07 12:00:00', '30.00', '支出')
    content = '日期,金额,交易类型\n2025-01-07 12:00:00,30.00,收入\n'
    assert _preview(content)['summary']['duplicate'] == 0


# ── 不变量与只读 ──────────────────────────────────────────

@pytest.mark.django_db
def test_summary_is_additive() -> None:
    """total = new + duplicate + error（inner_duplicate 是 new 的子集，不参与相加）。"""
    _seed_bill('2025-01-07 12:00:00', '30.00', '支出')
    content = (
        '日期,金额,交易类型\n'
        '2025-01-07 19:00:00,30.00,支出\n'
        '2025-01-08 12:00:00,20.00,支出\n'
        '昨天,1.00,支出\n'
    )
    s = _preview(content)['summary']
    assert s['total'] == s['new'] + s['duplicate'] + s['error']
    assert (s['new'], s['duplicate'], s['error']) == (1, 1, 1)


@pytest.mark.django_db
def test_preview_never_writes() -> None:
    """预演是只读的：连调两次，库中行数不变。"""
    before = _bill_count()
    content = '日期,金额,交易类型\n2025-01-07 12:00:00,30.00,支出\n'
    _preview(content)
    _preview(content)
    assert _bill_count() == before
