"""生存资源盘点 · 序列化器

分两类，**不要混用**：
    · 出参（*Serializer）—— 服务层算好的 dict，字段显式声明，不用 __all__；
    · 入参（*FormSerializer）—— 走服务层写入，视图只做协议转换。

⚠️ 两处手写唯一性校验（类别名 / 单位名）是必须的：模型上用的是
   `UniqueConstraint`（因为唯一键含 category），DRF **不会**自动校验它，
   重复值会以 `IntegrityError`(500) 而不是 400 的形式炸出来。
"""

from rest_framework import serializers

from ..constants import (
    SURVIVAL_ESSENTIAL_LEVELS,
    SURVIVAL_ESSENTIAL_SCOPES,
    SURVIVAL_FLOW_CHANNELS,
    SURVIVAL_FLOW_MAX_BATCH,
    SURVIVAL_FLOW_REASONS,
    SURVIVAL_STOCKTAKE_SOURCES,
)
from ..models import (
    SurvivalCategory,
    SurvivalCombo,
    SurvivalEssential,
    SurvivalItem,
    SurvivalRecipe,
    SurvivalRecipeComboLine,
    SurvivalRecipeLine,
    SurvivalUnit,
)


# ──────────────────────────────────────────────────────────────
# 出参
# ──────────────────────────────────────────────────────────────

class SurvivalUnitSerializer(serializers.Serializer):
    """消耗单位"""
    id = serializers.IntegerField()
    category_id = serializers.IntegerField()
    name = serializers.CharField()
    base_unit = serializers.CharField()
    to_base_rate = serializers.FloatField()
    is_serving_unit = serializers.BooleanField()
    note = serializers.CharField()
    sort_order = serializers.IntegerField()


class SurvivalCategorySerializer(serializers.Serializer):
    """物资类别（可带单位清单）

    `aggregate_mode_effective` 是**实际生效**的口径：配餐类固定取最小。
    界面显示这一个 —— 显示用户填进去但算法不用的那个是谎报。
    """
    id = serializers.IntegerField()
    name = serializers.CharField()
    consume_mode = serializers.CharField()
    consume_mode_label = serializers.CharField()
    aggregate_mode = serializers.CharField()
    aggregate_mode_label = serializers.CharField()
    aggregate_mode_effective = serializers.CharField()
    icon = serializers.CharField()
    description = serializers.CharField()
    sort_order = serializers.IntegerField()
    item_count = serializers.IntegerField()
    recipe_count = serializers.IntegerField()
    units = SurvivalUnitSerializer(many=True, required=False)


class SurvivalItemSerializer(serializers.Serializer):
    """物资物品"""
    id = serializers.IntegerField()
    category_id = serializers.IntegerField()
    category_name = serializers.CharField()
    name = serializers.CharField()
    quantity = serializers.FloatField()
    unit_id = serializers.IntegerField(allow_null=True)
    unit_name = serializers.CharField()
    satiety = serializers.CharField()
    satiety_label = serializers.CharField()
    grade = serializers.CharField()
    grade_label = serializers.CharField()
    status = serializers.CharField()
    status_label = serializers.CharField()
    priority = serializers.CharField()
    priority_label = serializers.CharField()
    days_per_unit = serializers.FloatField(allow_null=True)
    hours_per_unit = serializers.FloatField(allow_null=True)
    # 按次计量（v3.59.3）：四个「原话」字段照原样下发，界面自己拼
    # 「每 3 天用 1 次」，不在前端做任何换算（换算是计算层独一份的活）。
    uses_per_unit = serializers.FloatField(allow_null=True)
    use_cycle_num = serializers.FloatField(allow_null=True)
    use_cycle_unit = serializers.CharField()
    use_cycle_unit_label = serializers.CharField()
    use_times = serializers.FloatField(allow_null=True)
    # 折算结果：按天口径等于 days_per_unit，按次口径是算出来的那份。
    # ⚠️ 界面显示「一份可用」时必须用 effective 这个值 —— 直接显示 days_per_unit
    #    会让按次计量的物品看起来什么都没填。
    life_mode = serializers.CharField(allow_null=True)
    days_per_unit_effective = serializers.FloatField(allow_null=True)
    # 盘点相关
    stocktake_cycle_days = serializers.IntegerField(allow_null=True)
    restock_threshold = serializers.FloatField(allow_null=True)
    expire_date = serializers.CharField(allow_null=True)
    purchase_date = serializers.CharField(allow_null=True)
    purchase_cost = serializers.FloatField(allow_null=True)
    notes = serializers.CharField()
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    recipe_line_count = serializers.IntegerField()


class SurvivalRecipeLineSerializer(serializers.Serializer):
    """配方行"""
    id = serializers.IntegerField()
    item_id = serializers.IntegerField()
    item_name = serializers.CharField()
    item_quantity = serializers.FloatField()
    item_unit_id = serializers.IntegerField(allow_null=True)
    item_unit_name = serializers.CharField()
    satiety = serializers.CharField()
    role = serializers.CharField()
    role_label = serializers.CharField()
    quantity_per_serving = serializers.FloatField()
    unit_id = serializers.IntegerField(allow_null=True)
    unit_name = serializers.CharField()
    note = serializers.CharField()


class SurvivalRecipeComboLineSerializer(serializers.Serializer):
    """配方里的组合行（v3.59.13）

    ⚠️ 与食材行**刻意不同形**：组合行没有自己的「每餐用量」，
       用量在成员上（`members`）。硬凑成同形会让前端要靠猜来分派。
    """
    id = serializers.IntegerField()
    combo_id = serializers.IntegerField()
    combo_name = serializers.CharField()
    role = serializers.CharField()
    role_label = serializers.CharField()
    member_count = serializers.IntegerField()
    note = serializers.CharField()


class SurvivalRecipeSerializer(serializers.Serializer):
    """配餐配方"""
    id = serializers.IntegerField()
    category_id = serializers.IntegerField()
    category_name = serializers.CharField()
    name = serializers.CharField()
    meals_per_day = serializers.FloatField()
    note = serializers.CharField()
    sort_order = serializers.IntegerField()
    line_count = serializers.IntegerField()
    combo_line_count = serializers.IntegerField(required=False, default=0)
    lines = SurvivalRecipeLineSerializer(many=True, required=False)
    combo_lines = SurvivalRecipeComboLineSerializer(many=True, required=False)


# ── 综合分析 ──

class SurvivalIssueSerializer(serializers.Serializer):
    """配置问题（不是错误，是「这里还会算不准」的说明）

    字段一律 `required=False`：行级问题只有「物品 + 说明」，
    类别级问题才带 category，两者共用同一个结构 —— 让前端只写一套渲染。
    """
    category = serializers.CharField(allow_null=True, required=False)
    recipe = serializers.CharField(allow_null=True, required=False)
    code = serializers.CharField()
    message = serializers.CharField()
    item = serializers.CharField(allow_null=True, required=False)
    items = serializers.ListField(child=serializers.CharField(), required=False)
    detail = serializers.CharField(allow_null=True, required=False)


class SurvivalTripleSerializer(serializers.Serializer):
    """三档天数（乐观 / 最可能 / 悲观）—— 任何一层都可能算不出来，故都允许为空"""
    optimistic = serializers.FloatField(allow_null=True)
    likely = serializers.FloatField(allow_null=True)
    pessimistic = serializers.FloatField(allow_null=True)


