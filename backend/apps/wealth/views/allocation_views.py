"""资金排程分配计划 API"""
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from ..services.allocation_service import AllocationService


class AllocationViewSet(viewsets.GenericViewSet):
    """分配计划视图：手头现金 → 硬性承诺 → 预留分配 → 自由支配"""

    @action(detail=False, methods=['GET'], url_path='detail')
    def get_detail(self, request):
        """获取计划详情"""
        year_month = request.query_params.get('year_month') or timezone.now().strftime('%Y-%m')
        data = AllocationService.get_plan_detail(year_month)
        return Response(data)

    @action(detail=False, methods=['POST'], url_path='create')
    def create_plan(self, request):
        """创建/更新分配计划（幂等）"""
        year_month = request.data.get('year_month') or timezone.now().strftime('%Y-%m')
        total_cash = request.data.get('total_cash', 0)
        allocations = request.data.get('allocations', [])
        commitments = request.data.get('commitments', [])

        try:
            plan = AllocationService.create_plan(
                year_month=year_month,
                total_cash=total_cash,
                allocations=allocations,
                commitments=commitments,
            )
            return Response({
                'success': True,
                'plan_id': plan.id,
                'year_month': plan.year_month,
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['POST'], url_path='update-allocations')
    def update_allocations(self, request):
        """更新分配项"""
        plan_id = request.data.get('plan_id')
        allocations = request.data.get('allocations', [])

        try:
            plan = AllocationService.update_allocation(plan_id, allocations)
            return Response({
                'success': True,
                'free_cash': float(plan.free_cash),
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['POST'], url_path='record-spending')
    def record_spending(self, request):
        """记录某分类实际花费"""
        plan_id = request.data.get('plan_id')
        category_id = request.data.get('category_id')
        amount = request.data.get('amount')
        note = request.data.get('note', '')

        try:
            item = AllocationService.record_spending(plan_id, category_id, amount, note)
            return Response({
                'success': True,
                'remaining': float(item.remaining_amount),
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['POST'], url_path='save-decision')
    def save_decision(self, request):
        """保存自由决策"""
        plan_id = request.data.get('plan_id')
        content = request.data.get('content')
        category = request.data.get('category', '')

        try:
            decision = AllocationService.save_decision(plan_id, content, category)
            return Response({
                'success': True,
                'decision_id': decision.id,
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['GET'], url_path='categories')
    def categories(self, request):
        """获取可用分配类别"""
        from ..models.allocation_plan import AllocationCategory
        categories = AllocationCategory.objects.filter(is_active=True)
        return Response([
            {
                'id': c.id,
                'name': c.name,
                'icon': c.icon,
                'color': c.color,
                'priority': c.priority,
                'default_amount': float(c.default_amount),
            }
            for c in categories
        ])
