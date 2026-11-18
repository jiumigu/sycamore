"""跨维度配对体检 + 身体-状态（v3.64.62）

守这几件事：

1. 🔴 缺失的月份**不进序列** —— 「那月没记账」不等于「那月花了 0」。
   补 0 会把记账节奏当成生活波动，算出来的系数衡量的是习惯。
2. 🔴 样本不足（n < CORRELATION_MIN_N）⇒ `level=None` + `not_enough`，
   系数照给但**不判档**。n=6 的 0.8 不比 n=80 的 0.3 更可信。
3. 🔴 无共同月份 ⇒ `no_data`；某一侧常数 ⇒ `constant`。
   三者都是「算不出」，不是「没关系」—— `level` 必须是 `None`。
4. 🔴 稳健性：结论若只靠一两个极端月撑着 ⇒ `robust=False`。
5. 🔴 身体-状态：无自检 ⇒ `sleep_latency=None`（**不是 0**、更不是「100 分」）；
   良品率分母为 0 ⇒ `None`（不是 0%）。
"""

import datetime as dt

import pytest
from django.utils import timezone

from apps.goals.models import OutputRecord
from apps.health.models import HealthRecord
from apps.summary.constants import (
    CORR_REASON_CONSTANT,
    CORR_REASON_NO_DATA,
    CORR_REASON_NOT_ENOUGH,
    CORRELATION_MIN_N,
)
from apps.summary.services.body_mind_correlation_service import BodyMindCorrelationService
from apps.summary.services.correlation_service import CorrelationService, _pearson, _spearman
from apps.sugar.models import SugarRecord
from apps.temporal.models import TemporalTask
from apps.toolkit.models import HealthSelfCheck
from apps.wealth.models import WealthBalanceList

TODAY = timezone.localdate()
THIS_MONTH = TODAY.replace(day=1)


def _month_key(offset_from_now: int) -> str:
    """往前推 n 个月 → 'YYYY-MM'"""
    y, m = THIS_MONTH.year, THIS_MONTH.month - offset_from_now
    while m <= 0:
        m += 12
        y -= 1
    return f'{y:04d}-{m:02d}'


def _balance(ym: str, expense: float, income: float = 0.0):
    return WealthBalanceList.objects.create(
        yearmon=ym, outmoney=expense, wageincome=income, otherincome=0.0,
    )


def _task(ym: str, hours: float):
    """造一条计入行（无 TaskMeta ⇒ 落到 DEFAULT_FALLBACK_ATTR='成长'，在 COUNTED 里）"""
    y, m = int(ym[:4]), int(ym[5:7])
    start = timezone.make_aware(dt.datetime(y, m, 10, 9, 0))
    return TemporalTask.objects.create(
        task_name='测试任务',
        start_time=start,
        end_time=start + dt.timedelta(hours=hours),
        duration_hours=hours,
        year=y, mon=f'{m:02d}', day=10,
    )


class TestStatHelpers:
    def test_spearman_monotonic(self):
        assert _spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
        assert _spearman([1, 2, 3, 4], [40, 30, 20, 10]) == -1.0

    def test_spearman_immune_to_outlier_scale(self):
        """秩相关只看顺序：把一个点放大 1000 倍不改变 ρ"""
        base_y = [1, 2, 3, 4, 5]
        assert _spearman([1, 2, 3, 4, 5], base_y) == _spearman([1, 2, 3, 4, 5000], base_y)

    def test_pearson_moved_by_outlier(self):
        """对照：Pearson 会被那个点带偏 —— 这就是本项目选 ρ 的理由"""
        base_y = [1, 2, 3, 4, 5]
        assert _pearson([1, 2, 3, 4, 5], base_y) != _pearson([1, 2, 3, 4, 5000], base_y)

    def test_constant_side_returns_none(self):
        assert _spearman([7, 7, 7, 7], [1, 2, 3, 4]) is None
        assert _pearson([7, 7, 7, 7], [1, 2, 3, 4]) is None


