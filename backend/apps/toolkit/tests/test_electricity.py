"""用电记录：月度用电量聚合、PERT 三点估算、overview 接口与月份筛选

口径（见 services.py）：
- 月度用电量 = **本月最后一条读数 − 上月最后一条读数**（首月退化为本月初条）
- PERT：O/M/P = 最小/中位数/最大，E=(O+4M+P)/6，σ=(P−O)/6
- PERT 样本只含**已结束**的月，且需 ≥3 个；不足时一个数都不给
"""
from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.toolkit.models import ElectricityRecord
from apps.toolkit.services import (
    MONTHS_WINDOW,
    PERT_MIN_SAMPLES,
    ElectricityService,
    build_monthly_usage,
    pert_estimate,
)


class _Rec:
    """build_monthly_usage 的最小输入（纯函数不碰库）"""

    def __init__(self, day: date, reading, pk: int):
        self.record_date = day
        self.meter_reading = Decimal(str(reading))
        self.pk = pk
        self.id = pk


def _recs(*pairs):
    return [
        _Rec(date.fromisoformat(d), r, i + 1)
        for i, (d, r) in enumerate(pairs)
    ]


# ─── 月度用电量口径 ───────────────────────────────


class TestMonthlyUsage:
    def test_跨月读数差(self):
        """8 月 15.0→51.4、9 月 51.4→87.5 ⇒ 36.4 / 36.1"""
        out = build_monthly_usage(_recs(
            ('2026-08-01', 15.0), ('2026-08-31', 51.4), ('2026-09-29', 87.5)))
        aug, sep = out[(2026, 8)], out[(2026, 9)]
        assert aug['usage'] == 36.4
        assert aug['days'] == 30
        assert sep['usage'] == 36.1
        assert sep['days'] == 29
        assert sep['base_date'] == date(2026, 8, 31)

    def test_首月以本月初条作基准并被标记(self):
        out = build_monthly_usage(_recs(('2026-08-01', 15.0), ('2026-08-31', 51.4)))
        assert out[(2026, 8)]['base_source'] == 'own_first'

    def test_非首月基准来自上月(self):
        out = build_monthly_usage(_recs(
            ('2026-08-01', 15.0), ('2026-08-31', 51.4), ('2026-09-29', 87.5)))
        assert out[(2026, 9)]['base_source'] == 'prev_month'

    def test_单条记录的月算不出而不是0(self):
        """只有一条读数 ⇒ 没有间隔 ⇒ usage=None（**不是 0**）"""
        out = build_monthly_usage(_recs(('2026-08-01', 15.0)))
        assert out[(2026, 8)]['usage'] is None
        assert out[(2026, 8)]['single'] is True

    def test_日均按覆盖天数算(self):
        out = build_monthly_usage(_recs(('2026-08-01', 15.0), ('2026-08-31', 51.4)))
        assert out[(2026, 8)]['daily_avg'] == 1.21      # 36.4 ÷ 30

    def test_只回有记录的月(self):
        """窗口补齐是 overview 的职责；本函数只回有记录的月"""
        out = build_monthly_usage(_recs(
            ('2026-08-01', 15.0), ('2026-08-31', 51.4), ('2026-09-29', 87.5)))
        assert set(out) == {(2026, 8), (2026, 9)}

    def test_跨年连续(self):
        """12 月 → 次年 1 月，基准要跟得上"""
        out = build_monthly_usage(_recs(
            ('2026-12-01', 100.0), ('2026-12-31', 130.0), ('2027-01-31', 170.0)))
        assert out[(2027, 1)]['usage'] == 40.0
        assert out[(2027, 1)]['base_date'] == date(2026, 12, 31)


# ─── PERT ───────────────────────────────


class TestPert:
    def test_样本不足不给数值只给参考均值(self):
        r = pert_estimate([36.1, 36.4])
        assert r['ready'] is False
        assert r['expected'] is None and r['sigma'] is None
        assert r['samples'] == 2 and r['required'] == PERT_MIN_SAMPLES
        assert r['mean'] == 36.25                      # 参考均值照给
        assert r['issues']

    def test_三点与期望值(self):
        """(30 + 4×36 + 45) ÷ 6 = 36.5 ｜ σ = 15 ÷ 6 = 2.5"""
        r = pert_estimate([30.0, 36.0, 45.0])
        assert r['ready'] is True
        assert (r['optimistic'], r['most_likely'], r['pessimistic']) == (30.0, 36.0, 45.0)
        assert r['expected'] == 36.5
        assert r['sigma'] == 2.5
        assert r['low'] == 34.0 and r['high'] == 39.0

    def test_偶数样本中位数取中间两个均值(self):
        assert pert_estimate([10.0, 20.0, 30.0, 40.0])['most_likely'] == 25.0

    def test_三点相同时提示而不是假装自信(self):
        r = pert_estimate([36.4, 36.4, 36.4])
        assert r['ready'] is True
        assert r['sigma'] == 0.0
        assert any('完全相同' in s for s in r['issues'])

    def test_空样本(self):
        r = pert_estimate([])
        assert r['ready'] is False
        assert r['mean'] is None and r['samples'] == 0

    def test_期望值不等于最可能值(self):
        """钉住口径：PM 常见的误读 —— PERT 给的是期望值，不是中位数"""
        r = pert_estimate([30.0, 36.0, 45.0])
        assert r['most_likely'] == 36.0
        assert r['expected'] == 36.5


# ─── overview（服务层） ───────────────────────────────


