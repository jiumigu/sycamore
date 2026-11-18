"""年度回顾（叙事版）—— v3.64.63

守这几件事：

1. 🔴 **开头和结尾的空档不算断档**。结尾那头是「本月记账还没到」，
   开头那头去年已经算过一次 —— 两处都会造出假警报，
   而且「最后一条记录」那段已经把同一件事说过了。
2. 🔴 **每个维度最多一条空档**。同一个小确幸隔了 154 天、又隔 87 天，
   两条都进榜就变成同一件事讲两遍，真正长的别处反而挤不进来。
3. 🔴 **月粒度维度按「月」算空档**。拿天算会把它自己的记账节奏
   （账按月落、书按月读完）误报成断档。
4. 🔴 **每段都必须带证据**。取不到真实记录的段不生成 —— 宁可少讲，
   也不讲一句没有出处的话。
5. 🔴 **全程连续不算「一段」**。整年每天都连续时，那是「全程」，
   汇总句已经说了，再单列一段就是同一句话讲两遍。
6. 🔴 超限截断时 **first / last 必留** —— 叙事的两头不能因为条数上限丢掉。
"""

from datetime import date, timedelta
from unittest.mock import patch

import pytest

from apps.summary.constants import (
    RETRO_DENSEST_MIN_DAYS,
    RETRO_FIRST,
    RETRO_GAP,
    RETRO_GAP_MIN_DAYS,
    RETRO_GAP_MIN_MONTHS,
    RETRO_LAST,
    RETRO_MAX_SEGMENTS,
    RETRO_STAGE,
)
from apps.summary.services.year_retro_service import YearRetroService as Svc

D = date


def _ev(label='小确幸', text='吃了块蛋糕', day=None):
    """一条假证据：只测纯逻辑时用它顶住 `_evidence` 的库查询"""
    return {'type': 'sugar', 'label': label,
            'date': (day or D(2026, 1, 1)).isoformat(),
            'text': text, 'id': 1, 'weak': False}


def _marks(**kw):
    """七维都要有键，没给的就是空集"""
    from apps.summary.constants import MODULE_LIST
    out = {m: set() for m in MODULE_LIST}
    out.update(kw)
    return out


class TestGap:
    """空档：只算记录与记录之间"""

    @patch.object(Svc, '_evidence', staticmethod(lambda m, d: _ev()))
    def test_tail_gap_is_not_a_gap(self):
        """🔴 最后一条记录到年底那一段不算断档（本月账还没结，不是断了）"""
        marks = _marks(sugar={D(2026, 1, 5), D(2026, 1, 6)})
        with patch.object(Svc, '_month_gaps', staticmethod(lambda *a: [])):
            gaps = Svc._gaps(marks, D(2026, 1, 1), D(2026, 12, 31))
        assert gaps == [], '结尾那段空档（358 天）被当成了断档'

    @patch.object(Svc, '_evidence', staticmethod(lambda m, d: _ev()))
    def test_head_gap_is_not_a_gap(self):
        """🔴 年初到第一条记录那一段也不算 —— 去年已经算过一次"""
        marks = _marks(sugar={D(2026, 8, 1), D(2026, 8, 3)})
        with patch.object(Svc, '_month_gaps', staticmethod(lambda *a: [])):
            gaps = Svc._gaps(marks, D(2026, 1, 1), D(2026, 12, 31))
        assert gaps == [], '年初那段空档（212 天）被当成了断档'

    @patch.object(Svc, '_evidence', staticmethod(lambda m, d: _ev()))
    def test_middle_gap_fires(self):
        a = D(2026, 3, 8)
        b = a + timedelta(days=RETRO_GAP_MIN_DAYS + 1)
        marks = _marks(sugar={a, b})
        with patch.object(Svc, '_month_gaps', staticmethod(lambda *a: [])):
            gaps = Svc._gaps(marks, D(2026, 1, 1), D(2026, 12, 31))
        assert len(gaps) == 1
        assert '一条都没记' in gaps[0]['text']
        assert gaps[0]['date'] == a.isoformat()
        assert gaps[0]['date_end'] == b.isoformat()

    @patch.object(Svc, '_evidence', staticmethod(lambda m, d: _ev()))
    def test_one_gap_per_module_keeps_the_longest(self):
        """🔴 同一维度两条空档只留最长的那条"""
        a1 = D(2026, 1, 1)
        a2 = a1 + timedelta(days=40)     # 空 39 天
        a3 = a2 + timedelta(days=121)    # 空 120 天
        marks = _marks(sugar={a1, a2, a3})
        with patch.object(Svc, '_month_gaps', staticmethod(lambda *a: [])):
            gaps = Svc._gaps(marks, D(2026, 1, 1), D(2026, 12, 31))
        assert len(gaps) == 1
        assert gaps[0]['span_days'] == 120
        assert gaps[0]['date'] == a2.isoformat()

    @patch.object(Svc, '_evidence', staticmethod(lambda m, d: _ev()))
    def test_cost_threshold_respected(self):
        a = D(2026, 3, 1)
        b = a + timedelta(days=RETRO_GAP_MIN_DAYS - 1)   # 空档刚好差一天
        marks = _marks(sugar={a, b})
        with patch.object(Svc, '_month_gaps', staticmethod(lambda *a: [])):
            assert Svc._gaps(marks, D(2026, 1, 1), D(2026, 12, 31)) == []

    @patch.object(Svc, '_evidence', staticmethod(lambda m, d: None))
    def test_gap_without_evidence_is_dropped(self):
        """🔴 取不到证据 ⇒ 这句没有出处，不生成"""
        a = D(2026, 3, 1)
        marks = _marks(sugar={a, a + timedelta(days=90)})
        with patch.object(Svc, '_month_gaps', staticmethod(lambda *a: [])):
            assert Svc._gaps(marks, D(2026, 1, 1), D(2026, 12, 31)) == []


