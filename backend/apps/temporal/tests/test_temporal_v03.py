"""时间重构 v0.3 测试：三层分类(L1归因/L2类型/L3 task_name) / 历史迁移 / 完整度 / 旭日 / 归因解析"""
import io

import pytest
from datetime import datetime

from apps.temporal.constants import ACTIVITY_TYPE_PRESETS, ATTRIBUTION_ORDER, TASK_TO_L2
from apps.temporal.models import TaskMeta, TemporalTask
from apps.temporal.services import resolve_attribution, resolve_task_meta
from apps.redemption.models import RedemptionAttrRule


@pytest.mark.django_db
class TestResolveAttribution:
    def test_fallback_when_no_meta(self):
        """无 TaskMeta 时兜底=成长"""
        out = resolve_attribution(['某未知任务'])
        assert out['某未知任务'] == '成长'

    def test_rule_override_beats_default(self):
        """redemption_attr_rule 优先级高于 default_attribution"""
        TaskMeta.objects.create(task_name='写作', activity_type='深度工作', default_attribution='成长')
        # 默认成长，但规则覆盖为谋生
        RedemptionAttrRule.objects.create(
            match_field='task_name', match_value='写作', attribution='谋生', priority=50, is_active=True,
        )
        assert resolve_attribution(['写作'])['写作'] == '谋生'

    def test_activity_type_match_field(self):
        """match_field=activity_type 也能匹配"""
        TaskMeta.objects.create(task_name='X', activity_type='浅层工作', default_attribution='谋生')
        RedemptionAttrRule.objects.create(
            match_field='activity_type', match_value='浅层工作', attribution='流失', priority=10, is_active=True,
        )
        assert resolve_attribution(['X'])['X'] == '流失'

    def test_resolve_task_meta_shape(self):
        TaskMeta.objects.create(task_name='T', activity_type='深度工作', default_attribution='成长')
        m = resolve_task_meta(['T'])['T']
        assert m['activity_type'] == '深度工作'
        assert m['is_unclassified'] is False
        assert 'group_name' not in m   # v3.57.0 已取消「自建聚合分组」层


@pytest.mark.django_db
class TestCompletenessAndTrend:
    def _seed(self):
        TaskMeta.objects.create(task_name='A', activity_type='深度工作', default_attribution='成长')
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

        # L1 = 归因（A→成长、B→维持、C 未归类无归因兜底成长）
        assert keys_of(l1) == {'成长', '维持'}
        # L2 = 活动类型
        assert keys_of(l2) == {'深度工作', '维护性事务', '未归类'}
        # L3 = task_name
        assert keys_of(l3) == {'A', 'B', 'C'}

    def test_sunburst_three_levels(self):
        from apps.temporal.services import TemporalStatsService
        self._seed()
        sb = TemporalStatsService.get_sunburst(2026)
        # 内圈 L1 = 归因
        assert {g['name'] for g in sb['groups']} == {'成长', '维持'}
        toward = next(g for g in sb['groups'] if g['name'] == '成长')
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
            'task_names': ['写作'], 'activity_type': '深度工作', 'attribution': '成长',
        }, format='json')
        assert r.status_code == 200 and r.data['updated'] == 1
        meta = TaskMeta.objects.get(task_name='写作')
        assert meta.activity_type == '深度工作' and meta.default_attribution == '成长'
        rule = RedemptionAttrRule.objects.filter(match_field='task_name', match_value='写作').first()
        assert rule is not None and rule.attribution == '成长'

    def test_overview_drops_production_percentage(self):
        from apps.temporal.services import TemporalStatsService
        TaskMeta.objects.create(task_name='A', activity_type='深度工作', default_attribution='成长')
        TemporalTask.objects.create(task_name='A', start_time=datetime.fromisoformat('2026-08-01 09:00:00'),
                                    duration_hours=2, year=2026, mon='08', day=1)
        ov = TemporalStatsService.get_overview(2026)
        assert 'production_percentage' not in ov
        assert 'group_breakdown' not in ov          # 已取消自建分组层
        assert ov['activity_breakdown'].get('深度工作') == 2.0   # L2
        assert ov['attribution_breakdown'].get('成长') == 2.0    # L1


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
        # 命中 TASK_TO_L2：代码编程 → 深度工作/成长
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


