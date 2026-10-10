"""生存资源盘点（物资台账）—— 把生活当项目管理的「资源」侧

与 wealth 里既有的金融资产体系**刻意分开命名**：
    WealthAssetAccount / WealthAssetSnapshot = 钱（资产科目与快照）
    Survival*                               = 物（吃 / 穿 / 用 / 数字）
两套名字必须一眼能分辨 —— 「资产快照」这个表名已被金融侧占用，
照抄只会在建表时撞车，而且之后没人说得清哪张是哪张。

设计上只守一条：**派生值一律不落库**。
可支撑餐数、PERT 期望值、离散度、类别生存天数全部运行时算 ——
用户改了库存或用量而没重算，落库的那份就成了没人会发现脏数据。
"""

from django.db import models

from ..constants import (
    SURVIVAL_AGGREGATE_MODES,
    SURVIVAL_CONSUME_MODES,
    SURVIVAL_ESSENTIAL_SCOPES,
    SURVIVAL_FLOW_CHANNELS,
    SURVIVAL_FLOW_REASONS,
    SURVIVAL_GRADE_CHOICES,
    SURVIVAL_PRIORITY_CHOICES,
    SURVIVAL_ROLE_CHOICES,
    SURVIVAL_SATIETY_CHOICES,
    SURVIVAL_SNAPSHOT_SOURCES,
    SURVIVAL_STATUS_CHOICES,
    SURVIVAL_STOCKTAKE_SOURCES,
    SURVIVAL_USE_CYCLE_CHOICES,
)


