"""池注入从「自记金额」改成「标记账单」（v3.64.26）

背景：`selfrun_pool_inject` 原本自己记 amount / inject_date / source / note，
但账本里从来没有过录入入口，所以「中途注入」永远是 ¥0。
2026-11-05 用户裁决：**在账单明细页给收入加一个「中途注入」标识** ——
钱只录一次，注入金额与日期一律从账单读。

本迁移因此：

1. 删 `amount` / `inject_date` / `source` / `note` —— 金额与日期改为从账单读，
   再留一份就是「同一笔钱两个数」（账单改了、注入没改，分叉且静默）。
2. 删 `stage` 外键 —— 标记是**账单的属性**，注入额按阶段区间夹窗口算，
   与本金、消耗同一把尺子；再挂 stage 会出现「stage 说属于 A、账单日期落在 B」的双源。
3. 加 `bill_id`（唯一）—— 一笔账单只能标一次。

⚠️ 本表在写迁移时是 **0 行**（`SelfRunPoolInject.objects.count() == 0`，2026-11-05 实测），
   所以逐列删除不会丢数据。若在别的环境里非空，先备份再跑。
🔴 只写不跑：执行由用户手动完成（项目铁律一）。
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('selfrun', '0009_alter_selfrunstage_ledger_config_and_more'),
    ]

    operations = [
        migrations.RemoveField(model_name='selfrunpoolinject', name='amount'),
        migrations.RemoveField(model_name='selfrunpoolinject', name='inject_date'),
        migrations.RemoveField(model_name='selfrunpoolinject', name='source'),
        migrations.RemoveField(model_name='selfrunpoolinject', name='note'),
        migrations.RemoveField(model_name='selfrunpoolinject', name='stage'),
        migrations.AddField(
            model_name='selfrunpoolinject',
            name='bill_id',
            field=models.IntegerField(
                db_comment='账单ID', default=0, unique=True, verbose_name='账单ID',
            ),
            preserve_default=False,
        ),
        migrations.AlterModelOptions(
            name='selfrunpoolinject',
            options={
                'managed': True,
                'ordering': ['-created_at', '-id'],
                'verbose_name': '自我运转·池注入标记',
                'verbose_name_plural': '自我运转·池注入标记',
            },
        ),
        migrations.AlterModelTableComment(
            name='selfrunpoolinject',
            table_comment='池注入标记：被标为「中途注入」的账单 id（金额从账单读）',
        ),
        migrations.AlterField(
            model_name='selfrunpoolinject',
            name='bill_id',
            # ⚠️ 这条 `db_comment` 必须与 `core.db_comments.COLUMN_COMMENT_OVERRIDES`
            #    的文案**逐字相同**。写 '账单ID'（= verbose_name 派生的默认值）
            #    会让 `makemigrations --check` 永远报一条假差异（0010 之后又冒出 0012）。
            field=models.IntegerField(
                db_comment='被标为「中途注入」的账单 id —— 金额从账单读，本表不存钱',
                unique=True, verbose_name='账单ID',
            ),
        ),
        migrations.AlterField(
            model_name='selfrunpoolinject',
            name='created_at',
            field=models.DateTimeField(
                auto_now_add=True, db_comment='标记时间', verbose_name='标记时间',
            ),
        ),
    ]
