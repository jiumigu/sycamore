"""列名识别的兜底：同义写法、装饰符、没认出来的列。

起因（2026-11-11）：导入改成按列名识别之后，`消费分类` / `消费子分类`
这类同义列名一个都认不出来，结果是**接口返回「新增 2 条」、库里分类全空**，
用户在账单列表上才看见。按位置取值的老实现反而不会出这个问题，
所以这是一次真实的回归 —— 这组测试钉住它。

🔴 判据只有一条：**列里有的东西，不能因为列名换了个说法就消失。**
"""
import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from rest_framework.test import APIClient

from apps.wealth.services.bill_import_service import parse_bill_csv

PREVIEW_URL = '/api/wealth/import/preview/'
IMPORT_URL = '/api/wealth/import/csv/'


def _parse(content: str):
    return parse_bill_csv(content)


# ── 同义写法 ─────────────────────────────────────────────────

def test_synonym_category_columns_are_recognized() -> None:
    """`消费分类` / `消费子分类` / `类目` / `小类` 都要认成分级分类。"""
    content = (
        '交易类型,日期,消费分类,消费子分类,金额\n'
        '支出,2026-11-10 07:49:51,食品酒水,干货生鲜,243.16\n'
    )
    rec = _parse(content).records[0]
    assert rec.category == '食品酒水'
    assert rec.subcategory == '干货生鲜'

    content2 = (
        '交易类型,日期,类目,小类,金额\n'
        '支出,2026-11-09 22:23:19,食品酒水,早午晚餐,50.00\n'
    )
    rec2 = _parse(content2).records[0]
    assert rec2.category == '食品酒水'
    assert rec2.subcategory == '早午晚餐'


def test_subcategory_is_not_swallowed_by_category() -> None:
    """`子分类` 里含「分类」—— 先判子分类，否则这一列会被当成大类。"""
    content = (
        '日期,金额,交易类型,分类,子分类\n'
        '2026-11-10 07:49:51,243.16,支出,食品酒水,干货生鲜\n'
    )
    rec = _parse(content).records[0]
    assert rec.category == '食品酒水'
    assert rec.subcategory == '干货生鲜'


#: 第二级分类的列名，导出工具的叫法五花八门。穷举一定漏，
#: 所以既扩了关键词表，也加了结构性兜底（见 `_match_header`）。
_SUBCATEGORY_HEADERS = [
    '分类,子分类',
    '类别,子类别',
    '分类,分类2',
    '一级分类,二级分类',
    '消费分类,消费子分类',
    '分类,细分类',
    '分类(一级),分类(二级)',
    '类目,子类目',
    '分类,二级类别',
    ' 分类 , 子分类 ',
    '分类,子类',
]


@pytest.mark.parametrize('header', _SUBCATEGORY_HEADERS)
def test_two_level_category_never_drops_the_second_column(header: str) -> None:
    """两列分类：只要文件里有子分类这一列，就必须进 `subcategory`。

    2026-11-11 第二轮故障：`子类别` / `分类2` / `分类(二级)` 等写法下，
    第二列全被丢弃 —— 分类进来了、子分类空着，接口照旧「新增 2 条」。
    """
    content = f'交易类型,日期,{header},金额\n' '支出,2026-11-10 07:49:51,食品酒水,干货生鲜,243.16\n'
    result = _parse(content)
    rec = result.records[0]
    assert rec.category == '食品酒水', f'表头 {header!r} 的大分类丢了'
    assert rec.subcategory == '干货生鲜', f'表头 {header!r} 的子分类丢了'
    assert result.ignored_columns == [], f'表头 {header!r} 还有列没被认领'


# ── 列名上的装饰 ────────────────────────────────────────────

def test_decorated_header_names_are_cleaned() -> None:
    """必填星号、单位括号、全角空格都和「这一列是什么」无关。"""
    content = (
        '交易类型,日期(必填),*金额（元）,分类[一级]\n'
        '支出,2026-11-10 07:49:51,243.16,食品酒水\n'
    )
    rec = _parse(content).records[0]
    assert str(rec.amount) == '243.16'
    assert rec.category == '食品酒水'
    assert rec.date.strftime('%Y-%m-%d') == '2026-11-10'


