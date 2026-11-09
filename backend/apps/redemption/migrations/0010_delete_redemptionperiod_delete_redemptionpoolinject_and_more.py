"""赎回期退役：把配置搬成「长阶段」，然后删掉三张表

## 为什么数据搬运写在迁移里，而不是一个独立脚本

实施清单原本计划「一次性脚本搬运 + 迁移只删表」。真正排顺序时发现**两个时点都错**：

| 脚本跑在 | 问题 |
|---|---|
| `migrate` 之前 | `selfrun_pool_inject` 还没建，注水搬不进去 |
| `migrate` 之后 | `redemption_period` 已经被删，配置读不出来 |

Django 的 `migrate` 是「把 pending 的一次跑完」，中间没有能插脚本的缝。
所以搬运只能落在迁移内部，靠依赖关系保证顺序：
`selfrun 0009`（建新表）→ **本迁移的 RunPython**（搬）→ 三个 DeleteModel（删）。

## 🔴 只在「用户自己跑 migrate」时执行

AI 不执行本次迁移。跑之前**必须**备份数据库到 `db_backups/`。

## 🔴 反向迁移只重建空表，**数据不回流**

`RunPython.noop` 是刻意的：反向要「把长阶段拆回 redemption_period」，
而长阶段名下可能已经挂了新的小阶段与 KPI —— 自动拆会造出一个没人预期的
历史归属。真要回滚，先人工确认阶段与流水怎么分，别指望迁移替你决定。

## 幂等

正向重跑（反向再正向后）不会造出第二个「三年赎回期」：按
`name + parent + start_date` 命中已有那一行，只补窗口与本金。
"""

from django.db import migrations


def _migrate_period_to_long_stage(apps, schema_editor):
    """① 赎回期那一行 → 顶级长阶段 ② open 的小阶段挂上去 ③ 注水流水平移"""
    RedemptionPeriod = apps.get_model('redemption', 'RedemptionPeriod')
    RedemptionPoolInject = apps.get_model('redemption', 'RedemptionPoolInject')
    SelfRunStage = apps.get_model('selfrun', 'SelfRunStage')
    SelfRunPoolInject = apps.get_model('selfrun', 'SelfRunPoolInject')

    period = RedemptionPeriod.objects.order_by('id').first()
    if period is None:
        return

    principal = float(period.pool_principal or 0)

    # ① 顶级长阶段（零 KPI ⇒ 正是 `is_long_stage` 的判据）
    long_stage = (
        SelfRunStage.objects
        .filter(name='三年赎回期', parent__isnull=True, start_date=period.start_date)
        .first()
    )
    if long_stage is None:
        long_stage = SelfRunStage.objects.create(
            name='三年赎回期',
            start_date=period.start_date,
            end_date=period.end_date,
            status='paused' if period.tracking_status == 'paused' else 'active',
            note='由「三年赎回期」配置迁入（v3.64.20）',
            ledger_config={'pool_principal': principal},
        )
    else:
        # 已存在 ⇒ 只补窗口与本金（别覆盖 `ledger_config` 里将来可能多出的键）
        cfg = dict(long_stage.ledger_config or {})
        cfg.setdefault('pool_principal', principal)
        long_stage.start_date = period.start_date
        long_stage.end_date = period.end_date
        long_stage.ledger_config = cfg
        long_stage.save(
            update_fields=['start_date', 'end_date', 'ledger_config', 'updated_at'],
        )

    # ② **只挂还在跑的顶级叶子阶段**：已收尾的阶段是历史，挂到哪一段都不对。
    #    「≤2 层」约束要求的是「长阶段自己不是别人的孩子」，
    #    而不是「所有顶级阶段都必须有孩子」。
    SelfRunStage.objects.filter(
        parent__isnull=True, status__in=['active', 'paused'],
    ).exclude(pk=long_stage.pk).update(parent=long_stage)

    # ③ 注水流水（当前 0 行，仍走流程 —— 别的环境可能不是 0）
    for row in RedemptionPoolInject.objects.all().iterator():
        new_row = SelfRunPoolInject.objects.create(
            stage=long_stage,
            inject_date=row.inject_date,
            amount=row.amount,
            source=row.source or '其他',
            note=getattr(row, 'note', None),
        )
        # `created_at` 是 auto_now_add，create 时传不进去 ⇒ 再校正一次保住原时间
        if getattr(row, 'created_at', None):
            SelfRunPoolInject.objects.filter(pk=new_row.pk).update(
                created_at=row.created_at,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('redemption', '0009_delete_redemptionattrrule'),
        # 必须先建好 `selfrun_pool_inject` 与长阶段那两列，才谈得上搬进来
        ('selfrun', '0009_alter_selfrunstage_ledger_config_and_more'),
    ]

    operations = [
        migrations.RunPython(
            _migrate_period_to_long_stage,
            # 反向不搬数据，理由见文件头
            migrations.RunPython.noop,
        ),
        migrations.DeleteModel(
            name='RedemptionPeriod',
        ),
        migrations.DeleteModel(
            name='RedemptionPoolInject',
        ),
        migrations.DeleteModel(
            name='RedemptionWeekSnapshot',
        ),
    ]
