"""移除「资金排程」功能（FundSchedule / FundScheduleItem）

背景：资金排程（快照式资金排程计划 + 预留项子表）观察两周后确认与实际预期不符、
未被使用，整体移除，回归财富模块其余能力（账单/月度日历/宏观热力图/现金盘点/
定期存款/月度复盘/贡献图）不受影响。

注意：本迁移会 DROP 两张表（wealth_fund_schedule / wealth_fund_schedule_item），
数据不可恢复——执行前请先备份（db_backups/fund_schedule_before_removal_20260910.sql）。
反向迁移会重建空的表结构（数据不会回来）。
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('wealth', '0013_wealthbilllist'),
    ]

    operations = [
        # 先删子表（FK 指向 FundSchedule）
        migrations.DeleteModel(
            name='FundScheduleItem',
        ),
        migrations.DeleteModel(
            name='FundSchedule',
        ),
    ]
