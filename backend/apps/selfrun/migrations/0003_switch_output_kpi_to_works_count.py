"""把「输出次数 / 内容输出」的口径从**次数**改成**件数**（取数源改为作品库）

🔴 **这一条只改 `selfrun_template`（模板库），不碰任何已建阶段（`selfrun_metric`）。**

理由：模板是**起点**、阶段是**拷贝**（`templates.py` 铁律 1）。
现有阶段正在跑，把它的取数源从「日记流 MIGU 条数」换成「作品库件数」
会让**本期已经写好的那几篇**突然不计入 ⇒ 直接红灯。
「用哪把尺子」是用户的决定，不是升级的副作用。
（要切现有阶段：在「制定过程 → 本阶段 KPI」里改这一条即可。）

> 口径变更本身是有记录的：这条迁移把 `output_count` / `content_output`
> 两条模板的 `source_config.kind` 从 `diary_migu_count` 换成 `works_count`，
> 并同步改 `name` / `unit` / `goal_why` / `floor_why`。
> ⚠️ `key` **刻意不改** —— 它是 `Metric.template_key` 的指向，
> 改 key 会让「这条 KPI 从哪个模板来的」这一层关系认不出来。
"""
from django.db import migrations

# ⚠️ 迁移必须自包含：这里的字面量**刻意**与 `templates.py` 重复一次。
#    改了 `templates.py` 不该改写这条迁移已经做过的历史。
NEW = {
    'output_count': {
        'name': '留下件数',
        'unit': '件',
        'goal_value': 2,
        'floor_value': 1,
        'agg': 'count',
        'source_kind': 'auto',
        'source_config': {'kind': 'works_count'},
        'goal_why': '一周留下两件是节奏',
        'floor_why': '一件是底线',
    },
    'content_output': {
        'name': '留下件数',
        'unit': '件',
        'goal_value': 4,
        'floor_value': None,
        'agg': 'count',
        'source_kind': 'auto',
        'source_config': {'kind': 'works_count'},
        'goal_why': '每月 4 件（每周 1 件）—— 你不是全职博主，是「正在建造的人」',
        'floor_why': '',
    },
}

OLD = {
    'output_count': {
        'name': '输出次数',
        'unit': '次',
        'goal_value': 2,
        'floor_value': 1,
        'agg': 'count',
        'source_kind': 'auto',
        'source_config': {'kind': 'diary_migu_count', 'where': {'otype_eq': 'MIGU'}},
        'goal_why': '一次是底线，两次是节奏',
        'floor_why': '你写的底线：1 次（近 11 周达标 9/11）',
    },
    'content_output': {
        'name': '内容输出',
        'unit': '条',
        'goal_value': 4,
        'floor_value': None,
        'agg': 'count',
        'source_kind': 'auto',
        'source_config': {'kind': 'diary_migu_count', 'where': {'otype_eq': 'MIGU'}},
        'goal_why': '每月 4 条（每周 1 条）—— 你不是全职博主，是「正在建造的人」',
        'floor_why': '',
    },
}


def _apply(apps, table):
    Template = apps.get_model('selfrun', 'SelfRunTemplate')
    for key, vals in table.items():
        row = Template.objects.filter(key=key).first()
        if row is None:
            continue          # 用户把它删了 —— 不还原（templates.py 铁律）
        for field, value in vals.items():
            setattr(row, field, value)
        row.save()


def forward(apps, schema_editor):
    _apply(apps, NEW)


def backward(apps, schema_editor):
    _apply(apps, OLD)


class Migration(migrations.Migration):

    dependencies = [
        ('selfrun', '0002_selfruntemplate_alter_selfrunmetriclog_action_and_more'),
        # 逻辑依赖：`works_count` 取数器要读 `works_work` 这张表。
        # 不加这条也能跑（本迁移只改 JSON 字面量），但顺序上说不通。
        ('works', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
