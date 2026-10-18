"""身上之物 · 序列化器

两类分开（同物件资产的约定）：
    Form 结尾 = **入参**（校验 + 归一化）
    其余      = **出参**（展示，含派生值）

⚠️ `allow_null` 是**对着模型列**写的，不是对着「我这版想接受什么」写的：
   `satisfaction` / `property` / `survival_item` 三列都是 `null=True`，
   所以允许 `null`；`name` / `find_status` / `part` 是 NOT NULL，
   送 `null` 应当被 400 拦下，而不是放行到 MySQL 才报
   `IntegrityError (1048, "Column 'x' cannot be null")` → 500。

🔴 两个关联 FK 的**互斥**校验写在这里（`validate`），不指望 DB 约束：
   项目既有判据 —— 可空列上的约束 DRF 会**静默放过**，
   而「挂了两件」在界面上看起来完全正常（只会显示其中一个）。
"""

from rest_framework import serializers

from ..models import WealthBodyNeed, WealthBodyPart


# ──────────────────────────────────────────────────────────────
# 部位
# ──────────────────────────────────────────────────────────────

class BodyPartSerializer(serializers.Serializer):
    """部位展示（出参）。`need_count` 让「部位维护」能看出谁还在被用 ——
    也顺便解释了为什么它删不掉（有引用就是 400）。"""

    id = serializers.IntegerField()
    name = serializers.CharField()
    sort_order = serializers.IntegerField()
    note = serializers.CharField()
    need_count = serializers.IntegerField()


class BodyPartFormSerializer(serializers.ModelSerializer):
    """部位新增 / 编辑（入参）"""

    class Meta:
        model = WealthBodyPart
        fields = ['id', 'name', 'sort_order', 'note']
        read_only_fields = ['id']
        extra_kwargs = {
            'name': {'required': True, 'allow_blank': False},
            'note': {'required': False, 'allow_blank': True},
        }


class BodySeedResultSerializer(serializers.Serializer):
    created = serializers.IntegerField()
    updated = serializers.IntegerField()
    skipped = serializers.IntegerField()
    parts = BodyPartSerializer(many=True)


# ──────────────────────────────────────────────────────────────
# 位
# ──────────────────────────────────────────────────────────────

class BodyNeedSerializer(serializers.Serializer):
    """一个位的展示（出参）。

    刻意用普通 `Serializer` 而不是 `ModelSerializer`：
    这里有一半字段是**算出来的**（`satisfaction_blank_reason` / `linked_*` /
    `treasure_*`），不是列 —— 让这件事在代码里看得见。
    """

    id = serializers.IntegerField()
    part_id = serializers.IntegerField()
    part_name = serializers.CharField()
    name = serializers.CharField()

    # 进度轴
    find_status = serializers.CharField()
    # 满意轴 —— **可空**，且空 ≠ 凑合
    satisfaction = serializers.CharField(allow_null=True)
    # 空的**来由**（`no_item` / `unrated`）；有值时是 null。
    # 🔴 由后端算，不让前端拿 `property_id` 自己推 —— 口径只有一份。
    satisfaction_blank_reason = serializers.CharField(allow_null=True)

    wish = serializers.CharField()
    note = serializers.CharField()

    # 归属（事实）—— 两个 FK 互斥，最多挂一个
    property_id = serializers.IntegerField(allow_null=True)
    survival_item_id = serializers.IntegerField(allow_null=True)
    # 由后端把「挂在哪张表」与「它叫什么」说清 —— 前端不做三分支判断
    linked_kind = serializers.CharField(allow_null=True)
    linked_kind_label = serializers.CharField()
    linked_name = serializers.CharField()

    # 好恶物档案馆回流的评价徽标 —— **只读**、不参与任何计算。
    # ⚠️ `None` = 还没评过 ⇒ 界面什么都不显示（不是灰色的「无」）。
    treasure_badge = serializers.CharField(allow_null=True)
    treasure_record_id = serializers.IntegerField(allow_null=True)

    created_at = serializers.DateTimeField(allow_null=True)
    updated_at = serializers.DateTimeField(allow_null=True)


