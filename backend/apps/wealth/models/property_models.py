"""物件资产（v3.60.0）—— 耐用品台账。

文件分工，别混：
    钱     = WealthAsset*     （wealth_models.py，金融侧，迁移 0017）
    消耗物 = Survival*        （survival_models.py，会被用完，答案是「天」）
    耐用品 = WealthProperty*  （本文件，会折旧会报废，答案是「年」与「元」）

判据一句话：**纸巾会被用完 → 生存资源；冰箱会被用坏 → 物件资产。**

两张表：
    WealthPropertyCategory  类别主数据（轻量，用户可增删改）
    WealthProperty          物件本体

🔴 派生值一律不落库（净值 / 已用月数 / 剩余月数 / 月折旧 / 各项合计），全部运行时算。
   判据「以后重算得出同样结果吗」→ 能，所以不落库（同 §23.2）。
   唯一实现见 services/property_calc.py，视图层与前端都不许出现第二份公式。
"""

from django.db import models

from ..constants import (
    PROPERTY_CONDITION_CHOICES,
    PROPERTY_STATUS_CHOICES,
    PROPERTY_STATUS_IN_USE,
)


class WealthPropertyCategory(models.Model):
    """物件类别：家电 / 家具 / 数码 / 交通 / 家装 / 其他

    ⚠️ 类别**只装「用途」**（这东西干嘛用的）。
       不要把体型（大件 / 小玩意儿）或价值档（高 / 中 / 低）建进来 —— 那是另外两把尺子。
       三条理由见 constants.PROPERTY_CATEGORY_SEEDS 上方的注释与设计文档 §4.3 专条，
       核心一条是：类别带 default_lifespan_months 的预填语义，混装会变成**软兜底**。

    轻量主数据：用户可随时增删改；icon 与默认年限都只是给表单帮忙的。
    """

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    name = models.CharField(max_length=50, verbose_name='类别名称')
    icon = models.CharField(max_length=20, blank=True, default='', verbose_name='图标')

    # ⚠️ **仅作表单预填，绝不兜底。**
    # 用户没填年限的物件，净值一律算不出（返回 null），**不拿这个值顶上**。
    # 一旦兜底，界面上就分不出「他自己填了 5 年」与「他没填、系统按类别猜了 5 年」——
    # 而这正是本项目历史上最贵的一类 bug（错误结果是静默的，看着完全合理）。
    default_lifespan_months = models.IntegerField(
        null=True, blank=True, verbose_name='默认使用年限(月)',
        help_text='只用来预填新增表单、可逐件改；留空表示不预填。绝不作为任何计算依据',
    )

    sort_order = models.IntegerField(default=0, verbose_name='排序')
    note = models.CharField(max_length=200, blank=True, default='', verbose_name='说明')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        # 不设 Meta.ordering：ordering 会被注入 SELECT 而静默破坏聚合（项目硬坑②），
        # 本项目 managed 表统一不设，排序交给服务层。
        db_table = 'wealth_property_category'
        verbose_name = '物件类别'
        verbose_name_plural = '物件类别'
        constraints = [
            models.UniqueConstraint(
                fields=['user_id', 'name'], name='wealth_prop_cat_user_name_uniq',
            ),
        ]

    def __str__(self) -> str:
        return self.name


class WealthProperty(models.Model):
    """物件资产：一件具体的耐用品。

    回答三个问题：
        ① 这些家当一共花了多少钱      → purchase_amount 求和
        ② 现在还在用、还值多少        → status + purchase_date + lifespan_months 推净值
        ③ 哪些已经用够本了            → 已用月数 vs 计划月数 并排摆出来

    ⚠️ 不设 quantity（数量）：**一台冰箱 = 一条记录**。
       「椅子 ×4」请登记 4 条，或名称写「餐椅 ×4」并填整批总价。
       引入数量必然带出「单价还是总价」的歧义，而项目历史上正是
       「同一个数字被填两遍、算法静默乘起来」（洗脸巾 45,000 天）的一类成因。
       资产 99% 是单件，为 1% 的批量场景引入一个**会静默算错**的字段，代价不对称。

    ⚠️ 净值是**附带产出**，主产出是「已用月数 vs 计划月数」：
       给一台 2016 年的空调算「现在值 800 元」没有意义（你不会卖掉它），
       有意义的是「计划用 8 年、已经用了 10 年 2 月」—— 它一句话回答了该不该换。
    """

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    # 指向主数据用 PROTECT：删一个还被物件引用的类别，会让这件物件失去归属 ——
    # 宁可报错（400 + 可照做的提示）也不做级联删除这种魔法。
    category = models.ForeignKey(
        WealthPropertyCategory, on_delete=models.PROTECT,
        related_name='properties', verbose_name='类别',
    )
    name = models.CharField(max_length=100, verbose_name='物件名称')
    spec = models.CharField(max_length=100, blank=True, default='', verbose_name='品牌/型号')
    location = models.CharField(
        max_length=50, blank=True, default='', verbose_name='存放位置',
        help_text='厨房 / 卧室 / 老家 —— 盘家当最自然的问句是「这东西在哪儿」',
    )

    # ── 金额与时间（可空：盘家当必然有「想不起来多少钱了」的东西） ──
    purchase_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='购买金额',
        help_text='整件的总价；留空表示想不起来了，此时净值算不出（不按 0 计）',
    )
    purchase_date = models.DateField(null=True, blank=True, verbose_name='购买日期')
    lifespan_months = models.IntegerField(
        null=True, blank=True, verbose_name='计划使用年限(月)',
        help_text='界面按年填（支持小数，8.5 = 8 年 6 月），库里存月；留空则净值算不出',
    )

    # ── 两个正交维度（别合并成一个下拉框） ──
    status = models.CharField(
        max_length=20, choices=PROPERTY_STATUS_CHOICES, default=PROPERTY_STATUS_IN_USE,
        verbose_name='状态',
        help_text='回答「我还要不要它」：在用 / 闲置 / 已报废',
    )
    # ⚠️ `condition` 是 MySQL 保留字，且**不参与任何算法**。
    #    详见 constants.PROPERTY_CONDITION_CHOICES 上方的推导与设计文档 §4.3 专条。
    condition = models.CharField(
        max_length=20, choices=PROPERTY_CONDITION_CHOICES, default='normal',
        verbose_name='状况',
        help_text='回答「它现在好不好使」，与状态正交；不参与任何数字，只供查看与筛选',
    )

    # ── 报废（仅 status=scrapped 时有意义，由序列化器统一负责置空） ──
    scrapped_date = models.DateField(
        null=True, blank=True, verbose_name='报废日期',
        help_text='可空：人不一定记得日期；为空只影响「报废时的净值」算不出，不阻止保存',
    )
    dispose_note = models.CharField(
        max_length=200, blank=True, default='', verbose_name='处置备注',
        help_text='送人 / 以旧换新 / 坏了；纯记录，不参与算法',
    )

    note = models.TextField(blank=True, default='', verbose_name='备注')
    tags = models.JSONField(default=list, blank=True, verbose_name='标签')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'wealth_property'
        verbose_name = '物件资产'
        verbose_name_plural = '物件资产'
        # ⚠️ 新写 Index 一律显式写 name= —— Django 6.0 自动命名变更会凭空产出 RenameIndex。
        indexes = [
            models.Index(fields=['user_id', 'category'], name='wealth_prop_user_cat_idx'),
            models.Index(fields=['status'], name='wealth_prop_status_idx'),
        ]

    def __str__(self) -> str:
        return self.name
