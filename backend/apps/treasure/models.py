from django.db import models


class GoodThing(models.Model):
    """好恶物双面档案——记录你亲自验证过的好东西，和踩过的坑"""

    RECORD_TYPE_CHOICES = [
        ('好', '👍 好物'),
        ('歹', '👎 歹物'),
    ]

    CATEGORY_CHOICES = [
        ('吃', '🍽️ 吃'),
        ('穿', '👔 穿'),
        ('用', '🧴 用'),
        ('店', '🏪 好店'),
        ('地方', '📍 好地方'),
        ('方法', '💡 好方法'),
    ]

    user_id = models.IntegerField(default=1, verbose_name='用户ID（预留）')
    record_type = models.CharField(max_length=10, default='好', choices=RECORD_TYPE_CHOICES, verbose_name='类型')
    name = models.CharField(max_length=200, verbose_name='名称')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name='类别')
    scene = models.CharField(max_length=200, blank=True, default='', verbose_name='什么场景遇到的')

    # 好物字段
    why_good = models.TextField(blank=True, default='', verbose_name='为什么好')
    still_available = models.BooleanField(default=True, verbose_name='还能找到吗')
    where_to_find = models.CharField(max_length=200, blank=True, default='', verbose_name='在哪能找到')

    # 歹物字段
    avoid_reason = models.TextField(blank=True, default='', verbose_name='踩坑原因')
    consequence = models.TextField(blank=True, default='', verbose_name='实际后果')

    tags = models.CharField(max_length=200, blank=True, default='', verbose_name='标签')
    rating = models.IntegerField(default=5, verbose_name='评分')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'treasure_good_thing'
        verbose_name = '双面档案'
        verbose_name_plural = '双面档案'
        ordering = ['-created_at']

    def __str__(self):
        t = '👍' if self.record_type == '好' else '👎'
        return f'{t}[{self.get_category_display()}] {self.name}'
