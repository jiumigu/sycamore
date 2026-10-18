"""seed 作品的出口去向清单 + 给日记流预设标签补一个「值得留」

🔴 **两条都只做一次、且都是「补」不是「覆盖」**：

1. `work_channels` 这一行：**只在不存在时建**。
   ⚠️ 绝不写「表空就补」—— 用户把清单清空是他的决定，下次启动不该被自动还原。
2. `diary_tags`：**追加**一个「值得留」，不覆盖用户已有的增删
   （开发库现值 13 项，都是用户自己攒的）。
   ⚠️ 已经在列表里就什么都不做（幂等）。

> 为什么「值得留」必须走**预设表**而不是前端硬编码一个标签：
> 界面枚举随接口下发、前端零副本（项目判据）。
> 前端自己塞一个标签，用户在「系统预设」页就看不到它、也删不掉它。
"""
from django.db import migrations

# ⚠️ 与 `apps/works/constants.DEFAULT_WORK_CHANNELS` 刻意重复一次：
#    迁移必须自包含 —— 它的正确性是「当时那一刻」的正确性，
#    不能随 `constants.py` 后来的改动而变（改了 constants 不该改写历史迁移）。
WORK_CHANNELS = ['公众号', '小红书', 'GitHub', '面包多', '贴墙上', '给朋友看']

DIARY_TAG = '值得留'


def seed(apps, schema_editor):
    SystemPreset = apps.get_model('core', 'SystemPreset')

    if not SystemPreset.objects.filter(preset_type='work_channels').exists():
        SystemPreset.objects.create(
            preset_type='work_channels', values=list(WORK_CHANNELS),
        )

    row = SystemPreset.objects.filter(preset_type='diary_tags').first()
    if row is None:
        # 理论上不会走到（0004 那条 seed 已经建过），但空库时不能崩
        SystemPreset.objects.create(preset_type='diary_tags', values=[DIARY_TAG])
    elif DIARY_TAG not in (row.values or []):
        row.values = list(row.values or []) + [DIARY_TAG]
        row.save()


def unseed(apps, schema_editor):
    SystemPreset = apps.get_model('core', 'SystemPreset')
    SystemPreset.objects.filter(preset_type='work_channels').delete()
    row = SystemPreset.objects.filter(preset_type='diary_tags').first()
    if row and DIARY_TAG in (row.values or []):
        row.values = [v for v in row.values if v != DIARY_TAG]
        row.save()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_alter_systempreset_preset_type'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
