"""小确幸列表按标签筛选 — apps.sugar.views.SugarRecordViewSet

这一组守的核心是**「筛得到」与「筛得准」的区别**。

`tags` 是逗号分隔字符串，库里同时存在「成就」「内在成就」「外在成就」——
三者互为子串。用 `contains` 筛「成就」会得到 19 条而不是 6 条，
既不会 500、也不会返空，只是**悄悄多给了 13 条**。
所以每条断言的都是一等一的具体条数，不是「没报错」。
"""
import pytest
from rest_framework.test import APIClient

from apps.sugar.constants import TAG_UNTAGGED_LABEL, TAG_UNTAGGED_PARAM
from apps.sugar.models import SugarRecord

RECORDS_URL = '/api/sugar/records/'
OPTIONS_URL = '/api/sugar/records/tags/'
CATEGORIES_URL = '/api/sugar/categories/'


def _make(title: str, tags: str | None, day: str = '2026-03-05', level: float = 10) -> SugarRecord:
    """直接建记录（不走接口）：接口会顺带发奖，与本文件无关。"""
    return SugarRecord.objects.create(
        title=title,
        tags=tags,
        joy_type='',
        time=day,
        level_of_happiness=level,
        reward_amount=level,
        reward_synced=True,
        years=int(day[:4]),
        month=int(day[5:7]),
    )


def _ids(resp) -> list[int]:
    return sorted(row['s_id'] for row in resp.data['results'])


# ─── 精确匹配（本功能唯一容易做错的地方） ───

@pytest.mark.django_db
def test_substring_tag_does_not_leak_into_exact_match() -> None:
    """🔴 筛「成就」不能把「内在成就」「外在成就」一起捞出来

    这是整组里最重要的一条。库里的三个成就标签互为子串，
    任何 `tags__contains` 实现都会让「成就」从 6 条变成 19 条。
    """
    plain = _make('就是成就', '成就')
    _make('内在的', '内在成就')
    _make('外在的', '外在成就')

    resp = APIClient().get(RECORDS_URL, {'tag': '成就', 'page_size': 100})

    assert resp.data['count'] == 1
    assert _ids(resp) == [plain.s_id]


@pytest.mark.django_db
def test_longer_tag_does_not_match_shorter_one() -> None:
    """反过来也要成立：筛「内在成就」不该带上「成就」"""
    _make('就是成就', '成就')
    inner = _make('内在的', '内在成就')

    resp = APIClient().get(RECORDS_URL, {'tag': '内在成就', 'page_size': 100})

    assert _ids(resp) == [inner.s_id]


@pytest.mark.django_db
def test_multi_tag_record_is_found_by_each_of_its_tags() -> None:
    """一条记录带多个标签时，按其中任何一个都能筛到它"""
    both = _make('两个标签', '美食,成就')
    only_food = _make('只有美食', '美食')

    food = APIClient().get(RECORDS_URL, {'tag': '美食', 'page_size': 100})
    achievement = APIClient().get(RECORDS_URL, {'tag': '成就', 'page_size': 100})

    assert _ids(food) == sorted([both.s_id, only_food.s_id])
    assert _ids(achievement) == [both.s_id]


@pytest.mark.django_db
def test_tag_at_string_boundaries_matches() -> None:
    """标签在串首 / 串尾时也要命中 —— 正则的 `(^|,)` 与 `(,|$)` 各管一头"""
    head = _make('在开头', '成就,美食')
    tail = _make('在结尾', '美食,成就')

    resp = APIClient().get(RECORDS_URL, {'tag': '成就', 'page_size': 100})

    assert _ids(resp) == sorted([head.s_id, tail.s_id])


@pytest.mark.django_db
def test_tag_with_space_after_comma_still_matches() -> None:
    """历史手工录入可能在逗号后留空格 —— 那时下拉能显示、却筛不到，最难查"""
    spaced = _make('带空格', '美食, 成就')

    resp = APIClient().get(RECORDS_URL, {'tag': '成就', 'page_size': 100})

    assert _ids(resp) == [spaced.s_id]


# ─── 无标签与空参数 ───

@pytest.mark.django_db
def test_untagged_sentinel_selects_null_and_empty() -> None:
    """🔴 NULL 与空串是同一件事（没打标签），漏一种就会少几十条"""
    null_one = _make('NULL 标签', None)
    empty_one = _make('空串标签', '')
    _make('有标签', '成就')

    resp = APIClient().get(RECORDS_URL, {'tag': TAG_UNTAGGED_PARAM, 'page_size': 100})

    assert resp.data['count'] == 2
    assert _ids(resp) == sorted([null_one.s_id, empty_one.s_id])


