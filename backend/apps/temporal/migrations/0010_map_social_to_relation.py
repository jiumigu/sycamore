"""L2「社交」的默认归因由「谋生」改挂 v3.58.11 新增的第五格「关系」

背景：`temporal_task_meta.default_attribution` 是**落库值**。改 `TASK_TO_L2` 常量只影响
后续的 CSV 导入与 `migrate_temporal_categories` 路径，**不会回头改已存在的行** ——
不改的话，「人际交往」在页面/结构图上仍显示为「谋生」，与常量表口径不一致。

故按 L2 反查：凡是 `activity_type='社交'` 且归因仍为旧默认「谋生」的行改挂「关系」。
（「社交」现与「关系」1:1，故「社交 + 谋生」等价于"未被人工改过的旧默认值"，
不会误伤人工设置 —— 用户若手工把某条社交改回谋生，语义上仍是谋生，此处不覆盖。）
"""
from django.db import migrations

L2 = '社交'
OLD, NEW = '谋生', '关系'


def forwards(apps, schema_editor):
    TaskMeta = apps.get_model('temporal', 'TaskMeta')
    TaskMeta.objects.filter(activity_type=L2, default_attribution=OLD).update(default_attribution=NEW)


def backwards(apps, schema_editor):
    TaskMeta = apps.get_model('temporal', 'TaskMeta')
    TaskMeta.objects.filter(activity_type=L2, default_attribution=NEW).update(default_attribution=OLD)


class Migration(migrations.Migration):

    dependencies = [
        ('temporal', '0009_alter_taskmeta_default_attribution'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
