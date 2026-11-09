"""撤掉「游戏」角色：流失改按 L1 归因统计（v3.64.13）

为什么撤：

* 「游戏 ≤ 2h」是「流失 ≤ 4h」的**子集**，两条线量同一件事 ⇒ 读的人得自己判哪个算数；
* 那条线**永远不会亮**（实测历史最高 1.37h），等于没设；
* 流失直接读 `TaskMeta.default_attribution` / 归因规则即可，不必再逐个任务标角色 ——
  少一个「标漏了就静默失效」的环节。

数据侧只有一个动作：把已经标成 `game` 的行清空（值域里没有它了，留着会让
`role_count` 多算，且编辑器下拉显示不出这一项）。
"""
from django.db import migrations, models


def clear_game_role(apps, schema_editor):
    TaskMeta = apps.get_model('temporal', 'TaskMeta')
    TaskMeta.objects.filter(daily_role='game').update(daily_role='')


def restore_game_role(apps, schema_editor):
    """反向是**空操作**：清空的是用户手工标记，回不去，也不该猜回哪些行。

    真要继续用「游戏」那条线，是恢复 `constants.DAILY_GUARD_LINES` 里那一条，
    不必把标记塞回去 —— 流失口径下它本来就不需要标记。
    """


class Migration(migrations.Migration):

    dependencies = [
        ('temporal', '0018_taskmeta_daily_role'),
    ]

    operations = [
        migrations.RunPython(clear_game_role, restore_game_role),
        migrations.AlterField(
            model_name='taskmeta',
            name='daily_role',
            field=models.CharField(
                blank=True,
                choices=[('', '不参与'), ('sleep_night', '夜间睡眠'), ('nap', '午睡')],
                db_comment='日常护栏角色',
                default='',
                help_text='标了才计入「今天的三条线」：夜间睡眠按醒来那一刻归属日期，午睡按开始时刻（流失不看这列）',
                max_length=20,
                verbose_name='日常护栏角色',
            ),
        ),
    ]
