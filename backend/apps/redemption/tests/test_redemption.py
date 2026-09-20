"""三年赎回期 · 判定层测试：配置/暂停/池余额/覆盖率/同步推演/归因优先级"""
import pytest
from datetime import date, datetime, timedelta

from apps.redemption import services
from apps.redemption.models import (
    RedemptionPeriod, RedemptionPoolInject, RedemptionAttrRule,
)
from apps.wealth.models import WealthBillList
from apps.temporal.models import TemporalTask


@pytest.mark.django_db
class TestRedemptionCore:
    def _ensure_period(self):
        return services.get_or_create_period()

    def test_config_edit_recalculates(self):
        from rest_framework.test import APIClient
        c = APIClient()
        r = c.get('/api/redemption/')
        assert r.status_code == 200
        assert r.data['start_date'] == '2026-10-01'
        # 改起止后配置可写、旧 period_tag 不动（这里只验证可写与派生存在）
        r = c.put('/api/redemption/', {'start_date': '2026-11-01', 'end_date': '2029-10-31',
                                       'pool_principal': 120000}, format='json')
        assert r.status_code == 200
        assert r.data['pool_principal'] == '120000.00'
        # 还原，避免影响后续用例
        c.put('/api/redemption/', {'start_date': '2026-10-01', 'end_date': '2029-09-30',
                                   'pool_principal': 100000}, format='json')

    def test_pause_resume_statemachine(self):
        from rest_framework.test import APIClient
        c = APIClient()
        r = c.post('/api/redemption/pause/')
        assert r.status_code == 200
        assert r.data['tracking_status'] == 'paused'
        resume_at = datetime.fromisoformat(r.data['resume_at']).date()
        assert resume_at == date.today() + timedelta(days=14)

        r = c.post('/api/redemption/resume/')
        assert r.status_code == 200
        assert r.data['tracking_status'] == 'active'

    def test_pool_balance_with_inject(self):
        p = self._ensure_period()
        now = datetime.now()
        WealthBillList.objects.create(
            transaction_type='支出', date=datetime(2026, 10, 5, 10, 0), amount=3000,
            category='餐饮', user_id=1, created_at=now, updated_at=now, period_tag='为自己',
        )
        RedemptionPoolInject.objects.create(
            inject_date=date(2026, 10, 2), amount=5000, source='赔偿',
        )
        stats = services.compute_redemption_stats(p, include_time=False)
        # 余额 = 本金 100000 + 注入 5000 - 为自己支出 3000 + 收入 0 = 102000
        assert stats['pool']['balance'] == 102000.0
        assert stats['pool']['injected'] == 5000.0

    def test_config_stats_success(self):
        from rest_framework.test import APIClient
        c = APIClient()
        r = c.get('/api/redemption/stats/')
        assert r.status_code == 200
        assert 'window' in r.data and 'pool' in r.data and 'tier' in r.data

    def test_coverage_warn_low(self):
        """无时间记录时覆盖率 0 < 阈值，触发 warn 提示"""
        p = self._ensure_period()
        stats = services.compute_redemption_stats(p, include_time=True)
        # 当前日期早于窗口起点，elapsed=0 → 覆盖率 0、warn=True
        assert stats['time'] is not None
        assert stats['time']['coverage_warn'] is True
        assert stats['time']['coverage_rate'] == 0.0

    def test_sync_scenario_preview_no_write(self):
        from rest_framework.test import APIClient
        from apps.wealth.models import WealthCurrentScenario
        c = APIClient()
        # 先确保 periods 与推演存在
        self._ensure_period()
        scenario, _ = WealthCurrentScenario.objects.get_or_create(
            pk=1, defaults={
                'current_age': 30, 'current_week': 1,
                'current_cash': 50000, 'daily_budget': 100,
            },
        )
        old_cash = scenario.current_cash
        r = c.post('/api/redemption/sync-scenario/', {'mode': 'preview'}, format='json')
        assert r.status_code == 200
        assert r.data['mode'] == 'preview'
        assert r.data['scenario_exists'] is True
        scenario.refresh_from_db()
        # preview 不应改写 current_cash
        assert scenario.current_cash == old_cash

    def test_attr_rule_priority(self):
        """同一匹配值两条规则，取高优先级归因"""
        p = self._ensure_period()
        now = datetime.now()
        # 两个规则：低优先级 谋生 / 高优先级 成长
        RedemptionAttrRule.objects.create(
            match_field='task_type', match_value='阅读思考', attribution='谋生', priority=0,
        )
        RedemptionAttrRule.objects.create(
            match_field='task_type', match_value='阅读思考', attribution='成长', priority=10,
        )
        TemporalTask.objects.create(
            task_name='读书', task_type='阅读思考', start_time=datetime(2026, 10, 5, 9, 0),
            end_time=datetime(2026, 10, 5, 10, 0), duration_hours=1.0,
            year=2026, mon='2026-10', day=5, week=40,
        )
        attr = services.compute_time_attribution(p)
        assert attr['hours']['成长'] == 1.0
        assert attr['hours']['谋生'] == 0.0

    def test_attr_rule_activity_type(self):
        """`activity_type` 规则须在**两侧**同时生效（回归：曾只在 temporal 侧生效、redemption 侧静默跳过）

        背景：redemption 侧原用 `getattr(task, rule.match_field)` 匹配，而 `activity_type`
        不在 ATracker 外部表（它住在 `temporal_task_meta`）→ 取到 None 被静默跳过，
        症状是同一条规则「时间统计页算了、赎回期页面没算」。修复后两侧共用
        `redemption.services.match_attribution_rule`，本用例同时钉住这两个面。
        """
        from apps.temporal.models import TaskMeta
        from apps.temporal.services import resolve_attribution

        p = self._ensure_period()
        RedemptionAttrRule.objects.create(
            match_field='activity_type', match_value='被动消耗',
            attribution='流失', priority=5,
        )
        TaskMeta.objects.create(
            task_name='刷手机', activity_type='被动消耗', default_attribution='成长',
        )
        TemporalTask.objects.create(
            task_name='刷手机', task_type='刷手机', start_time=datetime(2026, 10, 5, 9, 0),
            end_time=datetime(2026, 10, 5, 10, 0), duration_hours=1.5,
            year=2026, mon='2026-10', day=5, week=40,
        )

        # ① redemption 侧（赎回期覆盖率）：规则须命中，且计入 covered
        attr = services.compute_time_attribution(p)
        assert attr['hours']['流失'] == 1.5
        assert attr['covered_hours'] == 1.5

        # ② temporal 侧（时间统计）：同一条规则须给出同一归因 —— 两侧不得漂移
        assert resolve_attribution(['刷手机'])['刷手机'] == '流失'

    def test_activity_type_rule_does_not_leak(self):
        """规则只覆盖它声明的活动类型；未命中的任务回落到 TaskMeta 默认归因"""
        from apps.temporal.models import TaskMeta
        from apps.temporal.services import resolve_attribution

        self._ensure_period()
        RedemptionAttrRule.objects.create(
            match_field='activity_type', match_value='被动消耗',
            attribution='流失', priority=5,
        )
        TaskMeta.objects.create(
            task_name='写作', activity_type='深度工作', default_attribution='成长',
        )
        TaskMeta.objects.create(
            task_name='刷手机', activity_type='被动消耗', default_attribution='成长',
        )
        got = resolve_attribution(['写作', '刷手机'])
        assert got['写作'] == '成长'      # 未被规则覆盖 → 用 TaskMeta 默认
        assert got['刷手机'] == '流失'    # 被 activity_type 规则覆盖


