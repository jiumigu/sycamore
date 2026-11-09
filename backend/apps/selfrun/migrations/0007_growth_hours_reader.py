"""成长小时数：从「L2 = 深度工作」切到「映射编辑器的成长计时开关」

2026-11-01 用户拍板：**开关说了算**。此前这条 KPI 的口径写死在配置里
（`{'kind': 'temporal_hours', 'where': {'l2': ['深度工作']}}`）—— 界面上看不见，
要新增一个「算成长」的分类只能把它塞进「深度工作」桶，等于用一个不相干的维度
表达另一件事；而且把某个任务从深度工作挪走会**顺手改掉成长口径**。

改后：`{'kind': 'growth_hours'}` —— 口径固定读 `temporal_task_meta.counts_growth`。

配套（缺一条就白改）：
- `temporal/migrations/0017` 已把当时 L2=深度工作 的任务名回填为 `counts_growth=True`
  ⇒ 迁移前后算出来的是**同一批任务**，本周数字一个字不变；
- `apps/selfrun/templates.py` 同口径（新建阶段直接用新的）；
- `constants.READER_KEYS / READER_WHERE_KEYS / STALE_RULES` 已登记 `growth_hours`。

🔴 只改「还是旧口径」的行（`kind == 'temporal_hours'` 且 `where.l2 == ['深度工作']`）：
   已经手改成别的口径的、或别的 L2 的时长 KPI，一律不碰 ⇒ 重复执行安全（幂等）。
⚠️ 已归档的历史期不动：它们存的是 `readings` 快照（归档即定格），
   换口径只影响还没归档的那一期往后。
⚠️ 代价（如实记下）：`source_config` 变了 ⇒ `config_fingerprint` 会变一次，
   历史复盘里「跨期可比」的分组会在这里断一节。集合其实没变（同一批任务），
   变的是**表示方式**。这是可接受的：真要假装没变，就得让指纹忽略配置，那更糟。
"""
from django.db import migrations

OLD_KIND = 'temporal_hours'
NEW_KIND = 'growth_hours'
DEEP_WORK = ['深度工作']


def _is_old(cfg):
    """旧口径判定：temporal_hours + 恰好按「深度工作」这一个 L2 过滤。"""
    if not cfg or cfg.get('kind') != OLD_KIND:
        return False
    return list((cfg.get('where') or {}).get('l2') or []) == DEEP_WORK


def _switch(apps, *, to_growth: bool):
    for model_name in ('SelfRunMetric', 'SelfRunTemplate'):
        Model = apps.get_model('selfrun', model_name)
        if to_growth:
            rows = Model.objects.filter(source_config__kind=OLD_KIND)
            for row in rows:
                if _is_old(row.source_config):
                    row.source_config = {'kind': NEW_KIND}
                    row.save(update_fields=['source_config'])
        else:
            rows = Model.objects.filter(source_config__kind=NEW_KIND)
            for row in rows:
                row.source_config = {'kind': OLD_KIND, 'where': {'l2': DEEP_WORK}}
                row.save(update_fields=['source_config'])


def forward(apps, schema_editor):
    _switch(apps, to_growth=True)


def backward(apps, schema_editor):
    _switch(apps, to_growth=False)


class Migration(migrations.Migration):

    dependencies = [
        ('selfrun', '0006_alter_selfrunperiod_status'),
        # 🔴 跨 app 依赖：新取数器读 `temporal_task_meta.counts_growth`，
        #    必须等那一列建好再切配置 —— 否则 `migrate` 的中间态里
        #    「配置已指向 growth_hours、列却还不存在」，任何读接口都会 500。
        ('temporal', '0017_taskmeta_counts_growth'),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
