"""时间重构 v0.3 测试：三层分类(L1归因/L2类型/L3 task_name) / 历史迁移 / 完整度 / 旭日 / 归因解析"""
import io

import pytest
from datetime import datetime

from apps.temporal.constants import ACTIVITY_TYPE_PRESETS, ATTRIBUTION_ORDER, TASK_TO_L2
from apps.temporal.models import TaskMeta, TemporalTask
from apps.temporal.services import resolve_attribution, resolve_task_meta


@pytest.mark.django_db
class TestResolveAttribution:
    def test_fallback_when_no_meta(self):
        """无 TaskMeta 时兜底=成长"""
        out = resolve_attribution(['某未知任务'])
        assert out['某未知任务'] == '成长'

    def test_meta_default_beats_fallback(self):
        """有 TaskMeta.default_attribution 就用它（归因只有这一处来源）"""
        TaskMeta.objects.create(task_name='写作', activity_type='深度工作', default_attribution='谋生')
        assert resolve_attribution(['写作'])['写作'] == '谋生'

    def test_empty_default_falls_back(self):
        """任务名在册但没设默认归因 ⇒ 兜底成长，而不是「跟着 L2 类型走」"""
        TaskMeta.objects.create(task_name='数独时间', activity_type='兴趣记录', default_attribution='')
        assert resolve_attribution(['数独时间'])['数独时间'] == '成长'

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

    def test_batch_set_meta_writes_only_meta(self):
        """改 L1 只写映射表那一列，不再产生一份影子规则（v3.64.16）"""
        from rest_framework.test import APIClient
        r = APIClient().post('/api/temporal/tasks/batch_set_meta/', {
            'task_names': ['写作'], 'activity_type': '深度工作', 'attribution': '成长',
        }, format='json')
        assert r.status_code == 200 and r.data['updated'] == 1
        meta = TaskMeta.objects.get(task_name='写作')
        assert meta.activity_type == '深度工作' and meta.default_attribution == '成长'
        assert resolve_attribution(['写作'])['写作'] == '成长'

    def test_attribution_without_activity_type_rejected(self):
        """归因脱离 activity_type 单发会被「只改开关」分支吃掉 ⇒ 直接 400 说清"""
        from rest_framework.test import APIClient
        TaskMeta.objects.create(task_name='写作', activity_type='深度工作', default_attribution='成长')
        r = APIClient().post('/api/temporal/tasks/batch_set_meta/', {
            'task_names': ['写作'], 'attribution': '谋生',
        }, format='json')
        assert r.status_code == 400
        assert TaskMeta.objects.get(task_name='写作').default_attribution == '成长'

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
        # ⚠️ v3.60.37 起「迷谷知松」的种子由「兴趣记录」订正为「深度工作」（与库中长期值对齐）
        assert TaskMeta.objects.get(task_name='迷谷知松').activity_type == '深度工作'

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
        # ⚠️ v3.60.36 又插了「体验」（同在「成长」之后）⇒ 排除**两个**后插的词再看原四词。
        assert [a for a in ATTRIBUTION_ORDER if a not in ('体验', '关系')] == ['成长', '维持', '谋生', '流失']

    def test_relation_wins_when_largest(self):
        """关系小时最多的那天，主导归因应着「关系」色，且进入 breakdown"""
        TaskMeta.objects.create(task_name='S', activity_type='社交', default_attribution='关系')
        TaskMeta.objects.create(task_name='B', activity_type='维护性事务', default_attribution='维持')
        self._mk('S', '2026-08-06', 3)
        self._mk('B', '2026-08-06', 1)
        d = self._get()['2026-08-06']
        assert d['attr'] == '关系'
        assert d['breakdown']['关系'] == 3

    def test_experience_slot_and_order_invariance(self):
        """v3.60.36 第六格「体验」：旅游类改挂体验，且**所有既有词的相对价值序**必须不变

        与 `test_relation_slot_and_order_invariance` 是同一判据的第二个样本：
        新词**只能纯增量地插**，插错位置会让历史数据「并列取谁」静默改变。
        """
        assert dict(ACTIVITY_TYPE_PRESETS)['主动经历'] == '体验'
        assert TASK_TO_L2['旅游观景'] == ('主动经历', '体验')
        # 「体验」必须紧挨在「成长」之后（本次的纯增量插入点）
        assert ATTRIBUTION_ORDER.index('体验') == ATTRIBUTION_ORDER.index('成长') + 1
        # 去掉两个后插的词，原四词次序原封不动
        assert [a for a in ATTRIBUTION_ORDER if a not in ('体验', '关系')] == ['成长', '维持', '谋生', '流失']
        # 词表 / 价值序 / 配色 三者键集必须一致 —— 漏配一个，界面会**静默**落灰色兜底
        from apps.temporal.constants import ATTRIBUTION_CHOICES_LIST, ATTRIBUTION_COLORS
        assert set(ATTRIBUTION_CHOICES_LIST) == set(ATTRIBUTION_ORDER) == set(ATTRIBUTION_COLORS)

    def test_experience_wins_when_largest(self):
        """体验小时最多的那天，主导归因应是「体验」，且进入 breakdown"""
        TaskMeta.objects.create(task_name='T', activity_type='主动经历', default_attribution='体验')
        TaskMeta.objects.create(task_name='B', activity_type='维护性事务', default_attribution='维持')
        self._mk('T', '2026-08-07', 5)
        self._mk('B', '2026-08-07', 1)
        d = self._get()['2026-08-07']
        assert d['attr'] == '体验'
        assert d['breakdown']['体验'] == 5

    def test_experience_beats_relation_on_tie(self):
        """并列时「体验」赢过「关系」—— 钉住插入位置的实际后果（成长 > 体验 > 关系）

        这条是「为什么必须想清楚插在哪」的可见证据：若把「体验」插到流失之后，
        同一天「旅游 + 社交」就会显示成「关系」色，而用户根本看不出为什么。
        """
        TaskMeta.objects.create(task_name='T', activity_type='主动经历', default_attribution='体验')
        TaskMeta.objects.create(task_name='S', activity_type='社交', default_attribution='关系')
        self._mk('T', '2026-08-08', 2)
        self._mk('S', '2026-08-08', 2)
        assert self._get()['2026-08-08']['attr'] == '体验'

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

    def test_attribution_source_two_ways(self):
        """有效归因来源只剩两档：default（映射表那列）> fallback（兜底）

        `rule`（赎回期外挂规则）那一档已随规则表退役：它只是 default 的影子副本，
        却只覆盖少数任务名，让赎回期页面的六类小时静默漏数。
        """
        self._seed()
        items = {i['task_name']: i for i in self._get()['items']}
        assert (items['写作']['effective_attribution'], items['写作']['attribution_source']) == ('成长', 'default')
        assert (items['刷手机']['effective_attribution'], items['刷手机']['attribution_source']) == ('流失', 'default')
        # 无默认归因 → 兜底成长
        assert (items['待定']['effective_attribution'], items['待定']['attribution_source']) == ('成长', 'fallback')
        # 规则相关的键已从响应中移除（不是置 None —— 留着恒为 None 的键等于第二套契约）
        assert 'rule_id' not in items['写作'] and 'rule_field' not in items['写作']

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

    def test_unset_attribution_is_its_own_state(self):
        """「没配 L1 归因」必须与「配好了」区分得开，并且能单独筛出来。

        回归 v3.64.28：从前只下发 `effective_attribution`，兜底行在映射编辑器里
        显示成选中的「成长」—— 与真配了「成长」的行长得一模一样。用户照着账本的
        「其中 X h 没设默认归因，去归好」点进来，看到那格已经填好，只能得出
        「明明都已经配置好了归因」的结论，然后无处可改。
        🔴 下拉要绑 `default_attribution`（表里真存的值），兜底值另立 `is_attr_unset`。
        """
        self._seed()
        items = {i['task_name']: i for i in self._get()['items']}
        assert items['写作']['is_attr_unset'] is False
        assert items['待定']['is_attr_unset'] is True
        # 兜底行的「原始配置」仍然是空 —— 这正是下拉该显示的样子
        assert items['待定']['default_attribution'] is None
        assert items['待定']['effective_attribution'] == '成长'

        sm = self._get()['summary']
        assert (sm['unset_attr_count'], sm['unset_attr_hours']) == (1, 5.0), sm
        # 与「未归类」是两个维度：这行恰好两边都占，但计数不能互相顶替
        assert (sm['unclassified'], sm['unclassified_hours']) == (1, 5.0), sm

        only = self._get('?unset_attr_only=1')['items']
        assert [i['task_name'] for i in only] == ['待定']

    def test_filters(self):
        self._seed()
        assert self._get('?unclassified_only=1')['returned'] == 1
        assert {i['task_name'] for i in self._get('?activity_type=深度工作')['items']} == {'写作'}
        assert {i['task_name'] for i in self._get('?attribution=流失')['items']} == {'刷手机'}
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
        # 🔴 逐键断言，不再整字典比对：每加一个口径小计都会让整字典比对变红，
        #    那种红不说明口径错、只说明「多了个键」，几次之后就会有人顺手改成
        #    `>=` 放水 —— 那时真的缺键也发现不了。
        s = d['summary']
        zero_keys = {
            'total', 'classified', 'unclassified', 'total_hours', 'unclassified_hours',
            'growth_count', 'growth_hours', 'role_count',
        }
        assert zero_keys <= set(s), f'空库概要在这些键上缺失：{zero_keys - set(s)}'
        for k in zero_keys:
            assert s[k] == 0, f'空库 {k} 应为 0，实际 {s[k]!r}'
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

    def test_keep_default_preserves_attribution(self):
        """改 L2 类型时保留原默认归因"""
        TaskMeta.objects.create(task_name='写作', activity_type='深度工作', default_attribution='成长')
        self._post({'task_names': ['写作'], 'activity_type': '兴趣记录', 'keep_default': True})
        m = TaskMeta.objects.get(task_name='写作')
        assert m.activity_type == '兴趣记录'
        assert m.default_attribution == '成长'          # 未被清空

    def test_legacy_behavior_unchanged_without_keep_default(self):
        """不传 keep_default → 旧语义：default_attribution 跟随 attribution（含置空）"""
        TaskMeta.objects.create(task_name='写作', activity_type='深度工作', default_attribution='成长')
        self._post({'task_names': ['写作'], 'activity_type': '深度工作', 'attribution': '谋生'})
        assert TaskMeta.objects.get(task_name='写作').default_attribution == '谋生'
        self._post({'task_names': ['写作'], 'activity_type': '深度工作'})
        assert TaskMeta.objects.get(task_name='写作').default_attribution is None

    def test_missing_required_fields_rejected(self):
        from rest_framework.test import APIClient
        r = APIClient().post(self.URL, {'task_names': ['写作']}, format='json')
        assert r.status_code == 400

    def test_attribution_requires_activity_type(self):
        """归因脱离 activity_type 单发 → 400

        旧实现会走进「只改开关」分支、把 attribution 丢掉：接口 200、值没变。
        """
        from rest_framework.test import APIClient
        TaskMeta.objects.create(task_name='写作', activity_type='深度工作', default_attribution='成长')
        r = APIClient().post(self.URL, {'task_names': ['写作'], 'attribution': '谋生'}, format='json')
        assert r.status_code == 400
        assert TaskMeta.objects.get(task_name='写作').default_attribution == '成长'

    def test_counts_growth_toggle_does_not_touch_attribution(self):
        """只发成长计时开关：归因不动（`None ≠ False` 的反面同样要命）"""
        TaskMeta.objects.create(task_name='写作', activity_type='深度工作',
                                default_attribution='成长', counts_growth=False)
        self._post({'task_names': ['写作'], 'counts_growth': True})
        m = TaskMeta.objects.get(task_name='写作')
        assert m.counts_growth is True
        assert m.default_attribution == '成长' and m.activity_type == '深度工作'


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
    「结束 − 开始 ≠ 时长」且 count 类指标偏小。新口径一条记录一行。

    判重（v3.60.29 起）= **同任务名 + 时段重叠**（单一真源 `services.find_duplicate_task`），
    不再是 `(task_name, start_time)` 精确相等 —— 后者会被规则 A 改写 start_time 打穿。
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
