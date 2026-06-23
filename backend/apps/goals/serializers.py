from datetime import datetime

from django.db import models
from rest_framework import serializers

from .models import Action, Goal, GoalReview, Milestone, OutputRecord


class MilestoneSerializer(serializers.ModelSerializer):
    """里程碑序列化器"""

    status_display = serializers.SerializerMethodField()
    reward_amount_display = serializers.SerializerMethodField()
    goal_title = serializers.CharField(source='goal.title', read_only=True)
    goal_deadline = serializers.DateField(source='goal.deadline', read_only=True)

    class Meta:
        model = Milestone
        fields = [
            'id', 'goal', 'goal_title', 'goal_deadline', 'title', 'status', 'status_display',
            'completed_note', 'description', 'order_num', 'target_date',
            'target_value', 'actual_value', 'self_review',
            'reward_amount', 'reward_synced', 'reward_issued_at', 'reward_transaction_id',
            'reward_amount_display',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'goal', 'reward_synced', 'reward_issued_at',
                            'reward_transaction_id', 'created_at', 'updated_at']

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_reward_amount_display(self, obj):
        """获取实际生效的奖励金额"""
        if obj.reward_amount is not None and obj.reward_amount > 0:
            return float(obj.reward_amount)
        goal = obj.goal
        if goal.enable_reward and goal.default_reward_amount > 0:
            return float(goal.default_reward_amount)
        if goal.enable_reward and goal.reward_value > 0:
            return float(goal.reward_value)
        return float(goal.reward_value) if goal.reward_value else 0


