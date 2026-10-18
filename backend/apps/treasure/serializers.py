from rest_framework import serializers

from .constants import (
    CATEGORY_KEYS,
    CATEGORY_LABELS_BY_TYPE,
    SUBJECT_KIND_METHOD,
    SUBJECT_KIND_OPTIONS,
    SUBJECT_KIND_PHYSICAL,
    category_label,
)
from .models import GoodThing


def _as_float(value):
    """Decimal / None → float / None。

    ⚠️ DRF 的 `FloatField` 在 `coerce_to_string=False` 时能吃下 Decimal，
       但在**校验**路径上会报 `TypeError`。一律先转，别指望两边碰巧一致。
    """
    return float(value) if value is not None else None


class GoodThingOptionSerializer(serializers.Serializer):
    """一个下拉选项。`hint` 给「记录对象」那种需要一句解释的项用。"""

    value = serializers.CharField()
    label = serializers.CharField()
    hint = serializers.CharField(required=False)


class TreasureMetaSerializer(serializers.Serializer):
    """口径与枚举的单一出口 —— 前端**不硬编码任何文案或选项**。

    ⚠️ 类别文案**按侧各一套**，所以这里是 `categories_by_type` 而不是一个扁平列表：
       前端拿到 `{好: [...], 歹: [...]}`，按当前 `record_type` 取。
       「🏪 好店」配一条 👎 歹物的那种自相矛盾，源头就是当年只有一份文案。

    ⚠️ `categories_by_type` 用裸 `DictField`（不做嵌套校验）：它是**出参**，
       值就是后端自己的 dict 列表 —— 没必要再过一遍反序列化。
    """

    subject_kind_options = GoodThingOptionSerializer(many=True)
    method_group_options = GoodThingOptionSerializer(many=True)
    categories_by_type = serializers.DictField()
    record_type_options = GoodThingOptionSerializer(many=True)


class GoodThingLinkedFactsSerializer(serializers.Serializer):
    """关联实物后带出的事实（v3.60.32 入口 5）。

    🔴 物件资产侧的值来自 `wealth.services.property_service.get_item()`
       —— 与物件页**同一段代码**算派生值，本序列化器一个都不重算。
    ⚠️ 列表接口不下发本字段（`with_linked_facts` 只在详情时为真）：
       对每条档案各算一次折旧是 N+1，而列表上并不需要这些数。
    """

    kind = serializers.CharField()            # 'property' / 'survival_item'
    name = serializers.CharField()
    purchase_date = serializers.CharField(allow_null=True)
    purchase_amount = serializers.FloatField(allow_null=True)
    age_months = serializers.IntegerField(allow_null=True)
    current_value = serializers.FloatField(allow_null=True)
    quantity = serializers.FloatField(allow_null=True)
    unit_name = serializers.CharField(allow_null=True)
    category_name = serializers.CharField(allow_null=True)


