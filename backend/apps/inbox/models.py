from django.db import models
from django.utils import timezone


class InboxItem(models.Model):
    """收件箱条目"""

    CATEGORY_CHOICES = [
        ('todo', '待办'),
        ('idea', '想法'),
        ('pain', '痛点'),
        ('reminder', '提醒'),
        ('work', '工作'),
        ('study', '学习'),
        ('other', '其他'),
    ]

    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('hesitating', '犹豫中'),
        ('processed', '已处理'),
        ('done', '已完成'),
        ('archived', '已归档'),
        ('abandoned', '已废弃'),
    ]

    PRIORITY_CHOICES = [
        ('high', '高'),
        ('medium', '中'),
        ('low', '低'),
    ]

    SOURCE_CHOICES = [
        ('manual', '手动'),
        ('import', '导入'),
        ('voice', '语音'),
        ('auto', '自动'),
    ]

    id = models.AutoField(primary_key=True, verbose_name='条目ID')
    content = models.CharField(max_length=500, verbose_name='内容')
    description = models.TextField(blank=True, null=True, verbose_name='详细描述')

    category = models.CharField(
        max_length=50, default='other', verbose_name='类别',
    )
    tags = models.CharField(max_length=500, blank=True, null=True, verbose_name='标签（逗号分隔）')

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态',
    )
    source = models.CharField(
        max_length=50, choices=SOURCE_CHOICES, default='manual', verbose_name='来源',
    )

    target_type = models.CharField(
        max_length=50, blank=True, null=True, verbose_name='目标模块类型',
    )
    target_id = models.IntegerField(blank=True, null=True, verbose_name='目标模块ID')

    due_date = models.DateField(blank=True, null=True, verbose_name='截止日期')
    remind_at = models.DateTimeField(blank=True, null=True, verbose_name='提醒时间')
    processed_at = models.DateTimeField(blank=True, null=True, verbose_name='处理时间')
    completion_note = models.TextField(blank=True, default='', verbose_name='完成备注')
    hesitate_reason = models.TextField(blank=True, default='', verbose_name='犹豫原因')
    abandon_reason = models.TextField(blank=True, default='', verbose_name='废弃原因')

    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default='medium', verbose_name='优先级',
    )

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'inbox_item'
        db_table_comment = '收件箱条目：随手记的入口；状态决定它还在待办，还是已转成别的模块'
        verbose_name = '收件箱条目'
        verbose_name_plural = '收件箱条目'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['status']),
            models.Index(fields=['category']),
            models.Index(fields=['created_at']),
            models.Index(fields=['due_date']),
            models.Index(fields=['target_type', 'target_id']),
        ]

    def __str__(self):
        return self.content[:50]

    def get_category_display(self):
        for val, label in self.CATEGORY_CHOICES:
            if val == self.category:
                return label
        return self.category

    # ── 「离开收件箱的时刻」= `processed_at` ──────────────────────────
    #
    # 六种状态按「时间该不该有」分三组，正好铺满 `STATUS_CHOICES`（有用例钉住）：
    #   STATUS_CLOSED  完成 / 转出   → 有（写下这一刻）
    #   STATUS_OPEN    待处理 / 犹豫 → 必须没有（退回待办要清空）
    #   （其余：已归档 / 已废弃）     → 不碰（收尾态，归档掉一条已完成的不该抹掉完成时刻）
    STATUS_CLOSED = ('done', 'processed')
    STATUS_OPEN = ('pending', 'hesitating')

    def sync_processed_at(self, new_status=None, now=None):
        """按状态对齐 `processed_at` —— **唯一写入口**。

        🔴 三条都是「不写就会静默错」：

        ① **编辑表单能把状态直接改成 `done`**（`InboxForm` 的下拉里就有它），
           走的是 PATCH 而不是 `complete` 动作。那条路径此前不写时间 ⇒
           「已完成」列表按完成时间倒序时，这一行永远排到最后，
           而界面上看不出它为什么在那儿。
        ② **再点一次「完成」不覆盖已有时间**：完成是既成事实，重记一次等于把
           9 月 30 日改成今天（与「已读完不再改 `readDate`」同一条口径）。
        ③ **退回待办要清空**：不清的话，一条待办会带着一个完成时间，
           「完成于」从此在非完成条目上也有值，谁也说不清它是什么意思。

        `new_status` 只给「刚改完、还没 save 的调用方」用（PATCH 路径）；
        不传就读当前 `status`（`ConverterService` 路径先写值再调）。
        """
        status = self.status if new_status is None else new_status
        if status in self.STATUS_CLOSED:
            if self.processed_at is None:
                self.processed_at = now or timezone.now()
        elif status in self.STATUS_OPEN:
            self.processed_at = None


class InboxProcessLog(models.Model):
    """收件箱处理日志"""

    ACTION_CHOICES = [
        ('convert_to_goal', '转为目标'),
        ('convert_to_milestone', '转为里程碑'),
        # 历史取值：能量清单已退役（sugar 三表已删）。新请求在 serializer 层就被拒，
        # 这里保留只为让旧日志还能显示中文标签 —— 删掉会让历史记录变成裸英文。
        ('convert_to_sugar', '转为能量（已下线）'),
        ('complete', '完成'),
        ('archive', '归档'),
    ]

    id = models.AutoField(primary_key=True, verbose_name='日志ID')
    inbox = models.ForeignKey(
        InboxItem, on_delete=models.CASCADE, related_name='process_logs', verbose_name='关联条目',
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, verbose_name='操作')
    target_type = models.CharField(max_length=50, blank=True, null=True, verbose_name='目标模块类型')
    target_id = models.IntegerField(blank=True, null=True, verbose_name='目标模块ID')
    notes = models.CharField(max_length=500, blank=True, null=True, verbose_name='备注')
    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'inbox_process_log'
        db_table_comment = '收件箱处理日志：条目被转成目标 / 里程碑 / 能量等动作的留痕'
        verbose_name = '处理日志'
        verbose_name_plural = '处理日志'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['inbox']),
            models.Index(fields=['user_id']),
        ]

    def __str__(self):
        return f'{self.get_action_display()} - {self.inbox.content[:30]}'
