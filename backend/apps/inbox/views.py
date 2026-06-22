from datetime import datetime, timedelta

from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import InboxItem
from .serializers import (
    BatchActionSerializer,
    InboxItemDetailSerializer,
    InboxItemSerializer,
    InboxStatsSerializer,
)
from .services import ConverterService
from apps.goals.models import Goal, Milestone


class InboxPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'


class InboxViewSet(viewsets.ModelViewSet):
    """收件箱视图集"""

    queryset = InboxItem.objects.all()
    permission_classes = [AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['content', 'description', 'tags']
    ordering_fields = ['created_at', 'due_date', 'priority', 'updated_at']
    ordering = ['-created_at']
    pagination_class = InboxPagination

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return InboxItemDetailSerializer
        return InboxItemSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        # 默认只对列表视图过滤状态，单对象操作（删除/编辑）不受影响
        if self.action in ('list', 'today_pending'):
            status_val = params.get('status', 'pending')
            if status_val == 'all':
                pass
            elif status_val:
                qs = qs.filter(status=status_val)
        else:
            status_val = params.get('status')
            if status_val:
                qs = qs.filter(status=status_val)

        category = params.get('category')
        if category:
            qs = qs.filter(category=category)

        priority = params.get('priority')
        if priority:
            qs = qs.filter(priority=priority)

        return qs

    def perform_create(self, serializer):
        serializer.save(user_id=1)

    def perform_update(self, serializer):
        serializer.save(user_id=1)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """标记为已完成"""
        item = self.get_object()
        completion_note = request.data.get('completion_note', '')
        item.completion_note = completion_note
        item = ConverterService.process(item, 'complete', notes=completion_note)
        serializer = self.get_serializer(item)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def convert(self, request, pk=None):
        """转为其他模块"""
        item = self.get_object()
        action_type = request.data.get('action')
        if not action_type:
            return Response({'error': '请指定操作类型'}, status=status.HTTP_400_BAD_REQUEST)

        extra = {
            'notes': request.data.get('notes', ''),
            'relationship_id': request.data.get('relationship_id'),
            'energy_score': request.data.get('energy_score', 0),
            'priority': request.data.get('priority', 'p2'),
            'goal_id': request.data.get('goal_id'),
            'milestone_name': request.data.get('milestone_name', ''),
            'target_date': request.data.get('target_date'),
            'description': request.data.get('description', ''),
        }
        item = ConverterService.process(item, action_type, **extra)
        serializer = self.get_serializer(item)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def batch(self, request):
        """批量操作"""
        serializer = BatchActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ids = serializer.validated_data['ids']
        action = serializer.validated_data['action']
        items = InboxItem.objects.filter(id__in=ids)

        if action == 'delete':
            items.delete()
            return Response({'deleted': len(ids)})

        extra = {
            'notes': serializer.validated_data.get('notes', ''),
            'relationship_id': serializer.validated_data.get('relationship_id'),
        }
        for item in items:
            ConverterService.process(item, action, **extra)

        return Response({'processed': len(ids)})

    @action(detail=False, methods=['post'])
    def convert_to_goal(self, request):
        """将多条收集箱事项转为目标+里程碑"""
        from datetime import date

        item_ids = request.data.get('item_ids', [])
        goal_name = request.data.get('goal_name', '').strip()
        goal_year = request.data.get('year', date.today().year)
        reward = request.data.get('reward_per_milestone', 0)

        if not item_ids or not goal_name:
            return Response({'error': '请选择事项并输入目标名称'}, status=status.HTTP_400_BAD_REQUEST)

        items = list(InboxItem.objects.filter(id__in=item_ids, status='pending'))
        if not items:
            return Response({'error': '未找到有效事项'}, status=status.HTTP_400_BAD_REQUEST)

        # 创建目标
        goal = Goal.objects.create(
            title=goal_name,
            category='month',
            year=int(goal_year) if goal_year else date.today().year,
            status='planning',
            default_reward_amount=float(reward) if reward else 0,
            enable_reward=bool(reward),
            user_id=1,
        )

        # 创建里程碑（每条事项 → 一个里程碑）
        milestones = []
        for i, item in enumerate(items):
            m = Milestone.objects.create(
                goal=goal,
                title=item.content,
                description=item.description or item.content,
                status='pending',
                order_num=i + 1,
                reward_amount=float(reward) if reward else None,
            )
            milestones.append(m)

            # 标记收集箱事项为已处理
            item.status = 'processed'
            item.save()

        return Response({
            'goal_id': goal.id,
            'goal_title': goal.title,
            'milestone_count': len(milestones),
            'converted_count': len(items),
        })

    @action(detail=False, methods=['get'])
    def calendar(self, request):
        """获取有截止日期的待办事项（日历视图用，排除已转为目标的）"""
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        qs = InboxItem.objects.filter(
            due_date__isnull=False,
        ).exclude(status='processed')
        if year:
            qs = qs.filter(due_date__year=year)
        if month:
            qs = qs.filter(due_date__month=month)
        qs = qs.order_by('due_date')
        serializer = InboxItemSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def today_pending(self, request):
        """获取收集箱中待处理的事项"""
        priority_order = Case(
            When(priority='high', then=Value(0)),
            When(priority='medium', then=Value(1)),
            When(priority='low', then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        )
        items = self.get_queryset().filter(
            status='pending',
        ).annotate(
            priority_sort=priority_order,
        ).order_by('priority_sort', '-created_at')

        page = self.paginate_queryset(items)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(items, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """统计信息"""
        qs = InboxItem.objects.all()

        stats = {
            'total': qs.count(),
            'pending': qs.filter(status='pending').count(),
            'hesitating': qs.filter(status='hesitating').count(),
            'completed': qs.filter(status='done').count(),
            'processed': qs.filter(status='processed').count(),
        }

        by_category = {}
        for item in qs.values('category').annotate(count=Count('id')):
            by_category[item['category']] = item['count']
        stats['by_category'] = by_category

        by_priority = {}
        for item in qs.values('priority').annotate(count=Count('id')):
            by_priority[item['priority']] = item['count']
        stats['by_priority'] = by_priority

        return Response(stats)
