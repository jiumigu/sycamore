"""退役 redemption_attr_rule（v3.64.16）

为什么删：它是 `temporal_task_meta.default_attribution` 的影子副本 ——
映射表改 L1 时由 `temporal.views.batch_set_meta` 顺带写一条 priority=100 的规则。
但规则只覆盖「被改过」的那几个任务名，赎回期页面却拿「命中规则」当统计口径，
于是未覆盖的记录**静默不计**：实测 2 天窗口 33.96h 只算 20h，
「成长」1.99h（真实 12.39h）、「谋生」恒为 0，且不报错。

⚠️ 本迁移只写、不跑。执行前那 12 行数据全是映射表的重复，
   删表不会丢任何口径 —— 但请先备份（`db_backups/`）。
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('redemption', '0008_db_comments'),
    ]

    operations = [
        migrations.DeleteModel(name='redemptionattrrule'),
    ]
