"""资金排程分配计划服务"""
from datetime import datetime, timedelta
from decimal import Decimal

from django.db import connection, transaction
from django.utils import timezone

from ..models.allocation_plan import (
    AllocationCategory,
    AllocationPlan,
    AllocationItem,
    Commitment,
    DecisionLog,
)


class AllocationService:
    """分配计划服务：分配是计划（预留），不是记录（花费）"""

    @staticmethod
    def get_or_create_plan(year_month: str) -> AllocationPlan:
        """获取或创建月度计划"""
        plan, _created = AllocationPlan.objects.get_or_create(
            year_month=year_month,
            defaults={'status': 'draft'},
        )
        return plan

    @staticmethod
    def calculate_commitments(year_month: str) -> list:
        """从财富账单自动计算硬性承诺（未来 60 天内的支出）"""
        year, month = map(int, year_month.split('-'))
        start_date = datetime(year, month, 1).date()
        end_date = start_date + timedelta(days=60)
        today = timezone.now().date()

        # wealth_bill_list 为原始 SQL 表，无 ORM 模型，用原生查询
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, category, notes, amount, date
                FROM wealth_bill_list
                WHERE transaction_type = '支出'
                  AND date >= %s AND date <= %s
                  AND user_id = %s
                ORDER BY date
            """, [start_date, end_date, 1])
            rows = cursor.fetchall()

        commitments = []
        for row in rows:
            bill_id, category, notes, amount, bill_date = row
            commitments.append({
                'id': bill_id,
                'name': f"{category or '支出'} - {notes or '支出'}",
                'amount': float(abs(amount or 0)),
                'due_date': bill_date.isoformat(),
                'status': 'urgent' if bill_date <= today else 'pending',
                'source': 'bill',
            })
        return commitments

    @staticmethod
    @transaction.atomic
    def create_plan(year_month: str, total_cash: float, allocations: list, commitments: list) -> AllocationPlan:
        """
        创建/更新分配计划（幂等，可反复保存）。
        allocations: [{'category_id': 1, 'amount': 5000}, ...]
        commitments: [{'name': '房租', 'amount': 3000, 'due_date': '2026-09-01'}, ...]
        """
        plan = AllocationService.get_or_create_plan(year_month)
        plan.total_cash = Decimal(str(total_cash or 0))
        plan.status = 'active'

        # 硬性承诺：无稳定客户端 id，先清空再重建
        plan.commitments.all().delete()
        commitments_total = Decimal('0')
        for c in commitments:
            Commitment.objects.create(
                plan=plan,
                name=c['name'],
                amount=c['amount'],
                due_date=c['due_date'],
                source=c.get('source', 'manual'),
                note=c.get('note', ''),
            )
            commitments_total += Decimal(str(c['amount']))
        plan.commitments_total = commitments_total

        # 分配项：按 (plan, category) upsert，保留已花费记录
        sent_cat_ids = []
        allocated_total = Decimal('0')
        for a in allocations:
            category = AllocationCategory.objects.get(id=a['category_id'])
            amount = Decimal(str(a['amount']))
            AllocationItem.objects.update_or_create(
                plan=plan,
                category=category,
                defaults={'planned_amount': amount, 'note': a.get('note', '')},
            )
            allocated_total += amount
            sent_cat_ids.append(category.id)
        # 移除本次未发送的类别项
        plan.items.exclude(category_id__in=sent_cat_ids).delete()
        plan.allocated_total = allocated_total

        plan.free_cash = plan.total_cash - plan.commitments_total - plan.allocated_total
        plan.save()
        return plan

    @staticmethod
    def get_plan_detail(year_month: str) -> dict:
        """获取计划详情（未创建的类别以默认金额占位，保证看板始终完整渲染）"""
        plan = AllocationService.get_or_create_plan(year_month)

        item_map = {item.category_id: item for item in plan.items.select_related('category')}
        categories = list(AllocationCategory.objects.filter(is_active=True))

        items = []
        for cat in categories:
            item = item_map.get(cat.id)
            items.append({
                'id': item.id if item else None,
                'category_id': cat.id,
                'category_name': cat.name,
                'category_icon': cat.icon,
                'category_color': cat.color,
                'planned_amount': float(item.planned_amount) if item else float(cat.default_amount),
                'spent_amount': float(item.spent_amount) if item else 0.0,
                'remaining_amount': float(item.remaining_amount) if item else float(cat.default_amount),
                'note': item.note if item else '',
            })

        commitments = [
            {
                'id': c.id,
                'name': c.name,
                'amount': float(c.amount),
                'due_date': c.due_date.isoformat(),
                'status': c.status,
                'source': c.source,
                'note': c.note,
            }
            for c in plan.commitments.all()
        ]

        decisions = [
            {
                'id': d.id,
                'content': d.content,
                'category': d.category,
                'created_at': d.created_at.isoformat(),
            }
            for d in DecisionLog.objects.filter(plan=plan)
        ]

        available_categories = [
            {
                'id': c.id,
                'name': c.name,
                'icon': c.icon,
                'color': c.color,
                'priority': c.priority,
                'default_amount': float(c.default_amount),
            }
            for c in categories
        ]

        return {
            'id': plan.id,
            'year_month': plan.year_month,
            'total_cash': float(plan.total_cash),
            'commitments_total': float(plan.commitments_total),
            'allocated_total': float(plan.allocated_total),
            'free_cash': float(plan.free_cash),
            'status': plan.status,
            'items': items,
            'commitments': commitments,
            'decisions': decisions,
            'available_categories': available_categories,
        }

    @staticmethod
    @transaction.atomic
    def update_allocation(plan_id: int, allocations: list) -> AllocationPlan:
        """更新分配计划（增量调整）"""
        plan = AllocationPlan.objects.get(id=plan_id)

        allocated_total = Decimal('0')
        for a in allocations:
            item_id = a.get('id')
            amount = Decimal(str(a['amount']))

            if item_id:
                item = AllocationItem.objects.get(id=item_id, plan=plan)
                item.planned_amount = amount
                item.note = a.get('note', '')
                item.save()
            else:
                category = AllocationCategory.objects.get(id=a['category_id'])
                AllocationItem.objects.create(
                    plan=plan,
                    category=category,
                    planned_amount=amount,
                    note=a.get('note', ''),
                )
            allocated_total += amount

        plan.allocated_total = allocated_total
        plan.free_cash = plan.total_cash - plan.commitments_total - plan.allocated_total
        plan.save()
        return plan

    @staticmethod
    @transaction.atomic
    def record_spending(plan_id: int, category_id: int, amount: float, note: str = '') -> AllocationItem:
        """记录某分类的实际花费（从预留额度中扣减）"""
        plan = AllocationPlan.objects.get(id=plan_id)
        item = AllocationItem.objects.get(plan=plan, category_id=category_id)
        item.spent_amount += Decimal(str(amount))
        if note:
            item.note = note
        item.save()
        return item

    @staticmethod
    def save_decision(plan_id: int, content: str, category: str = '') -> DecisionLog:
        """保存自由决策"""
        plan = AllocationPlan.objects.get(id=plan_id)
        return DecisionLog.objects.create(
            plan=plan,
            content=content,
            category=category,
        )
