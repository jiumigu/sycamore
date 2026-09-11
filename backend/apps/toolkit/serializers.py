from rest_framework import serializers

from .models import AskAnswer, AskScene, AskTopic, CareerEnergyAudit, CityCoordinate, DecisionRecord, DecisionTracker, ElectricityRecord, FixedExpense, FreeSpendingCalculator, HealthSelfCheck, HourlyWageRecord, Quote, TravelRoutePreset
from .services import _extra_income_monthly


class CityCoordinateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CityCoordinate
        fields = ['id', 'name', 'full_name', 'province', 'lng', 'lat', 'city_type', 'pinyin']


class ExecuteToolSerializer(serializers.Serializer):
    tool_key = serializers.CharField(help_text='工具标识')
    params = serializers.JSONField(help_text='工具参数')


class ToolInfoSerializer(serializers.Serializer):
    tool_key = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    icon = serializers.CharField()
    category = serializers.CharField()
    input_schema = serializers.JSONField()
    output_type = serializers.CharField()
    is_async = serializers.BooleanField()
    timeout_seconds = serializers.IntegerField()


class ExecutionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    tool_id = serializers.IntegerField(source='tool_id')
    tool_name = serializers.SerializerMethodField()
    tool_icon = serializers.SerializerMethodField()
    task_id = serializers.CharField()
    status = serializers.CharField()
    progress = serializers.IntegerField()
    error_message = serializers.CharField()
    execution_time_ms = serializers.IntegerField()
    created_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S')
    completed_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', allow_null=True)

    def get_tool_name(self, obj):
        return obj.tool.name if obj.tool_id else ''

    def get_tool_icon(self, obj):
        return obj.tool.icon if obj.tool_id else '🔧'


class TravelRoutePresetSerializer(serializers.ModelSerializer):
    class Meta:
        model = TravelRoutePreset
        fields = ['id', 'name', 'origin', 'destinations', 'description', 'created_at', 'updated_at']


class CareerEnergyAuditSerializer(serializers.ModelSerializer):
    def to_internal_value(self, data):
        # 将空字符串日期转为 None，避免 DRF DateField 校验失败
        if isinstance(data, dict):
            data = data.copy()
            for field in ('next_review_date',):
                if field in data and not data[field]:
                    data[field] = None
        return super().to_internal_value(data)

    class Meta:
        model = CareerEnergyAudit
        fields = '__all__'
        read_only_fields = ['total_score', 'decision', 'advice', 'work_score', 'env_score', 'growth_score', 'body_score', 'created_at']


class QuoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quote
        fields = '__all__'
        read_only_fields = ['review_count', 'created_at']


class DecisionTrackerSerializer(serializers.ModelSerializer):
    """决策追踪器（列表带记录数 / 剩余天数）"""

    record_count = serializers.SerializerMethodField()
    days_left = serializers.SerializerMethodField()

    class Meta:
        model = DecisionTracker
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def validate_lean_options(self, value):
        """自定义倾向选项：留空/null/空数组用默认；给了则要求 2–6 项非空去重文本"""
        if value is None or value == '' or value == []:
            return None
        if not isinstance(value, list):
            raise serializers.ValidationError('lean_options 需为字符串数组')
        cleaned: list[str] = []
        for item in value:
            text = str(item).strip()
            if not text:
                raise serializers.ValidationError('倾向选项不能为空字符串')
            if len(text) > 20:
                raise serializers.ValidationError('单个倾向选项不超过 20 个字')
            if text not in cleaned:
                cleaned.append(text)
        if len(cleaned) < 2:
            raise serializers.ValidationError('自定义倾向选项至少 2 项')
        if len(cleaned) > 6:
            raise serializers.ValidationError('自定义倾向选项最多 6 项')
        return cleaned

    def get_record_count(self, obj) -> int:
        return getattr(obj, 'record_count', None) or obj.records.count()

    def get_days_left(self, obj) -> int:
        from django.utils import timezone
        return (obj.end_date - timezone.localdate()).days


class DecisionRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = DecisionRecord
        fields = '__all__'
        read_only_fields = ['created_at']

    def validate(self, attrs):
        """tendency 必须属于所属追踪的倾向选项（默认三项或自定义文字）"""
        tracker = attrs.get('tracker') or getattr(self.instance, 'tracker', None)
        if tracker is None:
            raise serializers.ValidationError({'tracker': '必须指定所属决策追踪'})
        allowed_keys = [k for k, _ in tracker.tendency_options()]
        tendency = attrs.get('tendency') or getattr(self.instance, 'tendency', None)
        if tendency not in allowed_keys:
            raise serializers.ValidationError(
                {'tendency': f'倾向须是以下之一：{ "、".join(allowed_keys) }'}
            )
        return attrs


class HealthSelfCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthSelfCheck
        fields = '__all__'
        read_only_fields = ['health_score', 'last_score', 'score_change', 'alert_items', 'created_at']


class FreeSpendingCalculatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = FreeSpendingCalculator
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class FixedExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = FixedExpense
        fields = '__all__'
        read_only_fields = ['id', 'total_monthly', 'total_daily', 'total_yearly', 'created_at']


class HourlyWageRecordSerializer(serializers.ModelSerializer):
    salary_monthly = serializers.SerializerMethodField()
    extra_monthly = serializers.SerializerMethodField()
    total_monthly = serializers.SerializerMethodField()
    total_daily = serializers.SerializerMethodField()

    class Meta:
        model = HourlyWageRecord
        fields = '__all__'
        read_only_fields = ['id', 'work_days_per_month', 'work_hours_per_day', 'total_hours_per_month', 'hourly_wage', 'created_at']

    def get_salary_monthly(self, obj):
        return float(obj.monthly_salary)

    def get_extra_monthly(self, obj):
        return float(_extra_income_monthly(obj.extra_incomes))

    def get_total_monthly(self, obj):
        return round(float(obj.monthly_salary) + float(_extra_income_monthly(obj.extra_incomes)), 2)

    def get_total_daily(self, obj):
        return round((float(obj.monthly_salary) + float(_extra_income_monthly(obj.extra_incomes))) / 30, 2)


class ElectricityRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ElectricityRecord
        fields = '__all__'
        read_only_fields = ['id', 'interval_usage', 'interval_days', 'daily_avg', 'month_usage', 'created_at']


class AskAnswerSerializer(serializers.ModelSerializer):
    """AI 问答库·回答（同一 AI 不同会话 = 独立一条；parent 非空 = 对某条回答的追问）"""

    class Meta:
        model = AskAnswer
        fields = [
            'id', 'topic', 'parent', 'question', 'ai', 'session', 'answer', 'asked_at',
            'verdict', 'note', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class AskSceneSerializer(serializers.ModelSerializer):
    """AI 问答库·业务场景容器"""

    topic_count = serializers.SerializerMethodField()

    class Meta:
        model = AskScene
        fields = ['id', 'name', 'description', 'sort', 'topic_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_topic_count(self, obj) -> int:
        return getattr(obj, 'topic_count', None) or obj.topics.count()


class AskTopicSerializer(serializers.ModelSerializer):
    """AI 问答库·主题（nested answers 供详情对照）"""

    answers = AskAnswerSerializer(many=True, read_only=True)
    answer_count = serializers.SerializerMethodField()
    latest_asked_at = serializers.SerializerMethodField()
    accepted_count = serializers.SerializerMethodField()
    scene_name = serializers.SerializerMethodField()

    class Meta:
        model = AskTopic
        fields = [
            'id', 'scene', 'scene_name', 'title', 'question', 'background', 'tags',
            'answers', 'answer_count', 'latest_asked_at', 'accepted_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_scene_name(self, obj) -> str:
        return obj.scene.name if obj.scene_id else ''

    def get_answer_count(self, obj) -> int:
        return getattr(obj, 'answer_count', None) or obj.answers.count()

    def get_latest_asked_at(self, obj):
        ans = obj.answers.order_by('-asked_at').first()
        return ans.asked_at if ans else None

    def get_accepted_count(self, obj) -> int:
        return obj.answers.filter(verdict='采纳').count()
