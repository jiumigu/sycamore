from django.db import models

from .constants import HTYPE_CHOICES, HTYPE_LABELS


class HealthRecord(models.Model):
    """运动记录（步数/跳绳/跑步/骑行）"""

    hid = models.AutoField(primary_key=True)
    steps = models.IntegerField(blank=True, null=True, verbose_name='步数')
    htype = models.IntegerField(
        blank=True, null=True, default=1, choices=HTYPE_CHOICES, verbose_name='运动类型',
    )
    cofficient = models.FloatField(blank=True, null=True, verbose_name='转换系数')
    total = models.FloatField(blank=True, null=True, verbose_name='折算后步数')
    time = models.DateTimeField(blank=True, null=True, verbose_name='运动时间')
    remark = models.CharField(max_length=255, blank=True, null=True, verbose_name='备注')
    years = models.CharField(max_length=25, blank=True, null=True, verbose_name='年份')
    user_id = models.IntegerField(blank=True, null=True, verbose_name='用户ID')

    class Meta:
        managed = False
        db_table = 'health_step_info'
        verbose_name = '运动记录'
        verbose_name_plural = '运动记录'
        ordering = ['-time']

    def __str__(self):
        return f'{self.time} {HTYPE_LABELS.get(self.htype, "?")} {self.total}步'

    def save(self, *args, **kwargs):
        if self.time and not self.years:
            self.years = str(self.time.year)
        if self.steps is not None:
            if self.htype == 1 or not self.htype:
                self.total = float(self.steps)
            elif self.cofficient:
                self.total = float(self.steps) * self.cofficient
        super().save(*args, **kwargs)


class WeightRecord(models.Model):
    """体重记录"""

    MEASURE_TIME_CHOICES = [
        ('morning', '早晨'),
        ('afternoon', '下午'),
        ('evening', '晚上'),
    ]

    record_date = models.DateField(verbose_name='记录日期')
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='体重（公斤）')
    body_fat = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True, verbose_name='体脂率（%）')
    measure_time = models.CharField(max_length=20, choices=MEASURE_TIME_CHOICES, blank=True, null=True, verbose_name='测量时间')
    notes = models.CharField(max_length=200, blank=True, null=True, verbose_name='备注')
    user_id = models.IntegerField(verbose_name='用户ID')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'health_weight_record'
        verbose_name = '体重记录'
        verbose_name_plural = '体重记录'
        ordering = ['-record_date']
        constraints = [
            models.UniqueConstraint(fields=['user_id', 'record_date'], name='uk_weight_user_date'),
        ]
        indexes = [
            models.Index(fields=['record_date']),
            models.Index(fields=['user_id']),
        ]

    def __str__(self):
        return f'{self.record_date} {self.weight_kg}kg'

    @property
    def weight_jin(self):
        """体重（斤），自动计算"""
        if self.weight_kg is None:
            return None
        return round(float(self.weight_kg) * 2, 1)

    @property
    def bmi(self):
        """BMI，需关联身高"""
        if self.weight_kg is None:
            return None
        try:
            body_info = UserBodyInfo.objects.filter(user_id=self.user_id).first()
            if body_info and body_info.height_m:
                return round(float(self.weight_kg) / (body_info.height_m ** 2), 2)
        except Exception:
            pass
        return None


class WeightGoal(models.Model):
    """体重目标"""

    STATUS_CHOICES = [
        ('in_progress', '进行中'),
        ('completed', '已完成'),
        ('abandoned', '已放弃'),
    ]

    user_id = models.IntegerField(verbose_name='用户ID')
    target_weight_kg = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='最终目标体重（公斤）')
    start_weight_kg = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='起始体重（公斤）')
    monthly_target_kg = models.DecimalField(max_digits=4, decimal_places=2, default=1.5, verbose_name='每月目标减重（公斤）')
    start_date = models.DateField(verbose_name='目标开始日期')
    expected_end_date = models.DateField(blank=True, null=True, verbose_name='预计达成日期')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress', verbose_name='状态')
    current_month = models.IntegerField(default=1, verbose_name='当前第几个月')
    current_month_start_weight = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, verbose_name='本月起始体重')
    current_month_target = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, verbose_name='本月目标体重')
    is_active = models.BooleanField(default=True, verbose_name='是否当前活跃目标')
    completed_at = models.DateTimeField(blank=True, null=True, verbose_name='达成日期')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'health_weight_goal'
        verbose_name = '体重目标'
        verbose_name_plural = '体重目标'
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f'目标：{self.start_weight_kg}kg → {self.target_weight_kg}kg（第{self.current_month}月）'

    @property
    def target_weight_jin(self):
        if self.target_weight_kg is None:
            return None
        return round(float(self.target_weight_kg) * 2, 1)

    @property
    def start_weight_jin(self):
        if self.start_weight_kg is None:
            return None
        return round(float(self.start_weight_kg) * 2, 1)

    @property
    def monthly_target_jin(self):
        if self.monthly_target_kg is None:
            return None
        return round(float(self.monthly_target_kg) * 2, 1)


