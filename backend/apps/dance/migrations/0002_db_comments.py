# -*- coding: utf-8 -*-
"""给 `hobby_dance_list` 补表注释（批 3 收尾）。

## 为什么只有表注释、而且是手写的迁移

`DanceRecord` 是 `managed=False`（外部表）⇒ `documented_models()` 直接滤掉它，
**派生的通路对它根本不存在**；autodetector 当然也不会为一个它不托管的表
生成 `AlterModelTableComment`。所以只能手写这条 `RunSQL`。

列注释**不用补** —— `0001_initial` 里那张 `CREATE TABLE` 已经逐列写全了
（那是当年建表时一次性手工写的），库里的列注释是齐的。

## ⚠️ 只改表注释，不动列定义

外部表的列注释要改就得 `MODIFY COLUMN` 并带**完整列定义**，
而 Django 不托管这张表的结构（连字符集都不是本项目的锅：
建表用的是 `utf8mb3`，见 `0001_initial`）——
动列定义的风险远大于收益，故有意留在现状。

（外部表清单与处置口径见 `apps/core/README.md`。）
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dance', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                "ALTER TABLE `hobby_dance_list` COMMENT = "
                "'舞蹈学习记录（外部表：Django 不托管结构、不加列；year / month / quarter / weekinfo 由 save() 从学习日期派生）'",
            ],
            reverse_sql=[
                "ALTER TABLE `hobby_dance_list` COMMENT = ''",
            ],
        ),
    ]
