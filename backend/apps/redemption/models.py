"""三年赎回期 · 判定层模型

设计要点（见 docs/三年赎回期-功能设计-v0.x）：
- RedemptionPeriod 为单例（pk=1），承载窗口起止、启动现金池本金、暂停状态。
- 池注入流水 / 外挂归因规则 / 周归因快照 均为独立 managed 表，不污染财富或时间模块。
- 时间归因通过「外挂规则」映射 ATracker 任务属性，绝不向 managed=False 的外部时间表加列。
"""
from django.db import models


class RedemptionPeriod(models.Model):
    """赎回期配置单例（pk=1）"""

    id = models.AutoField(primary_key=True, verbose_name='ID')
    start_date = models.DateField(verbose_name='赎回期开始日期')
    end_date = models.DateField(verbose_name='赎回期结束日期')
    pool_principal = models.DecimalField(max_digits=14, decimal_places=2, default=100000, verbose_name='启动现金池本金')
    tracking_status = models.CharField(
        max_length=10, default='active',
        choices=[('active', '追踪中'), ('paused', '已暂停')],
        verbose_name='追踪状态',
    )
    paused_since = models.DateField(blank=True, null=True, verbose_name='暂停起始日')
    resume_at = models.DateField(blank=True, null=True, verbose_name='计划恢复日')
    baseline_toward_ratio = models.DecimalField(
        max_digits=5, decimal_places=4, blank=True, null=True,
        verbose_name='阶段一基线·投向占比',
    )
    baseline_set_week = models.IntegerField(blank=True, null=True, verbose_name='基线锁定周次')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'redemption_period'
        verbose_name = '赎回期配置'
        verbose_name_plural = '赎回期配置'

    def __str__(self):
        return f'赎回期 {self.start_date} ~ {self.end_date} ({self.tracking_status})'


class RedemptionPoolInject(models.Model):
    """启动现金池中途注入流水（B2 口径：赔偿/借款/额外收入等）"""

    id = models.AutoField(primary_key=True, verbose_name='ID')
    inject_date = models.DateField(verbose_name='注入日期')
    amount = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='注入金额(正数为注入池)')
    source = models.CharField(
        max_length=20, default='其他',
        choices=[
            ('赔偿', '赔偿'), ('借款', '借款'), ('额外收入', '额外收入'), ('其他', '其他'),
        ],
        verbose_name='来源',
    )
    note = models.TextField(blank=True, null=True, verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'redemption_pool_inject'
        verbose_name = '现金池注入'
        verbose_name_plural = '现金池注入'
        ordering = ['-inject_date']

    def __str__(self):
        return f'{self.inject_date} +{self.amount} ({self.source})'


class RedemptionAttrRule(models.Model):
    """时间归因外挂规则：把 ATracker 任务属性映射到四类归因"""

    MATCH_FIELD_CHOICES = [
        ('task_type', '任务类型'),
        ('task_name', '任务名称'),
        ('category_level2', '二级分类'),
        ('activity_type', '活动类型'),
    ]
    ATTRIBUTION_CHOICES = [
        ('投向', '投向(为自己)'),
        ('维持', '维持(生存运营)'),
        ('外部', '外部(为他人/牛马)'),
        ('流失', '流失(空转消耗)'),
    ]

    id = models.AutoField(primary_key=True, verbose_name='ID')
    match_field = models.CharField(max_length=20, choices=MATCH_FIELD_CHOICES, verbose_name='匹配字段')
    match_value = models.CharField(max_length=100, verbose_name='匹配值')
    attribution = models.CharField(max_length=10, choices=ATTRIBUTION_CHOICES, verbose_name='归因类别')
    priority = models.IntegerField(default=0, verbose_name='优先级(重叠时取高)')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    note = models.TextField(blank=True, null=True, verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'redemption_attr_rule'
        verbose_name = '归因规则'
        verbose_name_plural = '归因规则'
        ordering = ['-priority', 'id']

    def __str__(self):
        return f'{self.match_field}={self.match_value} → {self.attribution}'


class RedemptionWeekSnapshot(models.Model):
    """周归因快照（阶段二）：四类小时 + 覆盖率 + 单位赎回成本"""

    id = models.AutoField(primary_key=True, verbose_name='ID')
    year = models.IntegerField(verbose_name='年')
    week = models.IntegerField(verbose_name='周')
    toward_hours = models.FloatField(default=0, verbose_name='投向小时')
    maintain_hours = models.FloatField(default=0, verbose_name='维持小时')
    external_hours = models.FloatField(default=0, verbose_name='外部小时')
    drain_hours = models.FloatField(default=0, verbose_name='流失小时')
    covered_hours = models.FloatField(default=0, verbose_name='已记录小时(分子)')
    theoretical_hours = models.FloatField(default=0, verbose_name='理论小时(分母)')
    coverage_rate = models.FloatField(default=0, verbose_name='覆盖率')
    toward_ratio = models.FloatField(default=0, verbose_name='投向占比')
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name='单位赎回成本')
    snapshot_at = models.DateTimeField(auto_now_add=True, verbose_name='快照时间')

    class Meta:
        db_table = 'redemption_week_snapshot'
        verbose_name = '周归因快照'
        verbose_name_plural = '周归因快照'
        unique_together = [('year', 'week')]
        ordering = ['-year', '-week']

    def __str__(self):
        return f'{self.year}-W{self.week} 投向{self.toward_ratio:.0%} 覆盖{self.coverage_rate:.0%}'