class WeightMilestone(models.Model):
    """月度里程碑"""

    goal = models.ForeignKey(WeightGoal, on_delete=models.CASCADE, related_name='milestones', verbose_name='关联目标')
    month_number = models.IntegerField(verbose_name='第几个月')
    start_weight_kg = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='月初体重')
    target_weight_kg = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='月目标体重')
    end_weight_kg = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, verbose_name='月末实际体重')
    is_achieved = models.BooleanField(default=False, verbose_name='是否达成')
    achieved_at = models.DateField(blank=True, null=True, verbose_name='达成日期')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'health_weight_milestone'
        verbose_name = '月度里程碑'
        verbose_name_plural = '月度里程碑'
        ordering = ['month_number']
        indexes = [
            models.Index(fields=['goal']),
        ]

    def __str__(self):
        return f'第{self.month_number}月：{self.start_weight_kg}kg → {self.target_weight_kg}kg'


class UserBodyInfo(models.Model):
    """用户身体信息"""

    GENDER_CHOICES = [
        ('male', '男'),
        ('female', '女'),
    ]

    user_id = models.IntegerField(unique=True, verbose_name='用户ID')
    height_cm = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='身高（厘米）')
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True, verbose_name='性别')
    age = models.IntegerField(blank=True, null=True, verbose_name='年龄')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'health_user_body_info'
        verbose_name = '用户身体信息'
        verbose_name_plural = '用户身体信息'

    def __str__(self):
        return f'用户{self.user_id}：{self.height_cm}cm'

    @property
    def height_m(self):
        """身高（米），用于 BMI 计算"""
        if self.height_cm is None:
            return None
        return round(float(self.height_cm) / 100, 2)


class MenstrualRecord(models.Model):
    """好朋友跟踪"""

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    year = models.IntegerField(verbose_name='年份')
    month = models.CharField(max_length=10, verbose_name='月份')
    start_date = models.DateField(verbose_name='开始日期')
    offset = models.IntegerField(default=0, verbose_name='偏移量(天)')
    cycle_days = models.IntegerField(default=30, verbose_name='周期跨度(天)')
    notes = models.TextField(blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'health_menstrual_record'
        ordering = ['-start_date']
        verbose_name = '好朋友记录'
        verbose_name_plural = '好朋友记录'
        constraints = [
            models.UniqueConstraint(fields=['user_id', 'start_date'], name='uk_menstrual_user_date'),
        ]
        indexes = [
            models.Index(fields=['start_date']),
            models.Index(fields=['user_id']),
        ]

    def __str__(self):
        return f'{self.start_date} 周期{self.cycle_days}天'


class WeightGoalAdjustment(models.Model):
    """体重目标调整记录"""

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    goal = models.ForeignKey(WeightGoal, on_delete=models.CASCADE, related_name='adjustments', verbose_name='关联目标')
    before_value = models.DecimalField(max_digits=5, decimal_places=1, verbose_name='变更前目标(斤)')
    after_value = models.DecimalField(max_digits=5, decimal_places=1, verbose_name='变更后目标(斤)')
    change_amount = models.DecimalField(max_digits=5, decimal_places=1, verbose_name='调整值(斤)')
    reason = models.TextField(blank=True, default='', verbose_name='调整原因')
    adjusted_at = models.DateTimeField(auto_now_add=True, verbose_name='调整时间')

    class Meta:
        db_table = 'health_weight_goal_adjustment'
        ordering = ['-adjusted_at']
        verbose_name = '目标调整记录'
        verbose_name_plural = '目标调整记录'

    def __str__(self):
        return f'{self.before_value}斤 → {self.after_value}斤 ({self.change_amount}斤)'