@pytest.mark.django_db
class TestOverview:
    TODAY = date(2026, 9, 30)

    def _mk(self, pairs):
        for d, r in pairs:
            ElectricityRecord.objects.create(
                user_id=1, record_date=date.fromisoformat(d),
                meter_reading=Decimal(str(r)), notes='')

    def test_窗口补齐为12个自然月(self):
        self._mk([('2026-08-01', 15.0), ('2026-08-31', 51.4)])
        d = ElectricityService.overview(today=self.TODAY)
        assert len(d['months']) == MONTHS_WINDOW
        assert d['months'][0]['month'] == '2025-10'
        assert d['months'][-1]['month'] == '2026-09'

    def test_无记录月为None而不是0(self):
        self._mk([('2026-08-01', 15.0), ('2026-08-31', 51.4)])
        d = ElectricityService.overview(today=self.TODAY)
        empty = [m for m in d['months'] if m['records'] == 0]
        assert len(empty) == 11
        assert all(m['usage'] is None for m in empty)
        assert all(m['usage'] != 0 for m in empty)

    def test_当月被排除出PERT样本(self):
        self._mk([('2026-08-01', 15.0), ('2026-08-31', 51.4), ('2026-09-29', 87.5)])
        d = ElectricityService.overview(today=self.TODAY)
        sep = d['months'][-1]
        assert sep['month'] == '2026-09'
        assert sep['partial'] is True
        assert sep['in_pert_sample'] is False
        assert d['pert']['samples'] == 1               # 只剩 8 月
        assert any('尚未结束' in s for s in d['pert']['issues'])

    def test_已结束的首月进样本(self):
        self._mk([('2026-08-01', 15.0), ('2026-08-31', 51.4), ('2026-09-29', 87.5)])
        d = ElectricityService.overview(today=self.TODAY)
        aug = [m for m in d['months'] if m['month'] == '2026-08'][0]
        assert aug['in_pert_sample'] is True
        assert aug['partial'] is False

    def test_满三个月后PERT出数(self):
        """5 月 30 / 6 月 36 / 7 月 45 ⇒ E=(30+144+45)/6 = 36.5"""
        self._mk([('2026-05-01', 0.0), ('2026-05-31', 30.0), ('2026-06-30', 66.0),
                  ('2026-07-31', 111.0)])
        d = ElectricityService.overview(today=date(2026, 8, 15))
        p = d['pert']
        assert p['ready'] is True
        assert p['samples'] == 3
        assert p['expected'] == 36.5
        assert (p['optimistic'], p['pessimistic']) == (30.0, 45.0)

    def test_统计卡数据与分页解耦(self):
        self._mk([('2026-08-01', 15.0), ('2026-08-31', 51.4), ('2026-09-29', 87.5)])
        d = ElectricityService.overview(today=self.TODAY)
        assert d['total_records'] == 3
        assert d['latest']['record_date'] == '2026-09-29'
        assert d['latest']['meter_reading'] == 87.5

    def test_空库(self):
        d = ElectricityService.overview(today=self.TODAY)
        assert d['total_records'] == 0
        assert d['latest'] is None
        assert d['pert']['ready'] is False
        assert d['pert']['samples'] == 0
        assert len(d['months']) == MONTHS_WINDOW


# ─── 接口层 ───────────────────────────────

BASE = '/api/toolkit/electricity-records/'


@pytest.mark.django_db
class TestElectricityApi:
    def setup_method(self):
        self.c = APIClient()
        for d, r in [('2026-08-01', 15.0), ('2026-08-31', 51.4), ('2026-09-29', 87.5)]:
            ElectricityRecord.objects.create(
                user_id=1, record_date=date.fromisoformat(d),
                meter_reading=Decimal(str(r)), notes='')

    def test_overview返回dict而不是分页包装(self):
        """钉住：没被全局分页包成 {count, results}（前端按裸对象消费）"""
        r = self.c.get(BASE + 'overview/')
        assert r.status_code == 200
        assert isinstance(r.data, dict)
        assert 'count' not in r.data
        assert isinstance(r.data['months'], list)
        assert len(r.data['months']) == MONTHS_WINDOW
        assert set(r.data) == {'months', 'pert', 'latest', 'total_records'}

    def test_overview的months参数被夹紧(self):
        assert len(self.c.get(BASE + 'overview/?months=99').data['months']) == 36
        assert len(self.c.get(BASE + 'overview/?months=1').data['months']) == 3
        assert len(self.c.get(BASE + 'overview/?months=abc').data['months']) == 12

    def test_月份筛选(self):
        r = self.c.get(BASE + '?month=2026-09')
        assert r.data['count'] == 1
        assert r.data['results'][0]['record_date'] == '2026-09-29'

    def test_月份筛选_12月不会漏进次年1月(self):
        ElectricityRecord.objects.create(
            user_id=1, record_date=date(2027, 1, 3),
            meter_reading=Decimal('100.0'), notes='')
        r = self.c.get(BASE + '?month=2026-12')
        assert r.data['count'] == 0

    def test_月份筛选_非法值不过滤(self):
        r = self.c.get(BASE + '?month=abc')
        assert r.data['count'] == 3

    def test_列表接口仍走分页(self):
        r = self.c.get(BASE + '?page_size=2')
        assert r.data['count'] == 3
        assert len(r.data['results']) == 2

    def test_默认按日期倒序(self):
        r = self.c.get(BASE)
        dates = [x['record_date'] for x in r.data['results']]
        assert dates == sorted(dates, reverse=True)
