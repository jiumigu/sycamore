"""作品类型加「绘画作品 / 刺绣作品」，并把「画」这条**模板**改成按类型自动取数

v3.64.30。三件事：

1. `works.constants.WORK_KIND_CHOICES` 加 `drawing` / `embroidery`，
   并把 `craft` 的 label「实物」改成「**其他手作**」—— 不改名，「实物」就仍是
   一个能装下所有手工实物的桶，按类型自动数会**静默漏件**；
2. `selfrun.readers.works_count` 支持 `where.work_kind`（配错类型名直接抛错，不返 0）；
3. 本迁移改模板库里 `painting`（画）的取数方式，并新增 `embroidery`（绣品）。

🔴 **只改 `selfrun_template`，不碰 `selfrun_metric`。** 这是 `0003` 立下的规矩，
   这一次尤其要紧：库里 `画`（metric 5）已经有 **3 条手工登记**，
   贸然改成「自动 + 手工补记」会变成「作品库那几张 + 手工 3 张」——
   同一张画数两遍。双算不会报错，只会让月度状态从 3 张变 4 张，
   而 4 张看着同样合理。要不要切、那 3 条手工记录要不要作废，
   是用户的决定，不是升级的副作用（判据同 `0003` / `0005`）。

⚠️ 模板是「起点」不是「活引用」：本迁移改完之后，**已建阶段一个字都不会变**
   （`SelfRunMetric` 是拷贝）。要切现有阶段那条，走「制定配置 → 本阶段 KPI」。

⚠️ 历史期不会自动重算：已归档的期是定格快照（`auto_value` 写在归档那一刻），
   新口径从下一个**未归档**的期开始生效。
"""
from django.db import migrations

# ⚠️ 迁移必须自包含：字面量刻意与 `templates.py` 重复一次 ——
#    改模板不该改写这条迁移已经做过的历史。
PAINTING = {
    'agg': 'count',
    'source_kind': 'auto_plus_manual',
    'source_config': {'kind': 'works_count', 'where': {'work_kind': 'drawing'}},
}

EMBROIDERY = {
    'name': '绣品',
    'period_type': 'monthly',
    'unit': '件',
    'direction': 'at_least',
    'goal_value': None,
    'floor_value': None,
    'goal_why': '',
    'floor_why': '',
    'agg': 'count',
    'source_kind': 'auto_plus_manual',
    'source_config': {'kind': 'works_count', 'where': {'work_kind': 'embroidery'}},
    'sort_order': 65,
}


def forward(apps, schema_editor):
    Template = apps.get_model('selfrun', 'SelfRunTemplate')

    # 幂等：只改「还是手工」的那条。用户自己已经切过（或删过）的一律不碰 ——
    # 覆盖它等于把用户的选择改回默认值，而且不报错。
    Template.objects.filter(key='painting', source_kind='manual').update(**PAINTING)

    # 新 key 不可能被用户删过（此前不存在）⇒ `get_or_create` 语义安全。
    # ⚠️ 旧模板不要学这个写法：给已存在的 key 用 get_or_create 会把用户删掉的条目放回来。
    Template.objects.get_or_create(key='embroidery', defaults=EMBROIDERY)


class Migration(migrations.Migration):

    dependencies = [
        ('selfrun', '0010_poolinject_mark'),
        # 逻辑依赖：`works_count` 读 `works_work.kind`；没有这张表就会 500。
        ('works', '0005_work_media'),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
