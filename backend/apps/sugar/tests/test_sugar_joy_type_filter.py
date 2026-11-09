"""小确幸列表按快乐类型筛选 — apps.sugar.views.SugarRecordViewSet

这一组测试守的都是「不报错但少了几行」的失效方式：
筛选值写错一个字不会 500、只会静静返回全量；选项漏一种，那几条记录
就永远筛不出来。所以每条都断言「拿到的条数」而不是「没报错」。
"""
import pytest
from rest_framework.test import APIClient

from apps.sugar.constants import (
    JOY_TYPE_LEGACY_SUFFIX,
    JOY_TYPE_UNLABELED_LABEL,
    JOY_TYPE_UNLABELED_PARAM,
)
from apps.sugar.models import SugarRecord

RECORDS_URL = '/api/sugar/records/'
OPTIONS_URL = '/api/sugar/records/joy_types/'
CATEGORIES_URL = '/api/sugar/categories/'


def _make(title: str, joy_type: str, day: str = '2026-03-05', level: float = 10) -> SugarRecord:
    """直接建记录（不走接口）：接口会顺带发奖，与本文件无关。"""
    return SugarRecord.objects.create(
        title=title,
        joy_type=joy_type,
        time=day,
        level_of_happiness=level,
        reward_amount=level,
        reward_synced=True,
        years=int(day[:4]),
        month=int(day[5:7]),
    )


def _ids(resp) -> list[int]:
    return sorted(row['s_id'] for row in resp.data['results'])


def _count(url: str, **params) -> int:
    return APIClient().get(url, params).data['count']


@pytest.mark.django_db
def test_filter_by_standard_type_returns_only_that_type() -> None:
    a = _make('秩序一', '秩序型')
    _make('意外一', '意外型')
    b = _make('秩序二', '秩序型')

    resp = APIClient().get(RECORDS_URL, {'joy_type': '秩序型', 'page_size': 100})

    assert resp.status_code == 200
    assert resp.data['count'] == 2
    assert _ids(resp) == sorted([a.s_id, b.s_id])


@pytest.mark.django_db
def test_unlabeled_sentinel_selects_empty_joy_type() -> None:
    """「未标注」走哨兵值 —— 不能靠空串，空串在 query string 里等于「没传」"""
    blank = _make('没标类型', '')
    _make('标了类型', '秩序型')

    resp = APIClient().get(RECORDS_URL, {'joy_type': JOY_TYPE_UNLABELED_PARAM, 'page_size': 100})

    assert resp.data['count'] == 1
    assert _ids(resp) == [blank.s_id]


@pytest.mark.django_db
def test_empty_joy_type_param_means_no_filter() -> None:
    """`?joy_type=`（清空下拉）必须等于不筛，而不是「只看未标注」"""
    _make('没标类型', '')
    _make('标了类型', '秩序型')

    resp = APIClient().get(RECORDS_URL, {'joy_type': '', 'page_size': 100})

    assert resp.data['count'] == 2


@pytest.mark.django_db
def test_legacy_value_outside_choices_is_filterable() -> None:
    """早期词表残留（不在 choices 里）也必须能筛出来，否则永远清不掉"""
    legacy = _make('早期记的', '社交')
    _make('标准记的', '联结型')

    resp = APIClient().get(RECORDS_URL, {'joy_type': '社交', 'page_size': 100})

    assert resp.data['count'] == 1
    assert _ids(resp) == [legacy.s_id]


@pytest.mark.django_db
def test_options_list_all_five_standard_types_even_when_empty() -> None:
    """一条联结型都没有，它也必须出现在下拉里 —— 否则「能录入、不能筛」"""
    _make('只有秩序', '秩序型')

    resp = APIClient().get(OPTIONS_URL)

    assert resp.status_code == 200
    standard = [o['value'] for o in resp.data['options'] if o['kind'] == 'standard']
    assert standard == ['感官型', '秩序型', '联结型', '意外型', '独处型']
    joined = {o['value']: o['count'] for o in resp.data['options']}
    assert joined['联结型'] == 0


@pytest.mark.django_db
def test_options_include_legacy_values_and_unlabeled() -> None:
    _make('标准', '秩序型')
    _make('旧词', '创造')
    _make('空', '')

    options = APIClient().get(OPTIONS_URL).data['options']
    by_value = {o['value']: o for o in options}

    assert by_value['创造']['kind'] == 'legacy'
    assert by_value['创造']['label'] == f'创造{JOY_TYPE_LEGACY_SUFFIX}'
    assert by_value['创造']['count'] == 1
    assert by_value[JOY_TYPE_UNLABELED_PARAM]['kind'] == 'unlabeled'
    assert by_value[JOY_TYPE_UNLABELED_PARAM]['label'] == JOY_TYPE_UNLABELED_LABEL
    assert by_value[JOY_TYPE_UNLABELED_PARAM]['count'] == 1


@pytest.mark.django_db
def test_options_count_ignores_joy_type_itself() -> None:
    """选了「秩序型」之后，别的类型还得显示各自有多少条"""
    _make('秩序', '秩序型')
    _make('意外', '意外型')

    resp = APIClient().get(OPTIONS_URL, {'joy_type': '秩序型'})
    counts = {o['value']: o['count'] for o in resp.data['options']}

    assert counts['秩序型'] == 1
    assert counts['意外型'] == 1


@pytest.mark.django_db
def test_options_count_follows_year_scope() -> None:
    """选项条数跟着年份变，但选项集合本身不随筛选增减"""
    _make('2026 的', '秩序型', day='2026-03-05')
    _make('2025 的', '秩序型', day='2025-03-05')
    _make('2025 旧词', '社交', day='2025-04-05')

    resp = APIClient().get(OPTIONS_URL, {'year': 2026})
    by_value = {o['value']: o for o in resp.data['options']}

    assert by_value['秩序型']['count'] == 1
    # 2026 年没有旧词记录，但选项仍在（集合取全库）
    assert by_value['社交']['count'] == 0
    assert by_value['社交']['kind'] == 'legacy'


@pytest.mark.django_db
def test_categories_summary_uses_same_scope_as_list() -> None:
    """顶部统计与列表必须同一批记录 —— 否则同屏两个数互相矛盾"""
    _make('秩序一', '秩序型', level=12)
    _make('秩序二', '秩序型', level=8)
    _make('意外一', '意外型', level=20)

    summary = APIClient().get(CATEGORIES_URL, {'joy_type': '秩序型'}).data['summary']

    assert summary['total_count'] == _count(RECORDS_URL, joy_type='秩序型')
    assert summary['total_count'] == 2
    assert summary['total_reward'] == pytest.approx(20.0)
    assert summary['avg_happiness'] == pytest.approx(10.0)
