"""自我运转 · 序列化器

🔴 三条约定（照抄设计稿 §7.5 / §4.1）：

1. **快照字段只读** —— `Period.readings` / `status` / `config_fingerprint` / `period_*`
   全部 `read_only`；试图写它们由视图层显式**拒绝**（405），**不静默忽略**。
2. **`source_kind='auto'` 不提供补记入口** —— 序列化器直接拒收该 metric 的 checkin
   （不是渲染出来再报错）。
3. **空数组 = 清空，不传 = 不动** —— 这是项目既有约定，本模块沿用。
"""
from rest_framework import serializers

from .constants import (
    AGG_CHOICES, DIRECTION_CHOICES, METRIC_STATUS_CHOICES, PAUSE_REASON_CHOICES,
    PERIOD_STATUS_CHOICES, PERIOD_TYPE_CHOICES, PLAN_SCOPE_CHOICES,
    SOURCE_KIND_CHOICES, STAGE_STATUS_CHOICES,
)
from .models import (
    SelfRunCheckin, SelfRunMetric, SelfRunMetricLog, SelfRunMetricPlan,
    SelfRunPeriod, SelfRunStage, SelfRunTemplate,
)


# ══════════════════════════════════════════════════════════════
# 出参：7 张表
# ══════════════════════════════════════════════════════════════

class SelfRunTemplateSerializer(serializers.ModelSerializer):
    """模板库。`key` **只读**（它是 `Metric.template_key` 的指向，后端生成）。"""

    class Meta:
        model = SelfRunTemplate
        fields = '__all__'
        read_only_fields = ('key', 'created_at', 'updated_at')


class SelfRunMetricPlanSerializer(serializers.ModelSerializer):
    metric_name = serializers.CharField(source='metric.name', read_only=True)
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)

    class Meta:
        model = SelfRunMetricPlan
        fields = '__all__'
        read_only_fields = ('metric', 'created_at', 'updated_at')

class SelfRunStageSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    pause_reason_display = serializers.CharField(source='get_pause_reason_display', read_only=True)
    metric_count = serializers.SerializerMethodField()
    elapsed_days = serializers.SerializerMethodField()

    class Meta:
        model = SelfRunStage
        fields = '__all__'
        # 🔴 `start_date` 生效后不可改（改它会让已完成周期「掉出」阶段）
        read_only_fields = ('start_date', 'created_at', 'updated_at')

    def get_metric_count(self, obj):
        return obj.metrics.filter(status='active').count()

    def get_elapsed_days(self, obj):
        """现算不落库（判据：以后重算得出同样结果吗 —— 得得出，所以不落）。"""
        from django.utils import timezone
        end = obj.end_date or timezone.localdate()
        return max((end - obj.start_date).days + 1, 0)


class SelfRunMetricSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = SelfRunMetric
        fields = '__all__'
        read_only_fields = ('stage', 'created_at', 'updated_at')


class SelfRunMetricLogSerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    metric_name = serializers.CharField(source='metric.name', read_only=True)

    class Meta:
        model = SelfRunMetricLog
        fields = '__all__'


class SelfRunPeriodSerializer(serializers.ModelSerializer):
    """周期快照。**冻结字段只读**（视图层对它们的写入请求回 405）。"""

    status_display = serializers.SerializerMethodField()
    stage_name = serializers.CharField(source='stage.name', read_only=True)

    class Meta:
        model = SelfRunPeriod
        fields = '__all__'
        read_only_fields = (
            'stage', 'period_type', 'period_key', 'period_start', 'period_end',
            'is_partial', 'status', 'readings', 'config_fingerprint',
            'skipped_metric_ids', 'closed_at', 'is_backfilled', 'backfilled_at',
            'reopened_at', 'reopen_count', 'reopen_reason', 'review_edits',
            'created_at', 'updated_at',
        )

    def get_status_display(self, obj):
        if not obj.status:
            return '进行中'
        return dict(PERIOD_STATUS_CHOICES).get(obj.status, obj.status)


class SelfRunCheckinSerializer(serializers.ModelSerializer):
    metric_name = serializers.CharField(source='metric.name', read_only=True)
    unit = serializers.CharField(source='metric.unit', read_only=True)

    class Meta:
        model = SelfRunCheckin
        fields = '__all__'
        read_only_fields = ('created_at',)


# ══════════════════════════════════════════════════════════════
# 入参：T1 配置
# ══════════════════════════════════════════════════════════════

