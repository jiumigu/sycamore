"""体重：一天可以记多条（v3.64.73）

🔴 背景：表上原来有 `uk_weight_user_date` 唯一约束（每人每天一条）。
   于是「早上 63.10、晚上 63.25」第二次保存必然 400，而 DRF 那句是
   `The fields user_id, record_date must make a unique set.` —— 英文、说的是列名，
   前端又把它盖成「操作失败」。三个环节各说各的，用户只能看到一句「错了」。

   去掉约束只是第一步。一天多条之后**每个「取哪一条」的地方都必须有答案**：
   - 「现在多重」= 最后一天的当天结果；
   - 趋势图一天一个点，取当天结果；
   - 列表同日多条按后录入在前。
   这三处若各自随手写 `order_by('-record_date').first()`，同一天那几条的先后
   由数据库决定 ⇒ 当前体重在两个数之间随机跳，且没有任何报错。
"""
import datetime as dt
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.health.models import WeightGoal, WeightRecord
from apps.health.services import WeightService

URL = '/api/health/weight/records/'
TREND = '/api/health/weight/trend/'
STATS = '/api/health/weight/stats/'

DAY = dt.date(2026, 11, 16)


def _create(weight: str, day: dt.date = DAY, measure_time=None):
    return WeightRecord.objects.create(
        user_id=1,
        record_date=day,
        weight_kg=Decimal(weight),
        measure_time=measure_time,
    )


@pytest.mark.django_db
class TestSameDayCreate:
    def test_api_allows_two_records_on_same_day(self):
        """同一天记两次：都必须成功（这正是报障的场景：早 63.10 / 晚 63.25）。"""
        c = APIClient()
        base = {
            'record_date': '2026-11-16',
            'weight_kg': '63.10',
            'measure_time': 'morning',
            'notes': '',
            'user_id': 1,
        }
        r1 = c.post(URL, base, format='json')
        assert r1.status_code == 201, r1.data

        r2 = c.post(URL, {**base, 'weight_kg': '63.25', 'measure_time': 'evening'}, format='json')
        assert r2.status_code == 201, r2.data
        assert WeightRecord.objects.filter(record_date=DAY).count() == 2

    def test_second_record_keeps_own_values(self):
        """两条各存各的，不是把第一条改掉。"""
        _create('63.10', measure_time='morning')
        _create('63.25', measure_time='evening')
        weights = sorted(float(w) for w in WeightRecord.objects.filter(record_date=DAY).values_list('weight_kg', flat=True))
        assert weights == [63.10, 63.25]


@pytest.mark.django_db
class TestWhichRecordWins:
    def test_latest_is_evening_even_if_inserted_first(self):
        """「当天结果」按时刻算，不按插入顺序 —— 补录早上不该把结论改回早上的数。"""
        _create('63.25', measure_time='evening')
        _create('63.10', measure_time='morning')
        latest = WeightService.latest_record(1)
        assert float(latest.weight_kg) == 63.25

    def test_unknown_time_counts_as_earliest(self):
        """没填时刻的那条视为当天最早：填了「晚上」的更具体，也更靠后。"""
        _create('63.10', measure_time=None)
        _create('63.25', measure_time='evening')
        assert float(WeightService.latest_record(1).weight_kg) == 63.25

    def test_same_time_falls_back_to_id(self):
        """同一时刻两条（补录）：后录入的算后一次，比较结果必须稳定。"""
        first = _create('63.10', measure_time='morning')
        second = _create('63.25', measure_time='morning')
        assert second.id > first.id
        assert WeightService.latest_record(1).id == second.id

    def test_latest_spans_days(self):
        _create('62.00', day=dt.date(2026, 11, 10), measure_time='evening')
        _create('63.10', day=DAY, measure_time='morning')
        _create('63.25', day=DAY, measure_time='evening')
        assert float(WeightService.latest_record(1).weight_kg) == 63.25

    def test_no_record_returns_none(self):
        assert WeightService.latest_record(1) is None


