"""把**已建阶段**里的两条输出 KPI 从「日记流 MIGU 条数」切到「作品库件数」

`0003` 只改了 `selfrun_template`（模板库），并在注释里写明不碰 `selfrun_metric`
（已建阶段的拷贝）——理由是「用哪把尺子是用户的决定，不是升级的副作用」。
2026-10-18 这个决定已经做了：**输出口径改为作品库的作品明细条数**。

所以这条迁移做三件事，且只做三件：

| 改 | 值 |
|---|---|
| `name` | 输出次数 / 内容输出 → **留下件数** |
| `unit` | 次 / 条 → **件** |
| `source_config` | `{'kind': 'diary_migu_count', ...}` → `{'kind': 'works_count'}` |

🔴 **刻意不动 `goal_value` / `floor_value`。**
库里 `content_output` 的月目标是 **8 件**（模板写 4 件），这是建阶段时留下的数；
目标值是**用户手调过的输入**，不是口径的一部分（§114.1：seed 覆盖会抹掉手调值）。
要降到 4 就在「制定配置 → 本阶段 KPI」里改那一条 —— 那是唯一合法入口。

🔴 **过滤条件是「还是旧口径」**：只改 `source_config.kind == 'diary_migu_count'` 的行。
已经手动切过的、或已被退役的，一律不碰 ⇒ 重复执行安全（幂等）。

⚠️ 作品表刻意不落 `period_key`，所以切过来之后**历史期不会自动重算**：
过去那些期仍按当时写入的 `auto_value` 定格（归档即定格，§77），
从下一个未归档的期开始才是新口径。这是有意的，不是遗漏。

配套：`apps/selfrun/templates.py` 已同口径；`diff_templates_vs_db()` 可查出
「模板 vs 库里的行」还差哪些字段（只读，不改数据）。
"""
from django.db import migrations

# 迁移必须自包含：字面量刻意与 templates.py / 0003 各重复一次，
# 改模板不该改写这条迁移已经做过的历史。
NEW = {
    'output_count': {
        'name': '留下件数',
        'unit': '件',
        'source_config': {'kind': 'works_count'},
    },
    'content_output': {
        'name': '留下件数',
        'unit': '件',
        'source_config': {'kind': 'works_count'},
    },
}

OLD = {
    'output_count': {
        'name': '输出次数',
        'unit': '次',
        'source_config': {'kind': 'diary_migu_count', 'where': {'otype_eq': 'MIGU'}},
    },
    'content_output': {
        'name': '内容输出',
        'unit': '条',
        'source_config': {'kind': 'diary_migu_count', 'where': {'otype_eq': 'MIGU'}},
    },
}


def _apply(apps, table, *, only_old_kind):
    Metric = apps.get_model('selfrun', 'SelfRunMetric')
    for key, vals in table.items():
        qs = Metric.objects.filter(template_key=key)
        if only_old_kind:
            # 只认「还没切过」的行：口径标记仍是 diary_migu_count
            qs = qs.filter(source_config__kind='diary_migu_count')
        for row in qs:
            for field, value in vals.items():
                setattr(row, field, value)
            row.save(update_fields=list(vals.keys()))


def forward(apps, schema_editor):
    # 切换：只碰仍是旧口径的行
    _apply(apps, NEW, only_old_kind=True)


def backward(apps, schema_editor):
    # 回退：只把「已经是新口径」的行改回去，避免误伤用户后来手改的
    Metric = apps.get_model('selfrun', 'SelfRunMetric')
    for key, vals in OLD.items():
        for row in Metric.objects.filter(template_key=key, source_config__kind='works_count'):
            for field, value in vals.items():
                setattr(row, field, value)
            row.save(update_fields=list(vals.keys()))


class Migration(migrations.Migration):

    dependencies = [
        ('selfrun', '0004_db_comments'),
        # 逻辑依赖：`works_count` 取数器读 `works_work`；切片后没有这张表就会 500。
        ('works', '0004_db_comments'),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
