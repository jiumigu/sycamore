from datetime import datetime, timedelta

from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import InboxItem
from .serializers import (
    BatchActionSerializer,
    InboxItemDetailSerializer,
    InboxItemSerializer,
    InboxStatsSerializer,
)
from .services import ConverterService, InboxImportService
from apps.goals.models import Goal, Milestone


class InboxPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'


class InboxViewSet(viewsets.ModelViewSet):
    """收件箱视图集"""

    queryset = InboxItem.objects.all()
    permission_classes = [AllowAny]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['content', 'description', 'tags']
    ordering_fields = ['created_at', 'due_date', 'priority', 'updated_at', 'processed_at']
    # 默认排序（**除「已完成」以外**的状态都走它，见 `filter_queryset`）。
    # 「待办 / 犹豫」问的是「我最近记了什么」，创建时间是对的尺子。
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

    def filter_queryset(self, queryset):
        """默认排序 —— 按「这件事发生的时间」，不是按「记下来的时间」（v3.64.82）。

        | 看哪个列表 | 排序键 | 为什么 |
        |---|---|---|
        | 已完成 `status=done` | `-Coalesce(processed_at, created_at)`，次级 `-id` | 这一页问的是「我最近**完成**了什么」。按创建时间排，等于把 9 月记下、昨天才做完的那条埋在中间 |
        | 其它（待办 / 犹豫 / 已处理 / 废弃） | `-created_at`（`ordering` 默认值） | 问的是「我最近**记**了什么」 |

        🔴 `processed`（已转出）**不**按 `processed_at` 排：87 条里 61 条是历史空值
           （转出时还没记时间）。按它排会让那 61 条整体沉到底、内部又按 id 排，
           看起来像乱序 —— 比现在更糟。要改先补历史数据。

        🔴 显式传 `?ordering=` 时一律听调用方（排序控件、调试）。
        """
        queryset = super().filter_queryset(queryset)
        if self.request.query_params.get('ordering'):
            return queryset
        if self.request.query_params.get('status', 'pending') == 'done':
            # `Coalesce` 而不是 `nulls_last`：那几条历史空值用「记下的时间」兜底，
            # 与前端显示（`processed_at ?? created_at`）是**同一句**兜底；
            # 顺带不依赖 MySQL / SQLite 对 NULL 排序的差异。
            return queryset.order_by(
                Coalesce('processed_at', 'created_at').desc(), '-id',
            )
        return queryset

    def perform_create(self, serializer):
        serializer.save(user_id=1)

    def perform_update(self, serializer):
        # 状态迁移的唯一收口：`processed_at` 跟着状态走。
        # 编辑表单能直接把状态改成「已完成」（走 PATCH，不是 `complete` 动作），
        # 不在这里补时间，那一行就没有完成时刻 —— 列表排序与界面都说不清它。
        item = serializer.instance
        new_status = serializer.validated_data.get('status')
        if new_status and new_status != item.status:
            item.sync_processed_at(new_status)
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
        try:
            item = ConverterService.process(item, action_type, **extra)
        except ValueError as e:
            # 如：转为里程碑未指定目标
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            # 如：目标已被删除/失效
            return Response({'error': '转换失败，请检查所选目标是否仍有效'}, status=status.HTTP_400_BAD_REQUEST)
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

    @action(detail=False, methods=['post'], url_path='convert-to-milestone')
    def convert_to_milestone(self, request):
        """将多条收集箱事项批量转为已有目标的里程碑（同目标）"""
        item_ids = request.data.get('item_ids', [])
        goal_id = request.data.get('goal_id')

        if not item_ids or not goal_id:
            return Response({'error': '请选择事项并指定目标'}, status=status.HTTP_400_BAD_REQUEST)

        from apps.goals.models import Goal
        goal = Goal.objects.filter(id=goal_id).first()
        if not goal:
            return Response({'error': '目标不存在'}, status=status.HTTP_400_BAD_REQUEST)

        items = list(InboxItem.objects.filter(id__in=item_ids, status='pending'))
        if not items:
            return Response({'error': '未找到有效事项'}, status=status.HTTP_400_BAD_REQUEST)

        from apps.inbox.services import ConverterService
        converted = 0
        for item in items:
            try:
                # 复用单条转换：标题=内容，截止日期/详细描述各自带过去
                ConverterService.convert_to_milestone(item, goal_id=goal_id)
                item.status = 'processed'
                item.save(update_fields=['status'])
                converted += 1
            except Exception:
                continue

        return Response({
            'goal_id': goal.id,
            'goal_title': goal.title,
            'milestone_count': converted,
            'converted_count': converted,
            'failed_count': len(items) - converted,
        })

    @action(detail=False, methods=['post'], url_path='import')
    def import_items(self, request):
        """批量导入待办事项（CSV / Markdown / 纯文本）"""
        file = request.FILES.get('file')
        if not file:
            return Response({'success': False, 'error': '请上传文件'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            content = file.read().decode('utf-8')
        except UnicodeDecodeError:
            try:
                file.seek(0)
                content = file.read().decode('gbk')
            except UnicodeDecodeError:
                return Response(
                    {'success': False, 'error': '文件编码不支持，请使用 UTF-8 或 GBK'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        content = content.lstrip('﻿')  # 去除 Excel 导出常见的 UTF-8 BOM

        file_name = (file.name or '').lower()
        if file_name.endswith('.csv'):
            parsed = InboxImportService.parse_csv(content)
        elif file_name.endswith('.md'):
            parsed = InboxImportService.parse_markdown_tasks(content)
        else:
            parsed = InboxImportService.parse_plain_text(content)

        items, skipped = parsed['items'], parsed['skipped']
        if not items and not skipped:
            return Response({'success': False, 'error': '未识别到有效的待办事项'}, status=status.HTTP_400_BAD_REQUEST)

        # 单人系统：未接认证时 `request.user` 是 Anonymous（无 id）⇒ 兜底 1。
        # 接入认证后这行自动跟着走，不要再写死 1（历史硬编码，2026-11-09 修）。
        user_id = getattr(request.user, 'id', None) or 1
        result = InboxImportService.import_items(user_id, items)

        # 解析阶段被跳过的行与入库失败的行**合成一条清单**：前端只读 `failed`，
        # 每条都带 `row`。分成两个键必然只渲染一个（这次修的就是这个坑）。
        failed = skipped + result['failed']
        total = result['total'] + len(skipped)

        return Response({
            'success': not failed,
            'created': result['created'],
            'failed': failed,
            'total': total,
            'success_count': result['success_count'],
            'failed_count': len(failed),
        })

    @action(detail=False, methods=['get'])
    def calendar(self, request):
        """获取有截止日期的待办事项（日历视图用，排除已转为目标的）"""
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        qs = InboxItem.objects.filter(
            due_date__isnull=False,
        ).exclude(status__in=['processed', 'abandoned'])
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
            'abandoned': qs.filter(status='abandoned').count(),
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