class SurvivalCategory(models.Model):
    """物资类别：吃 / 穿 / 用 / 数字

    两个字段决定算法走向，都放在类别上而不是写死在服务层：

        consume_mode    怎么算 —— 配餐供餐 / 折旧 / 按需 / 时间消耗
        aggregate_mode  多件物品怎么合 —— 可替代求和 / 并列取最小

    放类别上的理由：用户把「吃」改名成「口粮」不该让算法失效，
    想给「穿」按配餐算也不该改代码（换个 mode 即可）。
    服务层**绝不出现 `if category.name == '吃'` 这种判断**。
    """

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    name = models.CharField(max_length=50, verbose_name='类别名称')
    consume_mode = models.CharField(
        max_length=20, choices=SURVIVAL_CONSUME_MODES, default='on_demand',
        verbose_name='消耗模式', help_text='决定用哪套算法：配餐/折旧/按需/时间',
    )
    aggregate_mode = models.CharField(
        max_length=20, choices=SURVIVAL_AGGREGATE_MODES, default='sum',
        verbose_name='聚合口径', help_text='可替代→求和；并列→取最小。没有「平均」这一档',
    )
    icon = models.CharField(max_length=20, blank=True, default='', verbose_name='图标')
    description = models.CharField(max_length=200, blank=True, default='', verbose_name='说明')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        # 不设 Meta.ordering：外部表的 ordering 会被注入 SELECT 而静默破坏聚合
        # （项目硬坑②），本项目 managed 表统一不设，排序交给服务层。
        db_table = 'wealth_survival_category'
        verbose_name = '物资类别'
        verbose_name_plural = '物资类别'
        constraints = [
            models.UniqueConstraint(
                fields=['user_id', 'name'], name='wealth_surv_cat_user_name_uniq',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.name}（{self.get_consume_mode_display()}）'


class SurvivalUnit(models.Model):
    """消耗单位：罐 / 克 / 袋 / 件 / 本 / 顿

    ⚠️ 单位不只是标签，**必须能换算到同一基准单位**，否则跨单位求和是错的：
        「20 罐 + 3000 克」在数学上无意义，而错误结果是静默的 ——
        它会给出一个看着完全合理的生存天数，没人会去查。

    换算规则：同一类别内先统一折算到 `base_unit`。
        base_unit 留空 = 本单位自成一系（to_base_rate 视为 1）。
    库存单位与配方单位属于不同基准时，计算层**报「单位不可比」**，
    而不是硬算一个数 —— 猜一个换算率比承认不知道更糟。
    """

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    category = models.ForeignKey(
        SurvivalCategory, on_delete=models.CASCADE,
        related_name='units', verbose_name='所属类别',
    )
    name = models.CharField(max_length=20, verbose_name='单位名称')
    base_unit = models.CharField(
        max_length=20, blank=True, default='', verbose_name='基准单位',
        help_text='同类别内的共同基准，如 克 / 件 / 册；留空表示自成基准',
    )
    to_base_rate = models.DecimalField(
        max_digits=14, decimal_places=4, default=1, verbose_name='换算率',
        help_text='1 个本单位 = N 个基准单位（1 千克 = 1000 克）',
    )
    is_serving_unit = models.BooleanField(
        default=False, verbose_name='可作为「一餐/一次」',
        help_text='如「顿」—— 可直接当作配餐的计数单位',
    )
    note = models.CharField(max_length=100, blank=True, default='', verbose_name='说明')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'wealth_survival_unit'
        verbose_name = '消耗单位'
        verbose_name_plural = '消耗单位'
        constraints = [
            models.UniqueConstraint(
                fields=['user_id', 'category', 'name'],
                name='wealth_surv_unit_user_cat_name_uniq',
            ),
        ]

    def __str__(self) -> str:
        base = self.base_unit or self.name
        return f'{self.name}（1 = {self.to_base_rate}{base}）'


class SurvivalItem(models.Model):
    """生存资源物品：一件具体的物资

    三档估算的**输入是可观测的量**，不是让人凭感觉填天数。两条口径**二选一**：

        days_per_unit                      按天（一份还能撑多少天）
            穿：一件大衣还能穿 3 年 → 1095
            用：一包纸巾能用 10 天 → 10
            数字：一本书按我的节奏能读几天
        uses_per_unit + 每 N 周期用 M 次    按次（一份能用多少次）
            卫生巾：一包 10 片、3 天用一片 → 10 次 × 3 天 = 30 天
            牙膏：一支 90 次、每天 2 次 → 90 × 1 ÷ 2 = 45 天
        （配餐类两条都不填，由配方决定每天消耗多少）

    ⚠️ 按次这条路是为「**不是每天都用**」的东西开的（卫生巾、刀片、滤芯）。
       对它们问「一份能用多少天」是问不出来的，答案只会是硬猜；
       而「一包 10 片」与「3 天用一片」两句人都答得出。判据与 `days_per_unit` 同源：
       **把问题换成可观测的量，而不是逼人给一个像样的数字。**

    ⚠️ 两条都填时**按次生效**（`compute_item_life` 里写死），因为按次填的是原始量、
       按天是折算结果，原始量更可信。界面用二选一保证不会同时提交两条。

    这样「最悲观能撑多久」就不用猜了 —— 季节、强度、心情的差异
    体现在消耗速率系数上（省着用 / 正常 / 费着用），那是人能回答的。
    """

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    category = models.ForeignKey(
        SurvivalCategory, on_delete=models.CASCADE,
        related_name='items', verbose_name='所属类别',
    )
    name = models.CharField(max_length=200, verbose_name='物品名称')
    quantity = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, verbose_name='数量',
    )
    # 指向主数据用 PROTECT：删掉一个还被物品引用的单位，会让这件物品
    # 悄悄失去计量口径 —— 宁可报错也不做这种魔法。
    unit = models.ForeignKey(
        SurvivalUnit, on_delete=models.PROTECT, null=True, blank=True,
        related_name='items', verbose_name='单位',
    )

    satiety = models.CharField(
        max_length=20, choices=SURVIVAL_SATIETY_CHOICES, blank=True, default='',
        verbose_name='饱腹角色',
        help_text='零食不参与「能撑多少顿」的计算，单独统计',
    )
    grade = models.CharField(
        max_length=20, choices=SURVIVAL_GRADE_CHOICES, blank=True, default='',
        verbose_name='等级',
    )
    status = models.CharField(
        max_length=20, choices=SURVIVAL_STATUS_CHOICES, default='stocked', verbose_name='状态',
    )
    priority = models.CharField(
        max_length=20, choices=SURVIVAL_PRIORITY_CHOICES, blank=True, default='',
        verbose_name='优先级',
    )

    days_per_unit = models.DecimalField(
        max_digits=10, decimal_places=1, null=True, blank=True,
        verbose_name='单件可用天数',
        help_text='一件/一份还能撑多少天；配餐类不填，由配方决定',
    )
    hours_per_unit = models.DecimalField(
        max_digits=8, decimal_places=1, null=True, blank=True,
        verbose_name='单件耗时(小时)',
        help_text='数字类专用：一册需要读多少小时，用来同时给出「还能读多少小时」',
    )

    # ── 按次计量（与 days_per_unit 二选一，v3.59.3） ──
    # 四个字段连起来读作：**一份能用 10 次，每 3 天用 1 次**。
    # ⚠️ 拆成四个而不是「直接填间隔天数」，是为了让用户填他的原话：
    #    他脑子里是「3 天一次」，不是「0.333 次/天」。
    #    折算（含「每周 2 次」这类周期换算）全在计算层做，界面不做除法。
    #
    # ⚠️ 后三个（num / unit / times）**只在按次口径下才有含义**，因此：
    #    ① 一律可空、且**不给默认值** —— 按天口径下它们必须是 NULL。
    #       给个 `default=1` 会凭空写出一句假话：一件羽绒服按天计量时，
    #       `use_cycle_num=1, use_cycle_unit='day', use_times=1` 读起来是
    #       「每天用 1 次」，而它其实在按「一件能穿 1095 天」算。
    #       更要命的是**序列化器放行 null、数据库拒收**，于是保存直接 500，
    #       界面上只剩一句兜底的「保存失败」，连是哪个字段错了都看不出来。
    #    ② 判据永远是「`uses_per_unit` 填了没有」，**不看这三个** ——
    #       它们是这一条口径的细节，不能反过来决定口径。
    #    ③ 置空由序列化器统一负责（`SurvivalItemFormSerializer.validate`），
    #       不指望每个客户端都记得送 null。
    uses_per_unit = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='一份可用次数',
        help_text='一包卫生巾 10 片就填 10；留空表示走「单份可用天数」',
    )
    use_cycle_num = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name='每几个周期',
        help_text='与下一个字段合读：「每 3 天」里的 3；按天口径下为空',
    )
    use_cycle_unit = models.CharField(
        max_length=10, choices=SURVIVAL_USE_CYCLE_CHOICES, null=True, blank=True,
        verbose_name='周期单位',
        help_text='「每 3 天」里的天；一个月按 30 天折算；按天口径下为空',
    )
    use_times = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name='每周期使用次数',
        help_text='「每 3 天用 1 次」里的 1；每天 2 次就填 2；按天口径下为空',
    )

    # ── 盘点相关（v3.59.3） ──
    stocktake_cycle_days = models.IntegerField(
        null=True, blank=True, verbose_name='建议盘点间隔(天)',
        help_text='按事件消耗的东西该按周期盘：一个经期后盘一次就填 30；留空表示不定周期',
    )
    restock_threshold = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='补货提醒阈值',
        help_text='库存低于这个数就该补货，与「数量」同一单位；留空表示不提醒',
    )

    expire_date = models.DateField(null=True, blank=True, verbose_name='过期日期')
    purchase_date = models.DateField(null=True, blank=True, verbose_name='购入日期')
    purchase_cost = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='购入成本',
    )

    notes = models.TextField(blank=True, default='', verbose_name='备注')
    tags = models.JSONField(default=list, blank=True, verbose_name='标签')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'wealth_survival_item'
        verbose_name = '生存资源物品'
        verbose_name_plural = '生存资源物品'
        indexes = [
            models.Index(fields=['user_id', 'category'], name='wealth_surv_item_cat_idx'),
            models.Index(fields=['expire_date'], name='wealth_surv_item_expire_idx'),
        ]

    def __str__(self) -> str:
        unit = self.unit.name if self.unit else '件'
        return f'{self.name} ×{self.quantity}{unit}'


