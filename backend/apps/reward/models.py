from django.db import models


class GiftList(models.Model):
    """礼物清单"""

    STATUS_CHOICES = [
        ('pending', '待兑换'),
        ('waiting', '可兑换'),
        ('redeemed', '已兑换'),
        ('cancelled', '已取消'),
    ]

    CATEGORY_CHOICES = [
        ('physical', '实物'),
        ('experience', '体验'),
        ('virtual', '虚拟'),
        ('other', '其他'),
    ]

    name = models.CharField(max_length=200, verbose_name='礼物名称')
    expected_reward = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='预期价格')
    actual_reward = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name='实际兑换价格')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, blank=True, null=True, verbose_name='分类')
    priority = models.IntegerField(default=0, verbose_name='优先级(越小越优先)')
    image_url = models.URLField(max_length=500, blank=True, null=True, verbose_name='图片链接')
    link_url = models.URLField(max_length=500, blank=True, null=True, verbose_name='购买链接')
    notes = models.TextField(blank=True, null=True, verbose_name='备注')
    redeemed_at = models.DateTimeField(blank=True, null=True, verbose_name='兑换时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'reward_gift_list'
        verbose_name = '礼物清单'
        verbose_name_plural = '礼物清单'
        ordering = ['priority', '-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
        ]

    def __str__(self):
        return self.name


class RewardPool(models.Model):
    """奖励池 — 单例模式，全局唯一"""

    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='当前余额')
    total_earned = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='累计获得')
    total_withdrawn = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='累计提取')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'reward_pool'
        verbose_name = '奖励池'
        verbose_name_plural = '奖励池'

    def __str__(self):
        return f'奖励池余额: {self.balance}'


class RewardTransaction(models.Model):
    """奖励流水"""

    TRANSACTION_TYPES = [
        ('milestone_complete', '里程碑完成'),
        ('milestone_update', '里程碑修改'),
        ('milestone_delete', '里程碑删除'),
        ('sugar_create', '小确幸'),
        ('sugar_update', '小确幸修改'),
        ('sugar_delete', '小确幸删除'),
        ('gift_exchange', '礼物兑换'),
        ('withdraw', '提取'),
    ]

    id = models.AutoField(primary_key=True, verbose_name='流水ID')
    source_id = models.IntegerField(blank=True, null=True, verbose_name='来源ID')
    source_type = models.CharField(max_length=50, blank=True, null=True, verbose_name='来源类型(milestone/sugar)')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='金额')
    transaction_type = models.CharField(max_length=50, choices=TRANSACTION_TYPES, verbose_name='交易类型')
    balance_before = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='交易前余额')
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='交易后余额')
    description = models.TextField(blank=True, null=True, verbose_name='描述')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'reward_transaction'
        verbose_name = '奖励流水'
        verbose_name_plural = '奖励流水'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_transaction_type_display()} {self.amount}'
