from django.db import models

from . import constants


class GoodThing(models.Model):
    """好恶物双面档案——记录你亲自验证过的好东西，和踩过的坑

    ## 两个维度必须分清（v3.60.32 的核心修正）

    | 字段 | 回答什么 | 取值 |
    |---|---|---|
    | `subject_kind` | **这东西是实物还是一种做法** | 实物 / 方法 |
    | `category` | **这东西干嘛用的**（只有实物才有） | 吃 / 穿 / 用 / 店 / 地方 / 服务 |
    | `method_group` | **这方法属于哪方面**（只有方法才有，可留空） | 生活 / 工作 / … |

    ⚠️ 这三者过去被压成「类别」一个下拉，于是「方法」变成兜底桶（实测 74%，
    里面装着人、公众号、课程、App 价格）。**一个互斥枚举里混进不同质的成员，
    它必然变成兜底桶。**

    ## 联动（评价真源在本表）

    `property` / `survival_item` 两个可空外键互斥，指向 `wealth` 的两个实物池。
    🔴 **评价的真源只在本表**：物件资产与物品清单**不加**「是不是好东西」字段，
    只在列表行内只读显示徽标。判定口径见 `apps/treasure/badges.py`。

    ⚠️ 用 `SET_NULL` 而不是 `CASCADE`：物件删了，这份评价文字**有独立价值**，
    应当留下、只失去关联。（项目禁用级联删除；`SET_NULL` 是保留而非删除。）
    ⚠️ `condition=broken` 的空调仍可以是 👍 好物。**👎 ≠ 该报废，👍 ≠ 状况良好** ——
    三把尺子（status / condition / 评价）正交，界面并列显示、互不推导。
    """

    RECORD_TYPE_CHOICES = [
        ('好', '👍 好物'),
        ('歹', '👎 歹物'),
    ]

    SUBJECT_KIND_CHOICES = constants.SUBJECT_KIND_CHOICES

    # 类别 choices 从 constants 取（中性文案）。
    # 🔴 界面文案走 `constants.category_label(record_type, key)` —— 按侧分流，
    #    `get_category_display()` 分不了侧，界面一律不用它。
    CATEGORY_CHOICES = constants.CATEGORY_CHOICES

    user_id = models.IntegerField(default=1, verbose_name='用户ID（预留）')
    record_type = models.CharField(max_length=10, default='好', choices=RECORD_TYPE_CHOICES, verbose_name='类型')

    # ── 记录对象：决定显示哪些字段 ──
    subject_kind = models.CharField(
        max_length=10, default=constants.SUBJECT_KIND_PHYSICAL,
        choices=SUBJECT_KIND_CHOICES, verbose_name='记录对象',
    )
    name = models.CharField(max_length=200, verbose_name='名称')

    # ⚠️ `category` 必须允许空：方法型**没有**类别，
    #    而「在哪能找到 / 还能找到吗」这类实物专属字段对方法也问不出答案
    #    —— 项目判据：字段长期填不进去 ⇒ 问题没答案，非用户懒（TECH-NOTES §22–34）。
    category = models.CharField(
        max_length=20, blank=True, default='',
        choices=CATEGORY_CHOICES, verbose_name='类别',
    )
    method_group = models.CharField(
        max_length=20, blank=True, default='',
        choices=constants.METHOD_GROUP_CHOICES, verbose_name='方法归类',
    )
    scene = models.CharField(max_length=200, blank=True, default='', verbose_name='什么场景遇到的')

    # 好物字段
    why_good = models.TextField(blank=True, default='', verbose_name='为什么好')
    still_available = models.BooleanField(default=True, verbose_name='还能找到吗')
    where_to_find = models.CharField(max_length=200, blank=True, default='', verbose_name='在哪能找到')

    # 歹物字段
    avoid_reason = models.TextField(blank=True, default='', verbose_name='踩坑原因')
    consequence = models.TextField(blank=True, default='', verbose_name='实际后果')

    # ── 联动：指向 wealth 的两个实物池（互斥，由序列化器校验）──
    property = models.ForeignKey(
        'wealth.WealthProperty',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='treasure_records',
        verbose_name='关联物件资产',
    )
    survival_item = models.ForeignKey(
        'wealth.SurvivalItem',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='treasure_records',
        verbose_name='关联物品清单',
    )

    tags = models.CharField(max_length=200, blank=True, default='', verbose_name='标签')
    # ⚠️ 保留但**前端已撤下**：23/23 全是默认的 5 分，每张卡片都渲染「5 分」，
    #    零信息量，且与 👍/👎 + 理由这个维度重复。列留着是为了不动存量数据。
    rating = models.IntegerField(default=5, verbose_name='评分')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'treasure_good_thing'
        db_table_comment = '好恶物双面档案：好物与坑同表，由「类型」分面；「实物 / 方法」两轴各有自己的分类列'
        verbose_name = '双面档案'
        verbose_name_plural = '双面档案'
        ordering = ['-created_at']
        constraints = [
            # 一件实物最多一条评价。⚠️ 必须用 UniqueConstraint 而不是 `unique=True`：
            #    `unique=True` 在 DRF 层会**静默放过**（可空列），到 IntegrityError 才 500。
            #    MySQL 唯一索引对 NULL 不去重，正好允许「多行未关联」。
            models.UniqueConstraint(
                fields=['property'], name='uniq_treasure_good_thing_property',
            ),
            models.UniqueConstraint(
                fields=['survival_item'], name='uniq_treasure_good_thing_survival_item',
            ),
        ]

    def __str__(self):
        t = '👍' if self.record_type == '好' else '👎'
        kind = self.category or self.method_group or self.subject_kind
        return f'{t}[{kind}] {self.name}'

    # ── 展示用的小工具（口径在 constants，本类不重复实现）──

    def has_reason(self) -> bool:
        """是否已写理由 —— 「待补理由」出口的判据。

        好物看 `why_good`、歹物看 `avoid_reason`。两边都空 ⇒ 待补。

        ⚠️ 刻意**不用 `@property` 装饰器**：本类有一个名为 `property` 的外键字段，
           它在类命名空间里把内置的 `property` 遮蔽了 —— 写 `@property` 会得到
           `TypeError: 'ForeignKey' object is not callable`（模型导入期就炸，
           报错行还指向装饰器，看不出是被字段名遮蔽）。
        """
        text = self.why_good if self.record_type == '好' else self.avoid_reason
        return bool((text or '').strip())
