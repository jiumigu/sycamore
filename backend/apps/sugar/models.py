from django.db import models


class EnergyTemplate(models.Model):
    """能量清单模板"""

    CATEGORY_CHOICES = [
        ('daily', '日常'),
        ('creative', '创意'),
        ('social', '社交'),
        ('relax', '放松'),
    ]

    content = models.CharField(max_length=200, verbose_name='内容描述')
    default_energy = models.IntegerField(default=1, verbose_name='默认能量值（1-5）')
    category = models.CharField(
        max_length=50, default='daily', choices=CATEGORY_CHOICES, verbose_name='分类',
    )
    icon = models.CharField(max_length=10, default='☀️', verbose_name='图标')
    estimated_seconds = models.IntegerField(default=60, verbose_name='预估耗时（秒）')
    is_system = models.BooleanField(default=True, verbose_name='是否系统预设')
    user_id = models.IntegerField(blank=True, null=True, verbose_name='用户ID（自定义时填写）')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'sugar_energy_template'
        verbose_name = '能量清单模板'
        verbose_name_plural = '能量清单模板'
        ordering = ['sort_order', 'id']
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['category']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f'{self.icon} {self.content}'


class EnergyLog(models.Model):
    """能量清单完成记录"""

    template = models.ForeignKey(
        EnergyTemplate, on_delete=models.SET_NULL, null=True, blank=True,
        db_column='template_id', verbose_name='关联模板',
    )
    content = models.CharField(max_length=200, verbose_name='实际内容')
    energy_gained = models.IntegerField(default=1, verbose_name='获得的能量值')
    is_custom = models.BooleanField(default=False, verbose_name='是否自定义内容')
    completed_at = models.DateTimeField(verbose_name='完成时间')
    user_id = models.IntegerField(verbose_name='用户ID')
    reward_processed = models.BooleanField(default=False, verbose_name='是否已处理奖励池')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'sugar_energy_log'
        verbose_name = '能量清单完成记录'
        verbose_name_plural = '能量清单完成记录'
        ordering = ['-completed_at']
        indexes = [
            models.Index(fields=['user_id', 'completed_at']),
            models.Index(fields=['user_id', 'reward_processed']),
        ]

    def __str__(self):
        return f'{self.content} +{self.energy_gained}'


class EnergyDailyStats(models.Model):
    """每日能量统计（缓存）"""

    user_id = models.IntegerField(verbose_name='用户ID')
    stat_date = models.DateField(verbose_name='统计日期')
    total_energy = models.IntegerField(default=0, verbose_name='当日总能量')
    completed_count = models.IntegerField(default=0, verbose_name='完成数量')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'sugar_energy_daily_stats'
        verbose_name = '每日能量统计'
        verbose_name_plural = '每日能量统计'
        unique_together = ['user_id', 'stat_date']

    def __str__(self):
        return f'{self.stat_date} 能量{self.total_energy}'


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
        max_digits=3, decimal_places=1, verbose_name='快乐程度 1.0-10.0',
    )
    time = models.DateField(verbose_name='发生日期')
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, blank=True, null=True, verbose_name='分类',
    )
    joy_type = models.CharField(
        max_length=20, blank=True, default='', verbose_name='快乐类型',
        choices=[
            ('创造', '🎨 创造'), ('社交', '💬 社交'), ('独处', '🧘 独处'),
            ('户外', '🌿 户外'), ('美食', '🍽️ 美食'), ('学习', '📚 学习'), ('其他', '✨ 其他'),
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
