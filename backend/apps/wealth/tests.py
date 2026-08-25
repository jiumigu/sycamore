from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import FundSchedule
from .services.fund_schedule_service import FundScheduleService


class FundScheduleServiceTest(TestCase):
    """FundSchedule 服务：Decimal 合计精度 + 预留项校验"""

    def test_compute_totals_sum_and_precision(self) -> None:
        items = [{'amount': '3000.005'}, {'amount': '2000'}, {'amount': '0.1'}]
        total, remaining = FundScheduleService.compute_totals(10000, items)
        self.assertEqual(total, Decimal('5000.11'))
        self.assertEqual(remaining, Decimal('4999.89'))

    def test_compute_totals_negative_remaining_allowed(self) -> None:
        total, remaining = FundScheduleService.compute_totals(4000, [{'amount': '5000'}])
        self.assertEqual(total, Decimal('5000.00'))
        self.assertEqual(remaining, Decimal('-1000.00'))

    def test_validate_items_rejects_negative_amount(self) -> None:
        with self.assertRaises(ValidationError):
            FundScheduleService.validate_items([{'name': '房租', 'amount': -1, 'type': 'hard'}])

    def test_validate_items_rejects_empty_name(self) -> None:
        with self.assertRaises(ValidationError):
            FundScheduleService.validate_items([{'name': '  ', 'amount': 100, 'type': 'hard'}])

    def test_validate_items_rejects_invalid_type(self) -> None:
        with self.assertRaises(ValidationError):
            FundScheduleService.validate_items([{'name': '房租', 'amount': 100, 'type': 'bogus'}])

    def test_validate_items_cleans_fields(self) -> None:
        cleaned = FundScheduleService.validate_items([{'name': ' 房租 ', 'amount': '3000', 'type': 'hard', 'linked_expense_id': 7}])
        self.assertEqual(cleaned, [{'name': '房租', 'amount': 3000.0, 'type': 'hard', 'linked_expense_id': 7}])

    def test_create_schedule_persists_snapshot(self) -> None:
        plan = FundScheduleService.create_schedule(
            '8月计划', 100000, [{'name': '房租', 'amount': 3000, 'type': 'hard'}, {'name': '旅行', 'amount': 2000, 'type': 'soft'}]
        )
        self.assertEqual(FundSchedule.objects.count(), 1)
        self.assertEqual(plan.total_reserved, Decimal('5000.00'))
        self.assertEqual(plan.remaining, Decimal('95000.00'))
        self.assertEqual(plan.user_id, 1)
