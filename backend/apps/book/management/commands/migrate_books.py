from django.core.management.base import BaseCommand
from django.db import connections


class Command(BaseCommand):
    help = '从旧数据库 sycamore_db 迁移书籍数据到 book_read_list'

    def handle(self, *args, **options):
        old_db = 'old_db'
        new_db = 'default'

        if old_db not in connections.databases:
            self.stderr.write(f'错误: 数据库连接 "{old_db}" 未配置')
            return

        conn_old = connections[old_db]
        conn_new = connections[new_db]

        # 查询旧表数据
        with conn_old.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM o_bookread_info")
            total = cursor.fetchone()[0]
            self.stdout.write(f'旧表 o_bookread_info 共 {total} 条记录')

            cursor.execute("""
                SELECT bid, years, btitle, author, original_title, btype,
                       status, recommend, reading_depth, beginDate, updateDate,
                       closedop, abandon_reason, openop, tags
                FROM o_bookread_info
                ORDER BY bid
            """)
            rows = cursor.fetchall()

        # 清空新表（从头迁移）
        with conn_new.cursor() as cursor:
            cursor.execute("TRUNCATE TABLE book_read_list")

        # 逐行插入新表
        inserted = 0
        skipped = 0

        with conn_new.cursor() as cursor:
            for row in rows:
                (bid, years, btitle, author, original_title, btype,
                 status, recommend, reading_depth, begin_date, update_date,
                 closedop, abandon_reason, openop, tags) = row

                # 字段映射
                # 旧 beginDate → 新 readDate
                # 旧 updateDate → 新 createDate / updateDate
                # 旧表弃用字段（key_insights, finishDate 等）不迁移

                sql = """
                    INSERT INTO book_read_list
                        (bid, years, btitle, author, original_title, btype,
                         status, recommend, reading_depth, readDate, tags,
                         closedop, abandon_reason, openop,
                         createDate, updateDate, user_id)
                    VALUES (%s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s)
                """
                params = [
                    bid,
                    years,
                    btitle,
                    author,
                    original_title,
                    btype,
                    status,
                    recommend if recommend is not None else 0,
                    reading_depth if reading_depth is not None else 3,
                    begin_date.date() if begin_date else None,
                    tags,
                    closedop,
                    abandon_reason,
                    openop,
                    update_date.date() if update_date else None,   # createDate ← 旧 updateDate
                    update_date.date() if update_date else None,   # updateDate ← 旧 updateDate
                    None,          # user_id — 预留字段
                ]

                try:
                    cursor.execute(sql, params)
                    inserted += 1
                except Exception as e:
                    self.stderr.write(f'  插入失败 bid={bid}: {e}')
                    skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f'迁移完成：成功 {inserted} 条，跳过 {skipped} 条'
        ))

        # 验证
        with conn_new.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM book_read_list")
            new_count = cursor.fetchone()[0]
            self.stdout.write(f'新表 book_read_list 共 {new_count} 条记录')

        if new_count == total:
            self.stdout.write(self.style.SUCCESS('数量一致，迁移验证通过'))
        else:
            self.stderr.write(f'数量不一致：旧表 {total}，新表 {new_count}')