@pytest.mark.django_db
class TestContribDominantAttr:
    """时间贡献图「主导归因」视图：每天按 L1 归因中时长最多者着色

    规则：① 取最多；② 并列按价值序（ATTRIBUTION_ORDER）取靠前者；
         ③ 当天无任何已归因时长（L2=未归类）→ attr=None（前端画灰格）
    """

    @staticmethod
    def _mk(task_name, day, hours):
        TemporalTask.objects.create(
            task_name=task_name, start_time=datetime.fromisoformat(f'{day} 09:00:00'),
            duration_hours=hours, year=int(day[:4]), mon=day[5:7], day=int(day[8:10]))

    @staticmethod
    def _get():
        from rest_framework.test import APIClient
        r = APIClient().get('/api/temporal/tasks/contrib/?metric=dominant_attr')
        assert r.status_code == 200, r.data
        assert r.data['mode'] == 'attribution'
        return {x['date']: x for x in r.data['data']}

    def test_picks_largest_attribution(self):
        TaskMeta.objects.create(task_name='写作', activity_type='主动休息', default_attribution='成长')
        TaskMeta.objects.create(task_name='刷手机', activity_type='被动消耗', default_attribution='流失')
        self._mk('写作', '2026-08-01', 2)
        self._mk('刷手机', '2026-08-01', 3)
        d = self._get()['2026-08-01']
        assert d['attr'] == '流失'
        assert d['value'] == 5                      # value 仍是当天总时长
        assert d['breakdown']['成长'] == 2 and d['breakdown']['流失'] == 3

    def test_tie_takes_value_order(self):
        TaskMeta.objects.create(task_name='A', activity_type='主动休息', default_attribution='成长')
        TaskMeta.objects.create(task_name='B', activity_type='维护性事务', default_attribution='维持')
        self._mk('A', '2026-08-02', 2)
        self._mk('B', '2026-08-02', 2)
        assert self._get()['2026-08-02']['attr'] == '成长'

    def test_attr_matches_displayed_breakdown(self):
        """回归：颜色判定必须与悬浮提示里展示的（2 位小数）breakdown 一致

        否则会出现提示里两值看着并列、颜色却按浮点尾数分胜负的观感矛盾。
        """
        TaskMeta.objects.create(task_name='C', activity_type='主动休息', default_attribution='成长')
        TaskMeta.objects.create(task_name='D', activity_type='维护性事务', default_attribution='维持')
        self._mk('C', '2026-08-05', 0.4999)
        self._mk('D', '2026-08-05', 0.5001)
        d = self._get()['2026-08-05']
        bd = d['breakdown']
        top = max(bd[k] for k in ATTRIBUTION_ORDER)
        expect = next(k for k in ATTRIBUTION_ORDER if bd[k] == top)
        assert d['attr'] == expect

    def test_unclassified_day_has_no_attr(self):
        TaskMeta.objects.create(task_name='待定', activity_type='未归类', default_attribution=None)
        self._mk('待定', '2026-08-03', 1.5)
        d = self._get()['2026-08-03']
        assert d['attr'] is None
        assert d['breakdown']['未归类'] == 1.5
        assert sum(d['breakdown'][k] for k in ATTRIBUTION_ORDER) == 0

    def test_relation_slot_and_order_invariance(self):
        """v3.58.11 第五格「关系」：社交类改挂关系，且原四词相对价值序必须不变

        ATTRIBUTION_ORDER 不只管显示序 —— 并列时靠前者胜出。若新增项插错位置，
        历史数据「并列取谁」的结果会**静默改变**，故钉死此断言。
        """
        assert dict(ACTIVITY_TYPE_PRESETS)['社交'] == '关系'
        assert TASK_TO_L2['人际交往'] == ('社交', '关系')
        assert [a for a in ATTRIBUTION_ORDER if a != '关系'] == ['成长', '维持', '谋生', '流失']

    def test_relation_wins_when_largest(self):
        """关系小时最多的那天，主导归因应着「关系」色，且进入 breakdown"""
        TaskMeta.objects.create(task_name='S', activity_type='社交', default_attribution='关系')
        TaskMeta.objects.create(task_name='B', activity_type='维护性事务', default_attribution='维持')
        self._mk('S', '2026-08-06', 3)
        self._mk('B', '2026-08-06', 1)
        d = self._get()['2026-08-06']
        assert d['attr'] == '关系'
        assert d['breakdown']['关系'] == 3

    def test_value_mode_unchanged(self):
        """量值模式仍返回 mode=value，不受本次改动影响"""
        from rest_framework.test import APIClient
        TaskMeta.objects.create(task_name='写作', activity_type='主动休息', default_attribution='成长')
        self._mk('写作', '2026-08-04', 2)
        r = APIClient().get('/api/temporal/tasks/contrib/?metric=record_count')
        assert r.status_code == 200
        assert r.data['mode'] == 'value'
        assert r.data['data'][0]['value'] == 1


