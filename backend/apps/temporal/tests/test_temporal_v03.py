"""时间重构 v0.3 测试：三层分类(L1归因/L2类型/L3 task_name) / 历史迁移 / 完整度 / 旭日 / 归因解析"""
import io

import pytest
from datetime import datetime

from apps.temporal.models import TaskMeta, TemporalTask
from apps.temporal.services import resolve_attribution, resolve_task_meta
from apps.redemption.models import RedemptionAttrRule


@pytest.mark.django_db
class TestResolveAttribution:
    def test_fallback_when_no_meta(self):
        """无 TaskMeta 时兜底=投向"""
        out = resolve_attribution(['某未知任务'])
        assert out['某未知任务'] == '投向'

    def test_rule_override_beats_default(self):
        """redemption_attr_rule 优先级高于 default_attribution"""
        TaskMeta.objects.create(task_name='写作', activity_type='深度工作', default_attribution='投向')
        # 默认投向，但规则覆盖为外部
        RedemptionAttrRule.objects.create(
            match_field='task_name', match_value='写作', attribution='外部', priority=50, is_active=True,
        )
        assert resolve_attribution(['写作'])['写作'] == '外部'

    def test_activity_type_match_field(self):
        """match_field=activity_type 也能匹配"""
        TaskMeta.objects.create(task_name='X', activity_type='浅层工作', default_attribution='外部')
        RedemptionAttrRule.objects.create(
            match_field='activity_type', match_value='浅层工作', attribution='流失', priority=10, is_active=True,
        )
        assert resolve_attribution(['X'])['X'] == '流失'

    def test_resolve_task_meta_shape(self):
        TaskMeta.objects.create(task_name='T', activity_type='深度工作', default_attribution='投向')
        m = resolve_task_meta(['T'])['T']
        assert m['activity_type'] == '深度工作'
        assert m['is_unclassified'] is False
        assert 'group_name' not in m   # v3.57.0 已取消「自建聚合分组」层


@pytest.mark.django_db
class TestCompletenessAndTrend:
    def _seed(self):
        TaskMeta.objects.create(task_name='A', activity_type='深度工作', default_attribution='投向')
        TaskMeta.objects.create(task_name='B', activity_type='维护性事务', default_attribution='维持')
        TaskMeta.objects.create(task_name='C', activity_type='未归类', default_attribution=None)
        for name, d, h in [('A', '2026-08-01', 4), ('A', '2026-08-02', 2),
                          ('B', '2026-08-01', 3), ('C', '2026-08-03', 5)]:
            TemporalTask.objects.create(
                task_name=name, start_time=datetime.fromisoformat(f'{d} 09:00:00'),
                duration_hours=h, year=2026, mon='08', day=int(d[8:10]),
            )

    def test_completeness_denominator(self):
        from apps.temporal.services import TemporalStatsService
        self._seed()
        c = TemporalStatsService.get_completeness(2026)
        # 已归类 = A(6) + B(3) = 9；未归类 C(5) 不计入
        assert c['classified_hours'] == 9.0
        assert c['total_hours'] == 14.0
        # 有记录 3 天 × 16 = 48 分母
        assert c['days_recorded'] == 3
        assert c['completeness'] == round(9 / 48, 4)

    def test_trend_level_l1_l2_l3(self):
        from apps.temporal.services import TemporalStatsService
        self._seed()
        l1 = TemporalStatsService.get_trend(2026, level='l1')
        l2 = TemporalStatsService.get_trend(2026, level='l2')
        l3 = TemporalStatsService.get_trend(2026, level='l3')

        def keys_of(rows):
            ks = set()
            for item in rows:
                ks.update(k for k in item if k != 'period')
            return ks

        # L1 = 归因（A→投向、B→维持、C 未归类无归因兜底投向）
        assert keys_of(l1) == {'投向', '维持'}
        # L2 = 活动类型
        assert keys_of(l2) == {'深度工作', '维护性事务', '未归类'}
        # L3 = task_name
        assert keys_of(l3) == {'A', 'B', 'C'}

    def test_sunburst_three_levels(self):
        from apps.temporal.services import TemporalStatsService
        self._seed()
        sb = TemporalStatsService.get_sunburst(2026)
        # 内圈 L1 = 归因
        assert {g['name'] for g in sb['groups']} == {'投向', '维持'}
        toward = next(g for g in sb['groups'] if g['name'] == '投向')
        # 中圈 L2 = 活动类型
        l2_names = [c['name'] for c in toward['children']]
        assert '深度工作' in l2_names and '未归类' in l2_names
        # 外圈 L3 = task_name
        deep = next(c for c in toward['children'] if c['name'] == '深度工作')
        assert any(x['name'] == 'A' for x in deep['children'])
        assert toward['color'] is not None


