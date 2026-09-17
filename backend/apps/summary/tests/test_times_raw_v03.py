"""summary 换算 v0.3：_times_raw 仅汇总非流失归因小时"""
import pytest
from datetime import datetime

from apps.temporal.models import TaskMeta, TemporalTask
from apps.summary.services.progress_aggregator import ProgressAggregator


@pytest.mark.django_db
class TestTimesRawExcludesDrain:
    def test_only_non_drain_counted(self):
        # 投向 10h，维持 4h，外部 2h，流失 5h，未归类 3h
        TaskMeta.objects.create(task_name='深度学习', activity_type='深度工作', default_attribution='投向')
        TaskMeta.objects.create(task_name='家务', activity_type='维护性事务', default_attribution='维持')
        TaskMeta.objects.create(task_name='开会', activity_type='浅层工作', default_attribution='外部')
        TaskMeta.objects.create(task_name='刷手机', activity_type='被动消耗', default_attribution='流失')
        TaskMeta.objects.create(task_name='无名', activity_type='未归类', default_attribution=None)
        for name, h in [('深度学习', 10), ('家务', 4), ('开会', 2), ('刷手机', 5), ('无名', 3)]:
            TemporalTask.objects.create(
                task_name=name, start_time=datetime.fromisoformat('2026-08-01 09:00:00'),
                duration_hours=h, year=2026, mon='08', day=1,
            )
        # 仅 {投向,维持,外部} = 10+4+2 = 16
        assert ProgressAggregator._times_raw(2026) == 16.0
        assert ProgressAggregator._times_raw(2026, 8) == 16.0
        # 其它年份应无数据
        assert ProgressAggregator._times_raw(2025) == 0.0
