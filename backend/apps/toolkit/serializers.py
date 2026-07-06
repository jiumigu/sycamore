from rest_framework import serializers

from .models import CareerEnergyAudit, CityCoordinate, DecisionLog, EnvironmentAudit, FreeSpendingCalculator, HealthSelfCheck, HourlyWageRecord, LanguageTraining, Quote, ReviewRecord, TravelRoutePreset


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


class EnvironmentAuditSerializer(serializers.ModelSerializer):
    class Meta:
        model = EnvironmentAudit
        fields = '__all__'
        read_only_fields = ['total_score', 'verdict', 'created_at']


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


class DecisionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = DecisionLog
        fields = '__all__'
        read_only_fields = ['created_at']


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


class HourlyWageRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = HourlyWageRecord
        fields = '__all__'
        read_only_fields = ['id', 'work_days_per_month', 'work_hours_per_day', 'total_hours_per_month', 'hourly_wage', 'created_at']


class ReviewRecordSerializer(serializers.ModelSerializer):
    review_type_display = serializers.SerializerMethodField()

    class Meta:
        model = ReviewRecord
        fields = '__all__'
        read_only_fields = ['id', 'created_at']

    def get_review_type_display(self, obj):
        return obj.get_review_type_display()


class LanguageTrainingSerializer(serializers.ModelSerializer):
    train_type_display = serializers.SerializerMethodField()

    class Meta:
        model = LanguageTraining
        fields = '__all__'
        read_only_fields = ['id', 'created_at']

    def get_train_type_display(self, obj):
        return obj.get_train_type_display()
