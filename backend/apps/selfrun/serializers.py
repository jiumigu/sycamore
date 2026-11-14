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
    status_display = serializers.SerializerMethodField()
    stage_kind_display = serializers.CharField(source='get_stage_kind_display', read_only=True)
    pause_reason_display = serializers.CharField(source='get_pause_reason_display', read_only=True)
    metric_count = serializers.SerializerMethodField()
    elapsed_days = serializers.SerializerMethodField()
    days_label = serializers.SerializerMethodField()
    range_label = serializers.SerializerMethodField()
    # 阶段分两层后的三个派生字段（**都不落库**）
    parent_name = serializers.SerializerMethodField()
    children_count = serializers.SerializerMethodField()
    is_long_stage = serializers.SerializerMethodField()

    class Meta:
        model = SelfRunStage
        fields = '__all__'
        # 🔴 `start_date` 生效后不可改（改它会让已完成周期「掉出」阶段）
        read_only_fields = ('start_date', 'created_at', 'updated_at')

    def get_metric_count(self, obj):
        return obj.metrics.filter(status='active').count()

    def get_parent_name(self, obj):
        """上级阶段名（顶级阶段为 `None`）。页头面包屑用。"""
        return obj.parent.name if obj.parent_id else None

    def get_children_count(self, obj):
        return obj.children.count()

    def get_is_long_stage(self, obj):
        """长阶段 = 顶级 + **一条 KPI 都没有**（与 `get_open_long_stage()` 同一判据）。

        ⚠️ 不用「有没有孩子」判：长阶段可以先建、后挂小阶段，那段空窗期它同样是长阶段。
        ⚠️ 用「任何状态的 metric」而不是「active 的」：一个 KPI 全部退役的叶子阶段
           曾经有过 KPI，不该因为退役就变成「长阶段」。
        🔴 记录型阶段**永远不是长阶段**（v3.64.56）：它同样「顶级 + 零 KPI」，
           不加这一条，一条「小学期」就会被判成长阶段 ——
           于是它出现在长阶段下拉、账本入口里，读起来就是「我的小学期有个账本」。
        """
        if obj.stage_kind != 'run':
            return False
        return obj.parent_id is None and not obj.metrics.exists()

    def get_status_display(self, obj):
        """委托 `services.stage_status_display` —— 显示词只在那份代码里定一次。

        ⚠️ 舞台账本（`services.stage_ledger`）的子阶段行也印它，
           两处各写一份三元表达式，迟早在一个边界上分叉。
        """
        from .services import stage_status_display

        return stage_status_display(obj)

    def get_elapsed_days(self, obj):
        """「今天第几天」委托 `services.stage_elapsed_days`（账本 `range` 同一个数）。

        🔴 取 `min(今天, 终点)`、clamp 到 0 —— 具体理由见 service 里的注释。
        """
        from .services import stage_elapsed_days

        return stage_elapsed_days(obj)

    def get_range_label(self, obj):
        """委托 `services.stage_range_label`（账本子阶段行也印同一句）。"""
        from .services import stage_range_label

        return stage_range_label(obj)

    def get_days_label(self, obj):
        """委托 `services.stage_days_label`（三种态用三种词，理由见那里）。"""
        from .services import stage_days_label

        return stage_days_label(obj)


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
    metrics = MetricInputSerializer(many=True, required=False)
    # 🔴 形态必须**显式声明**：`metrics` 空 + 没声明 ⇒ 400，不靠「有没有 KPI」猜意图
    #    （猜错了会得到一个「看着正常、其实永不判定」的阶段）。
    is_long_stage = serializers.BooleanField(required=False, default=False)
    # 挂在哪个长阶段下（两层封顶）；不传 = 顶级阶段
    parent = serializers.IntegerField(required=False, allow_null=True)
    # 只长阶段用：目前只有 `pool_principal`
    ledger_config = serializers.JSONField(required=False)


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
    """改 KPI 配置。`reason` 是**必问**的（校准 or 状态）—— 系统不判断，只记录。

    🔴 `source_kind` 也在这里（v3.64.31）：建完 KPI 才发现「这条该自动取数」
       时，以前只能退役重建 —— 而退役会把手工登记一起带走。
    """

    goal_value = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True,
    )
    floor_value = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True,
    )
    goal_why = serializers.CharField(max_length=200, required=False, allow_blank=True)
    floor_why = serializers.CharField(max_length=200, required=False, allow_blank=True)
    source_kind = serializers.ChoiceField(choices=SOURCE_KIND_CHOICES, required=False)
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


class RecordStageInputSerializer(serializers.Serializer):
    """建一条**记录型**阶段（谋生期 / 小学期 / 中学期 …）。

    🔴 没有 `metrics` / `is_long_stage` / `ledger_config` 三个字段 ——
       记录型不跑 KPI、不汇总、没有账本。给了这些字段等于暗示它能配，
       而服务层会直接拒绝（`create_record_stage` 只认这里列的五个）。
    """

    name = serializers.CharField(max_length=100)
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)
    note = serializers.CharField(max_length=200, required=False, allow_blank=True)
    # 挂在哪一段下面（例如小学/中学/高中/大学都挂在「求学阶段」下）；不传 = 顶级
    parent = serializers.IntegerField(required=False, allow_null=True)


class RecordStagePatchSerializer(serializers.Serializer):
    """改一条记录型阶段。

    🔴 与 `StagePatchSerializer` 的差别是**允许改 `start_date`**：
       记录型没有 Period，改日期不会让任何已完成周期掉出阶段 ——
       而补录人生阶段时把年份写错是常态。
    ⚠️ 也**不收** `status` / `stage_kind`：那会把记录型改成「进行中但永不判定」的幽灵。
    """

    name = serializers.CharField(max_length=100, required=False)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False, allow_null=True)
    note = serializers.CharField(max_length=200, required=False, allow_blank=True)


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