class ActionSerializer(serializers.ModelSerializer):
    """行为记录序列化器"""

    goal_title = serializers.SerializerMethodField()
    milestone_title = serializers.SerializerMethodField()

    class Meta:
        model = Action
        fields = [
            'id', 'goal', 'goal_title', 'milestone', 'milestone_title',
            'name', 'note', 'action_date', 'completion_log', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_goal_title(self, obj):
        return obj.goal.title if obj.goal else None

    def get_milestone_title(self, obj):
        return obj.milestone.title if obj.milestone else None

    def validate(self, attrs):
        if attrs.get('milestone') and attrs.get('goal'):
            if attrs['milestone'].goal_id != attrs['goal'].id:
                raise serializers.ValidationError({'milestone': '里程碑必须属于同一个目标'})
        return attrs


class BatchActionSerializer(serializers.Serializer):
    """批量创建行为序列化器"""

    goal_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    name = serializers.CharField(max_length=200)
    milestone_id = serializers.IntegerField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    action_date = serializers.DateField(required=False, allow_null=True)

    def validate_goal_ids(self, value):
        existing_ids = set(Goal.objects.filter(id__in=value).values_list('id', flat=True))
        missing = set(value) - existing_ids
        if missing:
            raise serializers.ValidationError(f'目标不存在: {sorted(missing)}')
        return value

    def validate(self, attrs):
        if attrs.get('milestone_id'):
            milestone = Milestone.objects.filter(id=attrs['milestone_id']).first()
            if not milestone:
                raise serializers.ValidationError({'milestone_id': '里程碑不存在'})
            if milestone.goal_id not in attrs['goal_ids']:
                raise serializers.ValidationError({'milestone_id': '里程碑必须属于选中的目标之一'})
        return attrs


class GoalReviewSerializer(serializers.ModelSerializer):
    """目标回顾序列化器"""

    review_type_display = serializers.SerializerMethodField()

    class Meta:
        model = GoalReview
        fields = [
            'id', 'goal', 'review_type', 'review_type_display',
            'review_date', 'score', 'what_worked', 'what_blocked',
            'next_adjustment', 'content', 'progress_note', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_review_type_display(self, obj):
        return obj.get_review_type_display()


class GoalListSerializer(serializers.ModelSerializer):
    """列表用序列化器——轻量字段"""

    category_display = serializers.SerializerMethodField()
    priority_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    action_count = serializers.SerializerMethodField()
    milestone_count = serializers.SerializerMethodField()
    is_tracking_mode = serializers.SerializerMethodField()

    class Meta:
        model = Goal
        fields = [
            'id', 'title', 'description', 'category', 'category_display',
            'tags', 'priority', 'priority_display', 'status', 'status_display',
            'progress_percentage', 'start_date', 'deadline', 'year',
            'notes', 'reward_value', 'user_id',
            'enable_reward', 'default_reward_amount', 'total_reward_issued',
            'action_count', 'milestone_count', 'is_tracking_mode',
            'created_at', 'updated_at',
        ]

    def get_category_display(self, obj):
        return obj.get_category_display()

    def get_priority_display(self, obj):
        return obj.get_priority_display()

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_action_count(self, obj):
        if hasattr(obj, 'action_count'):
            return obj.action_count
        return obj.actions.count()

    def get_milestone_count(self, obj):
        if hasattr(obj, 'milestone_count'):
            return obj.milestone_count
        return obj.milestones.count()

    def get_is_tracking_mode(self, obj):
        """行为追踪模式：只有1个行为时切换"""
        count = self.get_action_count(obj)
        return count == 1


class GoalDetailSerializer(serializers.ModelSerializer):
    """详情用序列化器——嵌套里程碑和行为"""

    category_display = serializers.SerializerMethodField()
    priority_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    milestones = MilestoneSerializer(many=True, read_only=True)
    actions = ActionSerializer(many=True, read_only=True)
    reviews = GoalReviewSerializer(many=True, read_only=True)

    class Meta:
        model = Goal
        fields = [
            'id', 'title', 'description', 'category', 'category_display',
            'tags', 'priority', 'priority_display', 'status', 'status_display',
            'progress_percentage', 'start_date', 'deadline', 'year',
            'notes', 'reward_value', 'user_id',
            'enable_reward', 'default_reward_amount', 'total_reward_issued',
            'decision_quality', 'mental_models_used', 'inversion_check',
            'first_principles', 'circle_check', 'happiness_impact', 'peace_impact',
            'milestones', 'actions', 'reviews',
            'created_at', 'updated_at',
        ]

    def get_category_display(self, obj):
        return obj.get_category_display()

    def get_priority_display(self, obj):
        return obj.get_priority_display()

    def get_status_display(self, obj):
        return obj.get_status_display()


class GoalCreateUpdateSerializer(serializers.ModelSerializer):
    """创建/更新用序列化器"""

    milestones = MilestoneSerializer(many=True, required=False)

    class Meta:
        model = Goal
        fields = [
            'title', 'description', 'category', 'tags', 'priority',
            'status',
            'start_date', 'deadline', 'notes', 'reward_value',
            'enable_reward', 'default_reward_amount',
            'milestones',
        ]

    def validate_deadline(self, value):
        if value is None:
            return value
        start_date = self.initial_data.get('start_date')
        if start_date:
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            if isinstance(value, str):
                value = datetime.strptime(value, '%Y-%m-%d').date()
            if value < start_date:
                raise serializers.ValidationError('截止日期不能早于开始日期')
        return value

    def validate_tags(self, value):
        if value and len(value) > 10:
            raise serializers.ValidationError('标签数量不能超过10个')
        return value

    def create(self, validated_data):
        milestones_data = validated_data.pop('milestones', [])
        start_date = validated_data.get('start_date')
        if start_date:
            validated_data['year'] = start_date.year
        goal = Goal.objects.create(**validated_data)
        for idx, m in enumerate(milestones_data):
            Milestone.objects.create(goal=goal, order_num=idx, **m)
        return goal

    def update(self, instance, validated_data):
        # 不处理里程碑——里程碑由独立的 API 管理
        validated_data.pop('milestones', None)
        start_date = validated_data.get('start_date')
        if start_date:
            validated_data['year'] = start_date.year
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class GoalStatsSerializer(serializers.Serializer):
    """统计信息序列化器"""

    total_goals = serializers.IntegerField()
    completed_goals = serializers.IntegerField()
    in_progress_goals = serializers.IntegerField()
    overdue_goals = serializers.IntegerField()
    avg_progress = serializers.FloatField()
    by_category = serializers.DictField()
    by_priority = serializers.DictField()
    by_status = serializers.DictField()
    by_year = serializers.DictField()
    popular_tags = serializers.ListField(default=[])


class QuickGoalSerializer(serializers.Serializer):
    """快速创建目标+批量里程碑序列化器"""

    name = serializers.CharField(max_length=255, help_text='目标名称')
    milestone_prefix = serializers.CharField(max_length=255, required=False, allow_blank=True, help_text='里程碑名称前缀')
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    frequency = serializers.ChoiceField(choices=['daily', 'weekly', 'monthly', 'quarterly', 'yearly'], help_text='频率')
    reward_per_milestone = serializers.DecimalField(max_digits=10, decimal_places=2, default=0)
    start_date = serializers.DateField(required=False, allow_null=True, help_text='开始日期')
    end_date = serializers.DateField(required=False, allow_null=True, help_text='结束日期')
    content_order = serializers.ChoiceField(choices=['asc', 'desc'], default='asc', help_text='内容排序：正序(第1天)或倒序(倒计时)')
    display_order = serializers.ChoiceField(choices=['asc', 'desc'], default='asc', help_text='显示排序：日期从早到晚或从晚到早')

    def validate(self, attrs):
        if attrs['frequency'] == 'daily':
            if not attrs.get('start_date') or not attrs.get('end_date'):
                raise serializers.ValidationError('每天频率需要填写开始日期和结束日期')
            if attrs['end_date'] < attrs['start_date']:
                raise serializers.ValidationError('结束日期不能早于开始日期')
        return attrs


class CloneGoalSerializer(serializers.Serializer):
    """复制目标序列化器"""

    name = serializers.CharField(max_length=255, help_text='新目标名称')
    copy_milestones = serializers.BooleanField(default=True, help_text='是否复制里程碑')
    copy_actions = serializers.BooleanField(default=True, help_text='是否复制行为记录')


class MilestoneToggleSerializer(serializers.Serializer):
    """里程碑状态切换序列化器"""

    status = serializers.ChoiceField(choices=Milestone.STATUS_CHOICES, required=False)
    completed_note = serializers.CharField(required=False, allow_blank=True)
    self_review = serializers.CharField(required=False, allow_blank=True)
    actual_value = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)


class OutputRecordSerializer(serializers.ModelSerializer):
    """产出记录序列化器"""

    quality_display = serializers.SerializerMethodField()
    category_display = serializers.SerializerMethodField()
    difficulty_display = serializers.SerializerMethodField()
    fail_type_display = serializers.SerializerMethodField()

    class Meta:
        model = OutputRecord
        fields = [
            'id', 'title', 'category', 'category_display',
            'expected_result', 'actual_result',
            'quality', 'quality_display',
            'difficulty', 'difficulty_display',
            'fail_reason', 'fail_type', 'fail_type_display',
            'lesson_learned', 'occurred_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_quality_display(self, obj):
        return obj.get_quality_display()

    def get_category_display(self, obj):
        return obj.get_category_display()

    def get_difficulty_display(self, obj):
        return obj.get_difficulty_display()

    def get_fail_type_display(self, obj):
        return obj.get_fail_type_display() if obj.fail_type else ''


class OutputStatsSerializer(serializers.Serializer):
    """良品率统计序列化器"""

    total_records = serializers.IntegerField()
    good_count = serializers.IntegerField()
    defective_count = serializers.IntegerField()
    waste_count = serializers.IntegerField()
    yield_rate = serializers.FloatField()
    defect_rate = serializers.FloatField()
    waste_rate = serializers.FloatField()
    by_category = serializers.DictField()
    by_difficulty = serializers.DictField()
    monthly_trend = serializers.ListField()
