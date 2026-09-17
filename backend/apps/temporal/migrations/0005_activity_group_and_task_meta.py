"""新增 L1 分组表 temporal_activity_group 与 L2 活动类型映射表 temporal_task_meta

均为 managed=True，仿 0002_weeklytimecache 用 CreateModel 建表。
外部表 temporal_time_atracker_tasks_list 不加列（绝不向 managed=False 表加列）。
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('temporal', '0004_oneday_rename_camelcase_columns'),
    ]

    operations = [
        migrations.CreateModel(
            name='ActivityGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True, verbose_name='分组名(L1)')),
                ('color', models.CharField(blank=True, max_length=7, null=True, verbose_name='主题色')),
                ('sort_order', models.IntegerField(default=0, verbose_name='排序')),
                ('is_system', models.BooleanField(default=False, verbose_name='系统预设')),
                ('note', models.TextField(blank=True, null=True, verbose_name='备注')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'db_table': 'temporal_activity_group',
                'verbose_name': '时间分组',
                'verbose_name_plural': '时间分组',
                'ordering': ['sort_order', 'id'],
            },
        ),
        migrations.CreateModel(
            name='TaskMeta',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('task_name', models.CharField(max_length=255, unique=True, verbose_name='任务名(L0)')),
                ('activity_type', models.CharField(max_length=50, verbose_name='活动类型(L2)')),
                ('default_attribution', models.CharField(blank=True, choices=[('投向', '投向(为自己)'), ('维持', '维持(生存运营)'), ('外部', '外部(为他人/牛马)'), ('流失', '流失(空转消耗)')], max_length=10, null=True, verbose_name='默认归因(L3)')),
                ('is_system', models.BooleanField(default=False, verbose_name='系统预设')),
                ('note', models.TextField(blank=True, null=True, verbose_name='备注')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('group', models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, to='temporal.activitygroup', verbose_name='所属L1分组')),
            ],
            options={
                'db_table': 'temporal_task_meta',
                'verbose_name': '活动类型映射',
                'verbose_name_plural': '活动类型映射',
                'indexes': [models.Index(fields=['activity_type'], name='temporal_ta_activi_2d3a6f_idx'), models.Index(fields=['group'], name='temporal_ta_group_3c4b7e_idx')],
            },
        ),
    ]
