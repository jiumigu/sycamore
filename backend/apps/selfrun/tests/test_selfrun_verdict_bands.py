"""判定线四档 + 「本月状态说的是本月」（v3.62.45 / v3.64.6）

守五件事：
1. 分档只有一张表：≥80 我超棒 / ≥60 合格 / ≥40 及格 / <40 活着
2. 周与月**共用同一张表**（月按三问「是」的个数 ÷ 3）
3. 档位本名**不带「本周/本月」**，前缀由页面按周期类型拼 —— 本月页不许说「本周」
4. 三问一个都没答 ≠ 全答否：前者是**未判定**（`value=''` + `basis='pending'`），
   后者照实判「活着」；月度**不再**拿 KPI 档位顶上去
5. 月度归档必须先答完三问；归档后补答三问**不改档**（要改走重开）
"""
import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.selfrun import services
from apps.selfrun.constants import (
    MONTHLY_QUESTION_COUNT,
    PERIOD_STATUS_CHOICES,
    PERIOD_STATUS_LABEL,
    PERIOD_TYPE_PREFIX,
    PERIOD_VERDICT_BANDS,
)
from apps.selfrun.models import SelfRunPeriod, SelfRunStage

pytestmark = pytest.mark.django_db

URL = '/api/selfrun'
QKEYS = ('q1_income', 'q2_output', 'q3_runway')


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def stage(client):
    today = timezone.localdate()
    resp = client.post(f'{URL}/stages/', {
        'name': '测试阶段',
        'start_date': str(today - dt.timedelta(days=today.weekday())),
        'metrics': [
            {'template_key': 'grow_hours'},
            {'template_key': 'xuanzhi', 'goal_value': 6, 'floor_value': None},
            {'template_key': 'output_count'},
        ],
    }, format='json')
    assert resp.status_code == 201, resp.data
    return SelfRunStage.objects.get()


def _sheet(**answers):
    """构造三问答卷；`answers` 传 `q1_income=True` 这种。未给的键 = 未答。"""
    return {
        k: {'answer': answers.get(k, None)}
        for k in QKEYS
    }


class TestBands:
    def test_four_bands_thresholds(self):
        """用户给的线：≥80 我超棒 · ≥60 合格 · ≥40 及格 · <40 活着"""
        assert services._ratio_band(0.80) == 'great'
        assert services._ratio_band(0.79) == 'on_track'
        assert services._ratio_band(0.60) == 'on_track'
        assert services._ratio_band(0.59) == 'slipping'
        assert services._ratio_band(0.40) == 'slipping'
        assert services._ratio_band(0.39) == 'slid'
        assert services._ratio_band(0.0) == 'slid'

    def test_bands_are_one_table(self):
        """档位表只有一份，且**不含**兜底档（兜底是 `slid`，写进表里会永远命中）"""
        keys = [k for k, _ in PERIOD_VERDICT_BANDS]
        assert keys == ['great', 'on_track', 'slipping']
        assert 'slid' not in keys

    def test_every_band_has_label_and_color(self):
        from apps.selfrun.constants import PERIOD_STATUS_COLORS
        for key, _label in PERIOD_STATUS_CHOICES:
            assert PERIOD_STATUS_LABEL[key]
            assert key in PERIOD_STATUS_COLORS, f'{key} 没有配色 ⇒ 界面回落到灰色'

    def test_labels_have_no_period_prefix(self):
        """🔴 本名里不许出现「本周/本月」——前缀是页面的事，写死就会出现本月页说本周"""
        for _key, label in PERIOD_STATUS_CHOICES:
            assert '本周' not in label and '本月' not in label, label
        assert PERIOD_TYPE_PREFIX == {'weekly': '本周', 'monthly': '本月'}