@pytest.mark.django_db
class TestContribWorkMetric:
    """v3.58.14：贡献图量值口径「牛马工作」替换原「睡眠」

    口径 = L3 任务名精确等于「牛马工作」的当日小时合计。**不是**按 L2=浅层工作、
    也不是 L1=谋生 —— 后者含其他谋生类任务，数字会比这个指标大。
    """

    URL = '/api/temporal/tasks/contrib/?metric=work'

    @staticmethod
    def _mk(task_name, day, hours):
        TemporalTask.objects.create(
            task_name=task_name, start_time=datetime.fromisoformat(f'{day} 09:00:00'),
            duration_hours=hours, year=int(day[:4]), mon=day[5:7], day=int(day[8:10]))

    @staticmethod
    def _get(query='metric=work'):
        from rest_framework.test import APIClient
        r = APIClient().get(f'/api/temporal/tasks/contrib/?{query}')
        assert r.status_code == 200, getattr(r, 'data', r.content)
        return r.data

    def test_only_exact_task_name_counted(self):
        """只有任务名精确为「牛马工作」的才计入；同日其他任务（哪怕同为谋生）不并进来"""
        TaskMeta.objects.create(task_name='牛马工作', activity_type='浅层工作', default_attribution='谋生')
        TaskMeta.objects.create(task_name='跑腿代办', activity_type='浅层工作', default_attribution='谋生')
        self._mk('牛马工作', '2026-08-11', 8)
        self._mk('牛马工作', '2026-08-12', 1.5)
        self._mk('跑腿代办', '2026-08-11', 3)
        d = {x['date']: x['value'] for x in self._get()['data']}
        assert d['2026-08-11'] == 8.0, d      # 3h 的「跑腿代办」不计入
        assert d['2026-08-12'] == 1.5, d

    def test_day_without_work_record_is_zero(self):
        """当天无牛马工作 → 该天值为 0（沿用 hours 口径的 0 值语义，不是缺失）"""
        TaskMeta.objects.create(task_name='写作', activity_type='深度工作', default_attribution='成长')
        self._mk('写作', '2026-08-13', 2)
        d = {x['date']: x['value'] for x in self._get()['data']}
        assert d['2026-08-13'] == 0.0, d

    def test_legacy_sleep_metric_falls_back_to_hours(self):
        """回归：旧链接残留的 ?metric=sleep 必须安全回落 hours，不得 500"""
        self._mk('牛马工作', '2026-08-14', 6)
        d = self._get('metric=sleep')
        assert d['mode'] == 'value'
        assert d['data'][0]['value'] == 6.0, d

    def test_value_mode_shape_unchanged(self):
        """量值模式响应结构不变（前端按 data/min_year/max_year 渲染）"""
        self._mk('牛马工作', '2026-08-15', 4)
        d = self._get()
        assert d['mode'] == 'value' and d['metric'] == 'work'
        assert set(d) >= {'data', 'min_year', 'max_year', 'summary'}, d