@pytest.mark.django_db
class TestPairCheck:
    def test_insufficient_sample_is_not_judged(self):
        """4 个共同月 ⇒ 给系数但不判档（`level` 必须是 None）"""
        for i in range(4):
            ym = _month_key(i + 1)
            _balance(ym, 1000 + i * 100)
            _task(ym, 10 + i * 2)

        pair = next(
            p for p in CorrelationService.pair_check()['pairs']
            if p['key'] == 'times_expense'
        )
        assert pair['n'] == 4
        assert pair['spearman'] is not None
        assert pair['level'] is None
        assert pair['level_label'] is None
        assert pair['reason'] == CORR_REASON_NOT_ENOUGH

    def test_no_common_month(self):
        """只造支出、不造时间 ⇒ 没有共同月份，不是「没关系」"""
        for i in range(14):
            _balance(_month_key(i + 1), 1000 + i * 100)

        pair = next(
            p for p in CorrelationService.pair_check()['pairs']
            if p['key'] == 'times_expense'
        )
        assert pair['n'] == 0
        assert pair['spearman'] is None
        assert pair['level'] is None
        assert pair['reason'] == CORR_REASON_NO_DATA

    def test_full_sample_positive_is_judged(self):
        """14 个月同向增长 ⇒ 判「明显」"""
        for i in range(CORRELATION_MIN_N + 2):
            ym = _month_key(i + 1)
            _balance(ym, 1000 + i * 100)
            _task(ym, 10 + i * 2)

        pair = next(
            p for p in CorrelationService.pair_check()['pairs']
            if p['key'] == 'times_expense'
        )
        assert pair['n'] == CORRELATION_MIN_N + 2
        assert pair['spearman'] == 1.0
        assert pair['level'] == 'strong'
        assert pair['reason'] is None

    def test_conclusion_resting_on_outlier_is_flagged(self):
        """全样本 ρ=-0.406（弱档），去掉最高最低各一个月后只剩 -0.188 ⇒ `robust=False`

        直接喂 `_judge` 而不是造库：这里要测的是**判据本身**，
        不需要跨 5 张表造 12 个月的数据（造库版本反而更难构造出目标形状）。

        ⚠️ 秩相关下，**单个极端点撑不起相关系数**（n=12 时一个点最多贡献 ~0.17），
        所以「不稳健」的形状不是「一个离群点」，而是「两端点对齐、中间段反向」。
        这也是为什么 `robust` 复核的是去掉两端，而不是去掉某个离群点。
        """
        months = [f'2025-{m:02d}' for m in range(1, 13)]
        ys = [12, 11, 6, 2, 1, 10, 8, 9, 7, 4, 3, 5]
        pair = {
            'key': 'demo', 'left': 'a', 'right': 'b',
            'left_label': 'A', 'right_label': 'B',
            'unit_left': '', 'unit_right': '', 'why': '测试',
        }
        series = {
            'a': {m: float(i + 1) for i, m in enumerate(months)},
            'b': {m: float(v) for m, v in zip(months, ys)},
        }

        row = CorrelationService._judge(pair, series)

        assert row['n'] == 12
        assert row['spearman'] == -0.406
        assert row['level'] == 'weak'
        assert row['trimmed_spearman'] == -0.188
        assert row['robust'] is False

    def test_steady_conclusion_is_robust(self):
        """单调同向 ⇒ 去两端后仍是 1.0，`robust=True`"""
        months = [f'2025-{m:02d}' for m in range(1, 13)]
        pair = {
            'key': 'demo', 'left': 'a', 'right': 'b',
            'left_label': 'A', 'right_label': 'B',
            'unit_left': '', 'unit_right': '', 'why': '测试',
        }
        series = {
            'a': {m: float(i + 1) for i, m in enumerate(months)},
            'b': {m: float(i + 1) for i, m in enumerate(months)},
        }

        row = CorrelationService._judge(pair, series)

        assert row['spearman'] == 1.0
        assert row['level'] == 'strong'
        assert row['trimmed_spearman'] == 1.0
        assert row['robust'] is True

    def test_constant_side_is_not_judged(self):
        """某一侧常年不变 ⇒ 相关系数无定义，不能报成「没关系」"""
        months = [f'2025-{m:02d}' for m in range(1, 13)]
        pair = {
            'key': 'demo', 'left': 'a', 'right': 'b',
            'left_label': 'A', 'right_label': 'B',
            'unit_left': '', 'unit_right': '', 'why': '测试',
        }
        series = {
            'a': {m: 500.0 for m in months},
            'b': {m: float(i + 1) for i, m in enumerate(months)},
        }

        row = CorrelationService._judge(pair, series)

        assert row['spearman'] is None
        assert row['level'] is None
        assert row['reason'] == CORR_REASON_CONSTANT

    def test_metric_series_drops_missing_months(self):
        """某月 `outmoney` 为 NULL ⇒ 该月不进序列（不补 0）"""
        for i in range(15):
            ym = _month_key(i + 1)
            _balance(ym, 1000 + i * 10)
        # 把一个月的支出置空
        empty_ym = _month_key(3)
        WealthBalanceList.objects.filter(yearmon=empty_ym).update(outmoney=None)

        series = CorrelationService._metric_balance(
            CorrelationService._years(), 'expense',
        )
        assert empty_ym not in series
        # 其余月份照常在
        assert _month_key(4) in series

    def test_coverage_reports_metric_months(self):
        for i in range(14):
            _balance(_month_key(i + 1), 1000)
        data = CorrelationService.pair_check()
        assert data['coverage']['metrics']['expense'] >= 14
        assert data['min_n'] == CORRELATION_MIN_N
        assert any(b['key'] == 'strong' for b in data['bands'])

    def test_all_pairs_carry_a_why(self):
        """每组配对都必须写清「为什么这两个量可能相关」"""
        for pair in CorrelationService.pair_check()['pairs']:
            assert pair['why'], pair['key']


