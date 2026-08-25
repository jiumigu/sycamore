from django.db import models


class FundSchedule(models.Model):
    """资金排程计划（快照式：每次保存新增一条历史记录）"""

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    plan_name = models.CharField('计划名称', max_length=200)
    cash_on_hand = models.DecimalField('手里现金', max_digits=12, decimal_places=2, default=0)
    reserve_items = models.JSONField(
        default=list,
        verbose_name='预留项目',
        help_text='[{name, amount, type: hard|soft, linked_expense_id}]',
    )
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
