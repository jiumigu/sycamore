"""L1 归因值改名：投向 → 成长、外部 → 谋生（维持 / 流失 不变）

背景（v3.58.10）：四词从「投向/维持/外部/流失」改为「成长/谋生/维持/流失」，语义一一对应、仅换名。
用户 2026-09-18 拍板「存储值一起改」，所以存量行必须同步 —— 否则
`resolve_attribution` 读出的旧值不在新枚举里，归因统计 / 旭日图会静默落空（不报错）。

幂等：按旧值过滤再改，重复执行是空操作；反向迁移同样可逆。
"""
from django.db import migrations

RENAME = {'投向': '成长', '外部': '谋生'}
REVERT = {new: old for old, new in RENAME.items()}


def _swap(apps, mapping):
    TaskMeta = apps.get_model('temporal', 'TaskMeta')
    for old, new in mapping.items():
        TaskMeta.objects.filter(default_attribution=old).update(default_attribution=new)


def forwards(apps, schema_editor):
    _swap(apps, RENAME)


def backwards(apps, schema_editor):
    _swap(apps, REVERT)


class Migration(migrations.Migration):

    dependencies = [
        ('temporal', '0007_alter_taskmeta_default_attribution'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
