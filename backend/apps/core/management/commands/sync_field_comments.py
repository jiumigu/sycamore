from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import connection


class Command(BaseCommand):
    help = '将 Django Model 的 verbose_name 同步到 MySQL 字段注释'

    def handle(self, *args, **options):
        all_models = apps.get_models()
        total = 0
        skipped = 0

        with connection.cursor() as cursor:
            for model in all_models:
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

                    # 转义注释中的特殊字符
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
