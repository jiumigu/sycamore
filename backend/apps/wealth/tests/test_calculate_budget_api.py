"""现金流反算端点 /api/wealth/calculate_budget/

对应 views.CalculateBudgetView —— 给定本金与目标天数，求每日可提取额。

🔴 本文件最重要的一条是 test_does_not_write_any_table：
反算由前端「输入即算」高频触发，**必须零写库**。若哪天有人顺手在里面
复用正算的落库逻辑（写 WealthCurrentScenario / WealthScenarioHistory），
那条断言会立刻失败 —— 这是刻意设置的护栏，不要为了让测试通过而删掉它。
"""
import pytest
from rest_framework.test import APIClient

from apps.wealth.models import WealthCurrentScenario, WealthScenarioHistory

URL = '/api/wealth/calculate_budget/'


def _post(payload: dict):
    return APIClient().post(URL, payload, format='json')


@pytest.mark.django_db
class TestCalculateBudgetApi:
    def test_plain_division_without_interest(self):
        """无利息：每日可提取额 = 本金 ÷ 天数"""
        r = _post({'current_cash': 100000, 'target_days': 365, 'daily_interest_rate': 0})
        assert r.status_code == 200
        assert r.data['daily_budget'] == pytest.approx(100000 / 365, abs=0.01)
        assert r.data['target_days'] == 365
        assert r.data['current_cash'] == 100000.0

    def test_interest_increases_budget(self):
        """有日利息：利息补贴使日均可花高于纯均摊"""
        plain = _post({'current_cash': 100000, 'target_days': 3650}).data['daily_budget']
        with_interest = _post({
            'current_cash': 100000, 'target_days': 3650, 'daily_interest_rate': 0.00015,
        }).data['daily_budget']
        assert with_interest > plain

    def test_fractional_days_accepted(self):
        """天数带小数（前端按「年 / 月」换算后会是小数值，如 10.5 年 = 3835.44 天）"""
        r = _post({'current_cash': 100000, 'target_days': 3835.44})
        assert r.status_code == 200
        assert r.data['daily_budget'] > 0

    def test_zero_cash_yields_zero(self):
        """本金为 0 → 0（前端据此显示空态，不报错）"""
        r = _post({'current_cash': 0, 'target_days': 365})
        assert r.status_code == 200
        assert r.data['daily_budget'] == 0

    def test_invalid_days_rejected(self):
        """天数非法（0 / 负 / 缺省）→ 400，不落任何计算"""
        assert _post({'current_cash': 100000, 'target_days': 0}).status_code == 400
        assert _post({'current_cash': 100000, 'target_days': -1}).status_code == 400
        assert _post({'current_cash': 100000}).status_code == 400

    def test_does_not_write_any_table(self):
        """🔴 护栏：反算是纯试算，不得写 strategy 两张表

        对比正算 CalculateCoverageView（会写 WealthCurrentScenario + 
        WealthScenarioHistory）。反算被高频调用，一旦开始落库会把历史表灌满
        无意义的中间态记录。
        """
        before_scenario = WealthCurrentScenario.objects.count()
        before_history = WealthScenarioHistory.objects.count()

        for _ in range(5):
            assert _post({
                'current_cash': 100000, 'target_days': 3650,
                'daily_interest_rate': 0.00015,
            }).status_code == 200

        assert WealthCurrentScenario.objects.count() == before_scenario
        assert WealthScenarioHistory.objects.count() == before_history

    def test_matches_service_function(self):
        """端点结果与纯函数一致（口径只有一处实现）"""
        from apps.wealth.services.coverage_calculator import calculate_daily_budget

        r = _post({'current_cash': 250000, 'target_days': 7305.6, 'daily_interest_rate': 0.00015})
        expected = round(calculate_daily_budget(250000, 7305.6, 0.00015), 2)
        assert r.data['daily_budget'] == expected
