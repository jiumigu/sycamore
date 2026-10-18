"""⚠️ 已被 `apps/core/db_comments.py` 取代 —— 保留仅作应急手工入口。

## 取代关系（v3.62.20）

「把 `verbose_name` 变成 MySQL 列注释」这件事，现在有**唯一实现**：
`apps/core/db_comments.py` 负责判据，`CoreConfig.ready()` 负责挂载，
迁移里的 `AlterField(db_comment=...)` 负责落库。

**新机制是本命令的超集**，且多了三件本命令给不了的东西：

| | 本命令 | 新机制 |
|---|---|---|
| 表注释 | ❌ 完全不涉及 | ✅ `Meta.db_table_comment` |
| 例外文案 | ❌ 只能等于 verbose_name | ✅ `COLUMN_COMMENT_OVERRIDES` |
| 可复现 | ❌ 手工执行、结果不可追溯 | ✅ 进迁移、可 review、可回滚 |

## 🔴 本命令现存的三处风险（动手前先看）

1. **会覆盖外部表里「更好」的注释**。它不区分 `managed=False`，而外部表是当年
   从旧系统导进来的、注释本就齐全且**比 verbose_name 好**。典型：
   `wealth_bill_list.created_at` 库里是 `'创建时间'`，而模型的 `verbose_name`
   是 `inspectdb` 自动生成的 `'created at'` —— 跑一遍就是把注释**改差**。
   （2026-10-16 实测：这类「库里比模型好」的列有 15 个。）
   已在此加护栏：**跳过 `managed=False` 的模型**。
2. **连 Django 内置表一起改**（`auth_user` / `django_admin_log` …）。框架表不该由
   本项目改注释，何况它们的 `verbose_name` 多为英文。
3. **注释转义顺序有 bug**：`replace("'", "\\'").replace('\\', '\\\\')` —— 先把引号
   变成 `\'`，再把其中的 `\\` 变成 `\\\\`，于是 `\'` 被二次转义成 `\\'`。
   旧数据集里没有带引号的 verbose_name 才一直没炸。**新机制不走字符串拼接**
   （`db_comment` 由 Django 自己参数化），没有这个问题。

## 处置

- 本项目**不再建议使用**本命令；需要同步注释请走新机制的迁移。
- 是否删除本文件属**用户决策**（本项目铁律：删入口由用户定，AI 只给结论）。
"""

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = '【已取代】将 Django Model 的 verbose_name 同步到 MySQL 字段注释'

    def handle(self, *args, **options):
        # 不静默：跑之前把「你正在用一个被取代的工具」和它的边界说清楚
        self.stdout.write(self.style.WARNING(
            '⚠️ 本命令已被 apps/core/db_comments.py 取代（v3.62.20）。\n'
            '   它不会写表注释，也不能表达例外文案；同步注释请改用新机制的迁移。\n'
            '   本次仍会执行，但已跳过 managed=False 的模型（保护外部表的既有注释）。'
        ))

        all_models = apps.get_models()
        total = 0
        skipped = 0
        skipped_unmanaged = 0

        with connection.cursor() as cursor:
            for model in all_models:
                # 🔴 外部表（managed=False）跳过：它们的注释是从旧系统导进来的，
                #    往往比模型的 verbose_name 更准确，覆盖 = 把注释改差。
                if not model._meta.managed:
                    skipped_unmanaged += 1
                    continue

                table = model._meta.db_table

                cursor.execute(f"SHOW TABLES LIKE '{table}'")
                if not cursor.fetchone():
                    continue

                for field in model._meta.fields:
                    col = field.column
                    verbose = (field.verbose_name or '').strip()
                    if not verbose:
                        continue

                    cursor.execute(f"SHOW COLUMNS FROM `{table}` LIKE '{col}'")
                    row = cursor.fetchone()
                    if not row:
                        continue

                    col_type = row[1]

                    # 构建 ALTER — 只改 COMMENT，保留原始列定义
                    parts = [f"ALTER TABLE `{table}` MODIFY COLUMN `{col}` {col_type}"]

                    # Null 约束
                    parts.append('NOT NULL' if row[2] == 'NO' else 'NULL')

                    # 默认值 — JSON 列不允许显式 DEFAULT
                    is_json = 'json' in col_type.lower()
                    if not is_json:
                        default = row[4]
                        if default is not None:
                            if default == 'CURRENT_TIMESTAMP' or (isinstance(default, str) and default.upper().startswith('CURRENT_TIMESTAMP')):
                                parts.append(f'DEFAULT {default}')
                            elif isinstance(default, str) and default.startswith('_utf8mb4'):
                                pass  # MySQL 内部表达式默认值
                            else:
                                parts.append(f"DEFAULT '{default}'")

                    # Extra（如 auto_increment, on update）
                    extra = row[5] if len(row) > 5 else ''
                    if extra:
                        # 过滤掉 MySQL 内部标记 DEFAULT_GENERATED，其默认值已在前一步跳过
                        cleaned = ' '.join(
                            p for p in extra.split() if p != 'DEFAULT_GENERATED'
                        )
                        if cleaned:
                            parts.append(cleaned)

                    # ⚠️ 转义顺序有 bug（见模块 docstring 第 3 条），新机制不依赖它
                    safe_comment = verbose.replace("'", "\\'").replace('\\', '\\\\')
                    parts.append(f"COMMENT '{safe_comment}'")

                    sql = ' '.join(parts)
                    try:
                        cursor.execute(sql)
                        total += 1
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'跳过 {table}.{col}: {e}'))
                        skipped += 1

        self.stdout.write(self.style.SUCCESS(f'完成：同步 {total} 个字段注释'))
        if skipped:
            self.stdout.write(self.style.WARNING(f'跳过 {skipped} 个字段'))
        if skipped_unmanaged:
            self.stdout.write(self.style.WARNING(
                f'跳过 {skipped_unmanaged} 个 managed=False 模型（保护外部表既有注释）'
            ))
