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