class MetricInputSerializer(serializers.Serializer):
    """配置向导 step 3 的单条 KPI（字段大多可省 —— 省了就取模板值）。"""

    template_key = serializers.CharField(max_length=40, required=False, allow_blank=True)
    name = serializers.CharField(max_length=100, required=False)
    period_type = serializers.ChoiceField(choices=PERIOD_TYPE_CHOICES, required=False)
    unit = serializers.CharField(max_length=20, required=False)
    direction = serializers.ChoiceField(choices=DIRECTION_CHOICES, required=False)
    # ⚠️ 允许 null：「只有目标没有底线」是合理状态；两条都空 ⇒ unconfigured
    goal_value = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True,
    )
    floor_value = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True,
    )
    goal_why = serializers.CharField(max_length=200, required=False, allow_blank=True)
    floor_why = serializers.CharField(max_length=200, required=False, allow_blank=True)
    agg = serializers.ChoiceField(choices=AGG_CHOICES, required=False)
    source_kind = serializers.ChoiceField(choices=SOURCE_KIND_CHOICES, required=False)
    source_config = serializers.JSONField(required=False)
    sort_order = serializers.IntegerField(required=False)


class StageCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False, allow_null=True)
    note = serializers.CharField(max_length=200, required=False, allow_blank=True)
    metrics = MetricInputSerializer(many=True)


class MetricPreviewSerializer(serializers.Serializer):
    period_type = serializers.ChoiceField(choices=PERIOD_TYPE_CHOICES, required=False)
    name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    unit = serializers.CharField(max_length=20, required=False, allow_blank=True)
    direction = serializers.ChoiceField(choices=DIRECTION_CHOICES, required=False)
    agg = serializers.ChoiceField(choices=AGG_CHOICES, required=False)
    source_kind = serializers.ChoiceField(choices=SOURCE_KIND_CHOICES, required=False)
    source_config = serializers.JSONField(required=False)
    goal_value = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True,
    )
    floor_value = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True,
    )
    floor_options = serializers.ListField(
        child=serializers.FloatField(), required=False,
    )
    periods = serializers.IntegerField(required=False, min_value=1, max_value=52)


class MetricPatchSerializer(serializers.Serializer):
    """改 KPI 配置。`reason` 是**必问**的（校准 or 状态）—— 系统不判断，只记录。"""

    goal_value = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True,
    )
    floor_value = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True,
    )
    goal_why = serializers.CharField(max_length=200, required=False, allow_blank=True)
    floor_why = serializers.CharField(max_length=200, required=False, allow_blank=True)
    source_config = serializers.JSONField(required=False)
    agg = serializers.ChoiceField(choices=AGG_CHOICES, required=False)
    direction = serializers.ChoiceField(choices=DIRECTION_CHOICES, required=False)
    name = serializers.CharField(max_length=100, required=False)
    unit = serializers.CharField(max_length=20, required=False)
    sort_order = serializers.IntegerField(required=False)
    reason = serializers.CharField(max_length=20, required=False, allow_blank=True)
    reason_note = serializers.CharField(max_length=200, required=False, allow_blank=True)


class StagePatchSerializer(serializers.Serializer):
    """阶段只能改 `note` / `end_date`（`start_date` 只读）。"""

    note = serializers.CharField(max_length=200, required=False, allow_blank=True)
    end_date = serializers.DateField(required=False, allow_null=True)


class CheckinInputSerializer(serializers.Serializer):
    """手工登记。

    🔴 `source_kind='auto'` 的条目**没有补记入口** —— 自动取错了要去改源
       （「一个写口」原则），不是在这里覆盖。
    🔴 登记只能填**正数**；撤销走 `DELETE`（补负值）。
    """

    metric = serializers.PrimaryKeyRelatedField(queryset=SelfRunMetric.objects.all())
    checkin_date = serializers.DateField(required=False)
    value = serializers.DecimalField(max_digits=12, decimal_places=2)
    note = serializers.CharField(max_length=200, required=False, allow_blank=True)

    def validate(self, attrs):
        metric = attrs['metric']
        if metric.source_kind == 'auto':
            raise serializers.ValidationError({
                'metric': f'「{metric.name}」是自动取数项，没有补记入口'
                          f'（自动取错了请去改数据源）。',
            })
        if metric.status != 'active':
            raise serializers.ValidationError({'metric': '这条 KPI 已退役，不能登记。'})
        if attrs['value'] is None or attrs['value'] <= 0:
            raise serializers.ValidationError({
                'value': '登记必须填正数；要撤销某一笔请用「撤销这一笔」。',
            })
        return attrs