@pytest.mark.django_db
class TestListApisReturnBareArray:
    """规则 / 注入列表接口必须返回**裸数组**

    回归（2026-09-18 发现）：全局 `StandardPagination` 会把列表包成
    `{count, next, previous, results}`，而前端（`AttrRuleEditor.vue` 的 `rules.length`、
    API 层的 `request<AttrRule[]>`）一律按裸数组取用 → 页面把对象当数组，
    `length` 得到 undefined，表现为「现有规则 ()」+ 空表格：
    **库里 3 条真实规则被显示成 0 条**。这里从响应类型上钉死，
    避免哪天分页配置回退时重现（当时没有任何用例覆盖这两个接口，所以一直没暴露）。
    """

    @staticmethod
    def _get(url):
        from rest_framework.test import APIClient
        return APIClient().get(url)

    def test_attr_rules_returns_bare_array(self):
        RedemptionAttrRule.objects.create(
            match_field='task_name', match_value='休闲娱乐', attribution='成长',
            priority=100, note='时间重构批量设置')
        r = self._get('/api/redemption/attr-rules/')
        assert r.status_code == 200
        assert isinstance(r.data, list), f'须为裸数组，实际 {type(r.data).__name__}'
        assert len(r.data) == 1
        assert r.data[0]['match_value'] == '休闲娱乐' and r.data[0]['priority'] == 100

    def test_attr_rules_empty_returns_empty_array(self):
        """空库 → `[]`，而不是 `{count: 0, results: []}`"""
        assert self._get('/api/redemption/attr-rules/').data == []

    def test_injects_returns_bare_array(self):
        RedemptionPoolInject.objects.create(inject_date=date(2026, 10, 1), amount=10000)
        r = self._get('/api/redemption/injects/')
        assert r.status_code == 200
        assert isinstance(r.data, list), f'须为裸数组，实际 {type(r.data).__name__}'
        assert len(r.data) == 1


