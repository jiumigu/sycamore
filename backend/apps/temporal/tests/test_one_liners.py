"""一句话回顾（`remark` → 按天倒序）的取数与接口。

这里守的是四件事：空白不算写过、一天只出一句、分母不跟关键词变、参数错要报 400。
"""

from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.temporal.models import OneDayPage
from apps.temporal.services import compute_one_liners

pytestmark = pytest.mark.django_db

URL = '/api/temporal/oneday/one_liners/'


def _row(day, remark=None, *, title='普通一天', total=0, otype='ONEDAY', flag=None):
    return OneDayPage.objects.create(
        title=title, begin_date=day, remark=remark, total=total,
        otype=otype, flag=flag, years=str(day.year),
    )


class TestComputeOneLiners:
    def test_only_rows_with_text_are_listed(self):
        _row(date(2026, 11, 1), '第一句')
        _row(date(2026, 11, 2), None)
        _row(date(2026, 11, 3), '')
        _row(date(2026, 11, 4), '   ')  # 纯空格 ≠ 写过

        data = compute_one_liners()
        assert [i['one_liner'] for i in data['items']] == ['第一句']
        assert data['summary']['days_with_liner'] == 1
        # 分母是「有日记的天数」，空格那几天也算写过日记
        assert data['summary']['days_total'] == 4

    def test_one_line_per_day_newest_oid_wins(self):
        _row(date(2026, 11, 5), '旧的那条')
        newer = _row(date(2026, 11, 5), '新的那条')

        data = compute_one_liners()
        assert len(data['items']) == 1
        assert data['items'][0]['one_liner'] == '新的那条'
        assert data['items'][0]['oid'] == newer.oid

    def test_sorted_by_date_desc_and_weekday_from_constants(self):
        _row(date(2026, 11, 2), '周一那天')   # 2026-11-02 是周一
        _row(date(2026, 11, 8), '周日那天')

        items = compute_one_liners()['items']
        assert [i['date'] for i in items] == ['2026-11-08', '2026-11-02']
        assert items[0]['weekday'] == '周日'
        assert items[1]['weekday'] == '周一'

    def test_year_filter_only_shrinks_items_not_years(self):
        _row(date(2025, 12, 31), '跨年前一天')
        _row(date(2026, 1, 1), '元旦')
        _row(date(2026, 1, 2), None)

        data = compute_one_liners(year=2026)
        assert [i['one_liner'] for i in data['items']] == ['元旦']
        # 年份按钮要能点回 2025，所以 years 不受当前筛选影响
        assert data['years'] == [2026, 2025]
        # 分母只算 2026 年写过的天数
        assert data['summary']['days_total'] == 2

    def test_keyword_does_not_change_denominator(self):
        _row(date(2026, 11, 1), '当初为什么要离职')
        _row(date(2026, 11, 2), '榴莲很好吃')
        _row(date(2026, 11, 3), None)

        data = compute_one_liners(keyword='离职')
        assert data['summary']['days_with_liner'] == 1
        assert data['summary']['days_total'] == 3
        assert data['summary']['keyword'] == '离职'
        assert data['items'][0]['one_liner'] == '当初为什么要离职'

    def test_keyword_is_case_insensitive(self):
        _row(date(2026, 11, 1), '第一次用 Django')
        assert compute_one_liners(keyword='django')['summary']['days_with_liner'] == 1

    def test_tags_split_and_blank_dropped(self):
        _row(date(2026, 11, 1), '写了点东西', flag='值得留, 思考')
        _row(date(2026, 11, 2), '空标签', flag='')
        items = compute_one_liners()['items']  # 倒序：11-02 在前
        assert items[0]['tags'] == []
        assert items[1]['tags'] == ['值得留', '思考']

    def test_empty_table_returns_zero_not_error(self):
        data = compute_one_liners()
        assert data['items'] == []
        assert data['years'] == []
        assert data['summary']['days_with_liner'] == 0
        assert data['summary']['latest_date'] is None

    def test_latest_and_earliest_are_not_swapped(self):
        _row(date(2026, 1, 1), '最早')
        _row(date(2026, 11, 20), '最新')
        s = compute_one_liners()['summary']
        assert s['latest_date'] == '2026-11-20'
        assert s['earliest_date'] == '2026-01-01'


class TestOneLinersApi:
    def test_ok_with_year_and_q(self):
        _row(date(2026, 3, 5), '挣扎的上班')
        client = APIClient()

        body = client.get(URL).json()
        assert body['summary']['days_with_liner'] == 1
        assert body['items'][0]['one_liner'] == '挣扎的上班'

        body = client.get(URL, {'year': '2026', 'q': '上班'}).json()
        assert body['summary']['days_with_liner'] == 1
        assert body['summary']['year'] == 2026

    def test_bad_year_is_400_not_empty_list(self):
        client = APIClient()
        assert client.get(URL, {'year': 'abc'}).status_code == 400
        assert client.get(URL, {'year': '99999'}).status_code == 400

    def test_year_with_no_liner_is_empty_not_400(self):
        _row(date(2026, 3, 5), '有内容')
        body = APIClient().get(URL, {'year': '2025'}).json()
        assert body['items'] == []
        assert body['summary']['days_total'] == 0