class BodyNeedFormSerializer(serializers.ModelSerializer):
    """位的新增 / 编辑（入参）

    ⚠️ 三个 FK 一律用 `<name>_id` 的整型入参（同物件资产的 `category_id`）：
       让「前端送的是 id」这件事在代码里看得见，也避免嵌套序列化器把
       `part` 的整个对象写进来。
    """

    part_id = serializers.IntegerField()
    property_id = serializers.IntegerField(required=False, allow_null=True)
    survival_item_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = WealthBodyNeed
        fields = [
            'id', 'part_id', 'name', 'find_status', 'satisfaction',
            'wish', 'note', 'property_id', 'survival_item_id',
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'name': {'required': True, 'allow_blank': False},
            'find_status': {'required': False},
            # 可空（列是 null=True）：还没东西在用的人填不出这一格
            'satisfaction': {'required': False, 'allow_null': True},
            'wish': {'required': False, 'allow_blank': True},
            'note': {'required': False, 'allow_blank': True},
        }

    def validate_name(self, value: str) -> str:
        name = (value or '').strip()
        if not name:
            raise serializers.ValidationError('「要什么」不能为空')
        return name

    def validate(self, attrs):
        """🔴 一个位最多挂一件 —— 互斥校验写在这里。

        ⚠️ 判据要**合并**「这次送的」与「原来就有的」：
           PATCH 只送 `survival_item_id` 时，`property_id` 不在 attrs 里，
           只看 attrs 会漏判 —— 而结果是一行同时挂着两件，界面上只显示一件。
        """
        prop_id = self._resolved(attrs, 'property_id')
        item_id = self._resolved(attrs, 'survival_item_id')
        if prop_id and item_id:
            raise serializers.ValidationError({
                'property_id': '一个位最多只能挂一件东西 —— '
                               '物件资产与物品清单只能选一个（两件都在用的话，请拆成两个位）',
            })
        # ⚠️ 空串归一为 None：`''` 落在可空 FK 上会变成「空字符串当主键」，
        #    在 MySQL 严格模式下直接报错、在宽松模式下静默成 0。
        #    这类「空有两种存法」的坑，对账时才发现。
        if 'satisfaction' in attrs and attrs['satisfaction'] == '':
            attrs['satisfaction'] = None
        return attrs

    def _resolved(self, attrs, field):
        """取「这次要提交的值」：优先看入参，没有就看原对象（编辑场景）。"""
        if field in attrs:
            return attrs[field]
        return getattr(self.instance, field, None)


# ──────────────────────────────────────────────────────────────
# 汇总与元信息
# ──────────────────────────────────────────────────────────────

class BodySummarySerializer(serializers.Serializer):
    """顶部计数。

    ⚠️ 四个枚举计数（`todo` / `searching` / `settled`）**必须逐个列出来**，
       不能省成「就这几个」—— 气泡与计数卡按 key 取值，少一个键会
       **静默渲染不出来**，而界面上不会报任何错（硬坑⑪）。
    """

    total = serializers.IntegerField()
    todo = serializers.IntegerField()
    searching = serializers.IntegerField()
    settled = serializers.IntegerField()
    # 🔴 唯一一个「我该做点什么」的数字：`find_status != 'settled'`。
    #    与清单筛选同源 —— 念出来的数必须等于点进去看到的那几行。
    pending_count = serializers.IntegerField()


class BodyOptionSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()


class BodyBlankReasonSerializer(serializers.Serializer):
    """满意为空时的说明 —— `short` 是格子里的字，`label` 是悬停的解释。

    ⚠️ 两个都给：只给长句的话前端得自己截短，那是第二份映射，
       改后端文案时它不会被改到，而界面上照旧说得通。
    """

    value = serializers.CharField()
    short = serializers.CharField()
    label = serializers.CharField()


class BodyMetricMetaSerializer(serializers.Serializer):
    """口径气泡的单一结构 —— 前端零硬编码（`bands` 恒为空数组，见 body_calc）"""

    key = serializers.CharField()
    label = serializers.CharField()
    unit = serializers.CharField()
    direction = serializers.CharField()
    formula = serializers.CharField()
    note = serializers.ListField(child=serializers.CharField())
    bands = serializers.ListField(child=serializers.JSONField())


class BodyMetaSerializer(serializers.Serializer):
    find_statuses = BodyOptionSerializer(many=True)
    satisfactions = BodyOptionSerializer(many=True)
    blank_reasons = BodyBlankReasonSerializer(many=True)
    metric_meta = BodyMetricMetaSerializer(many=True)
    part_seeds_available = serializers.BooleanField()
    subtitle = serializers.CharField()
    satisfaction_note = serializers.CharField()
