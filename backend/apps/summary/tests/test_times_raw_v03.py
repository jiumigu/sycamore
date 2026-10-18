"""summary 换算 v0.3：_times_raw 仅汇总非流失归因小时（口径见 ATTRIBUTION_COUNTED）"""
import pytest
from datetime import datetime

from apps.temporal.models import TaskMeta, TemporalTask
from apps.summary.services.progress_aggregator import ProgressAggregator


@pytest.mark.django_db
class TestTimesRawExcludesDrain:
    def test_only_non_drain_counted(self):
        # 成长 10h，关系 2h，维持 4h，谋生 2h，流失 5h，未归类 3h
        TaskMeta.objects.create(task_name='深度学习', activity_type='深度工作', default_attribution='成长')
        TaskMeta.objects.create(task_name='朋友聚会', activity_type='社交', default_attribution='关系')
        TaskMeta.objects.create(task_name='家务', activity_type='维护性事务', default_attribution='维持')
        TaskMeta.objects.create(task_name='开会', activity_type='浅层工作', default_attribution='谋生')
        TaskMeta.objects.create(task_name='刷手机', activity_type='被动消耗', default_attribution='流失')
        TaskMeta.objects.create(task_name='无名', activity_type='未归类', default_attribution=None)
        for name, h in [('深度学习', 10), ('朋友聚会', 2), ('家务', 4), ('开会', 2), ('刷手机', 5), ('无名', 3)]:
            TemporalTask.objects.create(
                task_name=name, start_time=datetime.fromisoformat('2026-08-01 09:00:00'),
                duration_hours=h, year=2026, mon='08', day=1,
            )
        # 仅 ATTRIBUTION_COUNTED = {成长,体验,关系,谋生,维持} = 10+2+4+2 = 18
        # （流失与未归类不计；本用例里没有「体验」任务）
        assert ProgressAggregator._times_raw(2026) == 18.0
        assert ProgressAggregator._times_raw(2026, 8) == 18.0
        # 其它年份应无数据
        assert ProgressAggregator._times_raw(2025) == 0.0

    def test_experience_is_counted(self):
        """🔴 v3.60.36：「体验」**计入**时间投入（与 成长/关系/谋生/维持 同档）

        钉住这个选择的后果：若哪天有人把它从 ATTRIBUTION_COUNTED 里拿掉，
        过去所有旅游时长会**回溯性地**掉出计分（≈139.8h ≈ 4.7 点），
        而且不会有任何地方报错 —— 分数只是悄悄变小。
        """
        TaskMeta.objects.create(task_name='旅游观景', activity_type='主动经历', default_attribution='体验')
        TemporalTask.objects.create(
            task_name='旅游观景', start_time=datetime.fromisoformat('2026-08-01 09:00:00'),
            duration_hours=7.0, year=2026, mon='08', day=1,
        )
        assert ProgressAggregator._times_raw(2026) == 7.0

    def test_drain_still_excluded_after_adding_experience(self):
        """回归：加「体验」不得顺手把「流失」也放进来（同一天两条，只算体验那条）"""
        TaskMeta.objects.create(task_name='旅游观景', activity_type='主动经历', default_attribution='体验')
        TaskMeta.objects.create(task_name='刷短视频', activity_type='被动消耗', default_attribution='流失')
        for name, h in [('旅游观景', 7), ('刷短视频', 3)]:
            TemporalTask.objects.create(
                task_name=name, start_time=datetime.fromisoformat('2026-08-02 09:00:00'),
                duration_hours=h, year=2026, mon='08', day=2,
            )
        assert ProgressAggregator._times_raw(2026) == 7.0
