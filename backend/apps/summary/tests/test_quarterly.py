"""summary 季度报告/聚合服务：services 拆包后跨类引用回归"""
import pytest

from apps.summary.services import BodyMindCorrelationService, ProgressAggregator, QuarterlyWorkbenchService


@pytest.mark.django_db
class TestSummaryServices:
    def test_quarterly_report_endpoint(self):
        """回归：拆分后 quarterly_workbench 引用 ProgressAggregator（曾 NameError → 500）"""
        from rest_framework.test import APIClient
        c = APIClient()
        r = c.get('/api/summary/quarterly_report/?year=2026&quarter=3')
        assert r.status_code == 200
        assert isinstance(r.data, dict)

    def test_quarterly_insights_endpoint(self):
        from rest_framework.test import APIClient
        c = APIClient()
        assert c.get('/api/summary/quarterly_insights/?year=2026&quarter=3').status_code == 200

    def test_quarterly_questions_answers_endpoints(self):
        from rest_framework.test import APIClient
        c = APIClient()
        assert c.get('/api/summary/quarterly_questions/?year=2026&quarter=3').status_code == 200
        assert c.get('/api/summary/quarterly_answers/?year=2026&quarter=3').status_code == 200

    def test_progress_aggregator_importable(self):
        assert callable(ProgressAggregator._get_raw_value)

    def test_body_mind_correlation_importable(self):
        assert callable(BodyMindCorrelationService)

    def test_quarterly_workbench_importable(self):
        assert callable(QuarterlyWorkbenchService)
