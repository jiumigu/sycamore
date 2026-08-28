"""资金排程 reserve_items 拆分子表：创建写子表 / 读取从子表 / 校验"""
import pytest
from decimal import Decimal

from apps.wealth.models import FundSchedule, FundScheduleItem
from apps.wealth.services.fund_schedule_service import FundScheduleService


@pytest.mark.django_db
class TestFundScheduleItems:
    def test_create_schedule_writes_subtable(self):
        items = [
            {'name': '房租', 'amount': 2500, 'type': 'hard'},
            {'name': '生活费', 'amount': 1500, 'type': 'soft'},
        ]
        s = FundScheduleService.create_schedule('测试计划', 5000, items)
        assert FundScheduleItem.objects.filter(schedule=s).count() == 2
        sub = list(s.items.order_by('sort_order'))
        assert sub[0].name == '房租' and float(sub[0].amount) == 2500
        assert sub[1].item_type == 'soft'
        assert s.total_reserved == Decimal('4000.00')
        assert s.remaining == Decimal('1000.00')

    def test_serializer_reads_from_subtable(self):
        from rest_framework.test import APIClient
        items = [{'name': '测试项', 'amount': 88, 'type': 'hard'}]
        FundScheduleService.create_schedule('读子表计划', 100, items)
        c = APIClient()
        r = c.get('/api/wealth/fund-schedule/')
        rows = r.data['results'] if isinstance(r.data, dict) else r.data
        latest = next(x for x in rows if x['plan_name'] == '读子表计划')
        assert latest['reserve_items'][0]['name'] == '测试项'
        assert latest['reserve_items'][0]['amount'] == 88.0
        assert latest['total_reserved'] == '88.00'

    def test_validate_items_rejects_bad_input(self):
        from django.core.exceptions import ValidationError
        with pytest.raises(ValidationError):
            FundScheduleService.validate_items([{'name': '', 'amount': 1, 'type': 'hard'}])
        with pytest.raises(ValidationError):
            FundScheduleService.validate_items([{'name': 'x', 'amount': -1, 'type': 'hard'}])
        with pytest.raises(ValidationError):
            FundScheduleService.validate_items([{'name': 'x', 'amount': 1, 'type': 'illegal'}])

    def test_schedule_items_cascade_delete(self):
        s = FundScheduleService.create_schedule('级联计划', 100, [{'name': '项', 'amount': 10, 'type': 'hard'}])
        sid = s.id
        s.delete()
        assert FundScheduleItem.objects.filter(schedule_id=sid).count() == 0
