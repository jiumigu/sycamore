from django.db import models
from django.utils import timezone

from .constants import CATEGORY_CHOICES


class TemporalTask(models.Model):
    """任务时间记录（映射现有表 temporal_time_atracker_tasks_list）"""

    task_name = models.CharField(max_length=255, verbose_name='任务名称')
    task_description = models.TextField(blank=True, null=True, verbose_name='任务说明')
    start_time = models.DateTimeField(blank=True, null=True, verbose_name='开始时间')
    end_time = models.DateTimeField(blank=True, null=True, verbose_name='结束时间')
    duration = models.TimeField(blank=True, null=True, verbose_name='持续时间')
    duration_hours = models.FloatField(blank=True, null=True, verbose_name='持续小时数')
    notes = models.TextField(blank=True, null=True, verbose_name='附注')
    tags = models.TextField(blank=True, null=True, verbose_name='标签')
    task_type = models.CharField(max_length=100, default='其他', verbose_name='任务类型')
    year = models.IntegerField(blank=True, null=True, verbose_name='年份')
    mon = models.CharField(max_length=10, blank=True, null=True, verbose_name='月份')
    day = models.IntegerField(blank=True, null=True, verbose_name='日期')
    week = models.IntegerField(blank=True, null=True, verbose_name='周数')
    quarter = models.IntegerField(blank=True, null=True, verbose_name='季度')
    category_level1 = models.CharField(
        max_length=50, blank=True, null=True, choices=CATEGORY_CHOICES, verbose_name='一级分类',
    )
    category_level2 = models.CharField(max_length=50, blank=True, null=True, verbose_name='二级分类')
    category_color = models.CharField(max_length=20, blank=True, null=True, verbose_name='分类颜色')
    import_batch = models.CharField(max_length=50, blank=True, null=True, verbose_name='导入批次号')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        managed = False
        db_table = 'temporal_time_atracker_tasks_list'
        verbose_name = '任务时间记录'
        verbose_name_plural = '任务时间记录'
        ordering = ['-start_time']

    def __str__(self):
        return f'{self.task_name} ({self.start_time})'


class OneDayPage(models.Model):
    """每日记录模型（oneday + page 字数统计）"""

    OTYPE_CHOICES = [
        ('MIGU', '迷谷知松'),
        ('HAPPY', '有点开心'),
        ('SAD', '有点闹心'),
        ('DIGITAL', '数字转型'),
        ('SUMMARY', '复盘总结'),
        ('ONEDAY', '普通一日'),
        ('IDEA', '有点想法'),
        ('ACHIEVE', '有点成就'),
    ]

    oid = models.AutoField(primary_key=True, verbose_name='编号')
    years = models.CharField(max_length=25, blank=True, null=True, verbose_name='年度')
    oneday = models.IntegerField(blank=True, null=True, verbose_name='oneday字数')
    page = models.IntegerField(blank=True, null=True, verbose_name='文章字数')
    total = models.IntegerField(blank=True, null=True, verbose_name='总字数')
    title = models.CharField(max_length=255, verbose_name='主题')
    begin_date = models.DateField(db_column='beginDate', default=timezone.localdate, verbose_name='创建日期')
    otype = models.CharField(max_length=50, default='ONEDAY', choices=OTYPE_CHOICES, verbose_name='内容类型')
    update_date = models.DateField(db_column='updateDate', default=timezone.localdate, verbose_name='更新日期')
    flag = models.CharField(max_length=50, blank=True, null=True, verbose_name='标签')
    remark = models.CharField(max_length=255, blank=True, null=True, verbose_name='备注')
    user_id = models.BigIntegerField(blank=True, null=True, verbose_name='预留用户ID')

    class Meta:
        managed = False
        db_table = 'temporal_oneday_page_list'
        verbose_name = '每日记录'
        verbose_name_plural = '每日记录'
        ordering = ['-begin_date']

    def __str__(self):
        return f"{self.title or '无标题'} - {self.begin_date}"

    def save(self, *args, **kwargs):
        if self.begin_date:
            self.years = str(self.begin_date.year)
        self.total = (self.oneday or 0) + (self.page or 0)
        self.update_date = timezone.localdate()
        super().save(*args, **kwargs)


class WeeklyTimeCache(models.Model):
    """周度时间固化统计表"""

    year = models.IntegerField(verbose_name='年份')
    week = models.IntegerField(verbose_name='周次')
    total_hours = models.FloatField(default=0, verbose_name='本周总小时')
    task_count = models.IntegerField(default=0, verbose_name='任务数')
    avg_hours_per_day = models.FloatField(default=0, verbose_name='日均小时')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'temporal_weekly_time_cache'
        unique_together = ['year', 'week']
        ordering = ['year', 'week']
        indexes = [
            models.Index(fields=['year']),
        ]
