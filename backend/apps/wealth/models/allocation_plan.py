from django.db import models


class AllocationCategory(models.Model):
    """分配类别（用户可自定义）"""

    name = models.CharField('类别名称', max_length=30)
    icon = models.CharField('图标', max_length=10, default='💰')
    color = models.CharField('颜色', max_length=10, default='#409EFF')
    priority = models.IntegerField('优先级', default=0, help_text='数字越小越优先预留')
    default_amount = models.DecimalField('默认金额', max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField('启用', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wealth_allocation_category'
        ordering = ['priority', 'id']
        verbose_name = '分配类别'
        verbose_name_plural = '分配类别'

    def __str__(self):
        return f"{self.icon} {self.name}"


class AllocationPlan(models.Model):
    """分配计划（按月份）"""

    year_month = models.CharField('年月', max_length=7)  # "2026-08"
    total_cash = models.DecimalField('手头现金', max_digits=12, decimal_places=2, default=0)
    commitments_total = models.DecimalField('硬性承诺合计', max_digits=12, decimal_places=2, default=0)
    allocated_total = models.DecimalField('预留分配合计', max_digits=12, decimal_places=2, default=0)
    free_cash = models.DecimalField('自由支配', max_digits=12, decimal_places=2, default=0)
    status = models.CharField('状态', max_length=10, default='draft')  # draft | active | closed
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wealth_allocation_plan'
        unique_together = [['year_month']]
        ordering = ['-year_month']
        verbose_name = '分配计划'
        verbose_name_plural = '分配计划'

    def __str__(self):
        return f"{self.year_month} 分配计划"


class AllocationItem(models.Model):
    """分配明细项"""

    plan = models.ForeignKey(AllocationPlan, on_delete=models.CASCADE, related_name='items')
    category = models.ForeignKey(AllocationCategory, on_delete=models.PROTECT)
    planned_amount = models.DecimalField('计划预留金额', max_digits=12, decimal_places=2)
    spent_amount = models.DecimalField('已花费', max_digits=12, decimal_places=2, default=0)
    remaining_amount = models.DecimalField('剩余', max_digits=12, decimal_places=2, default=0)
    note = models.CharField('备注', max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wealth_allocation_item'
        unique_together = [['plan', 'category']]
        verbose_name = '分配明细项'
        verbose_name_plural = '分配明细项'

    def save(self, *args, **kwargs):
        self.remaining_amount = self.planned_amount - self.spent_amount
        super().save(*args, **kwargs)


class Commitment(models.Model):
    """硬性承诺（未来必须花的钱）"""

    STATUS_CHOICES = [
        ('pending', '待付'),
        ('urgent', '紧急'),
        ('done', '已付'),
    ]

    name = models.CharField('项目名称', max_length=100)
    amount = models.DecimalField('金额', max_digits=12, decimal_places=2)
    due_date = models.DateField('截止日期')
    status = models.CharField('状态', max_length=10, choices=STATUS_CHOICES, default='pending')
    source = models.CharField('来源', max_length=20, choices=[
        ('bill', '账单'),
        ('inbox', '收件箱'),
        ('manual', '手动录入'),
    ], default='manual')
    plan = models.ForeignKey(AllocationPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name='commitments')
    note = models.CharField('备注', max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wealth_commitment'
        ordering = ['due_date']
        verbose_name = '硬性承诺'
        verbose_name_plural = '硬性承诺'

    def __str__(self):
        return f"{self.name} (¥{self.amount})"


class DecisionLog(models.Model):
    """自由决策记录"""

    content = models.CharField('决策内容', max_length=500)
    category = models.CharField('类别', max_length=20, blank=True)  # save/learn/travel/home/venture
    plan = models.ForeignKey(AllocationPlan, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wealth_decision_log'
        ordering = ['-created_at']
        verbose_name = '自由决策记录'
        verbose_name_plural = '自由决策记录'

    def __str__(self):
        return f"{self.content[:50]}..."
