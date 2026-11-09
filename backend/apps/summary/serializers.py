"""综合进度看板 — 响应结构序列化器"""

from rest_framework import serializers
from apps.summary.models import SevenDimConfig


class CoverageSerializer(serializers.Serializer):
    """覆盖率 + 强度（v3.62.43）

    两个分母刻意不同：覆盖率的分母是「该有的期数」，强度的分母是
    「实际有记录的期数」。`pct` / `intensity` 都可以是 null（算不出来），
    **null 不是 0%** —— 前端显示「—」而不是 0。
    """

    period_kind = serializers.CharField()          # 'day' | 'month'
    period_word = serializers.CharField()          # '天' | '月'
    label = serializers.CharField()                # 记录覆盖 / 记账覆盖 / 出行覆盖 / 阅读覆盖
    covered = serializers.IntegerField()
    periods = serializers.IntegerField()
    pct = serializers.FloatField(allow_null=True)
    intensity = serializers.FloatField(allow_null=True)
    intensity_label = serializers.CharField()
    intensity_unit = serializers.CharField()
    recent_covered = serializers.IntegerField(allow_null=True)
    recent_periods = serializers.IntegerField(allow_null=True)
    recent_pct = serializers.FloatField(allow_null=True)


class ModuleEntrySerializer(serializers.Serializer):
    """单维度条目。raw_value/display_value 可为 null（该区间取不到，≠ 0）

    ⚠️ `points` 仍在，但**界面不再展示** —— 它是内部评分单位，
    只用于「对目标达成率」。总览里没有总分。
    """

    module = serializers.CharField()
    label = serializers.CharField()
    color = serializers.CharField()
    points = serializers.FloatField()
    raw_value = serializers.FloatField(allow_null=True)
    display_value = serializers.FloatField(allow_null=True)
    unit = serializers.CharField()
    zero_reason = serializers.CharField(allow_null=True, required=False)
    coverage = CoverageSerializer()
    axis_max = serializers.FloatField(allow_null=True)
    achievement_pct = serializers.FloatField(allow_null=True)


class YearlyOverviewSerializer(serializers.Serializer):
    """年度总览 —— 🔴 没有 total_points / yearly_target（v3.62.43 拆除）"""

    year = serializers.CharField()
    as_of = serializers.CharField()
    window = serializers.DictField()
    modules = ModuleEntrySerializer(many=True)
    weakest = serializers.JSONField(allow_null=True)


class MonthlyDetailSerializer(serializers.Serializer):
    year = serializers.CharField()
    month = serializers.IntegerField()
    window = serializers.DictField()
    modules = ModuleEntrySerializer(many=True)
    weakest = serializers.JSONField(allow_null=True)


class TrendEntrySerializer(serializers.Serializer):
    """月度覆盖率：未来月份各维度为 null（不是 0）"""

    month = serializers.IntegerField()
    is_future = serializers.BooleanField()
    wealth = serializers.FloatField(allow_null=True)
    health = serializers.FloatField(allow_null=True)
    times = serializers.FloatField(allow_null=True)
    words = serializers.FloatField(allow_null=True)
    sugar = serializers.FloatField(allow_null=True)
    travel = serializers.FloatField(allow_null=True)
    book = serializers.FloatField(allow_null=True)


class RadarAxisSerializer(serializers.Serializer):
    module = serializers.CharField()
    name = serializers.CharField()
    color = serializers.CharField()
    # 覆盖率：null = 算不出来（该年还没开始），前端显示「—」
    coverage = serializers.FloatField(allow_null=True)
    achievement = serializers.FloatField(allow_null=True)
    axis_max = serializers.FloatField(allow_null=True)
    covered = serializers.IntegerField()
    periods = serializers.IntegerField()
    period_word = serializers.CharField()
    coverage_label = serializers.CharField()
    intensity = serializers.FloatField(allow_null=True)
    intensity_label = serializers.CharField()
    intensity_unit = serializers.CharField()
    total_display = serializers.FloatField(allow_null=True)
    total_unit = serializers.CharField()
    zero_reason = serializers.CharField(allow_null=True, required=False)


class RadarSerializer(serializers.Serializer):
    """七维雷达：一轴两套值，前端切换镜片，不用二次请求"""

    year = serializers.IntegerField()
    basis_default = serializers.CharField()
    axes = RadarAxisSerializer(many=True)
    values = serializers.ListField(child=serializers.FloatField())


class RecordEntrySerializer(serializers.Serializer):
    """通用原始记录条目"""
    pass  # 动态字段，不做严格校验


class QuarterlyModuleSerializer(serializers.Serializer):
    module = serializers.CharField()
    label = serializers.CharField()
    color = serializers.CharField()
    points = serializers.FloatField()
    raw_value = serializers.FloatField(allow_null=True)
    display_value = serializers.FloatField(allow_null=True)
    unit = serializers.CharField()
    zero_reason = serializers.CharField(allow_null=True, required=False)
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


class SevenDimConfigSerializer(serializers.ModelSerializer):
    """七维封顶配置序列化器"""

    class Meta:
        model = SevenDimConfig
        fields = [
            'id', 'wealth_max', 'health_max', 'times_max',
            'words_max', 'sugar_max', 'travel_max', 'book_max',
            'note', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'is_active', 'created_at']
        extra_kwargs = {
            f: {'min_value': 1, 'required': False}
            for f in ['wealth_max', 'health_max', 'times_max',
                      'words_max', 'sugar_max', 'travel_max', 'book_max']
        }