class SurvivalScoredSerializer(serializers.Serializer):
    """三档 + 期望值 + 离散度

    期望值与离散度是**在各自那一层**由三档算出来的（类别层用聚合后的三档，
    不是把各物品的期望值再平均）—— 后者会把 min 语义悄悄换成 mean。
    """
    days = SurvivalTripleSerializer()
    expected = serializers.FloatField(allow_null=True)
    spread = serializers.FloatField(allow_null=True)


class SurvivalComboMemberDetailSerializer(serializers.Serializer):
    """组合成员的计算底稿（配方展开明细里的一行）

    ⚠️ 与配方行的底稿**同形**（同一段 `_item_servings` 算出来的），
       前端因此可以复用同一套渲染：组合行展开后就是四行普通食材。
    """
    item_id = serializers.IntegerField()
    item_name = serializers.CharField()
    quantity_per_serving = serializers.FloatField(allow_null=True)
    unit_name = serializers.CharField()
    stock = serializers.FloatField(allow_null=True)
    stock_unit_name = serializers.CharField()
    expire_date = serializers.CharField(allow_null=True)
    expire_cap_days = serializers.IntegerField(allow_null=True)
    servings = serializers.FloatField(allow_null=True)
    issues = SurvivalIssueSerializer(many=True, required=False)


class SurvivalLineDetailSerializer(serializers.Serializer):
    """配方行的计算底稿 —— 「这个数是怎么来的」要摊得开

    ⚠️ `item_id` 允许为空：组合行没有「单一物品」（v3.59.13）。
       `line_kind` 是前端的**分派依据**（'item' / 'combo'），
       `line_key` 是聚合用的稳定键（两张表 id 会撞号，不能靠 id 判同一行）。
    """
    line_key = serializers.CharField(required=False)
    line_kind = serializers.CharField(required=False, default='item')
    line_id = serializers.IntegerField()
    combo_id = serializers.IntegerField(allow_null=True, required=False)
    combo_name = serializers.CharField(allow_null=True, required=False)
    item_id = serializers.IntegerField(allow_null=True)
    item_name = serializers.CharField()
    role = serializers.CharField()
    quantity_per_serving = serializers.FloatField(allow_null=True)
    unit_name = serializers.CharField()
    stock = serializers.FloatField(allow_null=True)
    stock_unit_name = serializers.CharField()
    satiety = serializers.CharField()
    grade = serializers.CharField()
    expire_date = serializers.CharField(allow_null=True)
    expire_cap_days = serializers.IntegerField(allow_null=True)
    servings = serializers.FloatField(allow_null=True)
    # 组合行专用：组内最先耗尽的那件（**不是**组合名）—— 缺口要点到具体物品
    bottleneck_item = serializers.CharField(allow_null=True, required=False)
    members = SurvivalComboMemberDetailSerializer(many=True, required=False)
    issues = SurvivalIssueSerializer(many=True, required=False)


class SurvivalRecipeResultSerializer(SurvivalScoredSerializer):
    """配餐结果：可支撑餐数 / 天数 / 短板 / 保质期封顶 / 是否可信"""
    recipe_id = serializers.IntegerField()
    recipe_name = serializers.CharField()
    meals_per_day = serializers.FloatField(allow_null=True)
    staple_servings = serializers.FloatField(allow_null=True)
    required_servings = serializers.FloatField(allow_null=True)
    # 配了几行必配位（不论算不算得出）—— 让界面能区分「没配」与「配了算不出」
    required_line_count = serializers.IntegerField(required=False, default=0)
    meals = serializers.FloatField(allow_null=True)
    bottleneck_role = serializers.CharField(allow_null=True)
    bottleneck_item = serializers.CharField(allow_null=True)
    expiry_cap_days = serializers.IntegerField(allow_null=True)
    capped_by_expiry = serializers.BooleanField()
    trustworthy = serializers.BooleanField()
    per_day_reference = serializers.FloatField(allow_null=True)
    lines = SurvivalLineDetailSerializer(many=True, required=False)


class SurvivalItemLifeSerializer(SurvivalScoredSerializer):
    """非配餐物品的时长底稿

    `life_mode` 是显示层的分派依据，**不能省**：
      'cycle' 按次 —— 「一份 10 次 × 每 3 天一次 = 30 天」这句话要说全，
              只给一个 30 天，用户没法核对是不是自己填的意思；
      'day'   按天 —— 直接显示 days_per_unit；
      None    两条都没填 —— 显示「未填」，不是 0 天。
    """
    item_id = serializers.IntegerField()
    name = serializers.CharField()
    quantity = serializers.FloatField(allow_null=True)
    unit_name = serializers.CharField()
    days_per_unit = serializers.FloatField(allow_null=True)
    uses_per_unit = serializers.FloatField(allow_null=True)
    use_cycle_num = serializers.FloatField(allow_null=True)
    use_cycle_unit = serializers.CharField()
    use_times = serializers.FloatField(allow_null=True)
    life_mode = serializers.CharField(allow_null=True)
    days_per_unit_effective = serializers.FloatField(allow_null=True)
    interval_days = serializers.FloatField(allow_null=True)
    hours_per_unit = serializers.FloatField(allow_null=True)
    satiety = serializers.CharField()
    grade = serializers.CharField()
    status = serializers.CharField()
    stocktake_cycle_days = serializers.IntegerField(allow_null=True)
    restock_threshold = serializers.FloatField(allow_null=True)
    expire_date = serializers.CharField(allow_null=True)
    expire_cap_days = serializers.IntegerField(allow_null=True)
    hours_total = serializers.FloatField(allow_null=True)
    issues = SurvivalIssueSerializer(many=True, required=False)


class SurvivalItemPreviewSerializer(SurvivalItemLifeSerializer):
    """试算结果（v3.59.11）—— 与保存后的列表行**同一个形状**

    🔴 刻意继承而不是另起一份字段清单：前端拿到的 `expected` / `days` /
       `days_per_unit_effective` 必须与列表里那个数**同源**，
       否则「试算说 150 天、保存后写着 123.7 年」就成了必然。
       字段清单一旦复制成两份，加字段时漏改一份是不会报错的。

    唯一的差别是 `item_id` 可以为空 —— 试算还没有 id。
    """

    item_id = serializers.IntegerField(allow_null=True)


class SurvivalCategoryResultSerializer(SurvivalScoredSerializer):
    """类别结果：四卡的数据源"""
    category_id = serializers.IntegerField()
    name = serializers.CharField()
    icon = serializers.CharField()
    consume_mode = serializers.CharField()
    aggregate_mode = serializers.CharField()
    aggregate_mode_effective = serializers.CharField()
    usable_item_count = serializers.IntegerField()
    item_count = serializers.IntegerField()
    snack_days = serializers.FloatField(allow_null=True)
    hours_total = serializers.FloatField(allow_null=True)
    trustworthy = serializers.BooleanField()
    items = SurvivalItemLifeSerializer(many=True, required=False)
    recipes = SurvivalRecipeResultSerializer(many=True, required=False)
    issues = SurvivalIssueSerializer(many=True, required=False)


class SurvivalOverallSerializer(SurvivalScoredSerializer):
    """跨类别综合（取最小）"""


class SurvivalCashSerializer(serializers.Serializer):
    """钱这条腿（复用应急金月数口径，不新写第二份）"""
    months = serializers.FloatField(allow_null=True)
    days = serializers.FloatField(allow_null=True)
    basis = serializers.CharField()