@pytest.mark.django_db
def test_empty_tag_param_means_no_filter() -> None:
    """`?tag=`（清空下拉）必须等于不筛，而不是「只看无标签」"""
    _make('没打标签', None)
    _make('打了标签', '成就')

    resp = APIClient().get(RECORDS_URL, {'tag': '', 'page_size': 100})

    assert resp.data['count'] == 2


@pytest.mark.django_db
def test_tag_combines_with_year_scope() -> None:
    """标签与年份是 AND —— 两者必须同时生效，不能一个盖掉另一个"""
    _make('2026 成就', '成就', day='2026-03-05')
    _make('2025 成就', '成就', day='2025-03-05')

    resp = APIClient().get(RECORDS_URL, {'tag': '成就', 'year': 2026, 'page_size': 100})

    assert resp.data['count'] == 1


# ─── 选项接口 ───

@pytest.mark.django_db
def test_options_list_every_tag_with_count() -> None:
    _make('一', '美食,成就')
    _make('二', '美食')

    options = APIClient().get(OPTIONS_URL).data['options']
    by_value = {o['value']: o for o in options}

    assert by_value['美食']['count'] == 2
    assert by_value['成就']['count'] == 1
    assert by_value['美食']['kind'] == 'tag'
    # 条数降序：美食(2) 排在 成就(1) 前面
    assert [o['value'] for o in options if o['kind'] == 'tag'] == ['美食', '成就']


@pytest.mark.django_db
def test_options_include_untagged_with_sentinel() -> None:
    _make('有标签', '美食')
    _make('没标签', None)
    _make('空标签', '')

    data = APIClient().get(OPTIONS_URL).data
    untagged = [o for o in data['options'] if o['kind'] == 'untagged']

    assert len(untagged) == 1
    assert untagged[0]['value'] == TAG_UNTAGGED_PARAM
    assert untagged[0]['label'] == TAG_UNTAGGED_LABEL
    assert untagged[0]['count'] == 2
    assert data['untagged_value'] == TAG_UNTAGGED_PARAM


@pytest.mark.django_db
def test_options_count_ignores_tag_itself() -> None:
    """选了「成就」之后，别的标签还得显示各自有多少条

    若把 `tag` 自己也算进去，选完就只剩被选中那一项有数字，
    「换一个标签看看」的路就被堵死了 —— 这是静默的、看起来像「本来就没数据」。
    """
    _make('一', '成就')
    _make('二', '美食')

    resp = APIClient().get(OPTIONS_URL, {'tag': '成就'})
    counts = {o['value']: o['count'] for o in resp.data['options']}

    assert counts['成就'] == 1
    assert counts['美食'] == 1


@pytest.mark.django_db
def test_options_set_is_global_but_counts_follow_scope() -> None:
    """选项集合取全库（当期 0 条也列出），条数跟着筛选走"""
    _make('2026 的', '美食', day='2026-03-05')
    _make('2025 的', '旅行', day='2025-03-05')

    resp = APIClient().get(OPTIONS_URL, {'year': 2026})
    by_value = {o['value']: o for o in resp.data['options']}

    assert by_value['美食']['count'] == 1
    # 2026 年没有「旅行」，但选项仍在
    assert by_value['旅行']['count'] == 0
    assert by_value['旅行']['kind'] == 'tag'


@pytest.mark.django_db
def test_options_do_not_duplicate_count_for_repeated_tag_on_one_record() -> None:
    """同一条记录里同一个标签写两遍，只算一条 —— 计数单位是「记录」不是「出现」"""
    _make('重复标签', '美食,美食')

    options = APIClient().get(OPTIONS_URL).data['options']
    by_value = {o['value']: o for o in options}

    assert by_value['美食']['count'] == 1


# ─── 与顶部统计同一把尺子 ───

@pytest.mark.django_db
def test_categories_summary_uses_same_tag_scope_as_list() -> None:
    """顶部「累计获得 / 平均快乐」必须跟下面列出来的是同一批记录"""
    _make('成就一', '成就', level=12)
    _make('成就二', '成就', level=8)
    _make('内在成就', '内在成就', level=20)

    summary = APIClient().get(CATEGORIES_URL, {'tag': '成就'}).data['summary']
    listed = APIClient().get(RECORDS_URL, {'tag': '成就', 'page_size': 100}).data

    assert summary['total_count'] == listed['count'] == 2
    assert summary['total_reward'] == pytest.approx(20.0)
    assert summary['avg_happiness'] == pytest.approx(10.0)
