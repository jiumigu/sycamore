"""把 `wealth_regular_list` 的字符集对齐到项目基线。

## 为什么需要这个迁移

库里的 `wealth_regular_list` 是 `utf8mb3_general_ci`，项目基线是
`utf8mb4` / `utf8mb4_0900_ai_ci`。本表有 `remark`（备注）、`bankinfo`（开户行）
两处文本列，utf8mb3 存不下 4 字节字符。

## ⚠️ 本表没有建表迁移 —— 它是纯外部表

`wealth/0001_squashed_0009` 里 `WealthRegularList` 的 `CreateModel` 带
`'managed': False`，Django **不会为它建表**（`allow_migrate_model` 返回 False）。
它先于项目存在，结构一直由人手工维护。

⇒ 别去找「和 `0001` 配对的那处改动」——**没有那一处**。
本迁移是唯一的改动点。

## ⚠️ 前提：这张表必须已经存在

本迁移**不做存在性守卫**，表不在就直接报错。这是有意的：

* 与其静默跳过（`if not exists: return`），不如**明确失败** ——
  「表不在」本身就是要人知道的事，静默跳过会伪装成「已经对齐好了」；
* 而且 `wealth/0030_db_comments` 已经对这张表发过无条件的
  `ALTER TABLE ... COMMENT`，同样假定它存在 —— 两处假设保持一致。

## 改动范围

只换字符集 / 排序规则，不动列定义、不动数据、不改索引（PK 是 int 的 `id`）。

## ⚠️ 这个迁移不能安全回滚

`reverse_sql` 退回 `utf8mb3`。若之后写进过 4 字节字符，回滚会**报错或截断**。
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('wealth', '0030_db_comments'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE `wealth_regular_list` "
                "CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci",
            reverse_sql="ALTER TABLE `wealth_regular_list` "
                        "CONVERT TO CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci",
        ),
    ]