class SurvivalCoverageSerializer(serializers.Serializer):
    """三年赎回期覆盖率"""
    pct = serializers.FloatField(allow_null=True)
    remaining_days = serializers.IntegerField(allow_null=True)
    reason = serializers.CharField(allow_null=True, required=False)
    window_start = serializers.CharField(required=False)
    window_end = serializers.CharField(required=False)


# ──────────────────────────────────────────────────────────────
# 必需品基准清单与缺口对账（v3.59.7）
# ──────────────────────────────────────────────────────────────

class SurvivalEssentialItemSerializer(SurvivalScoredSerializer):
    """基准项里**逐件**的对账明细（v3.59.12）

    ⚠️ 与顶层 `item_id` / `item_name` 的分工：顶层那几个指**代表件**
       （正常用量下最短的那件），本序列化器是**一整组**。
       前端「对应物品」的多选回显、以及「可支撑」的悬浮说明都用这一份。

    每件的 `level` 也由后端分档 —— 逐件上色时**同样只读不算**（同顶层那条）。
    """
    item_id = serializers.IntegerField()
    item_name = serializers.CharField()
    item_quantity = serializers.FloatField(allow_null=True)
    item_unit_name = serializers.CharField()
    item_status = serializers.CharField()
    expire_date = serializers.CharField(allow_null=True)
    level = serializers.CharField()
    issues = SurvivalIssueSerializer(many=True, required=False)


class SurvivalEssentialSerializer(SurvivalScoredSerializer):
    """基准项 + 逐项对账结果

    ⚠️ `level` 由后端分档（阈值真源是 `constants.SURVIVAL_ESSENTIAL_LEVEL_FLOORS`），
       前端**只按它上色、不重算** —— 两处判档迟早不一致，而不一致是静默的：
       两边都会显示出一个看着合理的颜色，没人会去对。
    """
    essential_id = serializers.IntegerField()
    name = serializers.CharField()
    category_id = serializers.IntegerField(allow_null=True)
    category_name = serializers.CharField()
    scope = serializers.CharField()
    unit_name = serializers.CharField()
    hint = serializers.CharField()
    note = serializers.CharField()
    sort_order = serializers.IntegerField()
    # 逐件明细（v3.59.12）。⚠️ 顺序由后端定：正常用量下最短的在前、
    # 算不出的排最后 —— 前端**不重排**（重排一次就有了第二份顺序口径）。
    items = SurvivalEssentialItemSerializer(many=True, required=False)
    # ↓ 以下 item_* 一律指**代表件**（正常用量下最短的那件）——
    #   多件挂上之后它们不再等于「唯一那件」，逐件请看上面 `items`。
    item_id = serializers.IntegerField(allow_null=True)
    item_name = serializers.CharField()
    item_quantity = serializers.FloatField(allow_null=True)
    item_unit_name = serializers.CharField()
    item_status = serializers.CharField()
    expire_date = serializers.CharField(allow_null=True)
    level = serializers.CharField()
    issues = SurvivalIssueSerializer(many=True, required=False)


class SurvivalEssentialShortestSerializer(serializers.Serializer):
    """核心必需品里最先见底的那一件"""
    essential_id = serializers.IntegerField()
    name = serializers.CharField()
    item_name = serializers.CharField()
    category_name = serializers.CharField()
    days = serializers.FloatField(allow_null=True)
    level = serializers.CharField()


class SurvivalEssentialUnclosedSerializer(serializers.Serializer):
    """尚未闭合的核心项 —— 未录入（没录）或待补数据（录了但算不出）

    两种都要人去补一件事，但补的东西不同，故 `level` 必须一起给，
    否则界面只能笼统说「有问题」，用户不知道该去录入还是去改口径。
    """
    essential_id = serializers.IntegerField()
    name = serializers.CharField()
    level = serializers.CharField()


class SurvivalEssentialSummarySerializer(serializers.Serializer):
    """对账汇总：各档计数 + 尚未闭合的核心项"""
    total = serializers.IntegerField()
    core_total = serializers.IntegerField()
    level_counts = serializers.DictField(child=serializers.IntegerField())
    core_level_counts = serializers.DictField(child=serializers.IntegerField())
    unclosed_core = SurvivalEssentialUnclosedSerializer(many=True)
    unclosed_core_count = serializers.IntegerField()
    complete = serializers.BooleanField()


class SurvivalEssentialReconcileSerializer(serializers.Serializer):
    """综合分析里内联的对账块

    只要汇总与最短的一件，**明细走 `/survival/essentials/` 列表端点**：
    两处都塞全量明细，将来必然出现「总览的数和列表的数不一样」——
    因为其中一处忘了同步取数条件。
    """
    summary = SurvivalEssentialSummarySerializer()
    shortest = SurvivalEssentialShortestSerializer(allow_null=True)
    is_configured = serializers.BooleanField()


class SurvivalEssentialFormSerializer(serializers.ModelSerializer):
    """基准项新增 / 编辑"""

    category_id = serializers.IntegerField()
    # 关联物品是一**组**（v3.59.12）。容器层严格（必须是数组）、元素层宽松
    # （`0` 之类在 `validate_item_ids` 里被当成「不关联」滤掉）。
    # ⚠️ 空数组是**合法**的，含义是「清空关联」—— 与「不传这个字段」不同。
    item_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_empty=True,
    )

    class Meta:
        model = SurvivalEssential
        fields = [
            'id', 'name', 'category_id', 'scope', 'unit_name', 'hint',
            'item_ids', 'note', 'sort_order',
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'name': {'required': True, 'allow_blank': False},
            'unit_name': {'required': False, 'allow_blank': True},
            'hint': {'required': False, 'allow_blank': True},
            'note': {'required': False, 'allow_blank': True},
            'sort_order': {'required': False},
        }

    def validate_name(self, value):
        """手写唯一性校验 —— 模型上用 `UniqueConstraint(user_id, name)`，
        DRF **不会**自动校验它，重复值会以 IntegrityError(500) 而不是 400 炸出来。
        """
        name = (value or '').strip()
        if not name:
            raise serializers.ValidationError('必需品名称不能为空')
        qs = SurvivalEssential.objects.filter(user_id=1, name=name)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(f'已存在名为「{name}」的必需品')
        return name

    def validate_category_id(self, value):
        if not SurvivalCategory.objects.filter(id=value, user_id=1).exists():
            raise serializers.ValidationError('归属类别不存在')
        return value

    def validate_item_ids(self, value):
        """关联物品可挂多件；空值与重复项在这里收敛（v3.59.12）

        ⚠️ 元素里的 `0` / `''` 表示「不关联」，滤掉 —— 直接塞进多对多会在
           落库时炸成 500，而界面上只剩一句兜底的「保存失败」，看不出哪错了。

        ⚠️ 去重**必须**在这里做：中间表上有 UNIQUE(survivalessential_id,
           survivalitem_id)，重复 id 会以 `IntegrityError` 崩在事务里 ——
           界面上同样只显示「保存失败」，看不出是「同一件挂了两次」。
           （同 §硬坑 6：不落在模型 `unique=True` 上的约束，DRF 不会自动校验。）

        ⚠️ 返回顺序按**用户提交的顺序**，不按 id 排 —— 展示顺序由天数决定，
           这一层没有理由替用户重排他刚勾的那几件。
        """
        if not value:
            return []
        wanted: list[int] = []
        for raw in value:
            if raw in (None, '', 0, '0'):
                continue
            try:
                number = int(raw)
            except (TypeError, ValueError):
                raise serializers.ValidationError('关联的物品不存在') from None
            if number not in wanted:
                wanted.append(number)
        if not wanted:
            return []
        found = set(
            SurvivalItem.objects
            .filter(id__in=wanted, user_id=1)
            .values_list('id', flat=True)
        )
        if any(number not in found for number in wanted):
            raise serializers.ValidationError('关联的物品不存在')

        # 🔴 一件物品只能挂在**一处**（v3.59.13）
        # 用户的原话：「已经进行过关联状态的物品，不要再出现在待关联列表里面，
        # 待后面物品越增越多时，列表会出现干扰性」。前端会把这类物品从候选里滤掉，
        # 但**只滤前端等于界面看着干净、数据里仍是重复的** —— 所以后端也硬拒。
        #
        # ⚠️ 排除**自己**：本行已经勾上的那几件必须留着 ——
        #    否则编辑时「取消勾选」都点不到（它不在候选里就选不掉）。
        taken = dict(
            SurvivalEssential.objects
            .filter(items__id__in=wanted)
            .exclude(pk=getattr(self.instance, 'pk', None))
            .values_list('items__id', 'name')
        )
        if taken:
            labels = dict(
                SurvivalItem.objects.filter(id__in=[i for i in wanted if i in taken])
                .values_list('id', 'name')
            )
            detail = '；'.join(
                f'「{labels.get(i, i)}」已挂在「{taken[i]}」下' for i in wanted if i in taken
            )
            raise serializers.ValidationError(
                f'一件物品只能挂在一处：{detail}。'
                f'要从那一条上摘掉，或者确认这件东西真的只属于这里。',
            )
        return wanted


