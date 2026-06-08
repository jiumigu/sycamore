from django.db import models

from .constants import DANCE_TYPE_CHOICES, DIFFICULTY_CHOICES


class DanceRecord(models.Model):
    """舞蹈学习记录"""

    study_time = models.DateField(verbose_name='学习日期')
    score = models.IntegerField(verbose_name='自我评分')
    teacher_name = models.CharField(max_length=20, blank=True, null=True, verbose_name='授课老师')
    dance_type = models.CharField(
        max_length=12, default='jazz', choices=DANCE_TYPE_CHOICES, verbose_name='舞蹈类型',
    )
    difficulty = models.CharField(
        max_length=10, default='入门', choices=DIFFICULTY_CHOICES, verbose_name='难度等级',
    )
    weekinfo = models.CharField(max_length=10, blank=True, null=True, verbose_name='周几')
    remark = models.CharField(max_length=100, blank=True, null=True, verbose_name='备注')
    file_path = models.CharField(max_length=100, blank=True, null=True, verbose_name='录屏文件地址')

    # 扩展字段
    year = models.IntegerField(blank=True, null=True, verbose_name='年份')
    month = models.IntegerField(blank=True, null=True, verbose_name='月份')
    quarter = models.IntegerField(blank=True, null=True, verbose_name='季度')
    duration_minutes = models.IntegerField(default=60, verbose_name='课程时长（分钟）')
    energy_level = models.IntegerField(blank=True, null=True, verbose_name='体能消耗（1-5）')
    improvement_note = models.CharField(max_length=200, blank=True, null=True, verbose_name='进步/待改进点')

    class Meta:
        managed = False
        db_table = 'hobby_dance_list'
        verbose_name = '舞蹈记录'
        verbose_name_plural = '舞蹈记录'
        ordering = ['-study_time']

    def __str__(self):
        return f'{self.study_time} {self.dance_type} {self.teacher_name}'

    def save(self, *args, **kwargs):
        if self.study_time:
            self.year = self.study_time.year
            self.month = self.study_time.month
            self.quarter = (self.study_time.month - 1) // 3 + 1
            self.weekinfo = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][self.study_time.weekday()]
        super().save(*args, **kwargs)
