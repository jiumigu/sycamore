from django.db import models


class SugarTemplate(models.Model):
    """小确幸模板"""

    CATEGORY_CHOICES = [
        ('daily', '日常'),
        ('creative', '创意'),
        ('social', '社交'),
        ('relax', '放松'),
    ]

    user_id = models.IntegerField(verbose_name='用户ID（预留）')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, verbose_name='分类')
    name = models.CharField(max_length=200, verbose_name='名称')
    icon = models.CharField(max_length=10, default='🌱', verbose_name='图标')
    points = models.IntegerField(default=1, verbose_name='积分')
    duration = models.CharField(max_length=50, default='1分钟', verbose_name='预估时长')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'sugar_template'
        db_table_comment = '小确幸模板：快速记录小确幸时的候选清单'
        verbose_name = '小确幸模板'
        verbose_name_plural = '小确幸模板'
        ordering = ['category', 'sort_order']

    def __str__(self):
        return f'{self.icon} {self.name}'


class SugarRecord(models.Model):
    """小确幸记录"""

    CATEGORY_CHOICES = [
        ('food', '美食'),
        ('travel', '旅行'),
        ('learn', '学习'),
        ('social', '社交'),
        ('leisure', '休闲'),
        ('work', '工作'),
        ('health', '健康'),
        ('other', '其他'),
    ]

    s_id = models.AutoField(primary_key=True, verbose_name='记录ID')
    years = models.IntegerField(blank=True, null=True, verbose_name='年份')
    month = models.IntegerField(blank=True, null=True, verbose_name='月份')
    title = models.CharField(max_length=100, verbose_name='小确幸标题')
    level_of_happiness = models.DecimalField(
        max_digits=3, decimal_places=1, verbose_name='快乐程度 5-20',
    )
    time = models.DateField(verbose_name='发生日期')
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, blank=True, null=True, verbose_name='分类',
    )
    joy_type = models.CharField(
        max_length=20, blank=True, default='', verbose_name='快乐类型',
        choices=[
            ('感官型', '🌿 感官型'), ('秩序型', '📋 秩序型'),
            ('联结型', '💬 联结型'), ('意外型', '🎁 意外型'),
            ('独处型', '🧘 独处型'),
        ],
    )
    tags = models.CharField(max_length=255, blank=True, null=True, verbose_name='标签，逗号分隔')
    notes = models.TextField(blank=True, null=True, verbose_name='详细描述')
    reward_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name='本记录产生的奖励金额',
    )
    reward_synced = models.BooleanField(default=False, verbose_name='奖励是否已同步')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'sugar_record'
        db_table_comment = '小确幸记录：快乐程度 5-20；reward_synced 是发奖的幂等标记'
        verbose_name = '小确幸记录'
        verbose_name_plural = '小确幸记录'
        ordering = ['-time', '-s_id']
        indexes = [
            models.Index(fields=['time']),
            models.Index(fields=['level_of_happiness']),
            models.Index(fields=['category']),
            models.Index(fields=['years', 'month']),
        ]

    def __str__(self):
        return self.title
