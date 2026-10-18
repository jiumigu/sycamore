"""「运动健身」的归因由「维持」订正为「成长」

背景（与 0010 / 0011 同源）：`temporal_task_meta.default_attribution` 是**落库值**。
改 `TASK_TO_L2` 常量只影响后续的 CSV 导入 / `migrate_atracker` / `migrate_temporal_categories`
路径，**不会回头改已存在的行**。

本次是**反向的一例**：常量表种子与库里**长期不一致**，而这次判「库里那行是错的」。

| | L2 类型 | L1 归因 |
|---|---|---|
| 常量表种子 `TASK_TO_L2['运动健身']` | 主动休息 | **成长** |
| 库 `temporal_task_meta` 实测 | 主动休息 | **维持** |

🔴 判据（用户 2026-10-12 拍板）：运动是**主动为自己做**的事，换回的是体能与精力，
   与 `ACTIVITY_TYPE_PRESETS` 里「主动休息 → 成长」的默认一致；
   归「维持」等于说「运动只是为了不出问题」，与「维持 = 换回运转」的口径不符。

⚠️ 影响面（实测，2026-10-12）：
   - 历史合计 **955 条 / 463.65h** 目前计在「维持」桶，改后移入「成长」桶；
   - 但**近 11 周为 0.00h**（近期完全没记录）⇒ **不影响当下的周读数**，
     只影响历史总量与贡献图的历史视图。
   - 本迁移**触及元数据，不触碰任何 `temporal_task` 记录**，
     归因是**运行时算**的（`resolve_attribution` 每次从本表现算），
     所以改完立即回溯，无需重算存量。

🔴 为什么按 task_name 精确定位、不按归因反查：
   `default_attribution='维持'` 下有「美食备餐 / 日常家务 / 整理房间 / 身体健康 / 断舍离 /
   生活杂事 / 午睡 / 休息睡眠」等大批任务，按归因反查会**连坐**它们。

⚠️ 条件是「仍是旧样子」才改（带旧值断言），保证：① 幂等；② 用户若已手工把这条
   改成别的（例如「流失」），不会被本迁移覆盖回去。

⚠️ 反向函数会把「成长」改回「维持」。它同样带值断言，所以若在本迁移之后
   有人再手工改动过这一行，回滚**不会**覆盖那次改动。
"""
from django.db import migrations

TASK_NAME = '运动健身'
L2 = '主动休息'          # L2 两边一致，本迁移不动它，只把它写进条件做精确定位
OLD_ATTR = '维持'
NEW_ATTR = '成长'


def forwards(apps, schema_editor):
    TaskMeta = apps.get_model('temporal', 'TaskMeta')
    TaskMeta.objects.filter(
        task_name=TASK_NAME, activity_type=L2, default_attribution=OLD_ATTR,
    ).update(default_attribution=NEW_ATTR)


def backwards(apps, schema_editor):
    TaskMeta = apps.get_model('temporal', 'TaskMeta')
    TaskMeta.objects.filter(
        task_name=TASK_NAME, activity_type=L2, default_attribution=NEW_ATTR,
    ).update(default_attribution=OLD_ATTR)


class Migration(migrations.Migration):

    dependencies = [
        ('temporal', '0012_alter_taskmeta_default_attribution'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
