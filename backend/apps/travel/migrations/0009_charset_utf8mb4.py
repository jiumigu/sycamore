"""把 `travel_list_info` 的字符集对齐到项目基线。

## 为什么需要这个迁移（本张表的情况和别的不一样）

`travel/0001_initial` 的建表语句**写的就是 `CHARSET=utf8mb4`**，
但库里实际是 `utf8mb3_general_ci`。原因在 `CREATE TABLE IF NOT EXISTS`：

    这张表先于迁移存在（早期从打卡记录导入的镜像表）
    ⇒ 迁移跑到时建表语句被**静默跳过**
    ⇒ 「迁移里写 utf8mb4」与「库里是 utf8mb3」长期不一致

🔴 `sqlmigrate` 看起来完全正确，库里却不是那样 ——
这是「`IF NOT EXISTS` 让 DDL 正确性验证失效」的又一个实例。

⇒ **`0001` 不用改**（它本来就对），已有库靠本迁移补上。

## 为什么是 RunSQL

`TravelRecord` 是 `managed=False`（外部表）⇒ Django 不托管结构。

## 索引长度

本表索引建在 `parentnode` / `ttime` 等短列上；最长的文本列
（`tremark` varchar(255)、`district` varchar(100)）**没有索引**，
所以 utf8mb3 → utf8mb4 不触及索引字节上限。

## ⚠️ 这个迁移不能安全回滚

`reverse_sql` 退回 `utf8mb3`。若之后写进过 4 字节字符，回滚会**报错或截断**。
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('travel', '0008_db_comments'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE `travel_list_info` "
                "CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci",
            reverse_sql="ALTER TABLE `travel_list_info` "
                        "CONVERT TO CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci",
        ),
    ]
