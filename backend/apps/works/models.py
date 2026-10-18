"""作品 · 两张 managed 表

## 「作品」是什么

> **一件从经历里长出来、以后还能再用的东西。**（可以只有自己看）

它**不是**「输出次数」的翻版 —— 那是个**计数**，这是个**清单**：

| | 计数（自我运转的 KPI） | 清单（本模块） |
|---|---|---|
| 回答 | 这一期做了几回 | 留下了哪几件、分别是什么 |
| 形态 | 一个数字 | N 条明细 |
| 错了会怎样 | 凑数 | 凑不出来（你得能说出它的名字） |

🔴 **两者是同一件事的两面，所以本模块与自我运转 KPI 共用同一份数据** ——
   KPI「留下件数」的取数器 `works_count` 直接数这里的行（见 `selfrun/readers.py`）。
   绝**不**另做一份「手工填的数字 + 一份明细」：那就是同一个事实两把尺子。

## 为什么「捕获」要单独一张表，而不是给七张源表各加一个布尔列

1. **日记流那张表是 `managed=False`（外部表）** —— 铁律：绝不给它加列；
2. **「待提炼」是一个独立事实**，不是源记录的属性 ——
   它有自己的生命周期（待提炼 → 已收进作品），源记录被删了它也在；
3. 分散加列 ⇒ 收口台要 JOIN 六张表，且「同一件事」的定义会随各处漂移。

⚠️ 捕获里存的是**快照**（`title` / `excerpt`）而不是每次回源表查：
   源记录改标题、或源记录被删（收件箱条目归档），
   收口台上仍要能看出「当时勾的是哪一条」。
"""
from django.db import models
from django.db.models import UniqueConstraint

from .constants import (
    CAPTURE_SOURCE_CHOICES,
    CAPTURE_STATUS_CHOICES,
    WORK_KIND_CHOICES,
    WORK_STATUS_CHOICES,
)


class Work(models.Model):
    """一件留下的东西。

    ⚠️ **刻意不落 `period_key`（属于哪一期）**：
       期是「按 `created_at` 现算」的纯派生值（ISO 周 / 自然月，跨年也稳定），
       落库就是第二份真源 —— 而且它会在「期定义」变化时与现算值漂移。
       （判据：以后重算得出同样结果 ⇒ 不落库。）
    """

    name = models.CharField(max_length=120, verbose_name='它叫什么')
    summary = models.CharField(
        max_length=200, blank=True, default='', verbose_name='一句话是什么',
    )
    kind = models.CharField(
        max_length=20, choices=WORK_KIND_CHOICES, default='other', verbose_name='类型',
    )
    # 出口状态：**只记状态，不逼你填日期或链接**（设计稿第六节）
    status = models.CharField(
        max_length=10, choices=WORK_STATUS_CHOICES, default='private',
        verbose_name='出口状态',
    )
    # 空串 = 「还没决定发到哪」，与「只给自己」是两件事：
    # 前者是「要发但没定」，后者是「本来就不发」。
    channel = models.CharField(
        max_length=40, blank=True, default='', verbose_name='发到哪',
    )
    note = models.CharField(
        max_length=200, blank=True, default='', verbose_name='备注',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='成形于')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='改于')

    class Meta:
        db_table = 'works_work'
        db_table_comment = '作品库：一件留下来、以后还能再用的东西；「值得留」勾的收口处'
        ordering = ['-created_at', '-id']
        verbose_name = '作品'
        verbose_name_plural = '作品'

    def __str__(self):
        return self.name


class WorkCapture(models.Model):
    """一件事被打上「值得留下」的记号，等着被合成一件作品。

    七个入口：里程碑完成 / 收件箱完成 / 读完一本书 / 日记打「值得留」标签 /
    摘录 / AI 问答主题 / 档案馆里的一条评价。
    **同一个勾，同一个含义** —— 七个入口不是七次设计。

    🔴 **档案馆那一条不新加布尔列**：给 `GoodThing` 加一个「值得留」字段，
       等于把「一个勾」抄成第二份，而两份迟早对不上（且对不上不报错）；
       更要紧的是它会成为**第二个录入口** —— 同一件事在收口台之外
       还有一处能标记，收口台就不再是收口台。

    ⚠️ `captured_at` 是**捕获那一刻**，不是「那件事发生那一刻」：
       周一时勾上周五的里程碑，算本周。这是对的 ——
       「哪一周在整理东西」才是这条 KPI 在量的事。
    """

    source_type = models.CharField(
        max_length=20, choices=CAPTURE_SOURCE_CHOICES, verbose_name='来自哪种',
    )
    # ⚠️ `source_id` 是**跨七张源表的裸 id**，单看会撞号
    #    （里程碑 3 / 摘录 3 / 主题 3 / 档案 3）。
    #    ⇒ 身份键必须是 `(source_type, source_id)` 复合，绝不用裸 id
    #      （项目铁律：聚合键不能用裸 id，跨表撞号会**静默合并两行**）。
    source_id = models.IntegerField(verbose_name='来源 ID')
    title = models.CharField(max_length=200, verbose_name='当时勾的是哪一条')
    excerpt = models.CharField(
        max_length=300, blank=True, default='', verbose_name='当时的摘要',
    )
    status = models.CharField(
        max_length=10, choices=CAPTURE_STATUS_CHOICES, default='pending',
        verbose_name='状态',
    )
    # ⚠️ `SET_NULL` 而不是 `PROTECT`：删掉一件作品**应当**把它的来源放回待提炼
    #    （合成是可逆的，服务层还会把 status 回滚成 pending）。
    #    这里物件不是主数据，它是「容器」。
    work = models.ForeignKey(
        Work, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='captures', verbose_name='收进哪件作品',
    )
    captured_at = models.DateTimeField(auto_now_add=True, verbose_name='标记于')

    class Meta:
        db_table = 'works_capture'
        db_table_comment = '待提炼：七个入口共用的那一个「值得留」勾，勾的唯一真源；存快照，源记录改名或删除后仍读得懂'
        ordering = ['-captured_at', '-id']
        verbose_name = '待提炼'
        verbose_name_plural = '待提炼'
        constraints = [
            UniqueConstraint(
                fields=['source_type', 'source_id'],
                name='uniq_works_capture_source',
            ),
        ]

    def __str__(self):
        return f'[{self.get_source_type_display()}] {self.title}'