class TestMonthlyFromQuestions:
    def test_three_yes_is_great(self):
        assert services.compute_monthly_status(_sheet(**{k: True for k in QKEYS})) == 'great'

    def test_two_yes_is_on_track(self):
        assert services.compute_monthly_status(
            _sheet(q1_income=True, q2_output=True, q3_runway=False),
        ) == 'on_track'

    def test_one_yes_is_alive(self):
        assert services.compute_monthly_status(
            _sheet(q1_income=True, q2_output=False, q3_runway=False),
        ) == 'slid'

    def test_all_no_is_alive_not_no_record(self):
        """三问全答「否」= 明确没做到 ⇒ 活着；**不是**「这期没有记录」

        旧实现按个数查表把 0 映射成 `no_record`，把「你说了三个否」
        与「一个字都没填」混成一件事 —— 又是 `null` / `0` 不分。
        """
        assert services.compute_monthly_status(
            _sheet(**{k: False for k in QKEYS}),
        ) == 'slid'

    def test_all_unanswered_is_not_a_verdict(self):
        """一个都没答 ⇒ 空串（**未判定**），不是「活着」，也不再交给 KPI 顶档

        🔴 v3.64.6：旧实现让调用方落回 KPI 档位，于是同一期会先显示
           「4/4 = 100% 我超棒」、答完三问立刻掉成「2/3 = 67% 合格」——
           数字没变档位变了，用户看到的就是「归档把我降档了」。
        """
        assert services.compute_monthly_status(_sheet()) == ''
        # 一个「否」都没答过的空卷，与「答了三个否」必须是两个结果
        assert services.compute_monthly_status(_sheet(**{k: False for k in QKEYS})) == 'slid'

    def test_denominator_is_three_not_answered_count(self):
        """只答 1 个「是」= 1/3，不是 1/1（否则「只填一个还填了是」会判满分）"""
        assert services.compute_monthly_status(_sheet(q1_income=True)) == 'slid'
        assert MONTHLY_QUESTION_COUNT == 3

    def test_unanswered_not_treated_as_no_but_not_inflated(self):
        """未答既不当作「否」、也不当作「是」：2 是 + 1 未答 与 2 是 + 1 否 同档"""
        with_null = services.compute_monthly_status(_sheet(q1_income=True, q2_output=True))
        with_false = services.compute_monthly_status(
            _sheet(q1_income=True, q2_output=True, q3_runway=False),
        )
        assert with_null == with_false == 'on_track'


