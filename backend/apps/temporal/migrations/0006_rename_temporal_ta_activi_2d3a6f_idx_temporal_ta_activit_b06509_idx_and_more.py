"""TaskMeta 两个索引改名：对齐 Django 6.0 变化后的自动索引命名规则

Django 6.0 去掉了升序索引名的 `+` 前缀位（`db/models/indexes.py`：
`("+%s" if order else "%s")` → `("-%s" if order else "%s")`），字段名切片随之右移一位、
hash 亦变，于是 0005 生成的自动名与本版模型声明（现已改为**显式 name=**）不再一致：

    temporal_ta_activi_2d3a6f_idx → temporal_ta_activit_b06509_idx  （activity_type）
    temporal_ta_group_3c4b7e_idx  → temporal_ta_group_i_78a288_idx  （group 外键）

执行后数据库层 = 2 条 `RENAME INDEX`，不增删索引、不动数据。

注：group 索引看似"可清理"，但 `group_id` 是外键列，InnoDB 强制要求 FK 列上有索引——
删掉后 Django/MySQL 会立即重建替代索引（`sqlmigrate` 实测为先 `CREATE INDEX
temporal_task_meta_group_id_d0aa3431` 再 `DROP INDEX`），净收益为零，故一并保留。
要真正清理，须连外键约束与 `group_id` 列一起删，属破坏性变更，暂不执行。
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('temporal', '0005_activity_group_and_task_meta'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='taskmeta',
            new_name='temporal_ta_activit_b06509_idx',
            old_name='temporal_ta_activi_2d3a6f_idx',
        ),
        migrations.RenameIndex(
            model_name='taskmeta',
            new_name='temporal_ta_group_i_78a288_idx',
            old_name='temporal_ta_group_3c4b7e_idx',
        ),
    ]
