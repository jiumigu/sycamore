from django.core.management.base import BaseCommand
from django.db import connections
from django.utils import timezone


class Command(BaseCommand):
    help = '从旧数据库 sycamore_db 迁移 oneday 数据到 temporal_oneday_page_list'

    def handle(self, *args, **options):
        old_db = 'old_db'
        new_db = 'default'

        # 确保旧数据库连接可用
        if old_db not in connections.databases:
            self.stderr.write(f'错误: 数据库连接 "{old_db}" 未配置')
            return

        conn_old = connections[old_db]
        conn_new = connections[new_db]

        # 查询旧表数据
        with conn_old.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM o_oneday_info")
            total = cursor.fetchone()[0]
            self.stdout.write(f'旧表 o_oneday_info 共 {total} 条记录')

            cursor.execute("""
                SELECT oid, years, oneday, page, total, title,
                       beginDate, otype, updateDate, is_sugar, remark
                FROM o_oneday_info
                ORDER BY oid
            """)
            rows = cursor.fetchall()

        # 清空新表（从头迁移）
        with conn_new.cursor() as cursor:
            cursor.execute("TRUNCATE TABLE temporal_oneday_page_list")

        # 逐行插入新表
        inserted = 0
        skipped = 0
        now = timezone.now()

        with conn_new.cursor() as cursor:
            for row in rows:
                (
                    oid, years, oneday, page, total, title,
                    begin_date, otype, update_date, is_sugar, remark,
                ) = row

                # 字段映射及默认值处理
                title = title or '无标题'

                # 标记：旧表 is_sugar 没有对应字段，丢弃
                # 新表 flag 保留为空

                sql = """
                    INSERT INTO temporal_oneday_page_list
                        (oid, years, oneday, page, total, title,
                         beginDate, otype, updateDate, flag, remark, user_id)
                    VALUES (%s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s)
                """
                params = [
                    oid,
                    years,
                    oneday,
                    page,
                    total,
                    title,
                    (begin_date.date() if begin_date else now.date()),
                    otype or 'ONEDAY',
                    (update_date.date() if update_date else now.date()),
                    None,   # flag — 无对应旧字段
                    remark,
                    None,   # user_id — 无对应旧字段
                ]

                try:
                    cursor.execute(sql, params)
                    inserted += 1
                except Exception as e:
                    self.stderr.write(f'  插入失败 oid={oid}: {e}')
                    skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f'迁移完成：成功 {inserted} 条，跳过 {skipped} 条'
        ))

        # 验证
        with conn_new.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM temporal_oneday_page_list")
            new_count = cursor.fetchone()[0]
            self.stdout.write(f'新表 temporal_oneday_page_list 共 {new_count} 条记录')

        if new_count == total:
            self.stdout.write(self.style.SUCCESS('✅ 数量一致，迁移验证通过'))
        else:
            self.stderr.write(f'⚠️  数量不一致：旧表 {total}，新表 {new_count}')
