from django.db import models


class InboxItem(models.Model):
    """收件箱条目"""

    CATEGORY_CHOICES = [
        ('todo', '待办'),
        ('idea', '想法'),
        ('pain', '痛点'),
        ('reminder', '提醒'),
        ('work', '工作'),
        ('other', '其他'),
    ]

    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('processed', '已处理'),
        ('done', '已完成'),
        ('archived', '已归档'),
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
        max_length=50, choices=CATEGORY_CHOICES, default='other', verbose_name='类别',
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

    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default='medium', verbose_name='优先级',
    )

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'inbox_item'
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


class InboxProcessLog(models.Model):
    """收件箱处理日志"""

    ACTION_CHOICES = [
        ('convert_to_goal', '转为目标'),
        ('convert_to_milestone', '转为里程碑'),
        ('convert_to_sugar', '转为能量'),
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
        verbose_name = '处理日志'
        verbose_name_plural = '处理日志'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['inbox']),
            models.Index(fields=['user_id']),
        ]

    def __str__(self):
        return f'{self.get_action_display()} - {self.inbox.content[:30]}'