class PeriodCloseSerializer(serializers.Serializer):
    period_type = serializers.ChoiceField(choices=PERIOD_TYPE_CHOICES)
    period_key = serializers.CharField(max_length=20)
    skipped_metric_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False,
    )
    answer_sheet = serializers.JSONField(required=False)


class PeriodReviewSerializer(serializers.Serializer):
    """归档后可写的**只有这两项**（你写的字是记忆型，不是数据型）。"""

    review_text = serializers.CharField(required=False, allow_blank=True)
    answer_sheet = serializers.JSONField(required=False)


class ReopenSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=200)


class HeartbeatSerializer(serializers.Serializer):
    seen = serializers.BooleanField(required=False, default=True)


class PauseSerializer(serializers.Serializer):
    reason = serializers.ChoiceField(choices=PAUSE_REASON_CHOICES, required=False)
    resume_at = serializers.DateField(required=False, allow_null=True)
    note = serializers.CharField(max_length=200, required=False, allow_blank=True)


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=200, required=False, allow_blank=True)


class SummarySerializer(serializers.Serializer):
    text = serializers.CharField(required=False, allow_blank=True)
    end_date = serializers.DateField(required=False, allow_null=True)


class StageCopySerializer(serializers.Serializer):
    from_stage_id = serializers.IntegerField()
    name = serializers.CharField(max_length=100)
    start_date = serializers.DateField(required=False)


# ══════════════════════════════════════════════════════════════
# 入参：T1 模板库（**可自定义**）
# ══════════════════════════════════════════════════════════════

class TemplateInputSerializer(serializers.Serializer):
    """新建模板。`key` 由后端生成（`custom_<8位>`），**不收** ——
    前端自己编 key 的话，撞了就是「来源指向别人的模板」。"""

    name = serializers.CharField(max_length=100)
    period_type = serializers.ChoiceField(choices=PERIOD_TYPE_CHOICES)
    unit = serializers.CharField(max_length=20, required=False, allow_blank=True)
    direction = serializers.ChoiceField(choices=DIRECTION_CHOICES, required=False)
    goal_value = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True,
    )
    floor_value = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True,
    )
    goal_why = serializers.CharField(max_length=200, required=False, allow_blank=True)
    floor_why = serializers.CharField(max_length=200, required=False, allow_blank=True)
    agg = serializers.ChoiceField(choices=AGG_CHOICES, required=False)
    source_kind = serializers.ChoiceField(choices=SOURCE_KIND_CHOICES, required=False)
    source_config = serializers.JSONField(required=False)
    sort_order = serializers.IntegerField(required=False)


class TemplatePatchSerializer(TemplateInputSerializer):
    """改模板 —— 字段全部可选（`key` 依旧不可改）。"""

    name = serializers.CharField(max_length=100, required=False)
    period_type = serializers.ChoiceField(choices=PERIOD_TYPE_CHOICES, required=False)


# ══════════════════════════════════════════════════════════════
# 入参：T1b 按期设定（「修订下一周 / 下一月」）
# ══════════════════════════════════════════════════════════════

class PlanSetSerializer(serializers.Serializer):
    """设定某一条 KPI 在某一期的目标。

    🔴 `goal_value` / `floor_value` **必填、但可为 `null`** ——
       「省略」与「显式传 null」是两件事：省略会让「我没动这条底线」
       变成「把底线删了」，而且**不报错**。要求显式传是有意为之。
    """

    period_key = serializers.CharField(max_length=20)
    scope = serializers.ChoiceField(choices=PLAN_SCOPE_CHOICES, required=False, default='single')
    goal_value = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    floor_value = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    goal_why = serializers.CharField(max_length=200, required=False, allow_blank=True)
    floor_why = serializers.CharField(max_length=200, required=False, allow_blank=True)
    note = serializers.CharField(max_length=200, required=False, allow_blank=True)


# 供视图层复用的清单（避免两处各写一份）
FROZEN_PERIOD_FIELDS = (
    'readings', 'status', 'config_fingerprint', 'period_type', 'period_key',
    'period_start', 'period_end', 'is_partial', 'closed_at', 'stage',
)