@pytest.mark.django_db
class TestMetaLedger:
    """分类台账（/tasks/meta_ledger/）：全量 task_name + 真实使用量 + 有效归因及来源

    v3.58.3 起「映射编辑器」页面主体改为台账，「未归类」只是其中一个筛选态。
    """

    URL = '/api/temporal/tasks/meta_ledger/'

    @staticmethod
    def _mk(task_name, day, hours):
        TemporalTask.objects.create(
            task_name=task_name, start_time=datetime.fromisoformat(f'{day} 09:00:00'),
            duration_hours=hours, year=int(day[:4]), mon=day[5:7], day=int(day[8:10]))

    @staticmethod
    def _get(query=''):
        from rest_framework.test import APIClient
        r = APIClient().get(f'{TestMetaLedger.URL}{query}')
        assert r.status_code == 200, r.data
        return r.data

    def _seed(self):
        TaskMeta.objects.create(task_name='写作', activity_type='深度工作', default_attribution='成长')
        TaskMeta.objects.create(task_name='刷手机', activity_type='被动消耗', default_attribution='流失')
        TaskMeta.objects.create(task_name='待定', activity_type='未归类', default_attribution=None)
        self._mk('写作', '2026-08-01', 2)
        self._mk('写作', '2026-08-02', 3)
        self._mk('写作', '2026-08-03', 1)
        self._mk('刷手机', '2026-08-01', 4)
        self._mk('待定', '2026-08-01', 5)

    def test_aggregation_not_broken_by_meta_ordering(self):
        """回归：外部表(managed=False) Meta.ordering=['-start_time'] 不能把 start_time 注入聚合分组

        若被注入，同 task_name 会按 start_time 拆成多行（次数虚高为 1、时长被拆散），
        正确口径是：按 task_name 聚合 → 「写作」3 次 / 6h。
        """
        self._seed()
        items = {i['task_name']: i for i in self._get()['items']}
        w = items['写作']
        assert w['record_count'] == 3, w
        assert w['total_hours'] == 6.0, w
        assert w['avg_minutes'] == 120.0, w       # 6h/3次
        assert w['last_used'] == '2026-08-03', w  # 最近一次使用
        assert len(self._get()['items']) == 3     # 而不是被拆成 5 行

    def test_attribution_source_three_ways(self):
        """有效归因来源：rule(赎回期规则) > default(类型默认) > fallback(兜底)"""
        self._seed()
        RedemptionAttrRule.objects.create(
            match_field='task_name', match_value='刷手机', attribution='谋生', priority=50, is_active=True)
        items = {i['task_name']: i for i in self._get()['items']}
        assert (items['写作']['effective_attribution'], items['写作']['attribution_source']) == ('成长', 'default')
        assert (items['刷手机']['effective_attribution'], items['刷手机']['attribution_source']) == ('谋生', 'rule')
        # 无默认归因且无规则 → 兜底成长
        assert (items['待定']['effective_attribution'], items['待定']['attribution_source']) == ('成长', 'fallback')

    def test_summary_is_global_and_counts_fallback(self):
        self._seed()
        sm = self._get('?attribution=流失')['summary']   # 概要不受筛选影响
        assert (sm['total'], sm['classified'], sm['unclassified']) == (3, 2, 1), sm
        assert sm['total_hours'] == 15.0, sm             # 6 + 4 + 5
        # 归因小计口径与 get_overview 的 attribution_breakdown / 结构图 / 趋势图一致：
        # 未归类（无默认归因）经「兜底成长」计入 L1，故四项之和 == 总时长
        assert sum(sm['by_attribution'].values()) == 15.0, sm
        assert sm['by_attribution']['成长'] == 11.0, sm  # 写作 6 + 待定(兜底) 5
        assert sm['by_attribution']['流失'] == 4.0, sm
        # 未归类时长另外单列，供页面在 >0 时显式提示
        assert sm['unclassified_hours'] == 5.0, sm

    def test_filters(self):
        self._seed()
        RedemptionAttrRule.objects.create(
            match_field='task_name', match_value='刷手机', attribution='谋生', priority=50, is_active=True)
        assert self._get('?unclassified_only=1')['returned'] == 1
        assert {i['task_name'] for i in self._get('?activity_type=深度工作')['items']} == {'写作'}
        assert {i['task_name'] for i in self._get('?attribution=谋生')['items']} == {'刷手机'}
        assert {i['task_name'] for i in self._get('?search=手')['items']} == {'刷手机'}
        # 组合筛选：L2=未归类 且 搜索命中
        assert self._get('?unclassified_only=1&search=待定')['returned'] == 1
        assert self._get('?unclassified_only=1&search=写作')['returned'] == 0

    def test_items_sorted_by_hours_desc(self):
        self._seed()
        hours = [i['total_hours'] for i in self._get()['items']]
        assert hours == sorted(hours, reverse=True), hours

    def test_empty_ledger_shape(self):
        """空库：结构稳定，不给前端留坑（未归类 0 是正常态，不是异常）

        by_attribution 的键集必须恒等于 ATTRIBUTION_ORDER（多一格少一格都会让台账列错位）。
        """
        d = self._get()
        assert set(d['summary']['by_attribution']) == set(ATTRIBUTION_ORDER)
        assert d['summary'] == {'total': 0, 'classified': 0, 'unclassified': 0,
                                'total_hours': 0.0, 'unclassified_hours': 0.0,
                                'by_attribution': {a: 0.0 for a in ATTRIBUTION_ORDER}}
        assert d['returned'] == 0 and d['items'] == []


