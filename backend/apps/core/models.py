from django.db import models


class SystemPreset(models.Model):
    """系统预设配置：统一管理标签预设与快捷短语，供各模块前端下拉/点选使用"""

    PRESET_TYPE_CHOICES = [
        ('tags', '标签预设'),
        ('quick_phrases', '快捷短语（里程碑完成感悟）'),
        ('sugar_tags', '小确幸预设标签'),
        ('diary_tags', '日记流预设标签'),
        ('ask_tags', 'AI 问答库标签'),
        ('book_tags', '图书预设标签'),
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


# ─── 金句池长度上限（v3.60.12：由硬编码常量改为可配置项） ───
# 「每日金句」卡只从「不超过这个字数」的摘录里取 —— 太长的整段文字推上卡片读不完。
# ⚠️ 默认值的**单一真源就在这里**：toolkit 侧读取配置时若没有 UserProfile 行，
#    回落到本字段的 default，读取端不写第二份默认值。
# ⚠️ 旧值 200 偏短（开发库实测：69 条里 ≤200 只有 43 条 = 62%，≤500 有 52 条 = 75%）。
# ⚠️ 超限只是**不进池** —— 摘录本身照样存着、照样能搜到，不删任何数据。
DEFAULT_QUOTE_POOL_MAX_LEN = 500

# 配置的合法区间：下限防「池子空掉」，上限防「卡片变成整篇文章」。
# 前端输入框与后端序列化器**都**引用这一份，避免两处各写一个数字。
QUOTE_POOL_LEN_RANGE = (50, 5000)


class UserProfile(models.Model):
    """用户配置（单用户系统，user_id=1）"""

    user_id = models.IntegerField(default=1, unique=True, verbose_name='用户ID')
    privacy_mode = models.BooleanField(default=False, verbose_name='脱敏模式')
    logseq_path = models.CharField(max_length=500, blank=True, default='', verbose_name='Logseq 日记目录')
    quote_pool_max_len = models.PositiveIntegerField(
        default=DEFAULT_QUOTE_POOL_MAX_LEN,
        verbose_name='金句池长度上限',
        help_text='超过这个字数的摘录不会出现在「每日金句」卡上（仍保留在摘录管理中）',
    )

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


class MenuPreference(models.Model):
    """菜单显示偏好（单用户系统，user_id=1）"""

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    menu_key = models.CharField(max_length=100, unique=True, verbose_name='菜单标识')
    is_favorite = models.BooleanField(default=True, verbose_name='是否常用')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'core_menu_preference'
        ordering = ['sort_order', 'menu_key']
        verbose_name = '菜单偏好'
        verbose_name_plural = '菜单偏好'

    def __str__(self):
        return f'{self.menu_key}: {"常用" if self.is_favorite else "归档"}'


class MenuGroup(models.Model):
    """菜单分组配置"""

    group_key = models.CharField(max_length=50, unique=True, verbose_name='分组标识')
    group_name = models.CharField(max_length=50, verbose_name='分组名称')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_visible = models.BooleanField(default=True, verbose_name='是否显示')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'core_menu_group'
        ordering = ['sort_order', 'group_key']
        verbose_name = '菜单分组'
        verbose_name_plural = '菜单分组'

    def __str__(self):
        return f'{self.group_name} ({self.group_key})'
