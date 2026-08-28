from django.db import models


class FundSchedule(models.Model):
    """资金排程计划（快照式：每次保存新增一条历史记录）"""

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    plan_name = models.CharField('计划名称', max_length=200)
    cash_on_hand = models.DecimalField('手里现金', max_digits=12, decimal_places=2, default=0)
    total_reserved = models.DecimalField('预留合计', max_digits=12, decimal_places=2, default=0)
    remaining = models.DecimalField('剩余可分配', max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wealth_fund_schedule'
        ordering = ['-created_at']
        verbose_name = '资金排程'
        verbose_name_plural = '资金排程'

    def __str__(self):
        return self.plan_name


class FundScheduleItem(models.Model):
    """资金排程预留项子表（reserve_items JSON 字段已拆分移除，本表为唯一存储）"""

    schedule = models.ForeignKey('FundSchedule', on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=200, verbose_name='预留项名称')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='金额')
    item_type = models.CharField(max_length=10, default='hard', verbose_name='类型')
    linked_expense_id = models.IntegerField(blank=True, null=True, verbose_name='关联支出ID')
    sort_order = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        db_table = 'wealth_fund_schedule_item'
        ordering = ['sort_order', 'id']
        verbose_name = '预留项'
        verbose_name_plural = '预留项'
        indexes = [
            models.Index(fields=['schedule']),
        ]

    def __str__(self):
        return f'{self.name} {self.amount}'