class GoodThingSerializer(serializers.ModelSerializer):
    """好恶物双面档案序列化器

    ## 类别的取数口径（v3.60.32）

    🔴 `category_display` **按 `record_type` 分流**，不再走 `get_category_display()`。
       后者拿不到 `record_type`，永远只能给一份文案 —— 那正是「登记歹物时下拉里
       躺着『好方法』」的成因。文案真源在 `constants.CATEGORY_LABELS_BY_TYPE`。

    ## 🔴 模型上带 `default` 的字段，PUT 不送时会被静默打回默认值

    DRF 在**非 partial 更新**且请求未送该字段时，会用模型 `default` 填进
    `validated_data` —— 于是「没传」变成了「传了默认值」：把一条方法型记录
    改一下名字，`subject_kind` 会**变回「实物」**（那些字段跟着全变）。
    区分这两件事只能看**原始请求体**（`initial_data`），因为在
    `validated_data` 里它们长得一模一样。`_keep_if_absent()` 就是这道护栏。
    """

    category_display = serializers.SerializerMethodField()
    record_type_display = serializers.SerializerMethodField()
    subject_kind_display = serializers.SerializerMethodField()
    method_group_display = serializers.SerializerMethodField()
    has_reason = serializers.SerializerMethodField()
    # 关联实物：`linked_name` 恒定下发（列表也要显示「🔗 物件资产 · 空气炸锅」）
    linked_kind = serializers.SerializerMethodField()
    linked_id = serializers.SerializerMethodField()
    linked_name = serializers.SerializerMethodField()
    linked_facts = serializers.SerializerMethodField()

    class Meta:
        model = GoodThing
        fields = [
            'id', 'user_id', 'record_type', 'record_type_display',
            'subject_kind', 'subject_kind_display', 'name',
            'category', 'category_display', 'method_group', 'method_group_display',
            'scene', 'why_good', 'still_available', 'where_to_find',
            'avoid_reason', 'consequence',
            'property', 'survival_item',
            'linked_kind', 'linked_id', 'linked_name', 'linked_facts',
            'has_reason',
            'tags', 'rating', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    # ──────────────────────────────────────────────────────
    # 读
    # ──────────────────────────────────────────────────────

    def get_category_display(self, obj):
        return category_label(obj.record_type, obj.category) if obj.category else ''

    def get_record_type_display(self, obj):
        return obj.get_record_type_display()

    def get_subject_kind_display(self, obj):
        for option in SUBJECT_KIND_OPTIONS:
            if option['value'] == obj.subject_kind:
                return option['label']
        return obj.subject_kind

    def get_method_group_display(self, obj):
        return obj.method_group or ''

    def get_has_reason(self, obj):
        return obj.has_reason()

    def _linked(self, obj):
        if obj.property_id:
            return 'property', obj.property
        if obj.survival_item_id:
            return 'survival_item', obj.survival_item
        return None, None

    def get_linked_kind(self, obj):
        return self._linked(obj)[0]

    def get_linked_id(self, obj):
        target = self._linked(obj)[1]
        return target.id if target else None

    def get_linked_name(self, obj):
        target = self._linked(obj)[1]
        return target.name if target else None

    def get_linked_facts(self, obj):
        """详情才下发（列表下发等于对每条档案各算一次折旧）。"""
        if not self.context.get('with_linked_facts'):
            return None
        kind, target = self._linked(obj)
        if not kind:
            return None
        if kind == 'property':
            # 🔴 走物件资产自己的服务层 —— 派生值口径不在这里复制一份。
            from apps.wealth.services import property_service

            row = property_service.get_item(target.id)
            if not row:
                return None
            return {
                'kind': 'property', 'name': row['name'],
                'purchase_date': row['purchase_date'],
                'purchase_amount': _as_float(row['purchase_amount']),
                'age_months': row['age_months'],
                'current_value': _as_float(row['current_value']),
                'quantity': None, 'unit_name': None, 'category_name': None,
            }
        # 物品清单侧给的是**列上的原值**（数量 / 单位 / 类别），不是派生值
        # —— 不重算任何口径，所以直接读列。
        return {
            'kind': 'survival_item', 'name': target.name,
            'purchase_date': target.purchase_date,
            'purchase_amount': _as_float(target.purchase_cost),
            'age_months': None, 'current_value': None,
            'quantity': _as_float(target.quantity),
            'unit_name': target.unit.name if target.unit_id else None,
            'category_name': target.category.name if target.category_id else None,
        }

    # ──────────────────────────────────────────────────────
    # 写
    # ──────────────────────────────────────────────────────

    def _keep_if_absent(self, attrs, field):
        """PUT 未送该字段时保留存量值（判据见类文档）。"""
        if self.instance is not None and field not in self.initial_data:
            attrs[field] = getattr(self.instance, field)
        return attrs

    def _resolved(self, attrs, field, default=None):
        """取「这次要提交的值」：优先入参、其次原对象（编辑场景）。"""
        if field in attrs:
            return attrs[field]
        if self.instance is not None:
            return getattr(self.instance, field)
        return default

    def validate(self, attrs):
        # 🔴 必须在改动 attrs 之前先补这两个 —— 它们带模型 default，
        #    PUT 不送时 DRF 已经用 default 填过了，只有 initial_data 能分辨。
        self._keep_if_absent(attrs, 'subject_kind')
        self._keep_if_absent(attrs, 'rating')

        kind = attrs.get('subject_kind') or SUBJECT_KIND_PHYSICAL
        record_type = attrs.get('record_type') or '好'

        # ── ① 记录对象决定「哪个维度必填、哪个必须为空」 ──
        # ⚠️ 置空写在**服务端**：不指望客户端记得送空串。前端表单若在切到
        #    「方法」时留着上一次的类别，会造出一条「方法 + 类别=吃」的怪行，
        #    而它在列表里看起来完全正常（同项目「按次三兄弟」的处置）。
        if kind == SUBJECT_KIND_METHOD:
            attrs['category'] = ''
        else:
            attrs['method_group'] = ''
            category = self._resolved(attrs, 'category', '')
            if not category:
                raise serializers.ValidationError({'category': '请选择类别'})
            # ⚠️ 当前两侧的 key 是**同一套**，所以下面这条与上一条等价；
            #    留着它是为了「哪天两侧 key 分家」时这里能自动接住 ——
            #    那一天若没有这道校验，错侧的值会静默落库。
            if category not in CATEGORY_KEYS or category not in CATEGORY_LABELS_BY_TYPE.get(record_type, {}):
                raise serializers.ValidationError(
                    {'category': '类别与「好物 / 歹物」不匹配'},
                )

        # ── ② 两个关联互斥 ──
        # ⚠️ 可空列上的约束 DRF 会**静默放过**（项目硬坑③）⇒ 必须手写。
        prop = self._resolved(attrs, 'property')
        item = self._resolved(attrs, 'survival_item')
        if prop and item:
            raise serializers.ValidationError(
                {'survival_item': '一条评价只能关联一个实物（物件资产或物品清单，二选一）'},
            )

        # ── ③ 一件实物最多一条评价 ──
        # 同上：`UniqueConstraint` 在可空列上 DRF 不自动校验，重复值到
        # IntegrityError 才是 500 —— 那时前端只拿得到一句兜底的「保存失败」。
        target_field = 'property' if prop else ('survival_item' if item else None)
        if target_field:
            qs = GoodThing.objects.filter(**{target_field: attrs.get(target_field)})
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {target_field: '这件实物已经有一条评价了 —— 去那条里补理由，不要重复登记'},
                )

        return attrs
