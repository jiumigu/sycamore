"""身上之物（v3.62.4）——「我该有什么、找到了没有」。

文件分工，别混（本项目第五个实物池子）：
    钱     = WealthAsset*     （wealth_models.py，金融侧）
    消耗物 = Survival*        （survival_models.py，会被用完，答案是「天」）
    耐用品 = WealthProperty*  （property_models.py，会折旧会报废，答案是「年」与「元」）
    该有的 = WealthBody*      （本文件，**不靠任何数量**，只记结论）

判据一句话（三问分开）：
    我有什么          → 物件资产 / 物品清单
    那些够不够用      → 基准清单（SurvivalEssential）
    **我该有什么、称不称心** → 本模块

两张表：
    WealthBodyPart  部位主数据（眼 / 脸 / 手 / 指甲 / 脚 ……，轻量、用户可增删改）
    WealthBodyNeed  一个「位」：眼睛要眼镜、手要护手霜、指甲要指甲剪 ……

🔴 为什么部位也要建表、不写死成下拉：用户列的六项里「指甲」是「手」的一部分，
   一个互斥枚举里混进不同质的成员，它必然变成**兜底桶**（treasure 实测「方法」占 74%）。
   写死六个值，「口腔」「耳朵」「私处」「头发」就没地方放。
   照 WealthPropertyCategory / SurvivalCategory 的既有做法：轻量主数据。

🔴 三把尺子**正交、互不推导**（本模块最容易做错的地方）：
   进度 find_status   这件事办到哪一步了    待寻 / 寻找中 / 已找到
   满意 satisfaction  现在用的这件称不称心  凑合 / 还行 / 称心（**可空**）
   归属 property / survival_item            我用的是哪一件（事实）

   合法组合举例（**不要**试图「修正」它们）：
     已找到 + 凑合 + 挂着那件   ⇒ 定了就是它，但用着一般
     寻找中 + 凑合 + 挂着那件   ⇒ 最典型：有一副凑合戴的、正在换
     待寻   + 无关联            ⇒ 压根还没有东西
     寻找中 + 称心 + 挂着那件   ⇒ 挺满意，但还想着有没有更好的

   ⚠️ `satisfaction` 为空 **≠ 凑合**，空的两种来由（`no_item` / `unrated`）
      由 `services/body_calc.py` 下发，前端只查表 —— 同 property_calc 的 zero_reason。

⚠️ 本模块**不落任何派生值**：`satisfaction_blank_reason` 与四个计数都在
   `services/body_calc.py` 运行时算（判据「以后重算得出同样结果吗」→ 能，所以不落库）。
"""

from django.db import models

from ..constants import (
    BODY_FIND_STATUS_CHOICES,
    BODY_SATISFACTION_CHOICES,
)
from .property_models import WealthProperty
from .survival_models import SurvivalItem


class WealthBodyPart(models.Model):
    """部位主数据：眼 / 耳 / 鼻 / 口 / 脸 / 头发 / 手 / 指甲 / 身体四肢 / 脚 / 私处

    轻量主数据，用户随时增删改 —— 同 `WealthPropertyCategory` / `SurvivalCategory`。
    `note` 只是给表单帮忙的一句提示（「眼镜 / 隐形眼镜 / 眼药水」），不参与任何计算。
    """

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    name = models.CharField(max_length=30, verbose_name='部位名称')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    note = models.CharField(max_length=200, blank=True, default='', verbose_name='说明')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        # 不设 Meta.ordering：ordering 会被注入 SELECT 而静默破坏聚合（项目硬坑②），
        # 本项目 managed 表统一不设，排序交给服务层。
        db_table = 'wealth_body_part'
        db_table_comment = '身上之物 · 部位主数据（眼 / 耳 / 鼻 / 口 / 脸 / 手 …）'
        verbose_name = '身上之物 · 部位'
        verbose_name_plural = '身上之物 · 部位'
        constraints = [
            models.UniqueConstraint(
                fields=['user_id', 'name'], name='wealth_body_part_user_name_uniq',
            ),
        ]

    def __str__(self) -> str:
        return self.name


