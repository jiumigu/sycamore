"""资金排程计划服务"""
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError

from ..models import FundSchedule

ITEM_TYPES = {'hard', 'soft'}


class FundScheduleService:
    """资金排程：快照式保存，服务端计算预留合计与剩余可分配"""

    @staticmethod
    def compute_totals(cash_on_hand: float | Decimal, reserve_items: list[dict]) -> tuple[Decimal, Decimal]:
        """服务端权威计算：预留合计 = Σamount；剩余 = 现金 - 预留合计（Decimal，避免浮点漂移）"""
        total = Decimal('0')
        for item in reserve_items or []:
            total += Decimal(str(item.get('amount') or 0))
        # ROUND_HALF_UP 与前端 Math.round(x*100)/100 一致，避免展示合计与后端权威合计不一致
        total_reserved = total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        cash = Decimal(str(cash_on_hand or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        remaining = (cash - total_reserved).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return total_reserved, remaining

    @staticmethod
    def validate_items(reserve_items: list[dict] | None) -> list[dict]:
        """校验预留项目并返回清洗后的列表"""
        cleaned: list[dict] = []
        for item in reserve_items or []:
            if not isinstance(item, dict):
                raise ValidationError('预留项目必须为对象 {name, amount, type}')
            name = str(item.get('name') or '').strip()
            if not name:
                raise ValidationError('预留项目名称不能为空')
            item_type = item.get('type', 'hard')
            if item_type not in ITEM_TYPES:
                raise ValidationError('预留类型只能是 hard 或 soft')
            try:
                amount = Decimal(str(item.get('amount') or 0))
            except Exception:
                raise ValidationError('预留金额格式错误')
            if amount < 0:
                raise ValidationError('预留金额不能为负数')
            cleaned.append({
                'name': name,
                'amount': float(amount),
                'type': item_type,
                'linked_expense_id': item.get('linked_expense_id'),
            })
        return cleaned

    @staticmethod
    def create_schedule(
        plan_name: str,
        cash_on_hand: float | Decimal,
        reserve_items: list[dict] | None,
        user_id: int = 1,
    ) -> FundSchedule:
        """创建资金排程快照（校验 + 计算合计 + 落库）"""
        cleaned = FundScheduleService.validate_items(reserve_items)
        total_reserved, remaining = FundScheduleService.compute_totals(cash_on_hand, cleaned)
        return FundSchedule.objects.create(
            user_id=user_id,
            plan_name=plan_name,
            cash_on_hand=Decimal(str(cash_on_hand or 0)).quantize(Decimal('0.01')),
            reserve_items=cleaned,
            total_reserved=total_reserved,
            remaining=remaining,
        )
