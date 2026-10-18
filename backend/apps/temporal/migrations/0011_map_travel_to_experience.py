"""「旅游观景」的 L2 由「兴趣记录」改挂新 L2「主动经历」，归因由「成长」改挂新第六格「体验」

背景（与 0010 同源）：`temporal_task_meta.default_attribution` 是**落库值**。
改 `TASK_TO_L2` 常量只影响后续的 CSV 导入 / `migrate_atracker` / `migrate_temporal_categories`
路径，**不会回头改已存在的行** —— 不跑本迁移，「旅游观景」在台账 / 结构图 / 贡献图上
仍是「兴趣记录 / 成长」，与常量表口径不一致，而且**静默**（没有任何地方会报错）。

🔴 为什么按 task_name 精确定位、不按 L2 反查：
   「旅游观景」是**唯一**要挪的任务名，而 `activity_type='兴趣记录'` 下还挂着另外 8 个
   （迷谷知松 / 悦己越己 / 手工编织 / ONEDAY / DIKW计划 …）。按 L2 反查会**连坐**它们。
   0010 敢用 L2 反查，是因为当时「社交」与「关系」刚好 1:1；这里不是 1:1，不能照抄。

🔴 为什么 activity_type 与 default_attribution **一起改**：
   只改归因不改 L2，会留下「兴趣记录 → 体验」这种在 `ACTIVITY_TYPE_PRESETS` 里
   不存在的组合（归因由 L2 默认值推导，页面上会显示成「这条的归因跟它的类型不搭」）。

⚠️ 归因是**运行时算**的（`resolve_attribution` 每次从本表现算，不缓存），
   所以本迁移一执行，过去 29 条 / ≈139.8h 的旅游记录会**立即回溯**改挂「体验」。
   这是**有意**的：否则新格「体验」只有未来的数据，历史两年多的旅游仍是「成长」。

⚠️ 条件是「仍是旧样子」才改（加了旧值断言），保证：① 幂等；② 用户若已手工把这条
   改成别的，不会被本迁移覆盖回去。
"""
from django.db import migrations

TASK_NAME = '旅游观景'
OLD_L2, OLD_ATTR = '兴趣记录', '成长'
NEW_L2, NEW_ATTR = '主动经历', '体验'


def forwards(apps, schema_editor):
    TaskMeta = apps.get_model('temporal', 'TaskMeta')
    TaskMeta.objects.filter(
        task_name=TASK_NAME, activity_type=OLD_L2, default_attribution=OLD_ATTR,
    ).update(activity_type=NEW_L2, default_attribution=NEW_ATTR)


def backwards(apps, schema_editor):
    TaskMeta = apps.get_model('temporal', 'TaskMeta')
    TaskMeta.objects.filter(
        task_name=TASK_NAME, activity_type=NEW_L2, default_attribution=NEW_ATTR,
    ).update(activity_type=OLD_L2, default_attribution=OLD_ATTR)


class Migration(migrations.Migration):

    dependencies = [
        ('temporal', '0010_map_social_to_relation'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
