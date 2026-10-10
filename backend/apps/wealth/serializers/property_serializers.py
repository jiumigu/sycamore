"""物件资产 · 序列化器

两类分开：
    Form 结尾 = **入参**（校验 + 归一化）
    其余      = **出参**（展示，含派生值）

⚠️ `allow_null` 是**对着模型列**写的，不是对着「我这版想接受什么」写的：
   模型列 `null=True` 才允许 `allow_null=True`。写在 NOT NULL 列上 ⇒
   DRF 放行、MySQL 拒收 ⇒ `IntegrityError` 变 500，而前端只拿到一句
   兜底的「保存失败」，连是哪个字段错了都看不出来。
"""

from rest_framework import serializers

from ..constants import PROPERTY_STATUS_SCRAPPED
from ..models import WealthProperty, WealthPropertyCategory


# ──────────────────────────────────────────────────────────────
# 类别
# ──────────────────────────────────────────────────────────────

class PropertyCategorySerializer(serializers.Serializer):
    """类别展示（出参）。`property_count` 让「类别维护」页能看出谁还在被用 ——
    也顺便解释了为什么它删不掉（有引用就是 400）。"""

    id = serializers.IntegerField()
    name = serializers.CharField()
    icon = serializers.CharField()
    default_lifespan_months = serializers.IntegerField(allow_null=True)
    sort_order = serializers.IntegerField()
    note = serializers.CharField()
    property_count = serializers.IntegerField()


class PropertyCategoryFormSerializer(serializers.ModelSerializer):
    """类别新增 / 编辑（入参）"""

    class Meta:
        model = WealthPropertyCategory
        fields = ['id', 'name', 'icon', 'default_lifespan_months', 'sort_order', 'note']
        read_only_fields = ['id']
        extra_kwargs = {
            'name': {'required': True, 'allow_blank': False},
            'icon': {'required': False, 'allow_blank': True},
            # 可空：用户可以把系统预填的默认年限撤掉
            'default_lifespan_months': {'required': False, 'allow_null': True},
            'note': {'required': False, 'allow_blank': True},
        }


class PropertySeedResultSerializer(serializers.Serializer):
    created = serializers.IntegerField()
    updated = serializers.IntegerField()
    skipped = serializers.IntegerField()
    categories = PropertyCategorySerializer(many=True)


# ──────────────────────────────────────────────────────────────
# 物件
# ──────────────────────────────────────────────────────────────

class PropertyIssueSerializer(serializers.Serializer):
    """算不出的原因 —— 前端点开「—」看到的就是它。"""

    code = serializers.CharField()
    label = serializers.CharField()


class PropertyItemSerializer(serializers.Serializer):
    """物件展示（出参）。

    刻意用普通 `Serializer` 而不是 `ModelSerializer`：
    这里有一半字段是**算出来的**，不是列 —— 让这件事在代码里看得见。
    """

    id = serializers.IntegerField()
    name = serializers.CharField()
    spec = serializers.CharField()
    location = serializers.CharField()
    category_id = serializers.IntegerField()
    category_name = serializers.CharField()
    purchase_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, allow_null=True,
    )
    purchase_date = serializers.DateField(allow_null=True)
    lifespan_months = serializers.IntegerField(allow_null=True)
    status = serializers.CharField()
    condition = serializers.CharField()
    scrapped_date = serializers.DateField(allow_null=True)
    dispose_note = serializers.CharField()
    note = serializers.CharField()
    tags = serializers.JSONField()
    created_at = serializers.DateTimeField(allow_null=True)
    updated_at = serializers.DateTimeField(allow_null=True)

    # ── 以下全部由 property_calc 算出来，前端**一个都不重算** ──
    age_months = serializers.IntegerField(allow_null=True)
    remaining_months = serializers.IntegerField(allow_null=True)   # 可为负 = 超期
    monthly_depreciation = serializers.DecimalField(
        max_digits=12, decimal_places=2, allow_null=True,
    )
    current_value = serializers.DecimalField(
        max_digits=12, decimal_places=2, allow_null=True,
    )
    # 净值为 0 的**来源**：'depreciated'（真折完了）/ 'broken'（坏了按 0 计），
    # 净值不为 0 时为 null。界面上要据此说「已折完」还是「损坏归 0」——
    # 让前端拿 condition 自己判，等于把口径搬出后端，下次改口径必然漏一份。
    zero_reason = serializers.CharField(allow_null=True)
    ref_date = serializers.DateField(allow_null=True)
    is_overdue = serializers.BooleanField()
    overdue_months = serializers.IntegerField()
    issues = PropertyIssueSerializer(many=True)


