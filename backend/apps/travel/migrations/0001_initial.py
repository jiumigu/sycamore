from django.db import migrations, models


class Migration(migrations.Migration):
    """初始化旅行模块 — 添加扩展字段 + 城市坐标表"""

    initial = True

    dependencies: list[tuple[str, str]] = []

    state_operations = [
        migrations.CreateModel(
            name='TravelRecord',
            fields=[
                ('tid', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('parentnode', models.CharField(blank=True, max_length=50, null=True, verbose_name='上一级')),
                ('tname', models.CharField(blank=True, max_length=255, null=True, verbose_name='城市/地点')),
                ('tyear', models.IntegerField(blank=True, null=True, verbose_name='年份')),
                ('tcost', models.FloatField(blank=True, null=True, verbose_name='花费')),
                ('ttime', models.DateField(blank=True, null=True, verbose_name='旅行日期')),
                ('tremark', models.CharField(blank=True, max_length=255, null=True, verbose_name='备注')),
                ('user_id', models.IntegerField(blank=True, null=True, verbose_name='用户ID')),
                ('duration_days', models.IntegerField(blank=True, null=True, verbose_name='停留天数')),
                ('rating', models.IntegerField(blank=True, null=True, verbose_name='满意度')),
                ('companions', models.CharField(blank=True, max_length=200, null=True, verbose_name='同行伙伴')),
                ('latitude', models.DecimalField(blank=True, decimal_places=6, max_digits=10, null=True, verbose_name='纬度')),
                ('longitude', models.DecimalField(blank=True, decimal_places=6, max_digits=10, null=True, verbose_name='经度')),
            ],
            options={
                'db_table': 'travel_list_info',
                'ordering': ['-tyear', '-ttime'],
                'verbose_name': '旅行记录',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='ChinaCityCoord',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('province', models.CharField(max_length=50, verbose_name='省份')),
                ('city', models.CharField(max_length=100, unique=True, verbose_name='城市')),
                ('latitude', models.DecimalField(decimal_places=6, max_digits=10, verbose_name='纬度')),
                ('longitude', models.DecimalField(decimal_places=6, max_digits=10, verbose_name='经度')),
                ('level', models.IntegerField(default=2, verbose_name='级别')),
            ],
            options={
                'db_table': 'china_city_coord',
                'ordering': ['province', 'city'],
                'verbose_name': '城市坐标',
                'managed': False,
            },
        ),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=state_operations,
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        CREATE TABLE IF NOT EXISTS `travel_list_info` (
                          `tid` int NOT NULL AUTO_INCREMENT COMMENT 'ID',
                          `parentnode` varchar(50) DEFAULT NULL COMMENT '上一级',
                          `tname` varchar(255) DEFAULT NULL COMMENT '城市/地点',
                          `tyear` int DEFAULT NULL COMMENT '年份',
                          `tcost` float DEFAULT NULL COMMENT '花费',
                          `duration_days` int DEFAULT NULL COMMENT '停留天数',
                          `rating` int DEFAULT NULL COMMENT '满意度',
                          `companions` varchar(200) DEFAULT NULL COMMENT '同行伙伴',
                          `latitude` decimal(10,6) DEFAULT NULL COMMENT '纬度',
                          `longitude` decimal(10,6) DEFAULT NULL COMMENT '经度',
                          `ttime` date DEFAULT NULL COMMENT '旅行日期',
                          `tremark` varchar(255) DEFAULT NULL COMMENT '备注',
                          `user_id` int DEFAULT NULL COMMENT '用户ID',
                          `district` varchar(100) DEFAULT '' COMMENT '区/县级市',
                          PRIMARY KEY (`tid`)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                        CREATE TABLE IF NOT EXISTS `china_city_coord` (
                          `id` int NOT NULL AUTO_INCREMENT COMMENT 'ID',
                          `province` varchar(50) NOT NULL COMMENT '省份',
                          `city` varchar(100) NOT NULL COMMENT '城市',
                          `latitude` decimal(10,6) NOT NULL COMMENT '纬度',
                          `longitude` decimal(10,6) NOT NULL COMMENT '经度',
                          `level` tinyint DEFAULT '2' COMMENT '级别',
                          PRIMARY KEY (`id`),
                          UNIQUE KEY `uk_city` (`city`)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                    """,
                    reverse_sql="",
                    state_operations=None,
                ),
            ],
        ),
    ]