@pytest.mark.django_db
class TestUnclassifiedAndBatch:
    def test_unclassified_endpoint(self):
        from rest_framework.test import APIClient
        TaskMeta.objects.create(task_name='ZZ', activity_type='未归类', default_attribution=None)
        TemporalTask.objects.create(task_name='ZZ', start_time=datetime.fromisoformat('2026-08-01 09:00:00'),
                                    duration_hours=3, year=2026, mon='08', day=1)
        r = APIClient().get('/api/temporal/tasks/unclassified/')
        assert r.status_code == 200
        assert r.data['count'] == 1
        assert r.data['items'][0]['task_name'] == 'ZZ'
        assert r.data['items'][0]['total_hours'] == 3.0

    def test_batch_set_meta_writes_attr_rule(self):
        from rest_framework.test import APIClient
        r = APIClient().post('/api/temporal/tasks/batch_set_meta/', {
            'task_names': ['写作'], 'activity_type': '深度工作', 'attribution': '投向',
        }, format='json')
        assert r.status_code == 200 and r.data['updated'] == 1
        meta = TaskMeta.objects.get(task_name='写作')
        assert meta.activity_type == '深度工作' and meta.default_attribution == '投向'
        rule = RedemptionAttrRule.objects.filter(match_field='task_name', match_value='写作').first()
        assert rule is not None and rule.attribution == '投向'

    def test_overview_drops_production_percentage(self):
        from apps.temporal.services import TemporalStatsService
        TaskMeta.objects.create(task_name='A', activity_type='深度工作', default_attribution='投向')
        TemporalTask.objects.create(task_name='A', start_time=datetime.fromisoformat('2026-08-01 09:00:00'),
                                    duration_hours=2, year=2026, mon='08', day=1)
        ov = TemporalStatsService.get_overview(2026)
        assert 'production_percentage' not in ov
        assert 'group_breakdown' not in ov          # 已取消自建分组层
        assert ov['activity_breakdown'].get('深度工作') == 2.0   # L2
        assert ov['attribution_breakdown'].get('投向') == 2.0    # L1


@pytest.mark.django_db
class TestCsvImportNoCategory:
    def test_import_stops_writing_category_columns(self):
        """v0.3：导入不再写 category_level1/category_color，并自动建 TaskMeta"""
        from rest_framework.test import APIClient
        csv_content = "任务名称,开始时间,持续时间（小时）\n代码编程,2026-08-10 09:00:00,2.5\n"
        f = io.BytesIO(csv_content.encode('utf-8'))
        f.name = 't.csv'
        c = APIClient()
        r = c.post('/api/temporal/tasks/import_csv/', {'file': f}, format='multipart')
        assert r.status_code == 201, r.data
        t = TemporalTask.objects.filter(task_name='代码编程').first()
        assert t is not None
        assert t.category_level1 is None and t.category_color is None
        # 命中 TASK_TO_L2：代码编程 → 深度工作/投向
        meta = TaskMeta.objects.filter(task_name='代码编程').first()
        assert meta is not None and meta.activity_type == '深度工作'


@pytest.mark.django_db
class TestMigrateCommandIdempotent:
    def test_idempotent_and_no_delete(self):
        """migrate_temporal_categories 幂等，且不改动旧列/旧数据"""
        for name, d, h in [('牛马工作', '2026-08-01', 3), ('迷谷知松', '2026-08-02', 2),
                           ('牛马工作', '2026-08-03', 1)]:
            TemporalTask.objects.create(task_name=name, start_time=datetime.fromisoformat(f'{d} 09:00:00'),
                                        duration_hours=h, year=2026, mon='08', day=int(d[8:10]),
                                        category_level1='工作', category_color='#EF4444')
        from apps.temporal.management.commands.migrate_temporal_categories import Command
        Command().handle()
        first = TaskMeta.objects.count()
        # 牛马工作/迷谷知松 各 1 条
        assert first == 2
        # 重跑不应增加
        Command().handle()
        assert TaskMeta.objects.count() == first
        # 旧列仍在（未删除）
        assert TemporalTask.objects.filter(category_level1='工作').count() == 3
        # 映射正确
        assert TaskMeta.objects.get(task_name='牛马工作').activity_type == '浅层工作'
        assert TaskMeta.objects.get(task_name='迷谷知松').activity_type == '兴趣记录'

    def test_dedup_not_broken_by_meta_ordering(self):
        """回归：Meta.ordering 不应让 DISTINCT 去重静默失效（虚增计数）

        TemporalTask.Meta.ordering=['-start_time'] 会让
        .values_list('task_name').distinct() 生成
        `SELECT DISTINCT task_name, start_time`，DISTINCT 实际按
        (task_name, start_time) 去重 —— 需 order_by() 清序。
        """
        for i in range(5):
            TemporalTask.objects.create(
                task_name='代码编程', start_time=datetime.fromisoformat(f'2026-08-0{i + 1} 09:00:00'),
                duration_hours=1, year=2026, mon='08', day=i + 1)
        for i in range(3):
            TemporalTask.objects.create(
                task_name='阅读思考', start_time=datetime.fromisoformat(f'2026-08-0{i + 1} 10:00:00'),
                duration_hours=1, year=2026, mon='08', day=i + 1)
        from apps.temporal.management.commands.migrate_temporal_categories import Command
        buf = io.StringIO()
        Command(stdout=buf).handle()
        out = buf.getvalue()
        # 真实去重 task_name = 2，若 DISTINCT 失效会被虚增为 8
        assert 'task_name 数：2' in out, out
        assert TaskMeta.objects.count() == 2
