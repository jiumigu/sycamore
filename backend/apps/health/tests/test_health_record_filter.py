"""health 运动记录的筛选（v3.62.15 新增 `start` / `end` 日期范围）。

重点是把**半开区间**这条约定钉住：`start` / `end` 两端都要**含当天整天**，
但 `end` 的**次日 00:00** 必须落在范围外。
谁要是把它「顺手优化」成 `time__date__lte=end`，下面第 ② 个用例会红。
"""
import datetime

import pytest
from django.test import Client
from django.utils import timezone

from apps.health.models import HealthRecord

URL = '/api/health/records/'


@pytest.mark.django_db
class TestHealthRecordFilter:
    @staticmethod
    def _rec(dt_str, total=1000, htype=1, remark=''):
        return HealthRecord.objects.create(
            time=timezone.make_aware(datetime.datetime.fromisoformat(dt_str)),
            total=total, steps=int(total), htype=htype, remark=remark,
        )

    @staticmethod
    def _count(**params):
        return Client().get(URL, params).json()['count']

    # ─── ① 结束日整天都算 ───

    def test_end_day_is_inclusive_whole_day(self):
        """结束日**整天**都算：当天 23:30 那条不能漏。"""
        self._rec('2026-08-01 08:00:00')
        self._rec('2026-08-01 23:30:00')
        assert self._count(start='2026-08-01', end='2026-08-01') == 2

    def test_start_boundary_is_inclusive(self):
        """开始日 00:00 那条算在内。"""
        self._rec('2026-08-01 00:00:00')
        self._rec('2026-07-31 23:59:59')
        assert self._count(start='2026-08-01') == 1

    # ─── ② 半开区间的上界：次日 00:00 必须排除 ───

    def test_next_day_0000_is_excluded(self):
        """`end=08-01` 时，`08-02 00:00` 那条**不能**被带进来。"""
        self._rec('2026-08-01 23:59:59')
        self._rec('2026-08-02 00:00:00')
        assert self._count(start='2026-08-01', end='2026-08-01') == 1

    def test_two_halves_partition_all(self):
        """只给 start 与只给 end 的两半，必须**不重不漏**地拼成全量。

        这条用例同时防住「边界重叠」与「边界有缝」两种改了半开区间的写法。
        """
        for d in ('2026-07-30 12:00:00', '2026-07-31 23:00:00', '2026-08-01 00:00:00', '2026-08-03 09:00:00'):
            self._rec(d)
        total = self._count()
        before = self._count(end='2026-07-31')   # < 08-01 00:00
        after = self._count(start='2026-08-01')  # >= 08-01 00:00
        assert before + after == total == 4

    # ─── ③ 空值 = 不限，非法格式 = 400 ───

    def test_empty_string_means_unbounded(self):
        """清空筛选时前端会送空串 ⇒ 视为「不限」，不是 400。"""
        self._rec('2026-08-01 08:00:00')
        assert self._count(start='', end='') == 1

    def test_invalid_date_returns_400(self):
        """格式不对要**显式报错**，不许静默退回「不限」（那会悄悄多给一堆数据）。"""
        for bad in ('2026/08/01', 'abc', '2026-13-99'):
            r = Client().get(URL, {'start': bad})
            assert r.status_code == 400, bad
            assert 'start' in r.json()

    # ─── ④ 与前缀筛选、分页共存 ───

    def test_htype_and_keyword_filters(self):
        self._rec('2026-08-01 08:00:00', htype=1, remark='晨跑')
        self._rec('2026-08-02 08:00:00', htype=3, remark='夜骑')
        assert self._count(htype=3) == 1
        assert self._count(search='晨跑') == 1
        assert self._count(year=2026, htype=1) == 1

    def test_page_size_20_and_30(self):
        """每页条数扩展（前端选项 10/20/30/50）—— 后端 `max_page_size=100` 之内都放行。"""
        for i in range(25):
            self._rec(f'2026-08-{i + 1:02d} 08:00:00')

        r20 = Client().get(URL, {'page_size': 20}).json()
        assert r20['count'] == 25 and len(r20['results']) == 20

        r30 = Client().get(URL, {'page_size': 30}).json()
        assert r30['count'] == 25 and len(r30['results']) == 25
