# 「成长计时」从隐式规则改成显式标记（v3.64.11）

from django.db import migrations, models


def backfill_from_deep_work(apps, schema_editor):
    """把当时「L2 = 深度工作」的任务名全部预置为「计入成长计时」。

    🔴 这一步是**行为不变**的保证：迁移前后「成长小时数」算出来的是同一批任务。
       不做回填，新口径下成长小时数会直接变 0 —— 那是最坏的静默失败
       （数字落在合理区间、不报错、只是全没了）。
    """
    TaskMeta = apps.get_model('temporal', 'TaskMeta')
    TaskMeta.objects.filter(activity_type='深度工作').update(counts_growth=True)


def unbackfill(apps, schema_editor):
    """回退：把标记清零（列本身由 RemoveField 删掉，这里只保证可逆、不残留语义）。"""
    TaskMeta = apps.get_model('temporal', 'TaskMeta')
    TaskMeta.objects.update(counts_growth=False)


class Migration(migrations.Migration):

    dependencies = [
        ('temporal', '0016_timersession'),
    ]

    operations = [
        migrations.AddField(
            model_name='taskmeta',
            name='counts_growth',
            # ⚠️ `db_comment` 必须显式写：`apps/core/db_comments.py` 会在模型层按
            #    verbose_name 自动派生它（本项目不逐字段手写），迁移里的字段定义
            #    不带这一项 ⇒ `makemigrations --check` 立刻报「还差一条 AlterField」。
            field=models.BooleanField(
                db_comment='计入成长计时',
                default=False,
                help_text='勾选后，该任务名下的时长进入每周状态的「成长小时数」',
                verbose_name='计入成长计时',
            ),
        ),
        migrations.RunPython(backfill_from_deep_work, unbackfill),
    ]