@pytest.mark.django_db
class TestAttributionDetailCarriesRuleField:
    """`resolve_attribution_detail` 必须报出「命中哪一条规则」

    用途：台账据此判断「撤销覆盖」能不能撤。只有 `task_name` 维度的规则能按行撤销；
    命中 `activity_type`（L2）规则时该规则同时覆盖同类型的其他任务名，
    单行撤销会连坐 —— 前端要据此拦截并指路，而不是发请求后报一个假成功。
    """

    def test_activity_type_rule_reports_its_field(self):
        from apps.temporal.models import TaskMeta
        from apps.temporal.services import resolve_attribution_detail

        RedemptionAttrRule.objects.create(
            match_field='activity_type', match_value='被动消耗', attribution='流失', priority=5)
        TaskMeta.objects.create(task_name='刷手机', activity_type='被动消耗', default_attribution='成长')
        d = resolve_attribution_detail(['刷手机'])['刷手机']
        assert d['source'] == 'rule'
        assert d['rule_field'] == 'activity_type'
        assert d['rule_value'] == '被动消耗'
        assert d['rule_id'] is not None

    def test_task_name_rule_reports_task_name_field(self):
        from apps.temporal.models import TaskMeta
        from apps.temporal.services import resolve_attribution_detail

        RedemptionAttrRule.objects.create(
            match_field='task_name', match_value='休闲娱乐', attribution='成长', priority=100)
        TaskMeta.objects.create(task_name='休闲娱乐', activity_type='被动消耗', default_attribution='流失')
        d = resolve_attribution_detail(['休闲娱乐'])['休闲娱乐']
        assert d['source'] == 'rule' and d['rule_field'] == 'task_name'

    def test_non_rule_sources_keep_null_rule_keys(self):
        """非 rule 来源：三个 rule_* 键**恒定存在**且为 None（前端不必做存在性判断）"""
        from apps.temporal.models import TaskMeta
        from apps.temporal.services import resolve_attribution_detail

        TaskMeta.objects.create(task_name='写作', activity_type='深度工作', default_attribution='成长')
        d = resolve_attribution_detail(['写作'])['写作']
        assert d['source'] == 'default'
        assert d['rule_id'] is None and d['rule_field'] is None and d['rule_value'] is None
