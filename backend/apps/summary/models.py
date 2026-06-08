from django.db import models


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
