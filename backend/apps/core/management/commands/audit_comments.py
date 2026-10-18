# -*- coding: utf-8 -*-
"""数据库注释审计 —— **只读**，不写任何东西。

## 为什么需要一个命令，而不是只有测试

`apps/core/test_db_comments.py` 守的是**模型层**（源头）：漏写、退回英文当场变红。
但有两件事模型层**看不见**：

1. **迁移到底跑了没有** —— `verbose_name` 写得再全也不会进库，
   只有 `migrate` 真的执行过，「打开 Navicat 看不懂」才解决。
2. **外部表（`managed=False`）** —— 派生通路对它们不存在（`documented_models()`
   就滤掉了），只能靠各 app 迁移里的 `RunSQL`。`hobby_dance_list` 的表注释
   就是这么漏掉的（2026-10-16 批 3 才发现）—— **没有任何测试会报它**。

所以这个命令补的正是「测试测不到的那一层」，用途有二：
- 交付后自检：跑 `migrate` 之后，缺口数应当**全部归零**；
- 以后新建表时的体检：加完 `managed` 表忘了写注释、或加了外部表忘了补 `RunSQL`，
  这里都会列出来。

## 🔴 只读

全程只有 `information_schema` 的 SELECT。**不改注释、不改表、不建表**。
「把注释写进库」这件事的唯一实现是迁移（`db_comments.py` 出判据，
`CoreConfig.ready()` 挂载，迁移里的 `AlterField(db_comment=…)` 落库）——
本命令**不是第二个写入口**，将来也不要把它改成写入口。

用法：
    python manage.py audit_comments          # 全量审计（退出码 1 = 存在缺口）
"""

import re

from django.apps import apps as django_apps
from django.core.management.base import BaseCommand
from django.db import connection

from apps.core.db_comments import DOCUMENTED_APPS

# 框架自带的 app：它们不是本项目的表，注释也不该由本项目负责。
SKIP_APPS = ('admin', 'auth', 'contenttypes', 'messages', 'sessions', 'staticfiles',
             'rest_framework', 'corsheaders')

CJK = re.compile(r'[\u4e00-\u9fff]')


class Command(BaseCommand):
    help = '【只读】审计数据库注释缺口：表注释 / 列注释 / 英文注释 / 外部表'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose', action='store_true',
            help='逐条列出缺口的完整清单（默认每种只显示前 10 条）',
        )

    def handle(self, *args, **options):
        verbose = options['verbose']
        limit = 10_000 if verbose else 10

        with connection.cursor() as cur:
            cur.execute(
                'SELECT TABLE_NAME, TABLE_COMMENT FROM information_schema.TABLES '
                'WHERE TABLE_SCHEMA = DATABASE()'
            )
            tbl_comment = {r[0]: (r[1] or '') for r in cur.fetchall()}
            cur.execute(
                'SELECT TABLE_NAME, COLUMN_NAME, COLUMN_COMMENT '
                'FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE()'
            )
            col_comment = {(t, c): (cm or '') for t, c, cm in cur.fetchall()}

        managed, external = [], []
        for cfg in django_apps.get_app_configs():
            if cfg.label in SKIP_APPS or cfg.label.startswith('django.'):
                continue
            for model in cfg.get_models():
                if model._meta.auto_created:
                    continue
                table = model._meta.db_table
                if table not in tbl_comment:
                    continue          # 库里还没有这张表（迁移未跑 / 纯外部数据源）
                item = (cfg.label, model, table)
                (managed if model._meta.managed else external).append(item)

        gaps = 0

        # ── 一、managed 表 ─────────────────────────────────
        no_tbl, no_col, non_cjk, half_pct = [], [], [], []
        for app, model, table in managed:
            tc = tbl_comment[table]
            if not tc.strip():
                no_tbl.append(f'{app}.{table}')
            elif not CJK.search(tc):
                non_cjk.append(f'表 {table}: {tc!r}')
            if '%' in tc:
                half_pct.append(f'表 {table}')
            for field in model._meta.concrete_fields:
                key = (table, field.column)
                if key not in col_comment:
                    continue          # 模型有、库里没有的列（迁移未跑）
                cc = col_comment[key]
                if not cc.strip():
                    no_col.append(f'{table}.{field.column}')
                elif not CJK.search(cc):
                    non_cjk.append(f'{table}.{field.column}: {cc!r}')
                if '%' in cc:
                    half_pct.append(f'{table}.{field.column}')

        self.stdout.write('=== 数据库注释审计（只读）===')
        self.stdout.write(f'接管白名单      : {len(DOCUMENTED_APPS)} 个 app')
        self.stdout.write(f'库中 managed 表 : {len(managed)} 张')
        self.stdout.write(f'库中外部表      : {len(external)} 张')
        self.stdout.write('')

        gaps += self._report('managed 表·表注释缺失', no_tbl, limit)
        gaps += self._report('managed 表·列注释缺失', no_col, limit)
        gaps += self._report('注释不含中文（英文残留）', non_cjk, limit)
        gaps += self._report('注释含半角 %（迁移会崩，机制会归一化成 ％）', half_pct, limit)

        # ── 二、外部表（managed=False）─────────────────────
        # 本机制**不派生**外部表，只能靠各 app 迁移里的 RunSQL。
        # ⚠️ 这里不把「外部表没有中文注释」算作缺口：历史遗留注释归别的年代所有，
        #    但「表注释为空」要列出来 —— 那是真的没人写过。
        ext_empty = [f'{app}.{table}' for app, model, table in external
                     if not tbl_comment[table].strip()]
        self.stdout.write(self.style.HTTP_INFO(
            '【外部表（managed=False）—— 本机制不派生，注释只能靠迁移里的 RunSQL】'
        ))
        self.stdout.write(f'  共 {len(external)} 张，其中表注释为空 {len(ext_empty)} 张')
        if ext_empty:
            for name in ext_empty[:limit]:
                self.stdout.write(f'    · {name}')
            if len(ext_empty) > limit:
                self.stdout.write(f'    …… 另有 {len(ext_empty) - limit} 张（用 --verbose 看全）')
        self.stdout.write('')

        # ── 三、还有哪些 app 没接管 ────────────────────────
        not_taken = sorted({
            app for app, model, table in managed
            if app not in DOCUMENTED_APPS
        })
        self.stdout.write(self.style.HTTP_INFO('【managed 表所在、但未接管的 app】'))
        if not_taken:
            self.stdout.write(f'  {len(not_taken)} 个：{not_taken}')
        else:
            self.stdout.write('  无（已收尾：所有 managed 表都在接管范围内）')
        gaps += len(not_taken)

        self.stdout.write('')
        if gaps:
            self.stdout.write(self.style.WARNING(
                f'⚠️ 共 {gaps} 处缺口。迁移没跑？先跑 migrate；'
                f'刚加的表缺注释？补 Meta.db_table_comment 后 makemigrations。'
            ))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS('✅ 无缺口：表注释、列注释、语言、外部表 全部就绪'))

    def _report(self, title, items, limit):
        """打一节结果；返回这节是否算缺口。"""
        if items:
            self.stdout.write(self.style.WARNING(f'【{title}】{len(items)} 处'))
            for text in items[:limit]:
                self.stdout.write(f'    · {text}')
            if len(items) > limit:
                self.stdout.write(f'    …… 另有 {len(items) - limit} 条（用 --verbose 看全）')
            self.stdout.write('')
            return len(items)
        self.stdout.write(self.style.SUCCESS(f'【{title}】0 ✅'))
        return 0
