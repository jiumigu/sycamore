# 为外部表 wealth_bill_list 增加 period_tag 列（赎回归属标记）
# managed=False 表：迁移不自动建列，需 ① 下方 RunSQL 在开发库执行 ② conftest 同步镜像 DDL
# 详见 docs/三年赎回期-功能设计-v0.3 第 1.1 / 1.3 节

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wealth', '0014_remove_fund_schedule'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE wealth_bill_list
                ADD COLUMN period_tag VARCHAR(10) NULL
                COMMENT '赎回归属(为自己/过渡/外部/不计入)'
            """,
            reverse_sql="ALTER TABLE wealth_bill_list DROP COLUMN period_tag",
        ),
        migrations.AddField(
            model_name='WealthBillList',
            name='period_tag',
            field=models.CharField(
                blank=True, max_length=10, null=True,
                verbose_name='赎回归属(为自己/过渡/外部/不计入)',
            ),
        ),
    ]