class TestMonthGrain:
    """月粒度维度按「月」算，不按天"""

    @patch.object(Svc, '_evidence', staticmethod(lambda m, d: _ev(label='财富')))
    def test_month_gap_measured_in_months(self):
        # 1 月与 4 月之间空了 2、3 两个月
        marks = _marks(wealth={D(2026, 1, 1), D(2026, 4, 1)})
        gaps = Svc._month_gaps('wealth', '财富', sorted(marks['wealth']))
        assert len(gaps) == 1
        assert gaps[0]['facts']['empty_months'] == RETRO_GAP_MIN_MONTHS
        assert '空了 2 个月' in gaps[0]['text']

    @patch.object(Svc, '_evidence', staticmethod(lambda m, d: _ev(label='阅读')))
    def test_month_gap_below_threshold(self):
        # 1 月与 3 月之间只空 2 月一个月 (< 2)
        gaps = Svc._month_gaps('book', '阅读', [D(2026, 1, 5), D(2026, 3, 9)])
        assert gaps == []


class TestDensest:
    """连续有记录的最长一段"""

    def _union(self, start: date, days: int):
        return {start + timedelta(days=i) for i in range(days)}

    def test_whole_span_is_not_a_segment(self):
        """🔴 全年都连续 ⇒ 不是「一段」，是「全程」，不单列"""
        start = D(2026, 1, 1)
        end = D(2026, 12, 31)
        assert Svc._densest(self._union(start, 365), start, end, 365) is None

    @patch.object(Svc, '_evidence_any', staticmethod(lambda d: _ev()))
    def test_partial_run_fires(self):
        start, end = D(2026, 1, 1), D(2026, 12, 31)
        union = self._union(D(2026, 3, 1), 40) | self._union(D(2026, 8, 1), 5)
        seg = Svc._densest(union, start, end, 365)
        assert seg is not None
        assert seg['span_days'] == 40
        assert seg['date'] == D(2026, 3, 1).isoformat()

    def test_short_run_is_skipped(self):
        start, end = D(2026, 1, 1), D(2026, 12, 31)
        union = self._union(D(2026, 3, 1), RETRO_DENSEST_MIN_DAYS - 1)
        assert Svc._densest(union, start, end, 365) is None

    @patch.object(Svc, '_evidence_any', staticmethod(lambda d: _ev(day=d)))
    def test_evidence_comes_from_segment_start(self):
        """证据取段首 —— 句子说的是「从这天起连续」"""
        start, end = D(2026, 1, 1), D(2026, 12, 31)
        union = self._union(D(2026, 5, 1), 60)
        seg = Svc._densest(union, start, end, 365)
        assert seg['evidence'][0]['date'] == seg['date'] == D(2026, 5, 1).isoformat()


class TestCap:
    """超限截断"""

    def _seg(self, kind, day, weight):
        return {'kind': kind, 'sort_date': day, 'date': day.isoformat(),
                'weight': weight, 'evidence': [_ev()]}

    def test_first_and_last_survive_truncation(self):
        """🔴 叙事的两头不能因为条数上限丢掉"""
        segs = [self._seg(RETRO_FIRST, D(2026, 1, 1), 10 ** 6)]
        segs += [self._seg(RETRO_GAP, D(2026, m, 1), 10) for m in range(2, 11)]
        segs.append(self._seg(RETRO_LAST, D(2026, 11, 14), 10 ** 6))
        out = Svc._cap(segs)
        assert len(out) == RETRO_MAX_SEGMENTS
        assert out[0]['kind'] == RETRO_FIRST
        assert out[-1]['kind'] == RETRO_LAST

    def test_under_limit_untouched(self):
        segs = [self._seg(RETRO_GAP, D(2026, 3, 1), 5)]
        assert Svc._cap(segs) == segs


