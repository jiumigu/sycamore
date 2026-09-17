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
        # 两个规则：低优先级 外部 / 高优先级 投向
        RedemptionAttrRule.objects.create(
            match_field='task_type', match_value='阅读思考', attribution='外部', priority=0,
        )
        RedemptionAttrRule.objects.create(
            match_field='task_type', match_value='阅读思考', attribution='投向', priority=10,
        )
        TemporalTask.objects.create(
            task_name='读书', task_type='阅读思考', start_time=datetime(2026, 10, 5, 9, 0),
            end_time=datetime(2026, 10, 5, 10, 0), duration_hours=1.0,
            year=2026, mon='2026-10', day=5, week=40,
        )
        attr = services.compute_time_attribution(p)
        assert attr['hours']['投向'] == 1.0
        assert attr['hours']['外部'] == 0.0
