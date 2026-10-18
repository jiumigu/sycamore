"""把 `hobby_dance_list` 的字符集从 utf8mb3 对齐到项目基线。

## 为什么需要这个迁移

`dance/0001_initial` 建表时写的是 `DEFAULT CHARSET=utf8mb3`，而项目其余表
是 `utf8mb4` / `utf8mb4_0900_ai_ci`（实测 113 / 127 张）。

诱因不是「不好看」，是 **utf8mb3 存不下 4 字节字符**（emoji、部分生僻字），
而本表恰恰有两处手写长文本：`remark`（备注）与 `improvement_note`
（进步 / 待改进点）。写进去的那一刻才会报错，属于「用到才发现」。

## 为什么是 RunSQL 而不是模型层声明

`DanceRecord` 是 `managed=False`（外部表）⇒ **Django 不托管它的结构**，
autodetector 根本不参与这张表 ⇒ 只能走原生 SQL。所以 `0001` 的
`CreateModel` 里也没有任何字符集字段可改。

## 两处必须同时改（只改一处 = 新库老库二选一地错）

| 位置 | 负责 |
|---|---|
| `0001_initial` 建表 DDL | **全新库**建表时直接对 |
| 本迁移的 `CONVERT` | **已存在的库**转换过来 |

`0001` 对已有库是 no-op（`managed=False` 时 Django 不建表，且那张表本来就
先于迁移存在），所以光改 `0001` 等于没改 —— 这是本轮最容易被漏掉的地方。

## 改动范围

只换表与列的字符集 / 排序规则，**不动列定义、不动数据、不改索引**。
utf8mb3 → utf8mb4 是**扩充**（utf8mb4 是 utf8mb3 的超集），已存字符逐字保留。

## 索引长度无风险

本表 varchar 索引最长的是 `teacher_name` varchar(20)：
utf8mb3 下 60 字节 → utf8mb4 下 80 字节，远低于 InnoDB 单索引 3072 字节上限。
（`study_time` 是 date、`dance_type` varchar(12)、`difficulty` varchar(10)，更小。）

## ⚠️ 这个迁移不能安全回滚

`reverse_sql` 把字符集退回 `utf8mb3`。若转换之后写进过 4 字节字符（emoji 等），
回滚会**报错或静默截断**。真要回滚，先确认数据里没有 4 字节字符。
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dance', '0002_db_comments'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE `hobby_dance_list` "
                "CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci",
            reverse_sql="ALTER TABLE `hobby_dance_list` "
                        "CONVERT TO CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci",
        ),
    ]
