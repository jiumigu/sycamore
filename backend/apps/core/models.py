from django.db import models


class SystemPreset(models.Model):
    """系统预设配置：统一管理标签预设与快捷短语，供各模块前端下拉/点选使用"""

    PRESET_TYPE_CHOICES = [
        ('tags', '标签预设'),
        ('quick_phrases', '快捷短语（里程碑完成感悟）'),
        ('sugar_tags', '小确幸预设标签'),
        ('diary_tags', '日记流预设标签'),
    ]

    preset_type = models.CharField('预设类型', max_length=50, choices=PRESET_TYPE_CHOICES, unique=True)
    values = models.JSONField('预设值列表', default=list, blank=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'core_system_preset'
        unique_together = ['preset_type']
        verbose_name = '系统预设'
        verbose_name_plural = '系统预设'

    def __str__(self):
        return f'[{self.preset_type}] {len(self.values)} 项'


class UserProfile(models.Model):
    """用户配置（单用户系统，user_id=1）"""

    user_id = models.IntegerField(default=1, unique=True, verbose_name='用户ID')
    privacy_mode = models.BooleanField(default=False, verbose_name='脱敏模式')
    logseq_path = models.CharField(max_length=500, blank=True, default='', verbose_name='Logseq 日记目录')

    class Meta:
        db_table = 'core_user_profile'
        verbose_name = '用户配置'
        verbose_name_plural = '用户配置'

    def __str__(self):
        return f'UserProfile(user_id={self.user_id}, privacy={self.privacy_mode})'


class Notification(models.Model):
    """系统通知"""

    CATEGORY_CHOICES = [
        ('reminder', '提醒'),
        ('alert', '警告'),
        ('info', '信息'),
    ]

    source_module = models.CharField(max_length=50, verbose_name='来源模块')
    source_object_id = models.IntegerField(blank=True, null=True, verbose_name='来源对象ID')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name='通知类别')
    title = models.CharField(max_length=200, verbose_name='标题')
    body = models.TextField(blank=True, verbose_name='内容')
    action_url = models.CharField(max_length=200, blank=True, verbose_name='跳转链接')
    is_read = models.BooleanField(default=False, verbose_name='是否已读')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'core_notification'
        ordering = ['-created_at']
        verbose_name = '系统通知'
        verbose_name_plural = '系统通知'

    def __str__(self):
        return f'[{self.get_category_display()}] {self.title}'