class SurvivalEssentialSeedResultSerializer(serializers.Serializer):
    """基准清单初始化结果

    `missing_categories` 是给「医药类别还没初始化」这种情形留的出口：
    静默跳过会让人以为清单本来就这么长。
    """
    created = serializers.IntegerField()
    updated = serializers.IntegerField()
    skipped = serializers.IntegerField()
    seeded_total = serializers.IntegerField()
    missing_categories = serializers.ListField(child=serializers.CharField())


class SurvivalAnalysisSerializer(serializers.Serializer):
    """综合分析 —— 首屏一次取全"""
    available = serializers.BooleanField()
    reason = serializers.CharField(allow_null=True)
    as_of = serializers.CharField()
    categories = SurvivalCategoryResultSerializer(many=True)
    shortest_category = serializers.CharField(allow_null=True)
    shortest_days = serializers.FloatField(allow_null=True)
    overall = SurvivalOverallSerializer()
    cash = SurvivalCashSerializer()
    bottleneck = serializers.CharField()
    bottleneck_label = serializers.CharField()
    coverage = SurvivalCoverageSerializer()
    issues = SurvivalIssueSerializer(many=True)
    snack_days = serializers.FloatField(allow_null=True)
    has_any_item = serializers.BooleanField()
    # 必需品缺口对账（v3.59.7）—— 与生存天数**并列的第二把尺子**：
    # 天数回答「够撑多久」，对账回答「漏了什么」。不合并成一个数：
    # 把「还没录的牙膏」折成 0 天会把「没录数据」说成「只够撑 0 天」。
    essentials = SurvivalEssentialReconcileSerializer()


class SurvivalMetricMetaSerializer(serializers.Serializer):
    """口径元信息 —— 气泡提示的数据源（与 /ratios/meta/ 同样的做法）

    `note` 只从 `constants.SURVIVAL_METRIC_NOTES` 来。前端不要在组件里
    另写一份口径文案：数字一变，界面上的说明就开始撒谎，而且没人会发现。

    字段结构与 `/ratios/meta/` 对齐（含 direction / bands / target），
    以便前端复用同一个气泡组件 —— `bands` 恒为空数组，
    意思是「本指标不设绝对判定线」，不是漏发。
    """
    key = serializers.CharField()
    label = serializers.CharField()
    unit = serializers.CharField()
    direction = serializers.CharField()
    formula = serializers.CharField()
    note = serializers.ListField(child=serializers.CharField())
    bands = serializers.ListField(child=serializers.ListField(), allow_null=True)
    target = serializers.FloatField(allow_null=True)


class SurvivalOptionSerializer(serializers.Serializer):
    """下拉选项（值 + 中文标签），选项真源在模型 choices 与 constants"""
    value = serializers.CharField()
    label = serializers.CharField()


class SurvivalWearReferenceSerializer(serializers.Serializer):
    """衣物可穿次数参考（v3.59.8）—— **只在录入时当锚点，不参与任何计算**

    `uses_*` 与 `days_*` 两列**不是同一把尺子**：次数与穿法无关、跨人可比；
    天数隐含了一个穿着频次，换个节奏就不成立。故两列并列下发、由界面分开呈现，
    后端**不做**「一年穿 N 次」这类隐含换算 —— 那条假设对睡衣与对外套都成立不了。
    """
    keyword = serializers.CharField()
    uses_low = serializers.IntegerField(allow_null=True)
    uses_high = serializers.IntegerField(allow_null=True)
    days_low = serializers.IntegerField(allow_null=True)
    days_high = serializers.IntegerField(allow_null=True)
    wears_per_week = serializers.IntegerField(allow_null=True)
    signal = serializers.CharField()


class SurvivalMetaSerializer(serializers.Serializer):
    """枚举与口径的单一出口 —— 前端零硬编码"""
    metric_meta = SurvivalMetricMetaSerializer(many=True)
    consume_modes = SurvivalOptionSerializer(many=True)
    aggregate_modes = SurvivalOptionSerializer(many=True)
    satiety = SurvivalOptionSerializer(many=True)
    satiety_counted = serializers.ListField(child=serializers.CharField())
    grades = SurvivalOptionSerializer(many=True)
    statuses = SurvivalOptionSerializer(many=True)
    priorities = SurvivalOptionSerializer(many=True)
    roles = SurvivalOptionSerializer(many=True)
    # 按次计量的周期单位（天 / 周 / 月）
    use_cycle_units = SurvivalOptionSerializer(many=True)
    scenarios = serializers.ListField(child=serializers.CharField())
    meal_scenarios = serializers.DictField(child=serializers.IntegerField())
    days_per_year = serializers.IntegerField()
    bottleneck_tolerance = serializers.FloatField()
    # 必需品基准清单的枚举（v3.59.7）—— 前端零硬编码，与其它选项同一出处
    essential_scopes = SurvivalOptionSerializer(many=True)
    essential_levels = SurvivalOptionSerializer(many=True)
    # 衣物可穿次数参考（v3.59.8）—— 录入锚点，算法一个字段都不读它
    wear_reference = SurvivalWearReferenceSerializer(many=True)


class SurvivalSeedResultSerializer(serializers.Serializer):
    """种子结果：类别 / 单位 / 必需基准清单，一次初始化

    `essentials` 一并返回 —— 基准清单**必须在类别建好之后**写
    （种子里的归属类别是按名字查的），两步合在一个命令里，
    用户不必先猜「类别建了吗」再去建清单。
    """
    created_categories = serializers.IntegerField()
    created_units = serializers.IntegerField()
    updated_categories = serializers.IntegerField()
    categories = SurvivalCategorySerializer(many=True)
    essentials = SurvivalEssentialSeedResultSerializer(required=False)


