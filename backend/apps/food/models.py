from django.db import models


class FoodRecord(models.Model):
    """美食记录"""

    CATEGORY_CHOICES = [
        ('chinese', '中餐'),
        ('western', '西餐'),
        ('japanese', '日料'),
        ('dessert', '甜品'),
        ('snack', '小吃'),
        ('drink', '饮品'),
        ('other', '其他'),
    ]

    TASTE_LEVEL_CHOICES = [
        ('good', '好吃'),
        ('very_good', '特别好吃'),
        ('want_again', '还想吃'),
        ('must_eat_again', '一定要再吃'),
    ]

    EAT_TIME_CHOICES = [
        ('breakfast', '早餐'),
        ('lunch', '午餐'),
        ('dinner', '晚餐'),
        ('snack', '小吃'),
    ]

    OCCASION_CHOICES = [
        ('date', '约会'),
        ('gathering', '聚餐'),
        ('solo', '独享'),
        ('travel', '旅游'),
        ('work', '工作餐'),
    ]

    id = models.AutoField(primary_key=True, verbose_name='ID')
    name = models.CharField(max_length=200, verbose_name='美食名称')
    dish_name = models.CharField(max_length=200, blank=True, null=True, verbose_name='具体菜名')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, blank=True, null=True, verbose_name='分类')
    province = models.CharField(max_length=50, verbose_name='省份')
    city = models.CharField(max_length=100, verbose_name='城市')
    location = models.CharField(max_length=500, blank=True, null=True, verbose_name='具体位置')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True, verbose_name='纬度')
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True, verbose_name='经度')
    taste_level = models.CharField(max_length=20, choices=TASTE_LEVEL_CHOICES, default='good', verbose_name='美味等级')
    eat_date = models.DateField(verbose_name='品尝日期')
    eat_time = models.CharField(max_length=20, choices=EAT_TIME_CHOICES, blank=True, null=True, verbose_name='时段')
    companions = models.CharField(max_length=200, blank=True, null=True, verbose_name='同行伙伴')
    occasion = models.CharField(max_length=100, choices=OCCASION_CHOICES, blank=True, null=True, verbose_name='场景')
    images = models.JSONField(blank=True, null=True, verbose_name='图片列表')
    cover_image = models.CharField(max_length=500, blank=True, null=True, verbose_name='封面图')
    rating = models.IntegerField(blank=True, null=True, verbose_name='评分（1-5）')
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name='价格')
    notes = models.TextField(blank=True, null=True, verbose_name='点评')
    tags = models.CharField(max_length=500, blank=True, null=True, verbose_name='标签')
    want_visit_again = models.BooleanField(default=True, verbose_name='是否还想再去')
    user_id = models.IntegerField(verbose_name='用户ID')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'food_record'
        verbose_name = '美食记录'
        verbose_name_plural = '美食记录'
        ordering = ['-eat_date', '-id']
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['province', 'city']),
            models.Index(fields=['taste_level']),
            models.Index(fields=['eat_date']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return self.name