@pytest.mark.django_db
class TestBatchSetMetaLedgerModes:
    """batch_set_meta 为台账单行编辑新增的两个可选开关（不传即保持旧行为）"""

    URL = '/api/temporal/tasks/batch_set_meta/'

    @staticmethod
    def _post(payload):
        from rest_framework.test import APIClient
        r = APIClient().post(TestBatchSetMetaLedgerModes.URL, payload, format='json')
        assert r.status_code == 200, r.data
        return r.data

    def test_keep_default_preserves_attribution_and_writes_no_rule(self):
        """改 L2 类型时保留原默认归因，且不应凭空产生归因规则"""
        TaskMeta.objects.create(task_name='写作', activity_type='深度工作', default_attribution='成长')
        self._post({'task_names': ['写作'], 'activity_type': '兴趣记录', 'keep_default': True})
        m = TaskMeta.objects.get(task_name='写作')
        assert m.activity_type == '兴趣记录'
        assert m.default_attribution == '成长'          # 未被清空
        assert RedemptionAttrRule.objects.count() == 0  # 未产生副作用规则

    def test_legacy_behavior_unchanged_without_keep_default(self):
        """不传 keep_default → 旧语义：default_attribution 跟随 attribution（含置空）"""
        TaskMeta.objects.create(task_name='写作', activity_type='深度工作', default_attribution='成长')
        self._post({'task_names': ['写作'], 'activity_type': '深度工作', 'attribution': '谋生'})
        m = TaskMeta.objects.get(task_name='写作')
        assert m.default_attribution == '谋生'
        assert RedemptionAttrRule.objects.filter(match_value='写作', is_active=True).count() == 1
        self._post({'task_names': ['写作'], 'activity_type': '深度工作'})
        assert TaskMeta.objects.get(task_name='写作').default_attribution is None

    def test_clear_rule_soft_deactivates_without_physical_delete(self):
        """清除覆盖：规则置 is_active=False（软停用，不物理删除），默认归因不动"""
        TaskMeta.objects.create(task_name='刷手机', activity_type='被动消耗', default_attribution='流失')
        rule = RedemptionAttrRule.objects.create(
            match_field='task_name', match_value='刷手机', attribution='谋生', priority=100, is_active=True)
        res = self._post({'task_names': ['刷手机'], 'activity_type': '被动消耗',
                          'keep_default': True, 'clear_rule': True})
        assert res['cleared'] == 1, res
        rule.refresh_from_db()
        assert rule.is_active is False                       # 软停用
        assert RedemptionAttrRule.objects.filter(pk=rule.pk).exists()  # 未物理删除
        assert TaskMeta.objects.get(task_name='刷手机').default_attribution == '流失'
        assert resolve_attribution(['刷手机'])['刷手机'] == '流失'        # 已回到类型默认

    def test_missing_required_fields_rejected(self):
        from rest_framework.test import APIClient
        r = APIClient().post(self.URL, {'task_names': ['写作']}, format='json')
        assert r.status_code == 400

    # ── 撤销覆盖 vs 非 task_name 维度规则（2026-09-18 修隐患）──
    # 台账的「撤销覆盖」只停用 `match_field='task_name'` 的规则。若该任务名的归因
    # 来自 L2/L3 维度规则（这类规则同时覆盖同维度下的**其他**任务名），撤销既无效、
    # 也不该由单行编辑顺手停掉 → 必须走响应 `blocked` 如实回报，不能报假成功。

    def test_clear_reports_blocked_when_l2_rule_still_covers(self):
        """只有 L2 规则时：cleared=0，且 blocked 说明是哪条规则还在生效"""
        TaskMeta.objects.create(task_name='刷手机', activity_type='被动消耗', default_attribution='成长')
        rule = RedemptionAttrRule.objects.create(
            match_field='activity_type', match_value='被动消耗', attribution='流失',
            priority=5, is_active=True)
        res = self._post({'task_names': ['刷手机'], 'activity_type': '被动消耗',
                          'keep_default': True, 'clear_rule': True})
        assert res['cleared'] == 0, res
        assert res['updated'] == 1, res
        b = res['blocked']
        assert len(b) == 1, res
        assert b[0]['task_name'] == '刷手机'
        assert b[0]['rule_field'] == 'activity_type' and b[0]['rule_value'] == '被动消耗'
        assert b[0]['attribution'] == '流失'
        rule.refresh_from_db()
        assert rule.is_active is True          # L2 规则不得被单行编辑波及（它覆盖多个任务名）

    def test_clear_task_name_rule_then_l2_takes_over(self):
        """同名规则撤掉后由 L2 规则接管 → cleared=1 且 blocked 非空（不能只报「已撤销」）"""
        TaskMeta.objects.create(task_name='刷手机', activity_type='被动消耗', default_attribution='成长')
        own = RedemptionAttrRule.objects.create(
            match_field='task_name', match_value='刷手机', attribution='维持',
            priority=100, is_active=True)
        RedemptionAttrRule.objects.create(
            match_field='activity_type', match_value='被动消耗', attribution='流失',
            priority=5, is_active=True)
        res = self._post({'task_names': ['刷手机'], 'activity_type': '被动消耗',
                          'keep_default': True, 'clear_rule': True})
        assert res['cleared'] == 1, res
        assert len(res['blocked']) == 1, res
        own.refresh_from_db()
        assert own.is_active is False                                  # 同名规则软停用
        assert res['blocked'][0]['rule_field'] == 'activity_type'      # 接手的是 L2 规则
        assert resolve_attribution(['刷手机'])['刷手机'] == '流失'

    def test_clear_returns_empty_blocked_when_truly_reverted(self):
        """只有同名规则时：撤销后确实回到类型默认 → blocked 为空"""
        TaskMeta.objects.create(task_name='休闲娱乐', activity_type='被动消耗', default_attribution='流失')
        RedemptionAttrRule.objects.create(
            match_field='task_name', match_value='休闲娱乐', attribution='成长',
            priority=100, is_active=True)
        res = self._post({'task_names': ['休闲娱乐'], 'activity_type': '被动消耗',
                          'keep_default': True, 'clear_rule': True})
        assert res['cleared'] == 1, res
        assert res['blocked'] == [], res
        assert resolve_attribution(['休闲娱乐'])['休闲娱乐'] == '流失'   # 回到 TaskMeta 默认