# ──────────────────────────────────────────────────────────────
# 入参
# ──────────────────────────────────────────────────────────────

class SurvivalCategoryFormSerializer(serializers.ModelSerializer):
    """类别新增/编辑"""

    class Meta:
        model = SurvivalCategory
        fields = [
            'id', 'name', 'consume_mode', 'aggregate_mode', 'icon',
            'description', 'sort_order',
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'name': {'required': True, 'allow_blank': False},
            'icon': {'required': False, 'allow_blank': True},
            'description': {'required': False, 'allow_blank': True},
        }

    def validate_name(self, value):
        name = (value or '').strip()
        if not name:
            raise serializers.ValidationError('类别名称不能为空')
        qs = SurvivalCategory.objects.filter(user_id=1, name=name)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(f'已存在名为「{name}」的类别')
        return name


class SurvivalUnitFormSerializer(serializers.ModelSerializer):
    """消耗单位新增/编辑"""

    category_id = serializers.IntegerField()

    class Meta:
        model = SurvivalUnit
        fields = [
            'id', 'category_id', 'name', 'base_unit', 'to_base_rate',
            'is_serving_unit', 'note', 'sort_order',
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'name': {'required': True, 'allow_blank': False},
            'base_unit': {'required': False, 'allow_blank': True},
            'note': {'required': False, 'allow_blank': True},
        }

    def validate_to_base_rate(self, value):
        """换算率必须为正 —— 0 或负数会让除法炸掉或产出负数天数"""
        if value is None or float(value) <= 0:
            raise serializers.ValidationError('换算率必须大于零')
        return value

    def validate(self, attrs):
        category_id = attrs.get('category_id') or getattr(self.instance, 'category_id', None)
        name = (attrs.get('name') or getattr(self.instance, 'name', '')).strip()
        qs = SurvivalUnit.objects.filter(user_id=1, category_id=category_id, name=name)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError({'name': f'该类别下已存在单位「{name}」'})
        return attrs


class SurvivalItemFormSerializer(serializers.ModelSerializer):
    """物资物品新增/编辑"""

    category_id = serializers.IntegerField()
    unit_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = SurvivalItem
        fields = [
            'id', 'category_id', 'name', 'quantity', 'unit_id',
            'satiety', 'grade', 'status', 'priority',
            'days_per_unit', 'hours_per_unit',
            'uses_per_unit', 'use_cycle_num', 'use_cycle_unit', 'use_times',
            'stocktake_cycle_days', 'restock_threshold',
            'expire_date', 'purchase_date', 'purchase_cost',
            'notes', 'tags',
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'name': {'required': True, 'allow_blank': False},
            'satiety': {'required': False, 'allow_blank': True},
            'grade': {'required': False, 'allow_blank': True},
            'priority': {'required': False, 'allow_blank': True},
            'notes': {'required': False, 'allow_blank': True},
            'tags': {'required': False},
            'days_per_unit': {'required': False, 'allow_null': True},
            'hours_per_unit': {'required': False, 'allow_null': True},
            'uses_per_unit': {'required': False, 'allow_null': True},
            'use_cycle_num': {'required': False, 'allow_null': True},
            'use_cycle_unit': {'required': False, 'allow_null': True},
            'use_times': {'required': False, 'allow_null': True},
            'stocktake_cycle_days': {'required': False, 'allow_null': True},
            'restock_threshold': {'required': False, 'allow_null': True},
        }

    def validate_quantity(self, value):
        if value is None or float(value) < 0:
            raise serializers.ValidationError('数量不能为负')
        return value

    def validate_days_per_unit(self, value):
        if value is not None and float(value) <= 0:
            raise serializers.ValidationError('单件可用天数必须大于零')
        return value

    def validate(self, attrs):
        """两条计量口径各自守住自己的完整性

        · 单位必须属于这件物品所在的类别 —— 跨类别的单位（拿「册」去量米粉）
          算出来的天数没有任何意义，而这种错误在界面上看不出来，
          只会在某天给出一个荒唐的天数。
        · **按天口径 ⇒ 频次三兄弟（num / unit / times）一律置空。**
          这三个字段只在按次口径下才有含义，留着值就是一句假话：
          按天计量的羽绒服上写着「每 3 天用 1 次」，谁也看不出来。
        """
        category_id = attrs.get('category_id') or getattr(self.instance, 'category_id', None)
        unit_id = attrs.get('unit_id', getattr(self.instance, 'unit_id', None))
        if unit_id:
            unit = SurvivalUnit.objects.filter(id=unit_id).first()
            if not unit:
                raise serializers.ValidationError({'unit_id': '单位不存在'})
            if unit.category_id != category_id:
                raise serializers.ValidationError(
                    {'unit_id': f'单位「{unit.name}」属于别的类别，不能用于本类别的物品'},
                )

        # ⚠️ 判据永远是「`uses_per_unit` 填了没有」，**不看那三个字段** ——
        #    它们是一条口径的细节，不能反过来决定口径是哪一条。
        uses = attrs.get('uses_per_unit', getattr(self.instance, 'uses_per_unit', None))

        # 按天口径：频次三兄弟一律置空（v3.59.6）
        # ⚠️ 不能只靠客户端送 null。送不送是客户端的自由，而「按天口径下这三个
        #    字段没有含义」是**口径本身**的规定 —— 属于服务端该守住的不变量。
        #    少了这一步，旧客户端残留的 use_cycle_num=3 会静默存进按天物品里：
        #    界面上看不出任何异常，库里却写着一句「每 3 天用 1 次」。
        if uses is None:
            for field in ('use_cycle_num', 'use_cycle_unit', 'use_times'):
                attrs[field] = None
            return attrs

        # 按次计量（v3.59.3）：填了「一份只能用多少次」就必须给得出频次。
        # ⚠️ 判据必须与计算层一致 —— `resolve_life` 是「填了按次就按次算、
        #    算不出就报错」，**不退回按天**。若这里放行了半个配置，
        #    界面会拿一个旧的按天值当结果，而用户以为系统用的是他刚填的次数。
        if float(uses) <= 0:
            raise serializers.ValidationError(
                {'uses_per_unit': '一份可用次数必须大于零'},
            )
        for field, label in (
            ('use_cycle_num', '每几个周期'), ('use_times', '每周期用几次'),
        ):
            value = attrs.get(field, getattr(self.instance, field, None))
            if value is None or float(value) <= 0:
                raise serializers.ValidationError({field: f'{label}必须大于零'})
        return attrs


class SurvivalRecipeLineWriteSerializer(serializers.Serializer):
    """配方行入参（配方保存时整体替换）"""
    item_id = serializers.IntegerField()
    role = serializers.ChoiceField(
        choices=[c[0] for c in SurvivalRecipeLine._meta.get_field('role').choices],
        required=False,
    )
    quantity_per_serving = serializers.DecimalField(max_digits=14, decimal_places=4)
    unit_id = serializers.IntegerField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True)

    def validate_quantity_per_serving(self, value):
        if value is None or float(value) <= 0:
            raise serializers.ValidationError('每餐用量必须大于零')
        return value