@pytest.mark.django_db
class TestStatsFollowsLatest:
    def test_current_weight_is_the_day_result(self):
        WeightGoal.objects.create(
            user_id=1,
            start_weight_kg=Decimal('65.00'),
            target_weight_kg=Decimal('52.50'),
            monthly_target_kg=Decimal('1.50'),
            start_date=dt.date(2026, 6, 24),
            status='in_progress',
            is_active=True,
        )
        _create('63.25', measure_time='evening')
        _create('63.10', measure_time='morning')
        stats = WeightService.get_stats(user_id=1)
        assert stats['current_weight_kg'] == pytest.approx(63.25, abs=0.001)
        assert stats['current_weight_jin'] == pytest.approx(126.5, abs=0.05)

    def test_goal_status_uses_day_result(self):
        """里程碑判定也吃「当天结果」，否则同一天两条会得出两个结论。"""
        goal = WeightGoal.objects.create(
            user_id=1,
            start_weight_kg=Decimal('65.00'),
            target_weight_kg=Decimal('52.50'),
            monthly_target_kg=Decimal('1.50'),
            start_date=dt.date(2026, 6, 24),
            status='in_progress',
            is_active=True,
        )
        _create('63.25', measure_time='evening')
        _create('63.10', measure_time='morning')
        assert float(WeightService.latest_record(goal.user_id).weight_kg) == 63.25


@pytest.mark.django_db
class TestTrendDaily:
    def test_daily_collapses_one_day_into_one_point(self):
        _create('63.10', measure_time='morning')
        _create('63.25', measure_time='evening')
        _create('62.90', day=dt.date(2026, 11, 15), measure_time='evening')

        data = APIClient().get(TREND).data
        assert len(data['daily']) == 2, '一天一个点'
        assert [p['date'] for p in data['daily']] == ['2026-11-15', '2026-11-16']

        today = data['daily'][-1]
        assert today['count'] == 2
        assert float(today['weight_jin']) == pytest.approx(126.5, abs=0.05)
        assert [r['weight_jin'] for r in today['readings']] == pytest.approx([126.2, 126.5], abs=0.05)

    def test_daily_uses_last_reading_of_the_day(self):
        _create('63.25', measure_time='evening')
        _create('63.10', measure_time='morning')
        day = APIClient().get(TREND).data['daily'][0]
        assert day['weight_jin'] == pytest.approx(126.5, abs=0.05)

    def test_daily_reading_carries_measure_label(self):
        _create('63.10', measure_time='morning')
        _create('63.25', measure_time='evening')
        day = APIClient().get(TREND).data['daily'][0]
        assert [r['measure_time_display'] for r in day['readings']] == ['早晨', '晚上']

    def test_records_keeps_every_row(self):
        """`daily` 是画图用的聚合，`records` 仍是逐条 —— 不能因为画图就把数吞掉。"""
        _create('63.10', measure_time='morning')
        _create('63.25', measure_time='evening')
        data = APIClient().get(TREND).data
        assert len(data['records']) == 2
        assert all('measure_time' in r for r in data['records'])

    def test_single_record_day_count_is_one(self):
        _create('63.10', measure_time='morning')
        day = APIClient().get(TREND).data['daily'][0]
        assert day['count'] == 1
        assert len(day['readings']) == 1


@pytest.mark.django_db
class TestListOrder:
    def test_same_day_later_record_first(self):
        """列表按 `-record_date, -id`：同日多条时后录入的在前，扫描顺序稳定。"""
        _create('63.10', measure_time='morning')
        _create('63.25', measure_time='evening')
        rows = APIClient().get(URL, {'user_id': 1}).data
        rows = rows['results'] if isinstance(rows, dict) else rows
        assert [float(r['weight_kg']) for r in rows] == [63.25, 63.10]

    def test_stats_endpoint_agrees_with_service(self):
        _create('63.10', measure_time='morning')
        _create('63.25', measure_time='evening')
        assert APIClient().get(STATS).data['current_weight_kg'] == pytest.approx(63.25, abs=0.001)