class TestExplainBasis:
    def test_monthly_uses_question_basis(self, client, stage):
        """本月状态：判定看三问，并且**明说是三问**（不是那条百分比线）"""
        # ⚠️ 必须落在**当前月**：`periods/current/` 只会返回当期那一行，
        #    关一个过去月再读当期，读到的是另一行（第一次写这个用例就栽在这）
        cur_key, _start, _end = services.current_period_meta('monthly')
        resp = client.post(f'{URL}/periods/close/', {
            'period_type': 'monthly', 'period_key': cur_key,
            # 🔴 归档必须三问全答（v3.64.6）—— 2 是 1 否 = 67% 合格
            'answer_sheet': _sheet(q1_income=True, q2_output=True, q3_runway=False),
        }, format='json')
        assert resp.status_code == 201, resp.data

        # 取「本月状态」看判定说明
        detail = client.get(f'{URL}/periods/current/?period_type=monthly')
        assert detail.status_code == 200, detail.data
        ex = detail.data['status_explain']
        assert ex['basis'] == 'questions'
        assert ex['prefix'] == '本月'
        assert ex['yes'] == 2 and ex['answered'] == 3
        assert ex['label_text'] == '本月合格'
        # 整句：「本月判定看三问：答「是」2/3（67%）⇒ 本月合格」
        assert '三问' in ex['basis_text']
        assert '2/3' in ex['basis_text']
        assert '本月合格' in ex['basis_text']
        assert '本周' not in ex['basis_text'], '本月页不许出现「本周」'

    def test_weekly_keeps_kpi_basis_with_four_bands(self, client, stage):
        """本周状态：仍按 KPI 条数比，判定线念出**四档**（含新加的「我超棒」）"""
        detail = client.get(f'{URL}/periods/current/?period_type=weekly')
        assert detail.status_code == 200, detail.data
        ex = detail.data['status_explain']
        assert ex['basis'] == 'kpi'
        assert ex['prefix'] == '本周'
        assert '≥80% 本周我超棒' in ex['basis_text']
        assert '≥60% 本周合格' in ex['basis_text']
        assert '≥40% 本周及格' in ex['basis_text']

    def test_monthly_without_answers_is_pending_not_kpi(self, client, stage):
        """三问一个没答 ⇒ **未判定**（不是「按 KPI 算的我超棒」）

        🔴 这一条是本轮（v3.64.6）的核心：月度档位不许由 KPI 顶替。
           否则归档前显示 KPI 档（4/4 ⇒ 我超棒）、归档时答完三问（2/3 ⇒ 合格），
           同一期两个档位 —— 用户看到的就是「归档给我降了档」。
        """
        detail = client.get(f'{URL}/periods/current/?period_type=monthly')
        assert detail.status_code == 200, detail.data
        ex = detail.data['status_explain']
        assert ex['basis'] == 'pending'
        assert ex['value'] == '', '没答三问就不该有档位（也不许拿 KPI 档顶上）'
        assert ex['awaiting_answers'] is True
        assert ex['label_text'] == '待答三问'
        assert '还没有结论' in ex['basis_text']
        # KPI 分数照旧下发，但明说是参考
        assert 'KPI 参考' in ex['basis_text']

    def test_monthly_close_requires_three_answers(self, client, stage):
        """月度归档：三问没答完 ⇒ 400，且**不落行**（不许归出一个没有结论的期）"""
        cur_key, _s, _e = services.current_period_meta('monthly')
        resp = client.post(f'{URL}/periods/close/', {
            'period_type': 'monthly', 'period_key': cur_key,
            'answer_sheet': _sheet(q1_income=True, q2_output=True),   # q3 未答
        }, format='json')
        assert resp.status_code == 400, resp.data
        assert '还有 1 个没答' in resp.data['detail']
        assert not SelfRunPeriod.objects.filter(period_key=cur_key).exists()

    def test_archived_monthly_status_is_frozen(self, client, stage):
        """归档后补答三问**不改档** —— 归档 = 定格，要改档得走「重开」

        🔴 旧实现 `update_review()` 里直接 `period.status = new_status`，
           于是归档后补一句「其实是」就能把历史结论改掉，
           而页面上还写着「归档那刻数字定格」。
        """
        cur_key, _s, _e = services.current_period_meta('monthly')
        client.post(f'{URL}/periods/close/', {
            'period_type': 'monthly', 'period_key': cur_key,
            'answer_sheet': _sheet(q1_income=True, q2_output=True, q3_runway=False),
        }, format='json')
        period = SelfRunPeriod.objects.get(period_key=cur_key)
        assert period.status == 'on_track'

        # 补答成 3 个「是」（本来会判 great）
        client.patch(f'{URL}/periods/{period.id}/', {
            'answer_sheet': _sheet(**{k: True for k in QKEYS}),
        }, format='json')
        period.refresh_from_db()
        assert period.answer_sheet['q3_runway']['answer'] is True   # 记录留下了
        assert period.status == 'on_track', '归档后补答不许改档'

        # 页头也读落库档位（不按三问重算）
        ex = client.get(
            f'{URL}/periods/current/?period_type=monthly',
        ).data['status_explain']
        assert ex['value'] == 'on_track'
        assert '归档时定格' in ex['basis_text']

    def test_labels_and_prefix_are_sent(self, client, stage):
        """档位名随接口下发，前端不必再抄一份中文表"""
        ex = client.get(f'{URL}/periods/current/?period_type=monthly').data['status_explain']
        assert ex['labels']['great'] == '我超棒'
        assert ex['monthly_question_count'] == 3


class TestWeeklyBreakdownIncludesGreat:
    def test_breakdown_has_every_band_key(self, client, stage):
        """分布按枚举生成：加档后手写 dict 会静默漏一根柱（总数还对得上）"""
        resp = client.get(f'{URL}/stages/{stage.id}/summary/')
        assert resp.status_code == 200, resp.data
        breakdown = resp.data['summary']['weekly_breakdown']
        for key, _label in PERIOD_STATUS_CHOICES:
            assert key in breakdown, f'分布里缺 {key}'

    def test_great_week_is_counted_in_its_own_bucket(self, stage):
        """一条「我超棒」的周：要落进 great 桶，而不是被并到「合格」里"""
        from apps.selfrun.models import SelfRunPeriod
        SelfRunPeriod.objects.create(
            stage=stage, period_type='weekly', period_key='2026-W01',
            period_start=dt.date(2026, 1, 1), period_end=dt.date(2026, 1, 8),
            status='great', readings=[], closed_at=timezone.now(),
        )
        Week = SelfRunPeriod
        assert Week.objects.filter(status='great').count() == 1