class SurvivalRecipeComboLineWriteSerializer(serializers.Serializer):
    """配方里的组合行入参（v3.59.13）

    ⚠️ 刻意**没有** `quantity_per_serving`、也**没有** `servings` / `multiplier`：
       组合的用量在成员身上，这里再加一个倍率就是「两个数相乘」的形状
       （本项目踩过：「一份能用几次」× 数量 = 45,000 天，两个数各自看着都正常）。
       要加量请去改组合里那一行的「每餐用量」。
    """
    combo_id = serializers.IntegerField()
    role = serializers.ChoiceField(
        choices=[c[0] for c in SurvivalRecipeComboLine._meta.get_field('role').choices],
        required=False,
    )
    note = serializers.CharField(required=False, allow_blank=True)


class SurvivalRecipeFormSerializer(serializers.ModelSerializer):
    """配餐配方新增/编辑（含配方行 + 组合行）"""

    category_id = serializers.IntegerField()
    lines = SurvivalRecipeLineWriteSerializer(many=True, required=False)
    combo_lines = SurvivalRecipeComboLineWriteSerializer(many=True, required=False)

    class Meta:
        model = SurvivalRecipe
        fields = [
            'id', 'category_id', 'name', 'meals_per_day', 'note', 'sort_order',
            'lines', 'combo_lines',
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'name': {'required': True, 'allow_blank': False},
            'note': {'required': False, 'allow_blank': True},
        }

    def validate_meals_per_day(self, value):
        if value is None or float(value) <= 0:
            raise serializers.ValidationError('每日餐数必须大于零')
        return value

    def validate(self, attrs):
        category_id = attrs.get('category_id') or getattr(self.instance, 'category_id', None)
        name = (attrs.get('name') or getattr(self.instance, 'name', '')).strip()
        qs = SurvivalRecipe.objects.filter(user_id=1, category_id=category_id, name=name)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError({'name': f'该类别下已存在配方「{name}」'})

        # 配方行里的食材必须属于同一类别 —— 跨类别混进配方会让
        # 「一顿饭」的定义失去边界，而算法只能照单全收
        lines = attrs.get('lines') or []
        if lines:
            item_ids = [line['item_id'] for line in lines]
            items = {
                it.id: it for it in SurvivalItem.objects.filter(id__in=item_ids)
            }
            missing = [i for i in item_ids if i not in items]
            if missing:
                raise serializers.ValidationError({'lines': f'食材不存在：{missing}'})
            wrong = [items[i].name for i in item_ids if items[i].category_id != category_id]
            if wrong:
                raise serializers.ValidationError(
                    {'lines': f'这些食材不属于本类别：{"、".join(wrong)}'},
                )

        # 组合行（v3.59.13）：与食材行同一条类别判据，只是走另一张表
        combo_lines = attrs.get('combo_lines') or []
        if combo_lines:
            combo_ids = [line['combo_id'] for line in combo_lines]
            combos = {
                c.id: c for c in SurvivalCombo.objects.filter(id__in=combo_ids, user_id=1)
            }
            missing = [i for i in combo_ids if i not in combos]
            if missing:
                raise serializers.ValidationError({'combo_lines': f'组合不存在：{missing}'})
            wrong = [
                combos[i].name for i in combo_ids if combos[i].category_id != category_id
            ]
            if wrong:
                raise serializers.ValidationError(
                    {'combo_lines': f'这些组合不属于本类别：{"、".join(wrong)}'},
                )

        # 「至少要有一样主食」两条线一起判 —— 只看 `lines` 的话，
        # 一个「只挂组合」的配方会被放过去，然后算出个空值。
        if lines or combo_lines:
            has_staple = any(line.get('role', 'staple') == 'staple' for line in lines) or any(
                line.get('role', 'staple') == 'staple' for line in combo_lines
            )
            if not has_staple:
                raise serializers.ValidationError(
                    {'lines': '至少要有一样主食（主食位）—— 没有主食的配方算不出能撑多少顿'},
                )
        return attrs


# ──────────────────────────────────────────────────────────────
# 组合（v3.59.13）
# ──────────────────────────────────────────────────────────────

class SurvivalComboMemberSerializer(serializers.Serializer):
    """组合成员（出参）"""
    item_id = serializers.IntegerField()
    item_name = serializers.CharField()
    quantity_per_serving = serializers.FloatField()
    unit_id = serializers.IntegerField(allow_null=True)
    unit_name = serializers.CharField()
    item_unit_name = serializers.CharField()
    stock = serializers.FloatField()
    stock_unit_name = serializers.CharField()


class SurvivalComboSerializer(serializers.Serializer):
    """组合（出参）

    `recipe_ref_count` 不是装饰：被配方引用的组合**删不掉**，
    界面必须在点删除之前就能看见这一点，否则用户只会白点一次再收到报错。
    """
    id = serializers.IntegerField()
    category_id = serializers.IntegerField()
    category_name = serializers.CharField()
    name = serializers.CharField()
    note = serializers.CharField()
    sort_order = serializers.IntegerField()
    member_count = serializers.IntegerField()
    recipe_ref_count = serializers.IntegerField(required=False, default=0)
    members = SurvivalComboMemberSerializer(many=True, required=False)


class SurvivalComboMemberWriteSerializer(serializers.Serializer):
    """组合成员入参

    ⚠️ `quantity_per_serving` 用 DecimalField 而不是 FloatField：
       落库列是 `numeric(14, 4)`，先过 float 会引入二进制误差
       （0.1 + 0.2 那类），而用量会经过除法 —— 误差会被放大到小数位上。
    """
    item_id = serializers.IntegerField()
    quantity_per_serving = serializers.DecimalField(max_digits=14, decimal_places=4)
    unit_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_quantity_per_serving(self, value):
        if value is None or float(value) <= 0:
            raise serializers.ValidationError('每餐用量必须大于零')
        return value


class SurvivalComboFormSerializer(serializers.ModelSerializer):
    """组合新增 / 编辑（含成员）"""

    category_id = serializers.IntegerField()
    members = SurvivalComboMemberWriteSerializer(many=True)

    class Meta:
        model = SurvivalCombo
        fields = ['id', 'category_id', 'name', 'note', 'sort_order', 'members']
        read_only_fields = ['id']
        extra_kwargs = {
            'name': {'required': True, 'allow_blank': False},
            'note': {'required': False, 'allow_blank': True},
            'sort_order': {'required': False},
        }

    def validate_name(self, value):
        """手写唯一性校验 —— 模型上是 `UniqueConstraint(user_id, category, name)`，
        DRF **不会**自动校验它（同类别 / 单位那两处），重复值会以
        `IntegrityError`(500) 而不是 400 炸出来。
        """
        name = (value or '').strip()
        if not name:
            raise serializers.ValidationError('组合名称不能为空')
        return name

    def validate(self, attrs):
        """类别 + 重名 + 成员三件事一起判

        🔴 成员三件事的判据（与 `survival_combo_service._members` 同源，**故意判两遍**）：
           容器层在这里挡 HTTP 面的请求；服务层那一份给脚本 / 别的调用方用。
           只有一处的话，绕过 HTTP 的调用会静默写进一个坏组合。
        """
        category_id = attrs.get('category_id') or getattr(self.instance, 'category_id', None)
        category = SurvivalCategory.objects.filter(id=category_id, user_id=1).first()
        if category is None:
            raise serializers.ValidationError({'category_id': '归属类别不存在'})

        name = (attrs.get('name') or getattr(self.instance, 'name', '')).strip()
        qs = SurvivalCombo.objects.filter(
            user_id=1, category_id=category_id, name=name,
        )
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError({'name': f'该类别下已存在组合「{name}」'})

        members = attrs.get('members')
        if members is not None:
            if not members:
                raise serializers.ValidationError(
                    {'members': '组合至少要有一件物品 —— 空组合会让配方里那一行变成无约束'},
                )
            item_ids = [m['item_id'] for m in members]
            if len(set(item_ids)) != len(item_ids):
                raise serializers.ValidationError(
                    {'members': '同一件物品在一个组合里只能出现一次；加量请改它的每餐用量'},
                )
            items = {
                it.id: it for it in SurvivalItem.objects.filter(id__in=item_ids, user_id=1)
            }
            missing = [i for i in item_ids if i not in items]
            if missing:
                raise serializers.ValidationError({'members': f'物品不存在：{missing}'})
            wrong = [items[i].name for i in item_ids if items[i].category_id != category_id]
            if wrong:
                raise serializers.ValidationError(
                    {'members': f'这些物品不属于本类别：{"、".join(wrong)}'},
                )
        return attrs


