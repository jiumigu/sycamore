from django.db import models


class TravelRecord(models.Model):
    """旅行记录 — 映射 travel_list_info 表"""

    tid = models.AutoField(primary_key=True, verbose_name='ID')
    parentnode = models.CharField(max_length=50, blank=True, null=True, verbose_name='上一级')
    tname = models.CharField(max_length=255, blank=True, null=True, verbose_name='城市/地点')
    tyear = models.IntegerField(blank=True, null=True, verbose_name='年份')
    tcost = models.FloatField(blank=True, null=True, verbose_name='花费')
    ttime = models.DateField(blank=True, null=True, verbose_name='旅行日期')
    tremark = models.CharField(max_length=255, blank=True, null=True, verbose_name='备注')
    user_id = models.IntegerField(blank=True, null=True, verbose_name='用户ID')
    duration_days = models.IntegerField(blank=True, null=True, verbose_name='停留天数')
    rating = models.IntegerField(blank=True, null=True, verbose_name='满意度')
    companions = models.CharField(max_length=200, blank=True, null=True, verbose_name='同行伙伴')
    district = models.CharField(max_length=100, blank=True, default='', verbose_name='区/县级市')
    latitude = models.DecimalField(max_digits=10, decimal_places=6, blank=True, null=True, verbose_name='纬度')
    longitude = models.DecimalField(max_digits=10, decimal_places=6, blank=True, null=True, verbose_name='经度')

    class Meta:
        managed = False
        db_table = 'travel_list_info'
        ordering = ['-tyear', '-ttime']
        verbose_name = '旅行记录'

    def __str__(self):
        return f'{self.tname} ({self.tyear})'


class ChinaCityCoord(models.Model):
    """中国城市坐标 — 城市→省份映射 + 经纬度"""

    id = models.AutoField(primary_key=True, verbose_name='ID')
    province = models.CharField(max_length=50, verbose_name='省份')
    city = models.CharField(max_length=100, unique=True, verbose_name='城市')
    latitude = models.DecimalField(max_digits=10, decimal_places=6, verbose_name='纬度')
    longitude = models.DecimalField(max_digits=10, decimal_places=6, verbose_name='经度')
    level = models.IntegerField(default=2, verbose_name='级别')

    class Meta:
        managed = False
        db_table = 'china_city_coord'
        ordering = ['province', 'city']
        verbose_name = '城市坐标'

    def __str__(self):
        return f'{self.city} ({self.province})'


class TravelPlan(models.Model):
    """旅行计划 — 出发前预算，旅行中逐项打卡"""

    STATUS_CHOICES = [
        ('计划中', '计划中'),
        ('进行中', '进行中'),
        ('已完成', '已完成'),
        ('已取消', '已取消'),
    ]

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    name = models.CharField(max_length=200, verbose_name='计划名称')
    destination = models.CharField(max_length=100, verbose_name='目的地')
    start_date = models.DateField(null=True, blank=True, verbose_name='计划出发日期')
    status = models.CharField(max_length=20, default='计划中', choices=STATUS_CHOICES, verbose_name='状态')
    total_estimate = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='预估总费用')
    notes = models.TextField(blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'travel_plan'
        ordering = ['-start_date']
        verbose_name = '旅行计划'

    def __str__(self):
        return f'{self.name} ({self.destination})'


class TravelPlanItem(models.Model):
    """旅行计划子项"""

    ITEM_TYPES = [
        ('food', '🍽️ 美食'),
        ('scenic', '📍 景点'),
        ('transport', '🚗 交通'),
        ('hotel', '🏠 住宿'),
    ]

    plan = models.ForeignKey(TravelPlan, on_delete=models.CASCADE, related_name='items', verbose_name='所属计划')
    wish = models.ForeignKey(
        'TravelWish', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='plan_items', verbose_name='关联心愿',
    )
    item_type = models.CharField(max_length=20, choices=ITEM_TYPES, verbose_name='类型')
    name = models.CharField(max_length=200, verbose_name='名称')
    estimate_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='预估费用')
    is_completed = models.BooleanField(default=False, verbose_name='是否完成')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    notes = models.TextField(blank=True, default='', verbose_name='备注')
    sort_order = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        db_table = 'travel_plan_item'
        ordering = ['item_type', 'sort_order']
        verbose_name = '旅行计划子项'

    def __str__(self):
        return f'[{self.get_item_type_display()}] {self.name}'


class TravelWish(models.Model):
    """旅行心愿单 — 想去的地方/想吃的美食，可加入旅行计划并逐项打卡"""

    STATUS_CHOICES = [
        ('想去', '想去'),
        ('已列入计划', '已列入计划'),
        ('已打卡', '已打卡'),
    ]

    CATEGORY_CHOICES = [
        ('景点', '📍 景点'),
        ('美食', '🍽️ 美食'),
        ('古镇', '🏘️ 古镇'),
        ('寺庙', '🛕 寺庙'),
        ('自然', '⛰️ 自然'),
        ('大学', '🎓 大学'),
        ('书店', '📚 书店'),
        ('街区', '🏙️ 街区'),
        ('夜市', '🍢 夜市'),
        ('路线', '🚶 路线'),
        ('其他', '📌 其他'),
    ]

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    name = models.CharField(max_length=200, verbose_name='名称')
    category = models.CharField(max_length=20, default='景点', choices=CATEGORY_CHOICES, verbose_name='分类')
    province = models.CharField(max_length=50, blank=True, default='', verbose_name='省份')
    city = models.CharField(max_length=100, blank=True, default='', verbose_name='城市')
    district = models.CharField(max_length=100, blank=True, default='', verbose_name='区县')
    lng = models.FloatField(null=True, blank=True, verbose_name='经度')
    lat = models.FloatField(null=True, blank=True, verbose_name='纬度')
    status = models.CharField(max_length=20, default='想去', choices=STATUS_CHOICES, verbose_name='状态')
    visited_at = models.DateField(null=True, blank=True, verbose_name='打卡日期')
    notes = models.TextField(blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'travel_wish'
        ordering = ['province', 'category', 'name']
        verbose_name = '旅行心愿'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['province']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'{self.name} ({self.city or self.province or "未定位"})'
