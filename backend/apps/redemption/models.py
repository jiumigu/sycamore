"""三年赎回期 · 判定层模型

设计要点（见 docs/三年赎回期-功能设计-v0.x）：
- RedemptionPeriod 为单例（pk=1），承载窗口起止、启动现金池本金、暂停状态。
- 池注入流水 / 外挂归因规则 / 周归因快照 均为独立 managed 表，不污染财富或时间模块。
- 时间归因通过「外挂规则」映射 ATracker 任务属性，绝不向 managed=False 的外部时间表加列。
"""
from django.db import models

# 归因词表单一真源（v3.58.10 起）：本模块曾自存一份副本，改词时极易与 temporal 漂移。
from apps.temporal.constants import ATTRIBUTION_CHOICES as _ATTRIBUTION_CHOICES


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
        verbose_name='阶段一基线·成长占比',
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

    # ⚠️ 声明即契约：`services.match_attribution_rule` 只认这三项，加项须同步实现。
    #    已移除 `category_level2` —— v0.3 起停写，全库非空行数为 0（永不匹配的死选项）。
    #    `task_type` 与 `task_name` 在当前数据里恒等（外部表写入约定，实测 4383 行 0 例外），
    #    保留是为兼容历史规则；标注清楚，避免误以为是独立维度。
    MATCH_FIELD_CHOICES = [
        ('task_name', '任务名称'),
        ('activity_type', '活动类型(L2)'),
        ('task_type', '任务类型(等同任务名称)'),
    ]
    # ⚠️ 单一真源：apps.temporal.constants.ATTRIBUTION_CHOICES（v3.58.10 起不再本地副本）
    ATTRIBUTION_CHOICES = _ATTRIBUTION_CHOICES

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
    """周归因快照（阶段二）：五类小时 + 覆盖率 + 单位赎回成本"""

    id = models.AutoField(primary_key=True, verbose_name='ID')
    year = models.IntegerField(verbose_name='年')
    week = models.IntegerField(verbose_name='周')
    # ⚠️ 下面五个**列名保持英文原样**（toward/relation/maintain/external/drain）——它们是内部标识
    #    兼 API 字段名，改列名要动 schema + 接口契约 + 前端，收益只是"名字好看"。
    #    中文化只做到 verbose_name 与页面展示。其中 toward=成长、external=谋生。
    #    relation_hours 是 v3.58.11 随 L1 第五格「关系」新增的列（见 temporal/constants.py）。
    toward_hours = models.FloatField(default=0, verbose_name='成长小时')
    relation_hours = models.FloatField(default=0, verbose_name='关系小时')
    maintain_hours = models.FloatField(default=0, verbose_name='维持小时')
    external_hours = models.FloatField(default=0, verbose_name='谋生小时')
    drain_hours = models.FloatField(default=0, verbose_name='流失小时')
    covered_hours = models.FloatField(default=0, verbose_name='已记录小时(分子)')
    theoretical_hours = models.FloatField(default=0, verbose_name='理论小时(分母)')
    coverage_rate = models.FloatField(default=0, verbose_name='覆盖率')
    toward_ratio = models.FloatField(default=0, verbose_name='成长占比')
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name='单位赎回成本')
    snapshot_at = models.DateTimeField(auto_now_add=True, verbose_name='快照时间')

    class Meta:
        db_table = 'redemption_week_snapshot'
        verbose_name = '周归因快照'
        verbose_name_plural = '周归因快照'
        unique_together = [('year', 'week')]
        ordering = ['-year', '-week']

    def __str__(self):
        return f'{self.year}-W{self.week} 成长{self.toward_ratio:.0%} 覆盖{self.coverage_rate:.0%}'
