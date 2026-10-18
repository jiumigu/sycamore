"""把 `health_step_info` 的字符集从 utf8mb3 对齐到项目基线。

## 为什么需要这个迁移

`health/0001_initial` 建表时写的是 `DEFAULT CHARSET=utf8mb3`，而项目基线是
`utf8mb4` / `utf8mb4_0900_ai_ci`。utf8mb3 **存不下 4 字节字符**，本表有
`remark` varchar(255) 与 `years` varchar(25) 两处文本列。

⚠️ 本表用的是 `CREATE TABLE IF NOT EXISTS` —— 开发库里这张表**先于迁移存在**，
建表语句当年被静默跳过，所以「迁移写的什么」与「库里是什么」一直是两回事。
改 `0001` 只让**全新库**对，已有库必须靠本迁移。

## 为什么是 RunSQL

`HealthRecord` 是 `managed=False`（外部表）⇒ Django 不托管结构，只能原生 SQL。

## 改动范围

只换字符集 / 排序规则，不动列定义、不动数据、不改索引。
utf8mb3 → utf8mb4 是扩充，已存字符逐字保留。

## 索引长度无风险

varchar 索引最长 `years` varchar(25)：utf8mb3 下 75 字节 → utf8mb4 下 100 字节，
远低于 InnoDB 单索引 3072 字节上限。

## ⚠️ 这个迁移不能安全回滚

`reverse_sql` 退回 `utf8mb3`。若之后写进过 4 字节字符，回滚会**报错或截断**。
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('health', '0007_db_comments'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE `health_step_info` "
                "CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci",
            reverse_sql="ALTER TABLE `health_step_info` "
                        "CONVERT TO CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci",
        ),
    ]
