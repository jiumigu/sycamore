"""综合进度看板 — 响应结构序列化器"""

from rest_framework import serializers


class ModuleEntrySerializer(serializers.Serializer):
    module = serializers.CharField()
    label = serializers.CharField()
    color = serializers.CharField()
    points = serializers.FloatField()
    raw_value = serializers.FloatField()
    unit = serializers.CharField()


class YearlyOverviewSerializer(serializers.Serializer):
    year = serializers.CharField()
    total_points = serializers.FloatField()
    yearly_target = serializers.FloatField()
    monthly_target = serializers.FloatField()
    progress_percent = serializers.FloatField()
    remaining_points = serializers.FloatField()
    modules = ModuleEntrySerializer(many=True)


class MonthlyDetailSerializer(serializers.Serializer):
    year = serializers.CharField()
    month = serializers.IntegerField()
    total_points = serializers.FloatField()
    month_target = serializers.FloatField()
    target_percent = serializers.FloatField()
    modules = ModuleEntrySerializer(many=True)


class TrendEntrySerializer(serializers.Serializer):
    month = serializers.IntegerField()
    total_points = serializers.FloatField()
    month_target = serializers.FloatField()
    wealth = serializers.FloatField()
    health = serializers.FloatField()
    times = serializers.FloatField()
    words = serializers.FloatField()
    sugar = serializers.FloatField()
    travel = serializers.FloatField()
    book = serializers.FloatField()


class RadarIndicatorSerializer(serializers.Serializer):
    name = serializers.CharField()
    max = serializers.FloatField()
    color = serializers.CharField()


class RadarSerializer(serializers.Serializer):
    year = serializers.IntegerField()
    indicators = RadarIndicatorSerializer(many=True)
    values = serializers.ListField(child=serializers.FloatField())


class RecordEntrySerializer(serializers.Serializer):
    """通用原始记录条目"""
    pass  # 动态字段，不做严格校验


class QuarterlyModuleSerializer(serializers.Serializer):
    module = serializers.CharField()
    label = serializers.CharField()
    color = serializers.CharField()
    points = serializers.FloatField()
    raw_value = serializers.FloatField()
    unit = serializers.CharField()
    prev_quarter_points = serializers.FloatField()
    qoq_change = serializers.FloatField()
    last_year_points = serializers.FloatField()
    yoy_change = serializers.FloatField()


class QuarterlyReportSerializer(serializers.Serializer):
    year = serializers.IntegerField()
    quarter = serializers.IntegerField()
    label = serializers.CharField()
    total_points = serializers.FloatField()
    quarter_target = serializers.FloatField()
    target_percent = serializers.FloatField()
    prev_quarter_total = serializers.FloatField()
    qoq_change = serializers.FloatField()
    last_year_total = serializers.FloatField()
    yoy_change = serializers.FloatField()
    modules = QuarterlyModuleSerializer(many=True)


class QuestionSerializer(serializers.Serializer):
    question_key = serializers.CharField()
    question_category = serializers.CharField()
    question_text = serializers.CharField()
    related_module = serializers.CharField()


class AnswerSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    question_key = serializers.CharField()
    question_text = serializers.CharField(read_only=True)
    question_category = serializers.CharField(read_only=True)
    answer_text = serializers.CharField()
    related_module = serializers.CharField(read_only=True)
    action_taken = serializers.BooleanField(default=False)
    updated_at = serializers.CharField(read_only=True)


class InsightSerializer(serializers.Serializer):
    type = serializers.CharField()
    icon = serializers.CharField()
    message = serializers.CharField()
