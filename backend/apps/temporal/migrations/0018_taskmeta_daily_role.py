# 「今天的三条线」从写死任务名改成显式角色标记（v3.64.12）

from django.db import migrations, models


# 迁移当时的真实任务名 → 角色。
# 🔴 只在这里出现一次：回填完之后，改名/新增都走映射编辑器的开关，
#    代码里不再有任何「按任务名判角色」的分支。
ROLE_SEED = {
    '休息睡眠': 'sleep_night',
    '午睡': 'nap',
    '玩游戏': 'game',
}


def backfill_roles(apps, schema_editor):
    """把已有的三个任务名标上角色。

    不做回填 ⇒ 三条线全部显示「未记录」，看起来像功能没做好，
    实际是「标签没标」—— 这类静默失败最难查，所以在迁移里一次补齐。
    """
    TaskMeta = apps.get_model('temporal', 'TaskMeta')
    for task_name, role in ROLE_SEED.items():
        TaskMeta.objects.filter(task_name=task_name).update(daily_role=role)


def clear_roles(apps, schema_editor):
    """回退：清空角色（列本身由 RemoveField 删掉，这里只保证可逆、不残留语义）。"""
    TaskMeta = apps.get_model('temporal', 'TaskMeta')
    TaskMeta.objects.update(daily_role='')


class Migration(migrations.Migration):

    dependencies = [
        ('temporal', '0017_taskmeta_counts_growth'),
    ]

    operations = [
        migrations.AddField(
            model_name='taskmeta',
            name='daily_role',
            # ⚠️ `db_comment` 必须显式写：`apps/core/db_comments.py` 会在模型层按
            #    verbose_name 自动派生它（本项目不逐字段手写），迁移里的字段定义
            #    不带这一项 ⇒ `makemigrations --check` 立刻报「还差一条 AlterField」。
            field=models.CharField(
                blank=True,
                choices=[('', '不参与'), ('sleep_night', '夜间睡眠'), ('nap', '午睡'), ('game', '游戏')],
                db_comment='日常护栏角色',
                default='',
                help_text='标了才计入「今天的三条线」：夜间睡眠按醒来那一刻归属日期，午睡/游戏按开始时刻',
                max_length=20,
                verbose_name='日常护栏角色',
            ),
        ),
        migrations.RunPython(backfill_roles, clear_roles),
    ]