# ──────────────────────────────────────────────────────────────
# 出参：盘点快照（v3.59.0 二期）
# ──────────────────────────────────────────────────────────────

class SurvivalSnapshotCategorySerializer(serializers.Serializer):
    """快照里的单个类别

    `category_id` 可为空（类别被删过），`category_name` 才是稳定标识 ——
    历史点自带当时的名字，不依赖类别仍然存在。
    """
    category_id = serializers.IntegerField(allow_null=True)
    category_name = serializers.CharField()
    consume_mode = serializers.CharField()
    aggregate_mode_effective = serializers.CharField()
    days = SurvivalTripleSerializer()
    expected = serializers.FloatField(allow_null=True)
    usable_item_count = serializers.IntegerField()
    item_count = serializers.IntegerField()
    snack_days = serializers.FloatField(allow_null=True)
    hours_total = serializers.FloatField(allow_null=True)
    issue_count = serializers.IntegerField()
    trustworthy = serializers.BooleanField()


class SurvivalSnapshotSerializer(serializers.Serializer):
    """单份盘点快照

    ⚠️ 天数类字段允许 `null` 且**与 0 不同义**：`null` = 那天算不出来，
       0 = 那天真的撑不了。前端据此显示「未算出」而不是「0 天」。
    """
    id = serializers.IntegerField()
    date = serializers.DateField()
    source = serializers.CharField()
    source_label = serializers.CharField()
    note = serializers.CharField()
    days = SurvivalTripleSerializer()
    expected = serializers.FloatField(allow_null=True)
    spread = serializers.FloatField(allow_null=True)
    shortest_category = serializers.CharField(allow_null=True)
    bottleneck = serializers.CharField()
    bottleneck_label = serializers.CharField()
    cash_months = serializers.FloatField(allow_null=True)
    cash_days = serializers.FloatField(allow_null=True)
    coverage_pct = serializers.FloatField(allow_null=True)
    coverage_remaining_days = serializers.IntegerField(allow_null=True)
    category_count = serializers.IntegerField()
    item_count = serializers.IntegerField()
    snack_days = serializers.FloatField(allow_null=True)
    issue_count = serializers.IntegerField()
    trustworthy = serializers.BooleanField()
    created_at = serializers.DateTimeField(allow_null=True)
    categories = SurvivalSnapshotCategorySerializer(many=True, required=False)


class SurvivalSnapshotPointSerializer(SurvivalSnapshotSerializer):
    """趋势上的一个点 = 快照 + 相对上一点的差

    `delta_expected` 为 `null` 表示算不出来（任一端缺值），**不是 0**：
    0 会显示成「跟上期持平」，那是把「不知道」说成了结论。
    """
    delta_expected = serializers.FloatField(allow_null=True)
    delta_kind = serializers.CharField(allow_null=True)
    days_since_previous = serializers.IntegerField(allow_null=True)


class SurvivalTrendSeriesSerializer(serializers.Serializer):
    """折线用的扁平数组；空值保持 null 由前端画断点"""
    dates = serializers.ListField(child=serializers.DateField())
    expected = serializers.ListField(child=serializers.FloatField(allow_null=True))
    optimistic = serializers.ListField(child=serializers.FloatField(allow_null=True))
    pessimistic = serializers.ListField(child=serializers.FloatField(allow_null=True))
    cash_days = serializers.ListField(child=serializers.FloatField(allow_null=True))
    item_count = serializers.ListField(child=serializers.IntegerField())


class SurvivalComparisonSerializer(serializers.Serializer):
    """最近两点之间的对比 + 「能不能直接比」的判断

    `comparable=False` 时界面必须显示 `reason`，不能只显示差值 ——
    期间改过类别或消耗模式的话，那个差里混着「换了算法」。
    """
    comparable = serializers.BooleanField()
    config_changed = serializers.BooleanField()
    changed_categories = serializers.ListField(child=serializers.CharField())
    reason = serializers.CharField()
    delta_expected = serializers.FloatField(allow_null=True)
    delta_item_count = serializers.IntegerField(allow_null=True)
    days_since_previous = serializers.IntegerField(allow_null=True)
    latest_date = serializers.DateField(required=False)
    previous_date = serializers.DateField(required=False)
    latest_expected = serializers.FloatField(allow_null=True, required=False)
    previous_expected = serializers.FloatField(allow_null=True, required=False)


class SurvivalTrendSerializer(serializers.Serializer):
    """趋势整体

    ⚠️ `points` 按日期**升序**（折线从左到右）；列表端点则是**倒序**
       （表格最近的在上）。两处顺序刻意不同，见 service 的说明。
    """
    available = serializers.BooleanField()
    count = serializers.IntegerField()
    min_points = serializers.IntegerField()
    has_enough_points = serializers.BooleanField()
    points = SurvivalSnapshotPointSerializer(many=True)
    comparison = SurvivalComparisonSerializer()
    series = SurvivalTrendSeriesSerializer()


class SurvivalSnapshotCreateSerializer(serializers.Serializer):
    """落一份快照的入参

    `overwrite` 显式声明「我知道今天盘过了，替换掉」——
    静默覆盖会让人以为点了两次只是刷新，实际旧结论已经没了。
    """
    date = serializers.DateField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, max_length=200)
    overwrite = serializers.BooleanField(required=False, default=False)


# ──────────────────────────────────────────────────────────────
# 实盘盘点（v3.59.3）
# ──────────────────────────────────────────────────────────────

class SurvivalStocktakeLineSerializer(serializers.Serializer):
    """盘点明细一行

    `delta` 与 `delta_kind` **不在表里**，由服务层现算 ——
    账面与实盘都在表里，一减就有。同一张表的 `book_quantity` 恰好相反：
    它在库存被校准之后就永久消失了，所以**必须**落库。
    这两者的区别正是「以后重算得出同样结果吗」那条判据的两侧。
    """
    id = serializers.IntegerField()
    item_id = serializers.IntegerField(allow_null=True)
    item_name = serializers.CharField()
    category_name = serializers.CharField()
    unit_name = serializers.CharField()
    book_quantity = serializers.FloatField(allow_null=True)
    actual_quantity = serializers.FloatField(allow_null=True)
    delta = serializers.FloatField(allow_null=True)
    delta_kind = serializers.CharField()
    note = serializers.CharField()


