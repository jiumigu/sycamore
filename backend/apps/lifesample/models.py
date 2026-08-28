from django.db import models
from django.utils import timezone


class LifeSample(models.Model):
    """人生样本索引"""

    TYPE_CHOICES = [
        ('acquaintance', '熟人'),
        ('online', '网友'),
        ('historical', '历史人物'),
        ('celebrity', '知名人士'),
        ('fictional', '虚构人物'),
    ]

    # === 状态 ===
    STATUS_CHOICES = [
        ('collected', '📥 已收集'),
        ('verified', '🔍 已核实'),
        ('reviewed', '✅ 已审阅'),
    ]

    # === 借鉴意义评级 ===
    RELEVANCE_CHOICES = [
        ('high', '🔥 高度借鉴'),
        ('reference', '📖 参考'),
        ('knowledge', '👀 了解'),
    ]

    # 核心信息
    name = models.CharField('姓名', max_length=50)
    alias = models.CharField('别名', max_length=100, blank=True)
    sample_type = models.CharField('类型', max_length=20, choices=TYPE_CHOICES, default='historical')
    tags = models.JSONField('标签', default=list, blank=True)
    summary = models.CharField('一句话简介', max_length=200, blank=True)

    # Obsidian 关联（核心）
    obsidian_path = models.CharField(
        'Obsidian文件路径',
        max_length=500,
        blank=True,
        help_text='相对于Obsidian仓库根目录，如：05_人生样本(LifeSamples)/曾国藩.md',
    )

    # === 状态管理 ===
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='collected')
    verified_at = models.DateTimeField('核实时间', null=True, blank=True)
    reviewed_at = models.DateTimeField('审阅时间', null=True, blank=True)

    # === 借鉴意义评级 ===
    relevance = models.CharField(
        '借鉴意义', max_length=20, choices=RELEVANCE_CHOICES, default='knowledge'
    )
    relevance_reason = models.CharField(
        '评级理由',
        max_length=200,
        blank=True,
        help_text='为什么这个样本对你有这个级别的借鉴意义',
    )

    # 用户笔记（Sycamore 侧记录）
    my_note = models.TextField('我的笔记', blank=True)

    # 关联其他模块
    related_goals = models.JSONField('关联目标', default=list, blank=True)
    related_diary = models.JSONField('关联日记', default=list, blank=True)

    # 系统字段
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'life_sample'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['obsidian_path'], name='idx_ls_obsidian_path'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['obsidian_path'], name='uq_ls_obsidian_path'),
        ]

    def __str__(self) -> str:
        return f"{self.get_sample_type_display()} · {self.name}"

    @property
    def obsidian_full_path(self) -> str:
        """获取 Obsidian 完整路径"""
        from .services.obsidian_service import ObsidianService

        if self.obsidian_path:
            return ObsidianService.get_full_path(self.obsidian_path)
        return ''

    @property
    def status_label(self) -> str:
        return dict(self.STATUS_CHOICES).get(self.status, self.status)

    @property
    def relevance_label(self) -> str:
        return dict(self.RELEVANCE_CHOICES).get(self.relevance, self.relevance)

    def save(self, *args, **kwargs):
        # 状态推进时补核实/审阅时间戳（序列化器只读，仅由状态变更驱动）
        if self.status == 'verified' and not self.verified_at:
            self.verified_at = timezone.now()
        if self.status == 'reviewed':
            if not self.verified_at:
                self.verified_at = timezone.now()
            if not self.reviewed_at:
                self.reviewed_at = timezone.now()
        super().save(*args, **kwargs)


class ObsidianConfig(models.Model):
    """Obsidian 集成配置（单例）"""

    enabled = models.BooleanField('启用集成', default=False)
    vault_path = models.CharField('仓库路径', max_length=500, blank=True)
    samples_folder = models.CharField('样本文件夹', max_length=200, default='05_人生样本(LifeSamples)')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'obsidian_config'

    def __str__(self) -> str:
        return f"Obsidian: {'已启用' if self.enabled else '未启用'}"

    @classmethod
    def get_config(cls) -> 'ObsidianConfig':
        """获取配置单例"""
        config, _ = cls.objects.get_or_create(id=1)
        return config
