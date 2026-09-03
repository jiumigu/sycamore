from django.db import models, transaction


class QuarterlyAnswer(models.Model):
    """季度决策工作台 — 用户对自动生成问题的回答"""

    year = models.IntegerField(verbose_name='年份')
    quarter = models.IntegerField(verbose_name='季度（1-4）')
    question_key = models.CharField(max_length=100, verbose_name='问题标识')
    question_text = models.TextField(verbose_name='问题内容')
    question_category = models.CharField(max_length=50, default='general', verbose_name='问题分类')
    answer_text = models.TextField(blank=True, default='', verbose_name='用户回答')
    related_module = models.CharField(max_length=30, blank=True, default='', verbose_name='关联模块')
    action_taken = models.BooleanField(default=False, verbose_name='是否已采取行动')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'summary_quarterly_answer'
        unique_together = ['year', 'quarter', 'question_key']
        ordering = ['-year', '-quarter', 'created_at']
        verbose_name = '季度问答'
        verbose_name_plural = '季度问答'

    def __str__(self):
        return f'{self.year}Q{self.quarter} - {self.question_key}'


class SevenDimConfig(models.Model):
    """七维平衡雷达图封顶值配置（版本化历史，仅 is_active 唯一生效）"""

    wealth_max = models.FloatField(default=10, verbose_name='财富封顶（万元）')
    health_max = models.FloatField(default=80, verbose_name='健康封顶（万步）')
    times_max = models.FloatField(default=80, verbose_name='时间投入封顶（百小时）')
    words_max = models.FloatField(default=20, verbose_name='文字记录封顶（万字）')
    sugar_max = models.FloatField(default=50, verbose_name='小确幸封顶（级）')
    travel_max = models.FloatField(default=20, verbose_name='旅行封顶（次）')
    book_max = models.FloatField(default=20, verbose_name='阅读封顶（本）')
    note = models.CharField(max_length=200, blank=True, default='', verbose_name='备注')
    is_active = models.BooleanField(default=True, verbose_name='是否生效')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='配置时间')

    class Meta:
        db_table = 'summary_seven_dim_config'
        ordering = ['-created_at']
        verbose_name = '七维封顶配置'
        verbose_name_plural = '七维封顶配置'

    @classmethod
    def get_active(cls) -> 'SevenDimConfig':
        """当前生效配置；无则创建初始默认"""
        obj = cls.objects.filter(is_active=True).first()
        if not obj:
            obj = cls.objects.create(note='初始默认配置')
        return obj

    @classmethod
    def apply_config(cls, values: dict, note: str = '') -> 'SevenDimConfig':
        """新增一条配置并生效（旧配置自动失效，保留历史）"""
        with transaction.atomic():
            cls.objects.filter(is_active=True).update(is_active=False)
            return cls.objects.create(**values, note=note, is_active=True)

    def __str__(self):
        return f'七维封顶配置 #{self.pk}（{"生效" if self.is_active else "历史"}）'
