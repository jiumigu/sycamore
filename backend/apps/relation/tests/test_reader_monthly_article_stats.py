"""读者月末复盘：发文篇数与最佳文章阅读数的口径

🔴 这一组测试钉住三件事：
1. 「没盘」(null) 与「发了 0 篇」(0) 是两个含义，序列化与聚合都不许把它们合并；
2. 年度合计在全年都没填时返回 null，不是 0 —— `Sum(...) or 0` 正是要防的写法；
3. 「最佳月份」按新增关注评，全部为 0 时不出结果，不再显示「互动 0 次」的假结论。
"""
import pytest
from rest_framework.test import APIClient

from apps.relation.models import ReaderGroup, ReaderMonthlySummary

LIST = '/api/relation/reader-monthly-summaries/'
STATS = '/api/relation/reader-monthly-summaries/stats/'


@pytest.mark.django_db
class TestReaderMonthlyArticleStats:
    def _group(self, name='公众号读者'):
        return ReaderGroup.objects.create(user_id=1, name=name)

    def _row(self, group, year, month, **kw):
        return ReaderMonthlySummary.objects.create(
            user_id=1, reader_group=group, year=year, month=month, **kw,
        )

    def _rows(self):
        body = APIClient().get(LIST).json()
        return body['results'] if isinstance(body, dict) and 'results' in body else body

    def test_blank_article_fields_stay_null(self):
        """一次都没盘过 ⇒ 两个字段是 null，不是 0"""
        group = self._group()
        self._row(group, 2026, 10, new_followers=0, total_followers=338)

        row = self._rows()[0]
        assert row['published_count'] is None
        assert row['top_article_views'] is None

    def test_zero_is_preserved(self):
        """确实一篇没发 ⇒ 0 必须存成 0，不能被当成「没填」"""
        group = self._group()
        self._row(group, 2026, 10, published_count=0, top_article_views=0)

        row = self._rows()[0]
        assert row['published_count'] == 0
        assert row['top_article_views'] == 0

    def test_create_and_update_round_trip(self):
        group = self._group()
        client = APIClient()
        resp = client.post(LIST, {
            'reader_group': group.id,
            'year': 2026,
            'month': 11,
            'new_followers': 1,
            'new_unfollowers': 0,
            'total_followers': 339,
            'published_count': 2,
            'top_article': '一个人用系统重建生活',
            'top_article_views': 486,
        }, format='json')
        assert resp.status_code == 201, resp.content
        assert resp.json()['published_count'] == 2
        assert resp.json()['top_article_views'] == 486

    def test_yearly_total_is_null_when_never_filled(self):
        """全年没填过 ⇒ 合计为 null；`or 0` 会把「没盘」说成「发了 0 篇」"""
        group = self._group()
        self._row(group, 2026, 9, new_followers=3)
        self._row(group, 2026, 10, new_followers=0)

        data = APIClient().get(STATS, {'year': 2026}).json()
        assert data['total_published'] is None
        assert data['max_article_views'] is None

    def test_yearly_total_sums_only_filled_months(self):
        group = self._group()
        self._row(group, 2026, 10, published_count=3, top_article_views=800)
        self._row(group, 2026, 11, published_count=None, top_article_views=None)

        data = APIClient().get(STATS, {'year': 2026}).json()
        assert data['total_published'] == 3
        assert data['max_article_views'] == 800

    def test_best_month_follows_new_followers(self):
        """按新增关注评，不按互动 —— 互动长期为 0 时不该评出「最佳月份」"""
        group = self._group()
        self._row(group, 2026, 6, new_followers=83, total_interactions=0)
        self._row(group, 2026, 10, new_followers=0, total_interactions=0)

        data = APIClient().get(STATS, {'year': 2026}).json()
        assert data['best_month']['month'] == 6
        assert data['best_month']['new_followers'] == 83

    def test_best_month_is_none_when_every_month_is_zero(self):
        group = self._group()
        self._row(group, 2026, 1, new_followers=0, total_interactions=0)
        self._row(group, 2026, 2, new_followers=0, total_interactions=0)

        data = APIClient().get(STATS, {'year': 2026}).json()
        assert data['best_month'] is None

    def test_list_returns_every_year_without_pagination(self):
        """🔴 全局 10 条/页会让「全部年份」只显示前 10 条：
        库里 12 条、页面数出 10 条，且没有任何翻页入口 —— 静默丢数。复盘一年最多 12 条，不该分页。"""
        group = self._group()
        for year in (2025, 2026):
            for month in range(1, 7):
                self._row(group, year, month, new_followers=1, total_followers=10)

        body = APIClient().get(LIST).json()
        assert isinstance(body, list), '复盘列表不该被包成 {count, results}'
        assert len(body) == 12

    def test_best_month_carries_year(self):
        """不选年份时统计是全期合计，只给 month 会让人把「6 月」读成今年的 6 月"""
        group = self._group()
        self._row(group, 2025, 6, new_followers=50)

        data = APIClient().get(STATS).json()
        assert data['best_month']['year'] == 2025
        assert data['best_month']['month'] == 6
