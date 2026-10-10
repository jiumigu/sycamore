"""结论条的口径可达性（v3.59.10）

结论条上有四个数：**综合能撑 / 钱能撑 / 瓶颈 / 覆盖率**。
四张卡各自挂了 ⓘ 口径气泡，而结论条在此之前**一个都没有** ——
越靠近答案的一行反而越不可解释。同一份 `SURVIVAL_METRIC_NOTES`
（经 `/survival/meta/` 下发）里其实早就有这几条的文案。

本文件钉三件事：

  ① ⭐ 结论条要挂的四个键**真实存在**于 `metric_meta` 里。
     前端 `bannerMeta(key)` 取不到时是**静默不渲染气泡**（而不是渲染一个空的），
     所以键名写错在界面上完全看不出来 —— 页面上就是「本来就没打算加 ⓘ」的样子。
  ② `cash_days` 是本次新补的一条（此前「钱能撑多久」只在 `bottleneck` 的
     note 里被顺带提过，没有可挂的口径），它的**公式必须与算法一致**：
     文案说 × 30，`cash_days_from_months` 就得真的 × 30。
  ③ `coverage` 的要点里有「覆盖率低不等于危险」这句话 ——
     它是这一页最容易被读成警报的一个数（3% 看着像快断粮）。
"""

from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.wealth.services import survival_calc as calc

META = '/api/wealth/survival/meta/'

# 与 `SurvivalView.vue` 的 `bannerMeta(...)` 调用逐字对应。
# 改动任何一边，这份名单必须跟着改 —— 它就是这个测试存在的理由。
BANNER_KEYS = ('pert_expected', 'cash_days', 'bottleneck', 'coverage')


def _notes() -> list[dict]:
    return APIClient().get(META).data['metric_meta']


def _note(key: str) -> dict:
    return next(n for n in _notes() if n['key'] == key)


def _joined(key: str) -> str:
    return '\n'.join(_note(key)['note'])


# ══════════════════════════════════════════════════════════════
# ① 四个键都取得到
# ══════════════════════════════════════════════════════════════

class TestBannerMetricReachability:
    """取不到就是静默没有气泡 —— 这正是「看着没问题、其实没接上」的典型"""

    def test_every_banner_number_has_a_note(self):
        keys = {n['key'] for n in _notes()}
        for key in BANNER_KEYS:
            assert key in keys, f'结论条挂了 {key} 的气泡，但 metric_meta 里没有这一条'

    def test_banner_keys_are_not_empty_shells(self):
        """有键但没文案，等于渲染一个空气泡"""
        for key in BANNER_KEYS:
            note = _note(key)
            assert note['label'], key
            assert note['formula'], key
            assert note['note'], key

    def test_no_thresholds_leak_in(self):
        """本模块刻意不设判定线 —— bands 恒为空数组（同 build_metric_meta 的注释）"""
        for key in BANNER_KEYS:
            assert _note(key)['bands'] == [], key


# ══════════════════════════════════════════════════════════════
# ② cash_days：口径与算法不许漂移
# ══════════════════════════════════════════════════════════════

class TestCashDaysNote:

    def test_formula_matches_the_algorithm(self):
        """文案说 × 30，算法就得真的 × 30 —— 两边各写各的迟早对不上"""
        assert calc.cash_days_from_months(2.0) == 60.0
        assert calc.cash_days_from_months(1.3) == 39.0
        assert '30' in _note('cash_days')['formula']

    def test_null_months_stay_null(self):
        """「算不出来」不许掉成 0 —— 0 是「真的一天都撑不了」的结论"""
        assert calc.cash_days_from_months(None) is None
        assert '不返回 0' in _joined('cash_days')

    def test_note_does_not_restate_the_emergency_fund_formula(self):
        """分子那半段归资产健康指标管 —— 写在这里就是第二份口径"""
        assert '÷' not in _note('cash_days')['formula']
        assert '现金类资产 ÷' not in _joined('cash_days')


# ══════════════════════════════════════════════════════════════
# ③ 最容易读错的那个数
# ══════════════════════════════════════════════════════════════

class TestCoverageWording:

    def test_low_coverage_is_not_an_alarm(self):
        """3% 看着像快断粮，而它其实只在说「物资顶不住整整三年」"""
        assert '不等于危险' in _joined('coverage')

    def test_coverage_explains_the_empty_case(self):
        """窗口没开始 / 已结束时返回空值，不除零 —— 这句要能读到"""
        assert '除零' in _joined('coverage')

    def test_coverage_refuses_to_divide_when_the_window_is_missing(self):
        out = calc.coverage_pct(120.0, None, None, date(2026, 9, 22))
        assert out['pct'] is None
        assert out['reason']

    def test_bottleneck_keeps_its_tolerance_wording(self):
        """「差不到 X% 就算均衡」是这一页最反直觉的一句，不能丢"""
        assert '均衡' in _joined('bottleneck')
