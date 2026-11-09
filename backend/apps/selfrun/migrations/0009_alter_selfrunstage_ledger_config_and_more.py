"""阶段现金池注入流水（原 `redemption_pool_inject`）+ 两列补 db_comment

2026-11-02 第 4 轮（`docs/赎回期并入自我运转-实施清单-20261102.md` §四）：
「三年赎回期」彻底退役成自我运转下的一个**长阶段**，它那张注水流水表跟过来，
改名 `selfrun_pool_inject` 并加 `stage` 外键。

为什么不是「给旧表加一列 stage」：那样 `redemption` 会反过来依赖 `selfrun`
（外键指向 `selfrun_stage`），而 `selfrun.services` 又在用 `redemption.services`
的计算函数 —— **双向依赖**，没有正确的加载顺序可言。

⚠️ 本迁移只建表与补注释，**不搬数据**：搬运在 `redemption.0010` 的 RunPython 里，
   因为必须等这张表建好之后才搬得进来。
⚠️ 本次迁移与 `redemption.0010` 都由**用户自己执行** `migrate`，跑前先备份。
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('selfrun', '0008_selfrunstage_ledger_config_selfrunstage_parent'),
    ]

    operations = [
        migrations.AlterField(
            model_name='selfrunstage',
            name='ledger_config',
            field=models.JSONField(blank=True, db_comment='账本参数（JSON）—— 目前只有 pool_principal 一项', default=dict, verbose_name='账本参数'),
        ),
        migrations.AlterField(
            model_name='selfrunstage',
            name='parent',
            field=models.ForeignKey(blank=True, db_comment='上级阶段 —— 空 = 顶级；只有两层，长阶段下才挂小阶段', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='children', to='selfrun.selfrunstage', verbose_name='上级阶段'),
        ),
        migrations.CreateModel(
            name='SelfRunPoolInject',
            fields=[
                ('id', models.AutoField(auto_created=True, db_comment='主键', primary_key=True, serialize=False, verbose_name='ID')),
                ('inject_date', models.DateField(db_comment='注入日期', verbose_name='注入日期')),
                ('amount', models.DecimalField(db_comment='注入金额（元）—— 正数为注入池', decimal_places=2, max_digits=14, verbose_name='注入金额（正数为注入池）')),
                ('source', models.CharField(choices=[('赔偿', '赔偿'), ('借款', '借款'), ('额外收入', '额外收入'), ('其他', '其他')], db_comment='来源', default='其他', max_length=20, verbose_name='来源')),
                ('note', models.TextField(blank=True, db_comment='备注', null=True, verbose_name='备注')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_comment='创建时间', verbose_name='创建时间')),
                ('stage', models.ForeignKey(db_comment='所属阶段 —— 注入流水按阶段归属，不按日期夹窗口', on_delete=django.db.models.deletion.PROTECT, related_name='pool_injects', to='selfrun.selfrunstage', verbose_name='所属阶段')),
            ],
            options={
                'verbose_name': '自我运转·池注入',
                'verbose_name_plural': '自我运转·池注入',
                'db_table': 'selfrun_pool_inject',
                'db_table_comment': '阶段现金池注入流水：启动池的中途注水，一行一笔',
                'ordering': ['-inject_date', '-id'],
                'managed': True,
            },
        ),
    ]
