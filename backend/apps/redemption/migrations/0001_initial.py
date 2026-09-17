# 三年赎回期 · 初始迁移（4 张 managed 表）
# 开发库建表由你手动执行（见 docs/三年赎回期-功能设计-v0.3 第 1.3 节）；
# 测试库经由 conftest 的 CREATE TABLE IF NOT EXISTS 镜像自动补齐（--no-migrations --reuse-db）。

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='RedemptionPeriod',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField(verbose_name='赎回期开始日期')),
                ('end_date', models.DateField(verbose_name='赎回期结束日期')),
                ('pool_principal', models.DecimalField(decimal_places=2, default=100000, max_digits=14, verbose_name='启动现金池本金')),
                ('tracking_status', models.CharField(choices=[('active', '追踪中'), ('paused', '已暂停')], default='active', max_length=10, verbose_name='追踪状态')),
                ('paused_since', models.DateField(blank=True, null=True, verbose_name='暂停起始日')),
                ('resume_at', models.DateField(blank=True, null=True, verbose_name='计划恢复日')),
                ('baseline_toward_ratio', models.DecimalField(blank=True, decimal_places=4, max_digits=5, null=True, verbose_name='阶段一基线·投向占比')),
                ('baseline_set_week', models.IntegerField(blank=True, null=True, verbose_name='基线锁定周次')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '赎回期配置',
                'verbose_name_plural': '赎回期配置',
                'db_table': 'redemption_period',
            },
        ),
        migrations.CreateModel(
            name='RedemptionPoolInject',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('inject_date', models.DateField(verbose_name='注入日期')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14, verbose_name='注入金额(正数为注入池)')),
                ('source', models.CharField(choices=[('赔偿', '赔偿'), ('借款', '借款'), ('额外收入', '额外收入'), ('其他', '其他')], default='其他', max_length=20, verbose_name='来源')),
                ('note', models.TextField(blank=True, null=True, verbose_name='备注')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
            ],
            options={
                'verbose_name': '现金池注入',
                'verbose_name_plural': '现金池注入',
                'db_table': 'redemption_pool_inject',
                'ordering': ['-inject_date'],
            },
        ),
        migrations.CreateModel(
            name='RedemptionAttrRule',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('match_field', models.CharField(choices=[('task_type', '任务类型'), ('task_name', '任务名称'), ('category_level2', '二级分类')], max_length=20, verbose_name='匹配字段')),
                ('match_value', models.CharField(max_length=100, verbose_name='匹配值')),
                ('attribution', models.CharField(choices=[('投向', '投向(为自己)'), ('维持', '维持(生存运营)'), ('外部', '外部(为他人/牛马)'), ('流失', '流失(空转消耗)')], max_length=10, verbose_name='归因类别')),
                ('priority', models.IntegerField(default=0, verbose_name='优先级(重叠时取高)')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('note', models.TextField(blank=True, null=True, verbose_name='备注')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '归因规则',
                'verbose_name_plural': '归因规则',
                'db_table': 'redemption_attr_rule',
                'ordering': ['-priority', 'id'],
            },
        ),
        migrations.CreateModel(
            name='RedemptionWeekSnapshot',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('year', models.IntegerField(verbose_name='年')),
                ('week', models.IntegerField(verbose_name='周')),
                ('toward_hours', models.FloatField(default=0, verbose_name='投向小时')),
                ('maintain_hours', models.FloatField(default=0, verbose_name='维持小时')),
                ('external_hours', models.FloatField(default=0, verbose_name='外部小时')),
                ('drain_hours', models.FloatField(default=0, verbose_name='流失小时')),
                ('covered_hours', models.FloatField(default=0, verbose_name='已记录小时(分子)')),
                ('theoretical_hours', models.FloatField(default=0, verbose_name='理论小时(分母)')),
                ('coverage_rate', models.FloatField(default=0, verbose_name='覆盖率')),
                ('toward_ratio', models.FloatField(default=0, verbose_name='投向占比')),
                ('unit_cost', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='单位赎回成本')),
                ('snapshot_at', models.DateTimeField(auto_now_add=True, verbose_name='快照时间')),
            ],
            options={
                'verbose_name': '周归因快照',
                'verbose_name_plural': '周归因快照',
                'db_table': 'redemption_week_snapshot',
                'unique_together': [('year', 'week')],
                'ordering': ['-year', '-week'],
            },
        ),
    ]