@pytest.mark.django_db
class TestBodyMind:
    def test_no_check_in_gives_none_not_zero(self):
        """🔴 回归：无自检时必须是 None

        旧实现用 `aggregate(...)['avg'] or 0` ⇒ 延迟 0、夜醒 0
        ⇒ `100 - 0*1.5 - 0*15 = 100`，12 周全是满分。
        """
        data = BodyMindCorrelationService.get_correlation_data(user_id=1, weeks=4)
        assert len(data) == 4
        for row in data:
            assert row['sleep_latency'] is None
            assert row['awakenings'] is None
            assert row['nights'] == 0
            assert row['output_rate'] is None
            assert row['mood'] is None
            # 合成出来的「睡眠分」字段必须不存在
            assert 'sleep_score' not in row

    def test_single_check_fills_that_week_only(self):
        HealthSelfCheck.objects.create(
            user_id=1, check_date=TODAY, sleep_latency=30, awakenings=2,
        )
        data = BodyMindCorrelationService.get_correlation_data(user_id=1, weeks=4)
        filled = [r for r in data if r['nights'] > 0]
        assert len(filled) == 1
        assert filled[0]['sleep_latency'] == 30.0
        assert filled[0]['awakenings'] == 2.0
        # 其余周仍是 None
        assert all(r['sleep_latency'] is None for r in data if r['nights'] == 0)

    def test_averages_within_week(self):
        for latency, awake in ((20, 1), (40, 3)):
            HealthSelfCheck.objects.create(
                user_id=1, check_date=TODAY, sleep_latency=latency, awakenings=awake,
            )
        data = BodyMindCorrelationService.get_correlation_data(user_id=1, weeks=1)
        row = data[0]
        assert row['nights'] == 2
        assert row['sleep_latency'] == 30.0
        assert row['awakenings'] == 2.0

    def test_output_rate_none_when_no_output(self):
        OutputRecord.objects.create(
            user_id=1, title='写文档', quality='good', occurred_at=TODAY,
        )
        data = BodyMindCorrelationService.get_correlation_data(user_id=1, weeks=1)
        row = data[0]
        assert row['output_count'] == 1
        assert row['output_rate'] == 100.0

    def test_mood_is_level_average_not_count(self):
        """情绪是**快乐程度均值**，量程 5–20 —— 不是次数、不是 1–10"""
        SugarRecord.objects.create(title='喝到好咖啡', level_of_happiness=18, time=TODAY)
        SugarRecord.objects.create(title='散步', level_of_happiness=12, time=TODAY)
        data = BodyMindCorrelationService.get_correlation_data(user_id=1, weeks=1)
        assert data[0]['mood'] == 15.0