@pytest.mark.django_db
class TestLedgerCarriesRuleField:
    """台账每行须带 `rule_field`/`rule_value` —— 前端据此判断「撤销覆盖」能不能撤"""

    URL = '/api/temporal/tasks/meta_ledger/'

    def test_row_reports_rule_field_for_l2_rule(self):
        from rest_framework.test import APIClient
        TaskMeta.objects.create(task_name='刷手机', activity_type='被动消耗', default_attribution='成长')
        RedemptionAttrRule.objects.create(
            match_field='activity_type', match_value='被动消耗', attribution='流失',
            priority=5, is_active=True)
        items = APIClient().get(self.URL).data['items']
        row = {i['task_name']: i for i in items}['刷手机']
        assert row['attribution_source'] == 'rule'
        assert row['rule_field'] == 'activity_type' and row['rule_value'] == '被动消耗'
        assert row['rule_id'] is not None

    def test_row_rule_field_is_null_for_default_source(self):
        from rest_framework.test import APIClient
        TaskMeta.objects.create(task_name='写作', activity_type='深度工作', default_attribution='成长')
        items = APIClient().get(self.URL).data['items']
        row = {i['task_name']: i for i in items}['写作']
        assert row['attribution_source'] == 'default'
        assert row['rule_field'] is None and row['rule_value'] is None and row['rule_id'] is None


