from collections import Counter

from django.db import transaction
from django.db.models import Avg, Count, F
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Action, Goal, GoalReview, Milestone, OutputRecord
from .serializers import (
    ActionSerializer,
    BatchActionSerializer,
    CloneGoalSerializer,
    GoalCreateUpdateSerializer,
    GoalDetailSerializer,
    GoalListSerializer,
    GoalReviewSerializer,
    GoalStatsSerializer,
    MilestoneSerializer,
    MilestoneToggleSerializer,
    OutputRecordSerializer,
    OutputStatsSerializer,
    QuickGoalSerializer,
)
from .services import GoalCloneService, GoalProgressService, MilestoneRewardService, QuickGoalService


class GoalPagination(PageNumberPagination):
    """目标分页：默认每页 100 条"""
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 1000


class GoalViewSet(viewsets.ModelViewSet):
    """目标视图集"""

    queryset = Goal.objects.all()
    permission_classes = [AllowAny]
    pagination_class = GoalPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description', 'notes']
    ordering_fields = ['created_at', 'deadline', 'priority', 'progress_percentage', 'updated_at', 'year']
    ordering = ['priority', '-created_at']

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return GoalCreateUpdateSerializer
        elif self.action == 'list':
            return GoalListSerializer
        elif self.action == 'stats':
            return GoalStatsSerializer
        return GoalDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        year = params.get('year')
        if year:
            try:
                qs = qs.filter(year=int(year))
            except ValueError:
                pass

        category = params.get('category')
        if category:
            qs = qs.filter(category=category)

        status_param = params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)

        priority = params.get('priority')
        if priority:
            qs = qs.filter(priority=priority)

        tag = params.get('tag')
        if tag:
            qs = qs.filter(tags__contains=[tag])

        search = params.get('search')
        if search:
            qs = qs.filter(title__icontains=search)
        return qs

    def list(self, request, *args, **kwargs):
        # 自动标记超期
        now = timezone.now().date()
        Goal.objects.filter(
            deadline__lt=now,
            status__in=['planning', 'in-progress'],
        ).update(status='archived')
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        goal = serializer.save()
        GoalProgressService.recalculate(goal)

    def perform_update(self, serializer):
        old_reward = serializer.instance.default_reward_amount if serializer.instance else None
        goal = serializer.save()
        new_reward = goal.default_reward_amount

        # 默认奖励金额变更时，同步调整已完成里程碑的奖励
        if old_reward is not None and old_reward != new_reward:
            from django.db import transaction as db_transaction
            from apps.reward.services import RewardPoolService

            delta = new_reward - old_reward
            milestones = goal.milestones.filter(
                status='completed',
                reward_synced=True,
                reward_amount__isnull=True,
            )
            if milestones.exists():
                with db_transaction.atomic():
                    for m in milestones:
                        RewardPoolService.adjust_reward(
                            source_id=m.id,
                            source_type='milestone',
                            delta=delta,
                            description=f'目标默认奖励变更：{old_reward}→{new_reward}（里程碑：{m.title}）',
                        )
                    # 用 bulk_update 一次性更新所有里程碑的 reward_amount
                    milestones.update(
                        reward_amount=F('reward_amount') + delta,
                    )

        GoalProgressService.recalculate(goal)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        goals = Goal.objects.all()
        now = timezone.now().date()
        overdue = goals.filter(deadline__lt=now).exclude(status='completed').count()

        by_category = {}
        for code, _ in Goal.CATEGORY_CHOICES:
            c = goals.filter(category=code).count()
            if c:
                by_category[code] = c

        by_priority = {}
        for code, _ in Goal.PRIORITY_CHOICES:
            c = goals.filter(priority=code).count()
            if c:
                by_priority[code] = c

        by_status = {}
        for code, _ in Goal.STATUS_CHOICES:
            c = goals.filter(status=code).count()
            if c:
                by_status[code] = c

        by_year = {}
        year_stats = goals.values('year').annotate(
            count=Count('id'),
            avg_progress=Avg('progress_percentage'),
        ).order_by('-year')
        for stat in year_stats:
            if stat['year']:
                by_year[str(stat['year'])] = {
                    'count': stat['count'],
                    'avg_progress': round(stat['avg_progress'] or 0, 2),
                }

        all_tags = []
        for g in goals:
            if g.tags:
                all_tags.extend(g.tags)
        popular_tags = [
            {'name': t, 'count': c}
            for t, c in Counter(all_tags).most_common(20)
        ]

        data = {
            'total_goals': goals.count(),
            'completed_goals': goals.filter(status='completed').count(),
            'in_progress_goals': goals.filter(status='in-progress').count(),
            'overdue_goals': overdue,
            'avg_progress': goals.aggregate(a=Avg('progress_percentage'))['a'] or 0,
            'by_category': by_category,
            'by_priority': by_priority,
            'by_status': by_status,
            'by_year': by_year,
            'popular_tags': popular_tags,
        }
        return Response(GoalStatsSerializer(data).data)

    @action(detail=True, methods=['post'])
    def toggle_milestone(self, request, pk=None):
        """切换里程碑状态（完成时自动发放奖励）"""
        goal = self.get_object()
        milestone_id = request.data.get('milestone_id')
        if not milestone_id:
            return Response({'error': '请提供里程碑ID'}, status=400)

        try:
            milestone = goal.milestones.get(id=milestone_id)
        except Milestone.DoesNotExist:
            return Response({'error': '里程碑不存在'}, status=404)

        serializer = MilestoneToggleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        data = serializer.validated_data
        new_status = data.get('status', 'completed' if milestone.status != 'completed' else 'pending')
        was_completed = milestone.status == 'completed'
        milestone.status = new_status
        if data.get('completed_note') is not None:
            milestone.completed_note = data['completed_note']
        if data.get('actual_value') is not None:
            milestone.actual_value = data['actual_value']
        milestone.save()

        reward_result = None
        if new_status == 'completed' and not was_completed:
            reward_result = MilestoneRewardService().complete_milestone(milestone)
        elif milestone.status == 'completed' and not milestone.reward_synced:
            # 补发：里程碑已是 completed 但未同步奖励（历史数据）
            reward_result = MilestoneRewardService().complete_milestone(milestone)

        GoalProgressService.recalculate(goal)
        return Response({
            'milestone': MilestoneSerializer(milestone).data,
            'goal_progress': goal.progress_percentage,
            'goal_status': goal.status,
            'reward': reward_result,
        })

    @action(detail=True, methods=['post'])
    def recalculate(self, request, pk=None):
        """手动重新计算进度"""
        goal = self.get_object()
        GoalProgressService.recalculate(goal)
        return Response({'progress_percentage': goal.progress_percentage})

    @action(detail=False, methods=['delete'])
    def bulk_delete(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': '请提供要删除的ID列表'}, status=400)
        count, _ = Goal.objects.filter(id__in=ids).delete()
        return Response({'deleted': count})

    @action(detail=False, methods=['post'])
    def quick_create(self, request):
        """快速创建目标+批量里程碑"""
        serializer = QuickGoalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        result = QuickGoalService.create_with_milestones(
            name=data['name'],
            milestone_prefix=data.get('milestone_prefix', ''),
            year=data['year'],
            frequency=data['frequency'],
            reward_per_milestone=data['reward_per_milestone'],
        )
        return Response({
            'goal': GoalDetailSerializer(result['goal']).data,
            'milestones': MilestoneSerializer(result['milestones'], many=True).data,
        }, status=201)

    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        """复制目标"""
        goal = self.get_object()
        serializer = CloneGoalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        new_goal = GoalCloneService.clone(
            goal=goal,
            name=data['name'],
            copy_milestones=data['copy_milestones'],
            copy_actions=data['copy_actions'],
        )
        return Response(GoalDetailSerializer(new_goal).data, status=201)


class ActionViewSet(viewsets.ModelViewSet):
    """行为记录视图集"""

    queryset = Action.objects.all()
    permission_classes = [AllowAny]
    serializer_class = ActionSerializer
    pagination_class = None

    def get_queryset(self):
        qs = super().get_queryset().select_related('goal', 'milestone')
        goal_id = self.request.query_params.get('goal_id')
        if goal_id:
            qs = qs.filter(goal_id=goal_id)
        milestone_id = self.request.query_params.get('milestone_id')
        if milestone_id:
            qs = qs.filter(milestone_id=milestone_id)
        # 按发生时间倒序，无发生时间则用创建时间（Coalesce 确保 NULL 不干扰排序）
        from django.db.models.functions import Coalesce, Cast
        from django.db.models import DateField, F
        qs = qs.annotate(
            sort_date=Coalesce('action_date', Cast('created_at', output_field=DateField()))
        ).order_by('-sort_date')
        return qs

    @action(detail=False, methods=['get'])
    def today_pending(self, request):
        """获取今日未完成的行为"""
        from datetime import date
        today = date.today().isoformat()

        qs = self.get_queryset().filter(is_active=True)
        pending = []
        for action in qs:
            log = action.completion_log or {}
            if not log.get(today, False):
                pending.append(action)

        page = self.paginate_queryset(pending)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(pending, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def batch(self, request):
        """批量创建行为"""
        serializer = BatchActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        goal_ids = serializer.validated_data['goal_ids']
        name = serializer.validated_data['name']
        milestone_id = serializer.validated_data.get('milestone_id')
        note = serializer.validated_data.get('note')
        from datetime import date
        action_date = serializer.validated_data.get('action_date') or date.today()

        with transaction.atomic():
            actions = Action.objects.bulk_create([
                Action(goal_id=gid, milestone_id=milestone_id, name=name, note=note, action_date=action_date)
                for gid in goal_ids
            ])

        # bulk_create may not set PKs on MySQL; re-fetch to get correct IDs
        ids = [a.id for a in actions if a.id]
        if ids:
            actions = Action.objects.filter(id__in=ids).select_related('goal', 'milestone')
        else:
            actions = Action.objects.filter(
                name=name, note=note, milestone_id=milestone_id,
                goal_id__in=goal_ids,
            ).select_related('goal', 'milestone')

        return Response(ActionSerializer(actions, many=True).data, status=201)


class MilestoneViewSet(viewsets.ModelViewSet):
    """里程碑视图集 — 支持 PATCH 编辑状态和备注"""

    queryset = Milestone.objects.all()
    permission_classes = [AllowAny]
    serializer_class = MilestoneSerializer

    def get_queryset(self):
        qs = super().get_queryset().select_related('goal')
        goal_id = self.request.query_params.get('goal')
        if goal_id:
            qs = qs.filter(goal_id=goal_id)
        return qs

    def perform_create(self, serializer):
        goal_id = self.request.data.get('goal')
        if not goal_id:
            raise ValidationError({'goal': '此字段必填。'})
        instance = serializer.save(goal_id=goal_id)
        GoalProgressService.recalculate(instance.goal)

    def perform_update(self, serializer):
        old_reward = MilestoneRewardService._get_reward_amount(serializer.instance)
        old_status = serializer.instance.status
        instance = serializer.save()
        MilestoneRewardService().sync_on_update(instance, old_status, old_reward)
        GoalProgressService.recalculate(instance.goal)

    def perform_destroy(self, instance):
        MilestoneRewardService().sync_on_delete(instance)
        goal = instance.goal
        instance.delete()
        GoalProgressService.recalculate(goal)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response({
            'milestone': MilestoneSerializer(instance).data,
            'goal_progress': instance.goal.progress_percentage,
            'goal_status': instance.goal.status,
        })


class GoalReviewViewSet(viewsets.ModelViewSet):
    """目标回顾视图集"""

    queryset = GoalReview.objects.all()
    permission_classes = [AllowAny]
    serializer_class = GoalReviewSerializer
    filter_backends = [filters.OrderingFilter]
    ordering = ['-review_date']

    def get_queryset(self):
        qs = super().get_queryset()
        goal_id = self.request.query_params.get('goal')
        if goal_id:
            qs = qs.filter(goal_id=goal_id)
        return qs


class OutputRecordViewSet(viewsets.ModelViewSet):
    """产出记录视图集——个人良品率管理"""

    queryset = OutputRecord.objects.all()
    permission_classes = [AllowAny]
    serializer_class = OutputRecordSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'fail_reason', 'lesson_learned']
    ordering_fields = ['created_at', 'occurred_at', 'difficulty']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        quality = params.get('quality')
        if quality:
            qs = qs.filter(quality=quality)

        category = params.get('category')
        if category:
            qs = qs.filter(category=category)

        difficulty = params.get('difficulty')
        if difficulty:
            qs = qs.filter(difficulty=difficulty)

        year = params.get('year')
        if year:
            qs = qs.filter(occurred_at__year=int(year))

        return qs

    def perform_create(self, serializer):
        serializer.save(user_id=1)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """良品率统计"""
        qs = OutputRecord.objects.all()
        params = self.request.query_params

        year = params.get('year')
        if year:
            qs = qs.filter(occurred_at__year=int(year))

        total = qs.count()
        good = qs.filter(quality='good').count()
        defective = qs.filter(quality='defective').count()
        waste = qs.filter(quality='waste').count()

        def rate(count):
            return round(count / total * 100, 1) if total else 0

        # 按类别统计
        by_category = {}
        for code, label in OutputRecord.CATEGORY_CHOICES:
            subset = qs.filter(category=code)
            sub_total = subset.count()
            if sub_total:
                sub_good = subset.filter(quality='good').count()
                by_category[code] = {
                    'label': label,
                    'total': sub_total,
                    'good': sub_good,
                    'yield_rate': round(sub_good / sub_total * 100, 1),
                }

        # 按难度统计
        by_difficulty = {}
        for d in range(1, 6):
            subset = qs.filter(difficulty=d)
            sub_total = subset.count()
            if sub_total:
                sub_good = subset.filter(quality='good').count()
                by_difficulty[str(d)] = {
                    'total': sub_total,
                    'good': sub_good,
                    'yield_rate': round(sub_good / sub_total * 100, 1),
                }

        # 月度趋势
        from django.db.models.functions import TruncMonth
        from django.db.models import Count, Q

        monthly = (
            qs.annotate(month=TruncMonth('occurred_at'))
            .values('month')
            .annotate(
                total=Count('id'),
                good=Count('id', filter=Q(quality='good')),
            )
            .order_by('month')
        )
        monthly_trend = [
            {
                'month': m['month'].strftime('%Y-%m') if m['month'] else None,
                'total': m['total'],
                'yield_rate': round(m['good'] / m['total'] * 100, 1) if m['total'] else 0,
            }
            for m in monthly if m['month']
        ]

        data = {
            'total_records': total,
            'good_count': good,
            'defective_count': defective,
            'waste_count': waste,
            'yield_rate': rate(good),
            'defect_rate': rate(defective),
            'waste_rate': rate(waste),
            'by_category': by_category,
            'by_difficulty': by_difficulty,
            'monthly_trend': monthly_trend,
        }
        return Response(OutputStatsSerializer(data).data)