class PropertyItemFormSerializer(serializers.ModelSerializer):
    """物件新增 / 编辑（入参）—— 状态与日期的耦合在这里收口。

    ⚠️ 置空这类「口径级」不变量写在**服务端**，不指望客户端记得送 null；
       客户端送了也照收，服务端自己归一（同 `SurvivalItemFormSerializer` 对
       「按次三兄弟」的处置）。
    """

    category_id = serializers.IntegerField()

    class Meta:
        model = WealthProperty
        fields = [
            'id', 'category_id', 'name', 'spec', 'location',
            'purchase_amount', 'purchase_date', 'lifespan_months',
            'status', 'condition', 'scrapped_date', 'dispose_note',
            'note', 'tags',
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'name': {'required': True, 'allow_blank': False},
            'spec': {'required': False, 'allow_blank': True},
            'location': {'required': False, 'allow_blank': True},
            'purchase_amount': {'required': False, 'allow_null': True},
            'purchase_date': {'required': False, 'allow_null': True},
            'lifespan_months': {'required': False, 'allow_null': True},
            'scrapped_date': {'required': False, 'allow_null': True},
            'dispose_note': {'required': False, 'allow_blank': True},
            'note': {'required': False, 'allow_blank': True},
        }

    def validate_purchase_amount(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('购买金额不能为负数')
        return value

    def validate_lifespan_months(self, value):
        # 0 会让「月折旧 = 金额 ÷ 年限」除零 —— 在这里拦，而不是在计算层兜
        if value is not None and value <= 0:
            raise serializers.ValidationError('计划使用年限必须大于 0')
        return value

    def _resolved(self, attrs, field):
        """取「这次要提交的值」：优先看入参，没有就看原对象（编辑场景）。"""
        if field in attrs:
            return attrs[field]
        return getattr(self.instance, field, None)

    def validate(self, attrs):
        status = self._resolved(attrs, 'status') or 'in_use'

        # ── ① 不在报废态 ⇒ 报废相关字段一律置空 ──
        # 🔴 刻意**置成空值**而不是「忽略不传」：否则从「已报废」改回「在用」之后，
        #    那两个格子还留着旧值，形成「状态是在用、却带着报废日期」的自相矛盾行 ——
        #    而那种行在列表里看起来完全正常。
        if status != PROPERTY_STATUS_SCRAPPED:
            attrs['scrapped_date'] = None
            attrs['dispose_note'] = ''

        # ── ② 报废日不得早于购买日 ──
        scrapped = self._resolved(attrs, 'scrapped_date')
        purchased = self._resolved(attrs, 'purchase_date')
        if (
            status == PROPERTY_STATUS_SCRAPPED
            and scrapped and purchased and scrapped < purchased
        ):
            raise serializers.ValidationError(
                {'scrapped_date': '报废日期不能早于购买日期'},
            )

        return attrs


# ──────────────────────────────────────────────────────────────
# 汇总与元信息
# ──────────────────────────────────────────────────────────────

class PropertyTotalBlockSerializer(serializers.Serializer):
    """一个合计块的四个数 —— **缺一不可**。

    只给 `total` 的话，界面没法把「少算了」摆出来：总额看着小一点、
    件数却是全的，两个数都对不上，还没人会去查。
    """

    total = serializers.DecimalField(max_digits=14, decimal_places=2)
    counted = serializers.IntegerField()
    unpriced_count = serializers.IntegerField()
    unvalued_count = serializers.IntegerField()


class PropertyNetValueBlockSerializer(PropertyTotalBlockSerializer):
    """净值块 = 合计块 + `broken_count`（因损坏被按 0 计的件数）。

    ⚠️ 刻意**继承**、而不是把 `broken_count` 加进 `PropertyTotalBlockSerializer`：
       那个块被「原值合计」共用，而原值合计与状况无关 —— 买的时候花了多少钱，
       不会因为后来坏了就变。塞进去就会多出一个恒为 0 的字段，
       而「一个恒为 0 的字段」最容易让人以为「这个数坏了」。
    ⚠️ 也不用 `ListField` 之类绕过键名清单：前端气泡与副行都按**键名**取值，
       少一个键会静默渲染不出来（硬坑⑪）。
    """

    broken_count = serializers.IntegerField()


class PropertySummarySerializer(serializers.Serializer):
    in_use_count = serializers.IntegerField()
    scrapped_count = serializers.IntegerField()
    total_amount = PropertyTotalBlockSerializer()
    in_use_net_value = PropertyNetValueBlockSerializer()


class PropertyOptionSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()


class PropertyMetricMetaSerializer(serializers.Serializer):
    """口径气泡的单一结构 —— 前端零硬编码（`bands` 恒为空数组，见 calc）"""

    key = serializers.CharField()
    label = serializers.CharField()
    unit = serializers.CharField()
    direction = serializers.CharField()
    formula = serializers.CharField()
    note = serializers.ListField(child=serializers.CharField())
    bands = serializers.ListField(child=serializers.JSONField())


class PropertyMetaSerializer(serializers.Serializer):
    statuses = PropertyOptionSerializer(many=True)
    conditions = PropertyOptionSerializer(many=True)
    metric_meta = PropertyMetricMetaSerializer(many=True)
    issue_labels = serializers.DictField(child=serializers.CharField())
    not_in_net_worth_note = serializers.CharField()
    subtitle = serializers.CharField()