@pytest.mark.django_db
class TestDailyDetailEndTime:
    """当日明细补「结束时间」（v3.58.4）：贡献图点格子弹出的当日记录要能看到结束时刻

    一行 = 一个 task_name 的一天汇总，end_time = 当天最晚结束时刻。
    断言键恒定存在（缺失时返回 None 而非省略），前端据此走 `v-if` 占位分支。
    """

    URL = '/api/temporal/tasks/daily_detail/'

    @staticmethod
    def _get(day='2026-08-04'):
        from rest_framework.test import APIClient
        r = APIClient().get(TestDailyDetailEndTime.URL, {'date': day})
        assert r.status_code == 200, getattr(r, 'data', r.content)
        return {x['task_name']: x for x in r.data['items']}

    def test_end_time_returned(self):
        """有结束时刻 → 返回该时刻（按本地时区归一后比对时刻）"""
        from django.utils import timezone as dj_tz
        from django.utils.dateparse import parse_datetime
        TemporalTask.objects.create(
            task_name='写作', start_time=datetime.fromisoformat('2026-08-04 12:00:00'),
            end_time=datetime.fromisoformat('2026-08-04 14:30:00'),
            duration_hours=2.5, year=2026, mon='08', day=4,
        )
        row = self._get()['写作']
        end = parse_datetime(row['end_time'])
        assert end is not None, row
        if dj_tz.is_aware(end):
            end = dj_tz.localtime(end)
        assert (end.hour, end.minute) == (14, 30), row['end_time']

    def test_end_time_key_present_when_absent(self):
        """无结束时刻 → 键仍在、值为 None（不是省略键）"""
        TemporalTask.objects.create(
            task_name='无结束', start_time=datetime.fromisoformat('2026-08-04 12:00:00'),
            duration_hours=1, year=2026, mon='08', day=4,
        )
        row = self._get()['无结束']
        assert 'end_time' in row and row['end_time'] is None, row


