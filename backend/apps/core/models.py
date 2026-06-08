from django.db import models


class UserProfile(models.Model):
    """用户配置（单用户系统，user_id=1）"""

    user_id = models.IntegerField(default=1, unique=True, verbose_name='用户ID')
    privacy_mode = models.BooleanField(default=False, verbose_name='脱敏模式')

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
