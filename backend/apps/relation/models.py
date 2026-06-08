import datetime

from django.db import models

from .constants import METHOD_CHOICES, QUALITY_CHOICES, SHIFT_CHOICES, STATUS_CHOICES


class Relationship(models.Model):
    """关系档案"""

    name = models.CharField(max_length=100, verbose_name='姓名/昵称')
    alias = models.CharField(max_length=200, blank=True, default='', verbose_name='曾用名/绰号')
    met_date = models.DateField(blank=True, null=True, verbose_name='认识时间')
    met_place = models.CharField(max_length=200, blank=True, default='', verbose_name='认识地点')
    met_scene = models.TextField(blank=True, default='', verbose_name='认识场景')
    identity_then = models.CharField(max_length=200, blank=True, default='', verbose_name='当时身份')
    they_give_me = models.TextField(blank=True, default='', verbose_name='他能给我什么')
    i_give_them = models.TextField(blank=True, default='', verbose_name='我能给他什么')
    current_status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='active', verbose_name='当前状态',
    )
    current_quality = models.CharField(
        max_length=20, choices=QUALITY_CHOICES, default='neutral', verbose_name='关系质量',
    )
    notes = models.TextField(blank=True, default='', verbose_name='备注')
    tags = models.CharField(max_length=200, blank=True, default='', verbose_name='标签')
    user_id = models.IntegerField(verbose_name='用户ID')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        managed = False
        db_table = 'relationship_relationship'
        verbose_name = '关系档案'
        verbose_name_plural = '关系档案'
        ordering = ['-updated_at']

    def __str__(self):
        return self.name


class Interaction(models.Model):
    """互动记录"""

    relationship = models.ForeignKey(
        Relationship, on_delete=models.CASCADE, related_name='interactions',
        db_column='relationship_id', verbose_name='关联关系',
    )
    happened_at = models.DateTimeField(verbose_name='互动时间')
    method = models.CharField(
        max_length=20, blank=True, default='', choices=METHOD_CHOICES, verbose_name='方式',
    )
    energy_score = models.IntegerField(verbose_name='能量分（-10 到 +10）')
    summary = models.CharField(max_length=200, blank=True, default='', verbose_name='一句话总结')
    quality_shift = models.CharField(
        max_length=20, blank=True, default='', choices=SHIFT_CHOICES, verbose_name='质量变化',
    )
    next_reminder = models.CharField(max_length=200, blank=True, default='', verbose_name='下次可以做什么')
    my_action = models.TextField(blank=True, default='', verbose_name='我为对方做了什么',
        help_text='记录自己为这段关系付出的行动')
    user_id = models.IntegerField(verbose_name='用户ID')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        managed = False
        db_table = 'relationship_interaction'
        verbose_name = '互动记录'
        verbose_name_plural = '互动记录'
        ordering = ['-happened_at']

    def __str__(self):
        return f'{self.relationship.name} {self.happened_at} {self.energy_score}'


class ReaderGroup(models.Model):
    """读者群体档案"""

    user_id = models.IntegerField(default=1, verbose_name='用户ID（预留）')
    name = models.CharField(max_length=100, verbose_name='群体名称')
    description = models.TextField(blank=True, default='', verbose_name='描述')
    total_energy = models.IntegerField(default=0, verbose_name='总能量分')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'relation_reader_group'
        verbose_name = '读者群体'
        verbose_name_plural = '读者群体'

    def __str__(self):
        return self.name


class ReaderInteraction(models.Model):
    """读者互动记录"""

    INTERACTION_TYPES = [
        ('comment', '💬 留言'),
        ('like', '❤️ 点赞'),
        ('share', '🔄 转发'),
        ('follow', '➕ 关注'),
        ('unfollow', '➖ 取关'),
        ('reward', '💰 打赏'),
    ]

    user_id = models.IntegerField(default=1, verbose_name='用户ID（预留）')
    reader_group = models.ForeignKey(
        ReaderGroup, on_delete=models.CASCADE, related_name='interactions',
        verbose_name='所属群体',
    )
    reader_name = models.CharField(max_length=100, verbose_name='读者昵称')
    interaction_type = models.CharField(
        max_length=20, choices=INTERACTION_TYPES, verbose_name='互动类型',
    )
    content = models.TextField(blank=True, default='', verbose_name='互动内容')
    article_title = models.CharField(max_length=255, blank=True, default='', verbose_name='关联文章')
    energy_score = models.IntegerField(default=1, verbose_name='能量分')
    tags = models.CharField(max_length=500, blank=True, default='', verbose_name='共振关键词')
    interaction_date = models.DateField(null=True, blank=True, verbose_name='互动时间', help_text='不填默认为创建日期')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'relation_reader_interaction'
        ordering = ['-energy_score', '-created_at']
        verbose_name = '读者互动'
        verbose_name_plural = '读者互动'

    def save(self, *args, **kwargs):
        if not self.interaction_date:
            self.interaction_date = datetime.date.today()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.reader_name} - {self.get_interaction_type_display()}'


class ConflictEvent(models.Model):
    """成长记录——记录人际冲突事件以便复盘"""
    user_id = models.IntegerField(default=1, verbose_name='用户ID（预留）')
    contact = models.ForeignKey(
        Relationship, on_delete=models.CASCADE, related_name='conflicts',
        verbose_name='关联联系人',
    )
    title = models.CharField(max_length=200, verbose_name='事件标题')
    description = models.TextField(blank=True, default='', verbose_name='事件描述')
    event_type = models.CharField(max_length=30, default='其他', verbose_name='事件类型')
    emotion_level = models.IntegerField(default=1, verbose_name='愤怒指数',
        help_text='1=轻微不爽, 5=极度愤怒')
    loss_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='经济损失(元)',
    )
    loss_time = models.CharField(max_length=50, blank=True, default='', verbose_name='时间成本')
    event_date = models.DateField(verbose_name='发生日期')
    is_resolved = models.BooleanField(default=False, verbose_name='是否已解决')
    resolution_note = models.TextField(blank=True, default='', verbose_name='解决备注')
    tags = models.CharField(max_length=200, blank=True, default='', verbose_name='标签')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'relation_conflict_event'
        ordering = ['-event_date']
        verbose_name = '成长记录'

    def __str__(self):
        return f'{self.contact.name} - {self.title} ({self.event_date})'


class ReaderMonthlySummary(models.Model):
    """读者月末盘点"""
    user_id = models.IntegerField(default=1, verbose_name='用户ID（预留）')
    reader_group = models.ForeignKey(
        ReaderGroup, on_delete=models.CASCADE, related_name='monthly_summaries',
        verbose_name='所属群体',
    )
    year = models.IntegerField(verbose_name='年份')
    month = models.IntegerField(verbose_name='月份')
    new_followers = models.IntegerField(default=0, verbose_name='本月新增关注')
    new_unfollowers = models.IntegerField(default=0, verbose_name='本月取关')
    total_followers = models.IntegerField(default=0, verbose_name='截至本月总关注')
    total_interactions = models.IntegerField(default=0, verbose_name='本月互动总量')
    high_energy_count = models.IntegerField(default=0, verbose_name='本月高能量互动数')
    top_article = models.CharField(max_length=255, blank=True, default='', verbose_name='本月最佳文章')
    notes = models.TextField(blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'relation_reader_monthly_summary'
        unique_together = ['reader_group', 'year', 'month']
        ordering = ['-year', '-month']
        verbose_name = '读者月末盘点'