@pytest.mark.django_db
class TestCsvImportPerRecord:
    """v3.58.5：CSV 导入按 ATracker 原始记录逐条落库（不再按「任务名 + 日期」合并）

    旧口径把同一天同名任务压成一行、时长累加、end_time 取当天最晚 → 导致
    「结束 − 开始 ≠ 时长」且 count 类指标偏小。新口径一条记录一行，
    去重键 = (task_name, start_time)。
    """

    URL = '/api/temporal/tasks/import_csv/'
    HEADER = '任务名称,开始时间,结束时间,持续时间（小时）\n'

    @classmethod
    def _post(cls, csv_content: str):
        from rest_framework.test import APIClient
        f = io.BytesIO(csv_content.encode('utf-8'))
        f.name = 't.csv'
        r = APIClient().post(cls.URL, {'file': f}, format='multipart')
        assert r.status_code == 201, getattr(r, 'data', r.content)
        return r.data

    def test_same_day_same_task_kept_as_two_rows(self):
        """同任务同日两条不同开始时刻 → 落 2 行；时长/结束时刻各归各（不累加、不取最晚）"""
        from django.utils import timezone
        d = self._post(
            self.HEADER
            + '代码编程,2026-08-10 09:00:00,2026-08-10 11:00:00,2.0\n'
            + '代码编程,2026-08-10 14:00:00,2026-08-10 15:30:00,1.5\n'
        )
        assert d['inserted'] == 2 and d['total_parsed'] == 2, d
        rows = list(TemporalTask.objects.filter(task_name='代码编程').order_by('start_time'))
        assert len(rows) == 2, rows
        assert [r.duration_hours for r in rows] == [2.0, 1.5]
        # 结束时刻各归各，不再是「当天最晚」
        ends = [(timezone.localtime(r.end_time).hour, timezone.localtime(r.end_time).minute) for r in rows]
        assert ends == [(11, 0), (15, 30)], ends
        # 展开后「时长 == 结束 − 开始」自然成立
        for r in rows:
            span = (r.end_time - r.start_time).total_seconds() / 3600
            assert abs(span - r.duration_hours) < 0.01, (r.start_time, r.end_time, r.duration_hours)

    def test_reimport_is_idempotent(self):
        """重复导入同一 CSV → 不新增不重复，全部走 skipped"""
        csv_content = self.HEADER + '代码编程,2026-08-10 09:00:00,2026-08-10 11:00:00,2.0\n' \
            + '代码编程,2026-08-10 14:00:00,2026-08-10 15:30:00,1.5\n'
        self._post(csv_content)
        d2 = self._post(csv_content)
        assert (d2['inserted'], d2['updated'], d2['skipped']) == (0, 0, 2), d2
        assert TemporalTask.objects.filter(task_name='代码编程').count() == 2

    def test_duration_change_updates_in_place(self):
        """同 (任务, 开始时刻) 时长变化 → 就地更新，行数不增"""
        self._post(self.HEADER + '代码编程,2026-08-10 09:00:00,2026-08-10 11:00:00,2.0\n')
        d = self._post(self.HEADER + '代码编程,2026-08-10 09:00:00,2026-08-10 11:00:00,3.5\n')
        assert (d['updated'], d['inserted']) == (1, 0), d
        rows = list(TemporalTask.objects.filter(task_name='代码编程'))
        assert len(rows) == 1 and rows[0].duration_hours == 3.5, rows

    def test_duplicate_lines_deduplicated_and_counted(self):
        """CSV 内完全重复行 → 去重并计数，只落 1 行（不静默丢弃）"""
        line = '代码编程,2026-08-10 09:00:00,2026-08-10 11:00:00,2.0\n'
        d = self._post(self.HEADER + line + line)
        assert (d['total_parsed'], d['deduplicated'], d['inserted']) == (2, 1, 1), d
        assert TemporalTask.objects.filter(task_name='代码编程').count() == 1

    def test_unclassified_task_still_registered(self):
        """新任务名仍自动建 TaskMeta（未命中预设 → 未归类桶）"""
        d = self._post(self.HEADER + '神秘任务,2026-08-10 09:00:00,2026-08-10 10:00:00,1.0\n')
        assert d['unclassified'] == 1, d
        m = TaskMeta.objects.get(task_name='神秘任务')
        assert m.activity_type == '未归类'

    def test_missing_end_time_leaves_null(self):
        """CSV 无结束时间列 → end_time 为 NULL（不臆造推算值）"""
        d = self._post('任务名称,开始时间,持续时间（小时）\n代码编程,2026-08-10 09:00:00,2.5\n')
        assert d['inserted'] == 1, d
        assert TemporalTask.objects.get(task_name='代码编程').end_time is None