class SurvivalStocktakeSerializer(serializers.Serializer):
    """盘点单（头 + 可选明细）

    汇总数（`line_count` / `surplus_count` / `deficit_count` / `flat_count`）
    同样由服务层现算、不落库：明细落库即不可编辑，从明细一算就有。
    """
    id = serializers.IntegerField()
    stocktake_date = serializers.CharField()
    source = serializers.CharField()
    source_label = serializers.CharField()
    note = serializers.CharField()
    line_count = serializers.IntegerField()
    surplus_count = serializers.IntegerField()
    deficit_count = serializers.IntegerField()
    flat_count = serializers.IntegerField()
    created_at = serializers.CharField(allow_null=True)
    lines = SurvivalStocktakeLineSerializer(many=True, required=False)


class SurvivalWorksheetRowSerializer(serializers.Serializer):
    """盘点工作表一行：待盘物品 + 当前账面 + 上次盘点

    ⚠️ `book_quantity` 只用于**界面回显**（让用户知道系统记的是多少），
       提交时服务端会重新读一次。这是「显示值」与「写入值」分离的少数地方之一 ——
       别顺手把它接进入参，那会把一个必然陈旧的值写成历史。
    """
    item_id = serializers.IntegerField()
    name = serializers.CharField()
    category_id = serializers.IntegerField()
    category_name = serializers.CharField()
    unit_name = serializers.CharField()
    book_quantity = serializers.FloatField(allow_null=True)
    status = serializers.CharField()
    expire_date = serializers.CharField(allow_null=True)
    last_stocktake_date = serializers.CharField(allow_null=True)
    days_since_stocktake = serializers.IntegerField(allow_null=True)
    stocktake_cycle_days = serializers.IntegerField(allow_null=True)
    stocktake_due = serializers.BooleanField()
    restock_threshold = serializers.FloatField(allow_null=True)
    below_threshold = serializers.BooleanField()


class SurvivalStocktakeLineWriteSerializer(serializers.Serializer):
    """盘点明细入参

    ⚠️ **刻意没有 `book_quantity`。** 账面由服务端在提交那一刻从库里读。
       让前端把它交上来看似方便（页面上本来就有），实际是把一个**必然陈旧**的值
       写进历史：盘点页可能开着半小时，其间库存在别处已经变过。
    """
    item_id = serializers.IntegerField()
    actual_quantity = serializers.DecimalField(max_digits=14, decimal_places=2)
    note = serializers.CharField(required=False, allow_blank=True, max_length=200)

    def validate_actual_quantity(self, value):
        if value is None or value < 0:
            raise serializers.ValidationError('实盘数量不能为负')
        return value


class SurvivalStocktakeCreateSerializer(serializers.Serializer):
    """提交一次盘点

    `lines` 必填且不许为空：一张没有任何物品的盘点单没有意义，
    服务层也会再拦一道（`allow_empty=False` 只是为了给出更靠前的报错）。
    """
    date = serializers.DateField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, max_length=200)
    source = serializers.ChoiceField(
        choices=[c[0] for c in SURVIVAL_STOCKTAKE_SOURCES],
        required=False, default='manual',
    )
    lines = SurvivalStocktakeLineWriteSerializer(many=True, allow_empty=False)


# ══════════════════════════════════════════════════════════════
# 库存流水（v3.60.18 · P0）
# ══════════════════════════════════════════════════════════════

class SurvivalFlowSerializer(serializers.Serializer):
    """出参：一条流水。字段就是服务层组好的 dict，不重算任何东西。"""
    id = serializers.IntegerField()
    item_id = serializers.IntegerField(allow_null=True)
    item_name = serializers.CharField()
    category_name = serializers.CharField()
    unit_name = serializers.CharField()
    delta = serializers.FloatField()
    channel = serializers.CharField()
    channel_label = serializers.CharField()
    reason = serializers.CharField()
    reason_label = serializers.CharField()
    occurred_at = serializers.CharField(allow_null=True)
    reverses_id = serializers.IntegerField(allow_null=True)
    reverted = serializers.BooleanField()
    item_missing = serializers.BooleanField()
    note = serializers.CharField()
    created_at = serializers.CharField(allow_null=True)


class SurvivalFlowWriteSerializer(serializers.Serializer):
    """入参：记一笔。

    ⚠️ `channel` **不由前端凭感觉选**：它是「谁写进来的」，手工浮层一律
       `manual`（默认值）。`shelter` 是预留渠道（原「推演落为真实」），当前无调用方。
    ⚠️ `delta` 是**变化量、不是存量**：`-2` = 用掉 2、`+3` = 入库 3。
       「还剩几件」由服务层从当前库存算出来，前端**不许并列问**（方案 §3.5.1）。
    """
    item_id = serializers.IntegerField()
    delta = serializers.DecimalField(max_digits=14, decimal_places=2)
    channel = serializers.ChoiceField(
        choices=[c[0] for c in SURVIVAL_FLOW_CHANNELS], required=False, default='manual',
    )
    reason = serializers.ChoiceField(
        choices=[c[0] for c in SURVIVAL_FLOW_REASONS],
        required=False, allow_blank=True, default='',
    )
    note = serializers.CharField(required=False, allow_blank=True, max_length=200)
    occurred_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_delta(self, value):
        # 写一条 0 的流水只是噪音。服务层也会拦（这里拦是为了给出字段级报错，
        # 让前端能把红字标在「数量」那一格上）。
        if value == 0:
            raise serializers.ValidationError('变化量为 0，没有可记的一笔')
        return value


class SurvivalFlowBatchWriteSerializer(serializers.Serializer):
    """入参：一次记多笔（批量入库 / 批量消耗）。

    🔴 **时间与原因是整批一个**（`occurred_at` 在这一层、`reason` 在每行但
       前端一般不传、由后端按类别自动填）—— 绝不把单件表单复制 N 份，
       那是重复填写的重灾区。
    """
    rows = SurvivalFlowWriteSerializer(many=True, allow_empty=False)
    occurred_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_rows(self, value):
        if len(value) > SURVIVAL_FLOW_MAX_BATCH:
            raise serializers.ValidationError(
                f'一次最多记 {SURVIVAL_FLOW_MAX_BATCH} 笔，当前 {len(value)} 笔',
            )
        return value


class SurvivalFlowSummaryRowSerializer(serializers.Serializer):
    """汇总的一行。⚠️ **一定带 `unit_name`**：跨单位不相加，桶内才可比。"""
    unit_name = serializers.CharField()
    consumed = serializers.FloatField()
    gained = serializers.FloatField()
    net = serializers.FloatField()
    count = serializers.IntegerField()
    category_name = serializers.CharField(required=False)
    item_name = serializers.CharField(required=False, allow_null=True)


class SurvivalFlowSummarySerializer(serializers.Serializer):
    """出参：按月汇总。

    🔴 **刻意不给「总消耗 X 件」这个合计数** —— 「3 斤米 + 2 罐罐头」加起来
       没有意义。要说总量，只能说「按单位分别多少」（`by_unit`）。
    """
    month = serializers.CharField()
    date_from = serializers.CharField()
    date_to = serializers.CharField()
    count = serializers.IntegerField()
    consumed_count = serializers.IntegerField()
    gained_count = serializers.IntegerField()
    by_unit = SurvivalFlowSummaryRowSerializer(many=True)
    by_category = SurvivalFlowSummaryRowSerializer(many=True)
    by_item = SurvivalFlowSummaryRowSerializer(many=True)