class TestBuild:
    """整体形状"""

    def test_future_year(self, db):
        d = Svc.build(2999)
        assert d['empty_reason'] == 'future'
        assert d['summary'] is None
        assert d['segments'] == []

    def test_no_data_year(self, db):
        d = Svc.build(1990)
        assert d['empty_reason'] == 'no_data'
        assert d['thin_reason'] == 'no_data'

    def test_every_segment_has_evidence(self, db):
        """🔴 不变量：输出里每一段都必须至少有一条证据"""
        for y in (2024, 2025, 2026):
            d = Svc.build(y)
            for s in d['segments']:
                assert s['evidence'], f'{y} 的 {s["kind"]} 段没有证据：{s["text"]}'

    def test_segments_are_time_ordered(self, db):
        for y in (2024, 2025, 2026):
            d = Svc.build(y)
            dates = [s['date'] for s in d['segments']]
            assert dates == sorted(dates), f'{y} 的叙事没有按时间排'

    def test_internal_keys_not_leaked(self, db):
        d = Svc.build(2026)
        for s in d['segments']:
            assert 'sort_date' not in s and 'weight' not in s and 'span_days' not in s
            for e in s['evidence']:
                assert 'weak' not in e


class TestSummary:
    """开头那一句"""

    def test_every_day(self):
        s = Svc._summary(D(2026, 1, 1), D(2026, 11, 14), 318, 318)
        assert s['every_day'] is True
        assert '每一天' in s['text']

    def test_gap_in_coverage(self):
        s = Svc._summary(D(2024, 1, 1), D(2024, 12, 31), 366, 322)
        assert s['every_day'] is False
        assert '322 天' in s['text']

    def test_md_format(self):
        assert Svc._md(D(2026, 3, 8)) == '3 月 8 日'


class TestBuildWithData:
    """喂一份合成的七维日期集合，确认四类段都能长出来

    （不依赖库里真有多少数据 —— 测试库是空的，只跑 `build` 会「全绿但什么都没测」）
    """

    class _Stage:
        def __init__(self, pk, name, start, end=None):
            self.id, self.name, self.start_date, self.end_date = pk, name, start, end

    def test_four_kinds(self):
        fake = {
            'words': {D(2024, 1, 2)},
            'sugar': {D(2024, 3, 1), D(2024, 6, 1)},
            'times': {D(2024, 12, 30)},
        }
        stages = [self._Stage(1, '谋生期', D(2024, 11, 1))]

        with patch('apps.summary.services.year_retro_service.ProgressAggregator._covered_marks',
                   new=lambda module, year: set(fake.get(module, set()))), \
             patch.object(Svc, '_evidence', staticmethod(lambda m, d: _ev(label=m))), \
             patch('apps.summary.services.stage_span_service.StageSpanService._top_stages',
                   new=staticmethod(lambda: stages)):
            d = Svc.build(2024)

        kinds = [s['kind'] for s in d['segments']]
        assert kinds == [RETRO_FIRST, RETRO_GAP, RETRO_STAGE, RETRO_LAST]
        assert d['summary']['coverage_days'] == 4
        assert d['empty_reason'] is None
        # 小确幸 3 月到 6 月隔了 91 天
        assert '隔了 91 天' in d['segments'][1]['text']
        # 阶段句里两个信息都在
        assert '谋生期' in d['segments'][2]['text']

    def test_week_long_run_does_not_become_a_segment(self):
        """连续天数不够 30 天 ⇒ 不讲「连续」"""
        fake = {'words': {D(2024, 1, 1) + timedelta(days=i) for i in range(10)}}
        with patch('apps.summary.services.year_retro_service.ProgressAggregator._covered_marks',
                   new=lambda module, year: set(fake.get(module, set()))), \
             patch.object(Svc, '_evidence', staticmethod(lambda m, d: _ev())), \
             patch('apps.summary.services.stage_span_service.StageSpanService._top_stages',
                   new=staticmethod(lambda: [])):
            d = Svc.build(2024)
        assert 'densest' not in [s['kind'] for s in d['segments']]


class TestThin:
    def test_sparse_data(self):
        assert Svc._thin_reason(10, 1) == 'sparse_data'

    def test_few_events(self):
        assert Svc._thin_reason(300, 2) == 'few_events'

    def test_normal(self):
        assert Svc._thin_reason(300, 6) is None


class TestEndpoint:
    """接口层：参数错要说清，不要把 `int()` 的 500 漏出去"""

    def test_missing_year(self, client, db):
        r = client.get('/api/summary/year_retro/')
        assert r.status_code == 400
        assert 'year' in r.json()['error']

    def test_non_numeric_year(self, client, db):
        """🔴 参数不是数字 ⇒ 400；不能 500，也不能吞成 200 空结果"""
        r = client.get('/api/summary/year_retro/?year=abc')
        assert r.status_code == 400

    def test_future_year_ok(self, client, db):
        r = client.get('/api/summary/year_retro/?year=2999')
        assert r.status_code == 200
        assert r.json()['empty_reason'] == 'future'