class WealthBodyNeed(models.Model):
    """一个「位」：某个部位需要的一样东西，以及这件事办到哪一步了。

    ⚠️ 与 `SurvivalEssential`（基准清单）**刻意分开、不互相关联**：
       那边问「够不够用」（挂库存物品算天数），这边问「称不称心」（不靠任何数量）。
       名字会撞（都有「鞋」「外衣」「面霜」），但两边的产出口完全不同 ——
       互相挂上就会出现「这一条到底算不算缺口」的第二种解释，
       而那是它们各自产出口的地基。

    ⚠️ 两个关联源都是 `SET_NULL`，不是 `CASCADE`：
       物件删了，「我该有一副眼镜」这条认知**应当留下**，只失去关联。
       （对照 `part` 是 `PROTECT`：删一个还被位引用的部位会被 400 拦住 ——
        类别是**归属**，删掉会让这一条无处安放；关联的那件东西是**事实**，卖掉就没了。）
    """

    user_id = models.IntegerField(default=1, verbose_name='用户ID')

    # 指向主数据用 PROTECT：删一个还被位引用的部位，会让这一条失去归属 ——
    # 宁可报错（400 + 可照做的提示），也不做级联删除这种魔法。
    part = models.ForeignKey(
        WealthBodyPart, on_delete=models.PROTECT,
        related_name='needs', verbose_name='部位',
    )
    name = models.CharField(
        max_length=60, verbose_name='要什么',
        help_text='眼镜 / 护手霜 / 指甲剪 —— 一个位就是「这个部位要的一样东西」',
    )

    # ── 进度轴：这件事办到哪一步了 ──
    find_status = models.CharField(
        max_length=20, choices=BODY_FIND_STATUS_CHOICES, default='todo',
        verbose_name='进度',
        help_text='待寻 / 寻找中 / 已找到；刻意不含「不想找了」（那是兜底桶）',
    )

    # ── 满意轴：现在顶着用的这件，称不称心（**可空**）──
    # ⚠️ 可空是**必须**的，不是偷懒：还没找到任何东西的人填不出这一格。
    #    「空」与「凑合」是两件事，空的两种来由见 constants.BODY_BLANK_REASON_LABELS。
    # ⚠️ **不给默认值**：「看着合理」的默认值就是假话的源头 ——
    #    它会让「没人评过」看起来像「评过了、结论是凑合」。
    satisfaction = models.CharField(
        max_length=10, choices=BODY_SATISFACTION_CHOICES, null=True, blank=True,
        default=None, verbose_name='满意',
        help_text='凑合 / 还行 / 称心；留空表示还没东西在用、或还没评过（两者不是一回事）',
    )

    # ── 想找什么样的 ──
    # ⚠️ 「已找到」之后**不清空、不改写**：它是你当时的标准，是一个快照
    #    （同 v3.62.0 作品模块「当时勾的是哪一条」）。
    wish = models.TextField(
        blank=True, default='', verbose_name='想找什么样的',
        help_text='把模糊的不满变成明确的要求；已找到之后也不清空，那是当时的标准',
    )

    # ── 归属：我用的是哪一件（**单件**，两个来源互斥）──
    #
    # 🔴 用两个可空 FK 而不是 `source_type + source_id`：只有两张源表，FK 可行，
    #    且 `SET_NULL` 由 DB 保证，**不会出现悬空引用**
    #    （`source_id` 指向一条已删记录，界面上静默显示成「没关联」——那是静默错值）。
    # 🔴 两个**互斥**（不能同时挂）：靠序列化器 `validate()` 手写 ——
    #    项目既有判据：可空列上的约束 DRF 会**静默放过**，不能指望 DB 约束。
    # ⚠️ 单件，不是 M2M：「我现在顶着用的是哪一件」是个**单数**问题；
    #    「日常镜 + 墨镜」本就该是**两个位**（部位都挂「眼」），
    #    这与「一台冰箱 = 一条记录」同源。
    property = models.ForeignKey(
        WealthProperty, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='body_needs', verbose_name='用的物件资产',
    )
    survival_item = models.ForeignKey(
        SurvivalItem, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='body_needs', verbose_name='用的物品清单',
    )

    note = models.TextField(blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'wealth_body_need'
        db_table_comment = '身上之物 · 一个「位」：某部位需要的一样东西 + 办到哪一步了'
        verbose_name = '身上之物 · 位'
        verbose_name_plural = '身上之物 · 位'
        # ⚠️ 新写 Index 一律显式写 name= —— Django 6.0 自动命名变更会凭空产出 RenameIndex。
        indexes = [
            models.Index(fields=['user_id', 'part'], name='wealth_body_need_user_part_idx'),
            models.Index(fields=['find_status'], name='wealth_body_need_status_idx'),
        ]

    def __str__(self) -> str:
        return self.name
