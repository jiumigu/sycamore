"""把 `temporal_time_atracker_tasks_list` 的字符集对齐到项目基线。

## 为什么需要这个迁移（本张表的情况和别的不同）

这张表的建表迁移 `temporal/0001_initial` **写的就是 `CHARSET=utf8mb4`**，
但库里实际是 `utf8mb3_general_ci`。原因在 `CREATE TABLE IF NOT EXISTS`：

    这张表先于迁移存在（早期从 ATracker 导入镜像建起来的）
    ⇒ 迁移跑到时建表语句被**静默跳过**
    ⇒ 「迁移里写 utf8mb4」与「库里是 utf8mb3」长期不一致

🔴 这正是「`IF NOT EXISTS` 会让 DDL 正确性验证失效」的一个实例 ——
`sqlmigrate` 看起来完全正确，库里却不是那样。

⇒ **`0001` 不用改**（它本来就对），已有库靠本迁移补上。

## 为什么是 RunSQL

`TemporalTask` 是 `managed=False`（外部表）⇒ Django 不托管结构。

## 索引长度无风险

`schema_editor` 之外唯一要留意的是 varchar 索引。本表索引建在
`task_name` varchar(255)：utf8mb3 下 765 字节 → utf8mb4 下 1020 字节，
仍低于 InnoDB 单索引 3072 字节上限（DYNAMIC 行格式），**不会超限**。

## ⚠️ 这个迁移不能安全回滚

`reverse_sql` 退回 `utf8mb3`。若之后写进过 4 字节字符，回滚会**报错或截断**。
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('temporal', '0014_db_comments'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE `temporal_time_atracker_tasks_list` "
                "CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci",
            reverse_sql="ALTER TABLE `temporal_time_atracker_tasks_list` "
                        "CONVERT TO CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci",
        ),
    ]