class SurvivalEssential(models.Model):
    """必需品基准项：一个人生活**本该**有的东西（v3.59.7）

    与 `SurvivalItem` 是**两件事**，刻意分开表、分开生命周期：

        SurvivalEssential = 「本该有什么」  用户视角，可增删改；不含数量
        SurvivalItem      = 「实际有多少」  库存事实；由消耗与盘点驱动

    🔴 为什么非得分两张表，而不是给物品加一个 `is_essential` 开关：

        开关加在**物品**上，就永远表达不了「这东西根本没录入」——
        物品不存在时那个开关也不存在，而「漏了」恰恰是本表要抓的主要缺口。
        实测原状：「用」类底下只录了 2 件（纸巾、洗脸巾），牙膏、洗发水、
        卫生纸、洗衣液从来没进过系统，短板却照样理直气壮地判在「吃」上。
        给物品加开关救不了这种情形 —— 它只会回答「我录的里面哪些重要」。

    两者靠 `items`（多对多，可空）对上：对上了算天数并分档，一件都没对上就是缺口。

    🔴 为什么是**多对多**而不是单个外键（v3.59.12）：

        一条基准项常常需要**几件不同的物品并列才成立** ——
        睡衣有夏季 / 秋季 / 冬季，卫生巾分日用 / 夜用，鞋分室内 / 室外。
        单个外键逼用户在「夏季睡衣」和「冬季睡衣」里二选一，
        而无论选哪件都答不对「睡衣还能撑多久」：冬天还是没得穿。

        所以关联变成一组，**组内取最小**（与类别口径同一条判据：可替代才求和，
        并列缺一不可就取最小）。取最小是**保守**方向：算错成「虚报缺口」，
        用户在界面上看得见并会去核实；反过来求和错了是「掩盖缺口」，
        静默且危险（「用」类曾被一件洗脸巾撑到 4.5 万天，而牙膏剩 5 天没人看见）。

    ⚠️ 关联物品后来被删掉，中间表的行会跟着没，基准项自动回到「未录入」——
       这正是要的语义：删一件物品不该连带删掉「我本该有牙膏」这条认知，
       它只是暂时没有对应的库存记录。（旧版用 `SET_NULL` 达成的就是这件事。）

    ⚠️ 本表**不存任何派生值**（覆盖天数、档位都不落库）：库存或用量一改它们就陈旧，
       而陈旧的分档比没有分档更糟 —— 它看起来是对的，没人会去查。
    """

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    name = models.CharField(max_length=100, verbose_name='必需品名称')
    category = models.ForeignKey(
        SurvivalCategory, on_delete=models.CASCADE,
        related_name='essentials', verbose_name='归属类别',
    )
    scope = models.CharField(
        max_length=20, choices=SURVIVAL_ESSENTIAL_SCOPES, default='core',
        verbose_name='性质',
        help_text='底线必需：缺了影响健康/卫生/体面；改善型：只是「有更好」',
    )
    unit_name = models.CharField(
        max_length=20, blank=True, default='', verbose_name='建议单位',
        help_text='仅作录入提示，不参与计算 —— 实际单位以关联物品为准',
    )
    hint = models.CharField(
        max_length=200, blank=True, default='', verbose_name='录入提示',
        help_text='帮用户回忆消耗节奏的一句话，如「一支约 90 次，每天早晚各一次」',
    )
    items = models.ManyToManyField(
        SurvivalItem, blank=True,
        related_name='essential_links', verbose_name='关联物品',
        help_text='对账的另一半，可挂多件（并列缺一不可，取最短的那件）；'
                  '一件都不挂表示这件必需品还没有对应的库存记录',
    )
    note = models.CharField(max_length=200, blank=True, default='', verbose_name='说明')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'wealth_survival_essential'
        verbose_name = '必需品基准项'
        verbose_name_plural = '必需品基准项'
        constraints = [
            # 不用 `unique=True`：那会连带把 name 单独设成唯一，
            # 而这里的语义是「同一用户下不重名」—— 两个字段一起才是约束。
            models.UniqueConstraint(
                fields=['user_id', 'name'], name='wealth_surv_ess_user_name_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['user_id', 'category'], name='wealth_surv_ess_cat_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.name}（{self.get_scope_display()}）'


class SurvivalRecipe(models.Model):
    """配餐 / 消耗配方：一顿饭由哪些「餐位」组成、每天吃几次

    存在的理由：一顿饭不是一种东西。
        「一罐八宝粥 + 100 克米粉 + 100 克面条」里，三者都能单独顶一顿，
        关系是**互相替代**；而主食与饮水之间才是**缺一不可**。
        所以单个食物项算不出「能撑多少天」，必须由配方把餐位组织起来。
    """

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    category = models.ForeignKey(
        SurvivalCategory, on_delete=models.CASCADE,
        related_name='recipes', verbose_name='所属类别',
    )
    name = models.CharField(max_length=50, verbose_name='配方名称')
    meals_per_day = models.DecimalField(
        max_digits=4, decimal_places=1, default=3, verbose_name='每日餐数',
        help_text='基准档（最可能）；最乐观/最悲观的餐数取 constants 里的三档',
    )
    note = models.CharField(max_length=200, blank=True, default='', verbose_name='说明')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'wealth_survival_recipe'
        verbose_name = '配餐配方'
        verbose_name_plural = '配餐配方'
        constraints = [
            models.UniqueConstraint(
                fields=['user_id', 'category', 'name'],
                name='wealth_surv_recipe_user_cat_name_uniq',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.name}（{self.meals_per_day} 餐/天）'


class SurvivalRecipeLine(models.Model):
    """配方行：一个餐位下的一件食材

    ⚠️ 用**真外键子表**而不是在配方上塞 JSONField 存 `[{"item_id": 1}]`：
       JSON 里的 ID 没有外键约束（删了物品就悬空）、改不了、查不了、
       没有索引，而且缺件时会静默跳过 —— 静默跳过的后果是**把这道菜算得更耐吃**
       （分母少了一项），得出一个偏乐观却没人发现的数字。

    `unit` 留空 = 与物品自己的单位相同。需要时（买一袋米、配方按克用）可以
    单独指定，计算层负责换算；换算不可比时报错而非硬算。
    """

    recipe = models.ForeignKey(
        SurvivalRecipe, on_delete=models.CASCADE,
        related_name='lines', verbose_name='所属配方',
    )
    item = models.ForeignKey(
        SurvivalItem, on_delete=models.PROTECT,
        related_name='recipe_lines', verbose_name='物品',
    )
    role = models.CharField(
        max_length=20, choices=SURVIVAL_ROLE_CHOICES, default='staple',
        verbose_name='餐位',
        help_text='同餐位内可替代（求和）；跨餐位必配（取最小）',
    )
    quantity_per_serving = models.DecimalField(
        max_digits=14, decimal_places=4, verbose_name='每餐用量',
    )
    unit = models.ForeignKey(
        SurvivalUnit, on_delete=models.PROTECT, null=True, blank=True,
        related_name='recipe_lines', verbose_name='用量单位',
        help_text='留空表示与物品单位相同',
    )
    note = models.CharField(max_length=200, blank=True, default='', verbose_name='说明')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'wealth_survival_recipe_line'
        verbose_name = '配方行'
        verbose_name_plural = '配方行'

    def __str__(self) -> str:
        return f'{self.recipe.name} · {self.item.name} ×{self.quantity_per_serving}'


class SurvivalCombo(models.Model):
    """组合：几件物品「一起用」的声明（v3.59.13）

    用户的话：「燕麦米、绿豆、薏仁、紫米我是**分开登记**的，但烹饪时**一起下锅**。」
    物品登记与「一起用」是两件事 —— 前者是库存事实（各自算数量、各自算保质期），
    后者是一次搭配声明。分开登记 + 一起烹饪的场景里，缺了这张表就只能
    「在配方里加四行」，而那四行之间没有任何东西说明它们是一锅的。

    🔴 组合里**只管三件事**：有哪几件、每餐各用多少、叫什么名字。

        不放餐位（主食位 / 必配位）—— 那是**配方行的属性**：
            同一锅杂粮粥，出现在早餐配方里可能是必配位、出现在别的场景里
            可能是主食位。锁死在组合上就表达不了。
        不放「份数」倍率 —— 🔴 这是刻意不做：见 `SurvivalRecipeComboLine` 的注释。

    🔴 组内口径 = **取最小**（并列缺一不可），与「基准项挂多件」同一条判据：
        四样都要下锅，能煮几顿由**最先耗尽**的那件决定。
        取最小是保守方向 —— 算错成「虚报缺口」用户看得见；
        反过来求和是「掩盖缺口」，静默且危险。

    ⚠️ 本表**不存任何派生值**（能支撑多少顿不落库）：库存或用量一改就会陈旧，
       而陈旧的值比没有值更糟 —— 它看起来是对的，没人会去查。

    ⚠️ 组合**不绑定消耗模式**：任何类别都能建。配方目前只出现在
       `consume_mode='meal'` 的类别下，但组合本身是一份可复用的搭配声明，
       不该因为「这个类别现在不算配餐」就建不了。
    """

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    category = models.ForeignKey(
        SurvivalCategory, on_delete=models.CASCADE,
        related_name='combos', verbose_name='归属类别',
    )
    name = models.CharField(max_length=50, verbose_name='组合名称')
    note = models.CharField(max_length=200, blank=True, default='', verbose_name='说明')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'wealth_survival_combo'
        verbose_name = '生存资源组合'
        verbose_name_plural = '生存资源组合'
        constraints = [
            models.UniqueConstraint(
                fields=['user_id', 'category', 'name'],
                name='wealth_surv_combo_user_cat_name_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['user_id', 'category'], name='wealth_surv_combo_cat_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.name}（{self.members.count()} 件）'


class SurvivalComboItem(models.Model):
    """组合成员：组合里的一件物品 + 每餐用量

    ⚠️ 用量定在**成员**上，不在组合上：四样东西每餐用量各不相同
       （燕麦米 40 克、绿豆 30 克…），放组合上就只能填一个数。

    ⚠️ `unit` 留空 = 与物品自己的单位相同（与配方行同源，计算层同一个换算函数）。

    🔴 `UNIQUE(combo, item)`：同一件物品在一个组合里**只能出现一次**。
       出现两次是一种**隐性的倍率**（「绿豆 ×2」= 用量悄悄翻倍），
       而界面上两行长得一模一样、看不出是被乘过的 —— 这正是硬坑 12 的形态。
       要加量请改这一行的「每餐用量」。
    """

    combo = models.ForeignKey(
        SurvivalCombo, on_delete=models.CASCADE,
        related_name='members', verbose_name='所属组合',
    )
    item = models.ForeignKey(
        SurvivalItem, on_delete=models.PROTECT,
        related_name='combo_members', verbose_name='物品',
    )
    quantity_per_serving = models.DecimalField(
        max_digits=14, decimal_places=4, verbose_name='每餐用量',
    )
    unit = models.ForeignKey(
        SurvivalUnit, on_delete=models.PROTECT, null=True, blank=True,
        related_name='combo_members', verbose_name='用量单位',
        help_text='留空表示与物品单位相同',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'wealth_survival_combo_item'
        verbose_name = '组合成员'
        verbose_name_plural = '组合成员'
        constraints = [
            models.UniqueConstraint(
                fields=['combo', 'item'],
                name='wealth_surv_combo_item_uniq',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.combo.name} · {self.item.name} ×{self.quantity_per_serving}'


class SurvivalRecipeComboLine(models.Model):
    """配方里的**组合行**：这一顿会用到「一整份组合」

    🔴 为什么是**独立的表**，而不是把 `SurvivalRecipeLine.item` 改成可空、
       再加一个 `combo` 外键（「二选一」）：

        二选一要靠 `CheckConstraint` 兜住，而「一行恰好有一个来源」这件事
        在两张表里是**由表结构本身**保证的 —— 一行在一张表里，就不可能在另一张。
        用约束去补一个本该由结构表达的不变量，等于把校验和语义分开放。

        另一层好处：既有 `wealth_survival_recipe_line` **一个字节都不用动**
        （不必把 `item_id` / `quantity_per_serving` 放宽成可空，
        也不必给已存在的表补列）。存量数据与既有用例零风险。

    🔴 这一行**没有「每餐用量」也没有「份数」** —— 用量全在组合成员上。

        刻意不做「组合 ×2」这种倍率：本项目踩过一次同形状的坑
        （「一份能用几次」与「数量」被都填成 300，静默乘出 45,000 天）。
        「倍数 × 另一处用量」就是同一个形状 —— 两个数各自看着正常，
        乘起来才错，而界面上看不出来。**要加量就改组合里那一行的每餐用量。**

    🔴 `UNIQUE(recipe, combo)`：同一组合在一个配方里只能挂一次 ——
       挂两次等于又一个隐性倍率（同 `SurvivalComboItem` 的判据）。

    ⚠️ 组内口径恒为**取最小**（用户在需求里拍板），与配方行的 `role` 无关：
       `role` 决定这一行**对外**怎么参与聚合（主食位求和 / 必配位取最小），
       组合**对内**永远取最小（四样缺一不可）。
       挂必配位时，「展开成四行必配位」与「一行组合」在数学上等价
       （min-of-min = min），但仍选一行 —— 展开会让列表膨胀四倍、
       且改组合不再回溯影响已展开的配方（**静默分叉**）。
    """

    recipe = models.ForeignKey(
        SurvivalRecipe, on_delete=models.CASCADE,
        related_name='combo_lines', verbose_name='所属配方',
    )
    combo = models.ForeignKey(
        SurvivalCombo, on_delete=models.PROTECT,
        related_name='recipe_lines', verbose_name='组合',
    )
    role = models.CharField(
        max_length=20, choices=SURVIVAL_ROLE_CHOICES, default='staple',
        verbose_name='餐位',
        help_text='对外怎么参与聚合：主食位求和、必配位取最小；组合内部恒取最小',
    )
    note = models.CharField(max_length=200, blank=True, default='', verbose_name='说明')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'wealth_survival_recipe_combo_line'
        verbose_name = '配方组合行'
        verbose_name_plural = '配方组合行'
        constraints = [
            models.UniqueConstraint(
                fields=['recipe', 'combo'],
                name='wealth_surv_recipe_combo_uniq',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.recipe.name} · [{self.combo.name}]'


class SurvivalSnapshot(models.Model):
    """盘点快照（头）：某一天算出来的结论，落下来成为历史

    ⭐ 唯一不变量：**快照一旦落库，就绝不因后续改动而变。**

    这条不变量解释了本模块与一期「派生值不落库」看似矛盾的地方 —— 两者禁的
    不是同一件事：一期禁的是「缓存当前随时可重算的派生值」（库存一改缓存就陈旧），
    而快照要的**恰恰是**「那时我以为能撑多久」这个历史事实。若快照只存库存明细、
    每次按今天的配置重算，历史曲线就会被追溯性改写 —— 那是假曲线。

    因此这里存的是**结论**（天数 / 短板 / 瓶颈 / 覆盖率 / 计数 / 可信度），
    再加上足以判断「两次之间是否可比」的最小配置指纹（见明细表）。

    ⚠️ 所有天数类字段都可为 NULL 且**与 0 不同义**：NULL = 那天算不出来
       （没有可用物品 / 配方配置不全），0 = 那天真的撑不了。混起来会把
       「还没录数据」显示成最坏结论。
    """

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    snapshot_date = models.DateField(verbose_name='盘点日期')
    source = models.CharField(
        max_length=20, choices=SURVIVAL_SNAPSHOT_SOURCES, default='manual', verbose_name='来源',
    )
    note = models.CharField(max_length=200, blank=True, default='', verbose_name='备注')

    # ── 综合结论（跨类别取最小） ──
    days_optimistic = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='乐观天数',
    )
    days_likely = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='最可能天数',
    )
    days_pessimistic = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='悲观天数',
    )
    days_expected = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='三点估算期望天数',
    )
    spread = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='离散度',
    )
    shortest_category = models.CharField(
        max_length=50, blank=True, default='', verbose_name='当时的最短类别',
        help_text='存当时的名字：类别后来改了名，历史点不该跟着改名',
    )

    # ── 钱这一条腿与三年覆盖率 ──
    bottleneck = models.CharField(max_length=20, blank=True, default='', verbose_name='瓶颈判定')
    cash_months = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='钱能撑的月数',
    )
    cash_days = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='钱能撑的天数',
    )
    coverage_pct = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True, verbose_name='三年覆盖率(%)',
    )
    coverage_remaining_days = models.IntegerField(
        null=True, blank=True, verbose_name='当时窗口剩余天数',
    )

    # ── 规模与可信度（判断两个点能不能直接比的依据） ──
    category_count = models.IntegerField(default=0, verbose_name='类别数')
    item_count = models.IntegerField(default=0, verbose_name='可用物品件数')
    snack_days = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='零食天数',
    )
    issue_count = models.IntegerField(default=0, verbose_name='当时的问题条数')
    trustworthy = models.BooleanField(
        default=True, verbose_name='结论是否可信',
        help_text='有任一类别或配方配置不全时为假；历史点要带着这个标记，否则回调时看不出它当初就不可信',
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'wealth_survival_snapshot'
        verbose_name = '生存资源盘点快照'
        verbose_name_plural = '生存资源盘点快照'
        constraints = [
            # 同一天只留一份：一天两个点会让曲线上出现竖直段，
            # 而且「哪份是真的」无法回答。重复盘点走「拒绝 + 提示」，不静默覆盖。
            models.UniqueConstraint(
                fields=['user_id', 'snapshot_date'], name='wealth_surv_snap_user_date_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['user_id', 'snapshot_date'], name='wealth_surv_snap_date_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.snapshot_date} · {self.days_expected} 天'


class SurvivalSnapshotCategory(models.Model):
    """快照的类别明细：某个类别在那一天的结论

    类别名与消耗模式在这里是**冗余留存**，不靠外键取回：

      · 类别可以改名 —— 「吃」改成「口粮」不该让过去的点集体改名；
      · 类别可以删除 —— 删掉一个已经不再盘点的类别，历史点不该直接消失。

    所以 `category` 用 `SET_NULL`：类别没了，历史留着，并且**不阻塞删除**。
    这正是「历史自带名字」的好处：删除保护只需要管当下的引用，不必管历史。
    """

    snapshot = models.ForeignKey(
        SurvivalSnapshot, on_delete=models.CASCADE,
        related_name='categories', verbose_name='所属快照',
    )
    category = models.ForeignKey(
        SurvivalCategory, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='snapshots', verbose_name='类别',
    )
    category_name = models.CharField(max_length=50, verbose_name='当时的类别名')
    consume_mode = models.CharField(
        max_length=20, verbose_name='当时的消耗模式',
        help_text='两次快照之间若变过，说明算法换了，天数不可直接比',
    )
    aggregate_mode_effective = models.CharField(
        max_length=20, blank=True, default='', verbose_name='当时生效的聚合口径',
    )

    days_optimistic = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='乐观天数',
    )
    days_likely = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='最可能天数',
    )
    days_pessimistic = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='悲观天数',
    )
    days_expected = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='期望天数',
    )

    usable_item_count = models.IntegerField(default=0, verbose_name='可用物品件数')
    item_count = models.IntegerField(default=0, verbose_name='物品件数')
    snack_days = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='零食天数',
    )
    hours_total = models.DecimalField(
        max_digits=12, decimal_places=1, null=True, blank=True, verbose_name='可读小时数',
    )
    issue_count = models.IntegerField(default=0, verbose_name='问题条数')
    trustworthy = models.BooleanField(default=True, verbose_name='该类别是否可信')

    class Meta:
        db_table = 'wealth_survival_snapshot_category'
        verbose_name = '盘点快照类别明细'
        verbose_name_plural = '盘点快照类别明细'
        constraints = [
            models.UniqueConstraint(
                fields=['snapshot', 'category_name'],
                name='wealth_surv_snapcat_name_uniq',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.category_name} · {self.days_expected} 天'


class SurvivalStocktake(models.Model):
    """实盘盘点单（头）：某一天我数了数，手头实际还有多少

    ⚠️ 与 `SurvivalSnapshot`（盘点快照）**不是一回事**，别合并成一张表：

        快照   = 系统算出来的**结论**（我以为能撑多久），不需要人动手
        盘点单 = 人填进去的**实盘**（实际还剩多少件），必须人动手

    混为一谈的后果是「点一下按钮就说自己盘过了」—— 那是假盘点，
    而假盘点会把历史记录的证据价值一并毁掉：记录在，但它证明不了任何事。
    两张表、两个入口，就是为了让「我核对过实物」这件事有迹可循。

    🔴 汇总数（盘了几项 / 几项盈 / 几项亏）**不落库**：
       明细行一旦落库就不可编辑，从明细一算就得出 —— 按「以后重算得出同样结果吗」
       的判据，得得出 ⇒ 不落库。快照表之所以落汇总，是因为它**没有明细**，
       汇总就是它的全部内容。两张表的差别恰好是这条判据的两侧。

    不设「一天一单」的唯一约束：盘点本来就是可以分批的 ——
    今天盘「用」明天盘「吃」、上午盘一半下午接着盘，都该成立。
    """

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    stocktake_date = models.DateField(verbose_name='盘点日期')
    source = models.CharField(
        max_length=20, choices=SURVIVAL_STOCKTAKE_SOURCES, default='manual', verbose_name='来源',
    )
    note = models.CharField(max_length=200, blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'wealth_survival_stocktake'
        verbose_name = '生存资源实盘盘点'
        verbose_name_plural = '生存资源实盘盘点'
        indexes = [
            models.Index(fields=['user_id', 'stocktake_date'], name='wealth_surv_take_date_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.stocktake_date} 实盘盘点'


class SurvivalStocktakeLine(models.Model):
    """实盘盘点明细：一件物品的「账面 vs 实际」

    🔴 `book_quantity` **必须落库** —— 这恰恰是本表存在的理由：
       「盘点那一刻账上有多少」事后**重算不出来**（库存随即被校准成实盘数，
       原来那个数就永久消失了）。按「以后重算得出同样结果吗」的判据 ——
       得不出 ⇒ 必须落库。而下面的 `delta` 正好相反，一减就有，故不落库。

    ⚠️ `book_quantity` 由**服务层在提交那一刻从库里读**，绝不取前端传来的值：
       盘点页面可能开着很久，期间库存已经被别处改过；信前端的数就会把
       「盘点期间发生的变化」算成盘盈盘亏，差额还会对不上。
       这不只是防篡改 —— 前端那个数本来就可能是**过期**的。

    物品名与类别名**冗余留存**（`item` 用 `SET_NULL`）：改名不该改写历史，
    删除不该让历史消失（同二期快照明细的判据）。
    """

    stocktake = models.ForeignKey(
        SurvivalStocktake, on_delete=models.CASCADE,
        related_name='lines', verbose_name='所属盘点',
    )
    item = models.ForeignKey(
        SurvivalItem, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='stocktake_lines', verbose_name='物品',
    )
    item_name = models.CharField(max_length=200, verbose_name='当时的物品名')
    category_name = models.CharField(
        max_length=50, blank=True, default='', verbose_name='当时的类别名',
    )
    unit_name = models.CharField(max_length=20, blank=True, default='', verbose_name='单位')

    book_quantity = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name='账面数量',
        help_text='提交那一刻系统读到的库存，不是前端传上来的',
    )
    actual_quantity = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name='实盘数量',
    )
    note = models.CharField(max_length=200, blank=True, default='', verbose_name='说明')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'wealth_survival_stocktake_line'
        verbose_name = '实盘盘点明细'
        verbose_name_plural = '实盘盘点明细'

    def __str__(self) -> str:
        return f'{self.item_name} 账 {self.book_quantity} → 实 {self.actual_quantity}'


# ══════════════════════════════════════════════════════════════
# 库存流水（v3.60.18 · P0）—— 库存「怎么变的」
# ══════════════════════════════════════════════════════════════

class SurvivalFlow(models.Model):
    """库存流水：这一件物品的数量**怎么变的**

    ⚠️ 生存资源已经有两张历史表，本表是**第三件不同的事**，别朝任何一张合并：

        SurvivalSnapshot   系统算出来的**结论**（我以为能撑多久）—— 不用人动手
        SurvivalStocktake  人**核对过**（账面 vs 实盘）        —— 必须人动手
        SurvivalFlow(本表) 库存**怎么变的**（连续流水）        —— 人登记 / 系统代记

    合并的后果是「这 2 罐是被我吃了，还是被脚本改了」再也分不出来。
    上一版缺的正是这一层：改库存不留痕 ⇒「这个月吃掉几罐」查不出来。

    🔴 **不落 `quantity_after`。** 留一列「变化后还剩多少」很贴心，但它是一列
       **存量**，而存量只有一个真源在 `SurvivalItem.quantity`。一旦有人绕过流水
       直接改库存（脚本、后台、以后新加的编辑入口），这一列就开始**静默过期**
       而看起来仍然像真的 —— 项目判据：**流表永不出现存量列**。
       界面要显示「3 → 2」时，用当前 `quantity` 反推一次即可（纯展示、不落库）。

    🔴 **不做物理删除，只做「撤销」**（`reverses` 指回被冲销的那条）：
       用户想的是「我记错了」，不是「我要删数据」。撤销 = 自动补一条反向流水 ——
       账正回来、历史全留。一条流水**最多被冲销一次**（服务层判，见
       `services/survival_flow.py`），否则点两次撤销就多扣一次。
    """

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    # 物品删了，历史留着 —— 所以是 SET_NULL 而不是 CASCADE，
    # 并且下面三列冗余留存「当时的样子」（改名 / 删类别都不回改历史，
    # 同快照明细与盘点明细的既有判据）。
    item = models.ForeignKey(
        SurvivalItem, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='flows', verbose_name='物品',
    )
    item_name = models.CharField(max_length=200, verbose_name='当时的物品名')
    category_name = models.CharField(
        max_length=50, blank=True, default='', verbose_name='当时的类别名',
    )
    unit_name = models.CharField(max_length=20, blank=True, default='', verbose_name='单位')
    # 🔴 正负皆可：`−2` = 用掉 2、`+3` = 入库 3。**是变化量，不是存量。**
    delta = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name='变化量',
        help_text='正数为入库、负数为消耗；绝不存「变化后还剩多少」',
    )
    channel = models.CharField(
        max_length=20, choices=SURVIVAL_FLOW_CHANNELS, verbose_name='渠道',
        help_text='这一笔是谁写进来的：手工登记 / 盘点校准 / 推演落为真实 …',
    )
    reason = models.CharField(
        max_length=20, choices=SURVIVAL_FLOW_REASONS, blank=True, default='',
        verbose_name='原因', help_text='为什么变：吃掉 / 坏了 / 买入 …',
    )
    occurred_at = models.DateTimeField(
        verbose_name='发生时刻', help_text='默认现在，可补记过去，但不许未来',
    )
    reverses = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reverts', verbose_name='冲销对象',
        help_text='本行是来冲销哪一条的；被冲销的原行不动，历史全留',
    )
    note = models.CharField(max_length=200, blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'wealth_survival_flow'
        verbose_name = '生存资源库存流水'
        verbose_name_plural = '生存资源库存流水'
        # 最近发生的在最前；同刻多条按 id 倒序 —— 保证顺序稳定可预期
        ordering = ['-occurred_at', '-id']
        indexes = [
            models.Index(fields=['user_id', 'occurred_at'], name='wealth_surv_flow_time_idx'),
            models.Index(fields=['user_id', 'item'], name='wealth_surv_flow_item_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.occurred_at:%Y-%m-%d} {self.item_name} {self.delta:+}'
