from collections import Counter

import datetime as dt

from django.db import models, transaction
from django.db.models import Avg, Case, Count, F, IntegerField, Prefetch, Q, When
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .constants import ACTIVE_STATUSES
from .models import Action, Goal, GoalReview, Milestone, OutputRecord
from .serializers import (
    ActionSerializer,
    BatchActionSerializer,
    CloneGoalSerializer,
    GoalCheckupSerializer,
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
from .services import (
    GoalCloneService,
    GoalProgressService,
    MilestoneRewardService,
    QuickGoalService,
    build_checkup,
    calculate_streak,
)


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
        # 嵌套 milestones 用 Prefetch 注入智能排序（目标详情/列表展开都生效）
        milestone_qs = Milestone.objects.annotate(
            _sort_active=Case(
                When(status__in=['pending', 'in-progress'], then=0),
                default=1,
                output_field=IntegerField(),
            ),
            _sort_has_date=Case(
                When(target_date__isnull=False, then=0),
                default=1,
                output_field=IntegerField(),
            ),
        ).order_by('_sort_active', '_sort_has_date', 'target_date', 'order_num', 'id')

        qs = super().get_queryset().annotate(
            action_count=Count('actions', distinct=True),
            milestone_count=Count('milestones', distinct=True),
        ).prefetch_related(Prefetch('milestones', queryset=milestone_qs))
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
        parent = serializer.validated_data.get('parent_goal')
        if parent and parent.parent_goal:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'parent_goal': '父目标本身已是子目标，不能作为父目标'})
        goal = serializer.save()
        GoalProgressService.recalculate(goal)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        goals = Goal.objects.all()
        now = timezone.now().date()
        # 逾期只看「还会被推进的」目标：已放弃 / 已归档的截止日过了不是逾期，
        # 它们已经有过决策了（v3.62.42 前把这两类也算进去，虚报 2 条）
        overdue = goals.filter(deadline__lt=now, status__in=ACTIVE_STATUSES).count()

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

    @action(detail=False, methods=['get'])
    def checkup(self, request):
        """PDCA 的「C」—— 过程检查（只读，不改任何数据）

        回答「哪些目标名义上还在进行、实际上已经不动了」。
        判据与阈值全在 `constants.py` + `services/goal_checkup.py`，
        本视图只负责把结果套上白名单序列化器。
        """
        data = build_checkup()
        return Response(GoalCheckupSerializer(data).data)

    @action(detail=False, methods=['get'])
    def status_stats(self, request):
        """各状态的目标数量统计"""
        stats = Goal.objects.values('status').annotate(count=Count('id'))
        result = {
            'total': Goal.objects.count(),
            'stats': {s['status']: s['count'] for s in stats},
        }
        return Response(result)

    @action(detail=False, methods=['get'])
    def dimension_stats(self, request):
        """按人生维度聚合统计数据（用于雷达图）"""
        from django.db.models import Avg, Count

        qs = Goal.objects.exclude(life_dimension='').exclude(life_dimension__isnull=True)
        aggregates = qs.values('life_dimension').annotate(
            count=Count('id'),
            avg_progress=Avg('progress_percentage'),
        )

        labels = dict(Goal._meta.get_field('life_dimension').choices)
        indicators = []
        values = []
        for agg in aggregates:
            dim = agg['life_dimension']
            indicators.append({
                'name': labels.get(dim, dim),
                'max': 100,
            })
            values.append(round(agg['avg_progress'] or 0, 1))

        return Response({
            'indicators': indicators,
            'values': values,
            'dimensions': {
                agg['life_dimension']: {
                    'count': agg['count'],
                    'avg_progress': round(agg['avg_progress'] or 0, 1),
                }
                for agg in aggregates
            },
        })

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
        if data.get('self_review') is not None:
            milestone.self_review = data['self_review']
        if data.get('difficulty_met') is not None:
            milestone.difficulty_met = data['difficulty_met']
        if data.get('next_action') is not None:
            milestone.next_action = data['next_action']
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
    def abandon(self, request, pk=None):
        """放弃一条目标 —— PDCA 的 A：**放弃也是决策**。

        一个动作同时做两件事，不新造语义：
        - 真源：`Goal.status = 'abandoned'`
        - 留痕：`GoalReview(review_type='monthly', what_blocked=理由)`

        🔴 理由必填：放弃可以，但要能对自己解释。
        🔴 里程碑**不动**：目标级决策不级联删子项（项目铁律：禁级联删除）。
        """
        goal = self.get_object()

        if goal.status == 'abandoned':
            return Response({'detail': '这条已经是「已放弃」了'}, status=status.HTTP_409_CONFLICT)
        if goal.status == 'completed':
            return Response(
                {'detail': '已完成的目标不能放弃 —— 它已经走完了'},
                status=status.HTTP_409_CONFLICT,
            )

        reason = (request.data.get('reason') or '').strip()
        if not reason:
            return Response(
                {'reason': ['写一句为什么 —— 放弃可以，但要能对自己解释']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(reason) > 200:
            return Response(
                {'reason': ['一句话就够（≤200 字）']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            review = GoalReview.objects.create(
                goal=goal,
                review_type='monthly',
                review_date=timezone.localdate(),
                what_blocked=reason,
                next_adjustment='放弃',
                content=f'放弃「{goal.title}」',
            )
            goal.status = 'abandoned'
            # `updated_at` 是 auto_now，必须写进 update_fields 才会刷新
            goal.save(update_fields=['status', 'updated_at'])

        return Response({
            'id': goal.id,
            'status': goal.status,
            'review_id': review.id,
            'review_date': review.review_date,
            'milestone_count': goal.milestones.count(),
        })

    @action(detail=True, methods=['post'])
    def recalculate(self, request, pk=None):
        """手动重新计算进度"""
        goal = self.get_object()
        GoalProgressService.recalculate(goal)
        return Response({'progress_percentage': goal.progress_percentage})

    @action(detail=True, methods=['get'])
    def sub_goals(self, request, pk=None):
        """获取子目标列表"""
        goal = self.get_object()
        subs = goal.sub_goals.all()
        return Response(GoalListSerializer(subs, many=True).data)

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
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            content_order=data.get('content_order', 'asc'),
            display_order=data.get('display_order', 'asc'),
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

    @action(detail=True, methods=['post'])
    def checkin(self, request, pk=None):
        """打卡 — 标记完成并发放里程碑奖励，支持指定日期补打卡"""
        from datetime import date

        action = self.get_object()
        goal = action.goal

        checkin_date = request.data.get('date')
        if checkin_date:
            checkin_date = date.fromisoformat(checkin_date)
            if checkin_date > date.today():
                return Response({'error': '不能为未来日期打卡'}, status=400)
        else:
            checkin_date = date.today()

        date_str = checkin_date.isoformat()

        log = action.completion_log or {}
        already = log.get(date_str, False)

        if not already:
            log[date_str] = True
            action.completion_log = log
            action.save(update_fields=['completion_log'])

        # 仅当本次为新增打卡时推进里程碑：
        # 优先完成打卡日期对应的里程碑，若日期未命中（如倒计时里程碑无 target_date），
        # 则推进下一个未完成的里程碑（按顺序）
        reward_result = None
        completed_any = False
        if not already:
            milestones = goal.milestones.filter(target_date=checkin_date).exclude(status='completed')
            if not milestones.exists():
                milestones = goal.milestones.exclude(status='completed').order_by('order_num', 'id')[:1]
            for milestone in milestones:
                milestone.status = 'completed'
                milestone.save(update_fields=['status'])
                completed_any = True
                reward_result = MilestoneRewardService().complete_milestone(milestone)

        GoalProgressService.recalculate(goal)
        streak = calculate_streak(log)

        return Response({
            'checked': not already,
            'already_checked': already,
            'streak': streak,
            'milestone_completed': completed_any,
            'reward': reward_result,
            'goal_id': goal.id,
            'goal_progress': goal.progress_percentage,
        })

    @action(detail=True, methods=['get'])
    def checkin_stats(self, request, pk=None):
        """获取打卡统计数据（日历热力图 + 连续天数 + 目标里程碑奖励）"""
        action = self.get_object()
        goal = action.goal
        log = action.completion_log or {}

        streak = calculate_streak(log)

        # Total milestones count for this goal
        total_milestones = goal.milestones.count()
        completed_milestones = goal.milestones.filter(status='completed').count()

        # Reward milestones (milestones with reward_amount)
        reward_milestones = goal.milestones.exclude(
            models.Q(reward_amount__isnull=True) | models.Q(reward_amount=0)
        ).values('id', 'title', 'reward_amount', 'status', 'order_num').order_by('order_num')

        # All milestones (for behavior track card milestone list)
        all_milestones = goal.milestones.all().order_by('order_num').values(
            'id', 'title', 'status', 'reward_amount', 'description',
            'completed_note', 'self_review', 'target_date', 'order_num',
        )

        return Response({
            'streak': streak,
            'total_milestones': total_milestones,
            'completed_milestones': completed_milestones,
            'progress_percentage': goal.progress_percentage,
            'calendar': log,
            'reward_milestones': [
                {
                    'id': m['id'],
                    'title': m['title'],
                    'reward_amount': float(m['reward_amount']),
                    'status': m['status'],
                    'order_num': m['order_num'],
                }
                for m in reward_milestones
            ],
            'milestones': [
                {
                    'id': m['id'],
                    'title': m['title'],
                    'status': m['status'],
                    'reward_amount': float(m['reward_amount']) if m['reward_amount'] else 0,
                    'description': m['description'] or '',
                    'completed_note': m['completed_note'] or '',
                    'self_review': m['self_review'] or '',
                    'target_date': m['target_date'].isoformat() if m['target_date'] else None,
                    'order_num': m['order_num'],
                }
                for m in all_milestones
            ],
        })

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
        params = self.request.query_params
        goal_id = params.get('goal')
        if goal_id:
            qs = qs.filter(goal_id=goal_id)
        target_year = params.get('target_date_year')
        target_month = params.get('target_date_month')
        if target_year:
            qs = qs.filter(target_date__year=target_year)
        if target_month:
            qs = qs.filter(target_date__month=target_month)
        # 🔴 日程视图用：**已放弃目标 + 还没完成的里程碑**不算待办（2026-10-26）
        #    `abandon` 明确「里程碑不动，目标级决策不级联删子项」⇒ 放弃后
        #    那些 pending 里程碑会一直留在日历里，十月看起来像还有 24 件事要做。
        # 🔴 但**已完成的要留**：它是历史日程，翻回去看「那天我做了什么」还得在。
        #    ⇒ 保留条件 = 目标没放弃 **或** 里程碑已完成，不能直接排除整个目标。
        # ⚠️ 必须是**显式开关**，不能默认过滤：目标详情页要看得到自己的全部里程碑，
        #    否则「放弃一条目标」会让它的子项在页面上凭空消失（静默丢数据）。
        if params.get('exclude_abandoned_goals') in ('1', 'true', 'True'):
            qs = qs.filter(~Q(goal__status='abandoned') | Q(status='completed'))
        # 排序：未完成在前 → 有截止日期在前 → 截止日期最近在前 → 手排/ID 兜底
        return qs.annotate(
            _sort_active=Case(
                When(status__in=['pending', 'in-progress'], then=0),
                default=1,
                output_field=IntegerField(),
            ),
            _sort_has_date=Case(
                When(target_date__isnull=False, then=0),
                default=1,
                output_field=IntegerField(),
            ),
        ).order_by('_sort_active', '_sort_has_date', 'target_date', 'order_num', 'id')

    def perform_create(self, serializer):
        goal_id = self.request.data.get('goal')
        if not goal_id:
            raise ValidationError({'goal': '此字段必填。'})
        instance = serializer.save(goal_id=goal_id)
        GoalProgressService.recalculate(instance.goal)

    def perform_update(self, serializer):
        old_instance = self.get_object()
        old_status = old_instance.status
        new_status = serializer.validated_data.get('status', old_status)

        instance = serializer.save()

        # 取消完成 → 扣回奖励
        if old_status == 'completed' and new_status != 'completed' and old_instance.reward_synced:
            from apps.reward.services import RewardPoolService
            reward_amount = (
                old_instance.reward_amount
                or old_instance.goal.default_reward_amount
                or 0
            )
            if reward_amount > 0:
                RewardPoolService.deduct_reward(
                    source_id=old_instance.id,
                    source_type='milestone',
                    amount=reward_amount,
                    reason='milestone_uncheck',
                    description=f'取消完成里程碑「{old_instance.title}」（{old_instance.goal.title}），扣回{reward_amount}元',
                )
                Goal.objects.filter(id=instance.goal_id).update(
                    total_reward_issued=F('total_reward_issued') - reward_amount,
                )
                instance.reward_synced = False
                instance.reward_issued_at = None
                instance.save(update_fields=['reward_synced', 'reward_issued_at'])

        # 首次完成 → 发放奖励
        elif old_status != 'completed' and new_status == 'completed' and not old_instance.reward_synced:
            from apps.reward.services import RewardPoolService
            from decimal import Decimal

            reward_amount = (
                instance.reward_amount
                or instance.goal.default_reward_amount
                or Decimal('0')
            )
            if reward_amount > 0:
                RewardPoolService.add_reward(
                    source_id=instance.id,
                    source_type='milestone',
                    amount=reward_amount,
                    transaction_type='milestone_complete',
                    description=f'完成里程碑「{instance.title}」（{instance.goal.title}），获得{reward_amount}元奖励',
                )
                Goal.objects.filter(id=instance.goal_id).update(
                    total_reward_issued=F('total_reward_issued') + reward_amount,
                )
                instance.reward_synced = True
                instance.reward_issued_at = timezone.now()
                instance.save(update_fields=['reward_synced', 'reward_issued_at'])

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
        params = self.request.query_params

        goal_id = params.get('goal')
        if goal_id:
            qs = qs.filter(goal_id=goal_id)

        review_type = params.get('review_type')
        if review_type:
            qs = qs.filter(review_type=review_type)

        # `review_date` 是 DateField（不是 DateTimeField），按年/月过滤不撞 CONVERT_TZ
        month = params.get('month')  # '2026-10'
        if month:
            try:
                y, m = str(month).split('-')
                y, m = int(y), int(m)
            except (ValueError, AttributeError):
                raise ValidationError({'month': '格式应为 YYYY-MM'})
            qs = qs.filter(review_date__year=y, review_date__month=m)
        return qs


class OutputRecordViewSet(viewsets.ModelViewSet):
    """产出记录视图集——个人良品率管理"""

    queryset = OutputRecord.objects.all()
    permission_classes = [AllowAny]
    serializer_class = OutputRecordSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'fail_reason', 'lesson_learned']
    ordering_fields = ['created_at', 'occurred_at', 'difficulty']
    # 🔴 按**发生日期**排，不按创建时间：列表里显示的是发生日期，
    #    用 `-created_at` 会让补录的旧事插到最前面，看起来像日期错乱。
    #    MySQL 的 DESC 把 NULL 排在最后 ⇒ 未填日期的老记录沉底，不会顶在最上面。
    ordering = ['-occurred_at', '-created_at']

    #: 样本下限：低于这个数不给比例（5 件里 3 件成不了，说「60%」是自欺）
    MIN_SAMPLE = 5

    #: 窗口键 → 口径。**只在这里定义一次**，前端只传 key、不自己算边界。
    WINDOW_DAYS = {'30d': 30, '90d': 90}

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

        # `window` 优先；老的 `year` 参数保留（外部脚本 / 旧书签可能还在用）
        window = params.get('window')
        if window:
            qs = self._apply_window(qs, window)
        else:
            year = params.get('year')
            if year:
                qs = qs.filter(occurred_at__year=int(year))

        return qs

    def _apply_window(self, qs, window: str):
        """把窗口键翻译成 occurred_at 的过滤条件（唯一实现）。"""
        today = timezone.localdate()
        days = self.WINDOW_DAYS.get(window)
        if days:
            # 含今天在内共 N 天：[today-(N-1), +∞)
            return qs.filter(occurred_at__gte=today - dt.timedelta(days=days - 1))
        if window == 'year':
            return qs.filter(occurred_at__year=today.year)
        # 'all' 或未知值都按「全量」处理：宁可多给，不可静默少给
        return qs

    def perform_create(self, serializer):
        serializer.save(user_id=1)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """产出统计。

        口径（v3.62.39 起）：
        * `window` 必须是显式参数，**默认近 30 天** —— 以前恒按「今年」过滤但界面上
          没有年份选择器，用户看不到自己正在看的是一个被悄悄缩小的样本。
        * 样本 < `MIN_SAMPLE` 时 `sample_enough=False`，前端只显示件数、不显示比例。
        * `by_fail_type` / `top_fail_type` 是这一页**唯一能指导下一步**的东西，
          以前完全没有统计。
        """
        params = request.query_params
        window = params.get('window') or '30d'
        if window not in ('30d', '90d', 'year', 'all'):
            window = '30d'

        qs = self._apply_window(OutputRecord.objects.all(), window)

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

        # 按难度统计：**已停用**（v3.62.39）
        # 22 条记录里 16 条躺在默认值 3 上 —— 这个维度没有信息量，
        # 而页面上那句「难度越高，良品率越低」是写死的，不是算出来的。
        # 删掉统计与展示，`difficulty` 列暂时保留（删列要迁移，等确认后再做）。

        # 失败类型分布（只统计没做成的）—— 这才是「下次改什么」的依据
        redo_qs = qs.exclude(quality='good')
        by_fail_type = []
        for code, label in OutputRecord.FAIL_TYPE_CHOICES:
            n = redo_qs.filter(fail_type=code).count()
            if n:
                by_fail_type.append({'value': code, 'label': label, 'count': n})
        by_fail_type.sort(key=lambda x: (-x['count'], x['label']))
        # 没填类型的单独计数：不补这一项，`sum(by_fail_type) < redo_count` 就成了静默缺口
        fail_type_missing = redo_qs.filter(fail_type='').count()

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
            'window': window,
            'total_records': total,
            'good_count': good,
            'defective_count': defective,
            'waste_count': waste,
            'redo_count': defective + waste,
            'yield_rate': rate(good),
            'defect_rate': rate(defective),
            'waste_rate': rate(waste),
            'min_sample': self.MIN_SAMPLE,
            'sample_enough': total >= self.MIN_SAMPLE,
            'by_category': by_category,
            'by_fail_type': by_fail_type,
            'top_fail_type': by_fail_type[0] if by_fail_type else None,
            'fail_type_missing': fail_type_missing,
            # 全库范围内未填日期的条数（不受窗口影响）：
            # 它们进不了任何按日期过滤的口径，界面必须说明「另有 N 条没算进来」
            'undated_count': OutputRecord.objects.filter(occurred_at__isnull=True).count(),
            'monthly_trend': monthly_trend,
        }
        return Response(OutputStatsSerializer(data).data)