def test_exact_match_wins_over_synonym() -> None:
    """`创建时间` 排在 `日期` 前面时，日期不能被它抢走。

    兜底只在精确匹配捡剩下的列上生效 —— 否则「按列名识别」会变成
    「按谁名字里含时间识别」，比按位置更不可预测。
    """
    content = (
        '创建时间,日期,金额,交易类型\n'
        '2026-11-01 08:00:00,2026-11-10 07:49:51,243.16,支出\n'
    )
    rec = _parse(content).records[0]
    assert rec.date.strftime('%Y-%m-%d') == '2026-11-10'


# ── 没认出来的列 ────────────────────────────────────────────

def test_ignored_columns_lists_only_filled_ones() -> None:
    """有值的未识别列必须报出来；整列空着的不报（否则等于噪音）。"""
    content = (
        '交易类型,日期,金额,订单号,标签\n'
        '支出,2026-11-10 07:49:51,243.16,TB20261110001,\n'
        '支出,2026-11-09 22:23:19,50.00,TB20261109002,\n'
    )
    result = _parse(content)
    assert [c['raw'] for c in result.ignored_columns] == ['订单号']
    assert result.ignored_columns[0]['filled'] == 2
    assert result.ignored_columns[0]['sample'] == 'TB20261110001'


# ── 端到端：预演与落库都要留住分类 ───────────────────────────

def _post(url: str, content: str, **extra):
    client = APIClient()
    return client.post(
        url,
        {'file': SimpleUploadedFile('bills.csv', content.encode('utf-8-sig')), **extra},
        format='multipart',
    )


@pytest.mark.django_db
def test_preview_shows_synonym_category() -> None:
    content = (
        '交易类型,日期,消费分类,消费子分类,账户,币种,金额,备注\n'
        '支出,2026-11-10 07:49:51,食品酒水,干货生鲜,叶子,CNY,243.16,天猫超市\n'
    )
    resp = _post(PREVIEW_URL, content)
    data = resp.json()
    assert resp.status_code == 200
    assert data['ignored_columns'] == []
    mapped = {c['raw']: c['mapped'] for c in data['columns']}
    assert mapped['消费分类'] == 'category'
    assert mapped['消费子分类'] == 'subcategory'
    assert data['rows'][0]['category'] == '食品酒水'
    assert data['rows'][0]['subcategory'] == '干货生鲜'


@pytest.mark.django_db
def test_import_keeps_synonym_category() -> None:
    """这条是本次故障的回归判据：库里的分类不能是空的。"""
    content = (
        '交易类型,日期,消费分类,消费子分类,账户,币种,金额,备注\n'
        '支出,2026-11-10 07:49:51,食品酒水,干货生鲜,叶子,CNY,243.16,天猫超市\n'
    )
    preview = _post(PREVIEW_URL, content).json()
    mapping = {c['raw']: c['mapped'] for c in preview['columns']}

    resp = _post(IMPORT_URL, content, mapping=json.dumps(mapping))
    assert resp.status_code == 200
    assert resp.json()['created'] == 1

    with connection.cursor() as cursor:
        cursor.execute('SELECT category, subcategory, account, notes FROM wealth_bill_list')
        category, subcategory, account, notes = cursor.fetchone()
    assert category == '食品酒水'
    assert subcategory == '干货生鲜'
    assert account == '叶子'
    assert notes == '天猫超市'


@pytest.mark.django_db
def test_partial_user_mapping_keeps_detected_columns() -> None:
    """用户只补了日期和金额（其余列由后端在 400 响应里已经认出来并回传），
    前端把这份「已认出的映射」原样带回来，分类不能因此变成未识别。
    """
    content = (
        '交易类型,花销日,消费分类,消费子分类,花销钱\n'
        '支出,2026-11-10 07:49:51,食品酒水,干货生鲜,243.16\n'
    )
    first = _post(PREVIEW_URL, content)
    assert first.status_code == 400
    detected = {c['raw']: c['mapped'] for c in first.json()['columns']}
    assert detected['消费分类'] == 'category'
    assert detected['花销日'] == ''

    # 用户在界面上把两列指对，其余沿用后端已认出的结果
    mapping = {**detected, '花销日': 'date', '花销钱': 'amount'}
    resp = _post(IMPORT_URL, content, mapping=json.dumps(mapping))
    assert resp.status_code == 200

    with connection.cursor() as cursor:
        cursor.execute('SELECT category, subcategory FROM wealth_bill_list')
        assert cursor.fetchone() == ('食品酒水', '干货生鲜')
