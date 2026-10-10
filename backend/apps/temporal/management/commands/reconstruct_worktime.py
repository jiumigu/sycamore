"""把「月度加班台账」反推成「牛马工作」逐日时间记录（v3.60.8）

用法
----
    # 默认干跑（只读不写）：打印逐月核对表 + 前若干条样例
    python manage.py reconstruct_worktime /path/to/工作簿1.xlsx

    # 落库
    python manage.py reconstruct_worktime /path/to/工作簿1.xlsx --apply

    # 常用开关
    --task-name 牛马工作           目标 task_name（默认「牛马工作」）
    --batch overtime_recon_2020_2022   批次号（默认见 overtime_recon.BATCH_DEFAULT）
    --date-from / --date-to        只处理某区间（默认 2020-04-01 ~ 2022-12-31）
    --limit N                      只新增前 N 条（冒烟用）
    --report out.csv               明细 CSV（UTF-8 BOM，Excel 可直接打开）

⚠️ 这些记录是**推定值**，不是恢复值
------------------------------------
月度加班总量、上下班时间、请假记录都是真实的；**哪一天加班、加多久是按规则摊出来的**
（原始数据里没有这个信息）。生成规则见 `apps/temporal/overtime_recon.py` 模块头，是
**确定性**的（同样输入永远同样输出）。整批带批次号，可整批筛出、整批回滚：

    DELETE FROM temporal_time_atracker_tasks_list WHERE import_batch='overtime_recon_2020_2022';

工作流：先干跑 → 给用户看逐月核对表 → 确认 → `mysqldump` 备份 → `--apply` → 校验。
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.temporal.models import TemporalTask
from apps.temporal.overtime_recon import (
    BATCH_DEFAULT,
    KIND_LABEL,
    RANGE_END,
    RANGE_START,
    build_plan,
)
from apps.temporal.services import _ensure_task_meta, build_time_fields

DEFAULT_TASK_NAME = '牛马工作'

BRANCH_LABEL = {
    'overfull': '溢出去周末',
    'all_cand': '全候选日加班',
    'partial': '部分候选日加班',
}


class Command(BaseCommand):
    help = '把月度加班台账反推成「牛马工作」逐日记录（默认干跑，--apply 才写库）'

    def add_arguments(self, parser):
        parser.add_argument('path', help='台账 xlsx 路径（Sheet1 = YYYY-M → 加班小时）')
        parser.add_argument('--apply', action='store_true', help='真正写入数据库（默认只干跑）')
        parser.add_argument('--task-name', default=DEFAULT_TASK_NAME, help='目标 task_name')
        parser.add_argument('--batch', default=BATCH_DEFAULT, help='import_batch 批次号')
        parser.add_argument('--date-from', default=None, help='只处理 >= 该日期（YYYY-MM-DD）')
        parser.add_argument('--date-to', default=None, help='只处理 <= 该日期（YYYY-MM-DD）')
        parser.add_argument('--limit', type=int, default=0, help='只新增前 N 条（冒烟用，0=不限）')
        parser.add_argument('--report', default=None, help='明细 CSV 输出路径')

    # ── 主流程 ────────────────────────────────────────────────────────────
    def handle(self, *args, **opts):
        path, task_name, batch = opts['path'], opts['task_name'], opts['batch']
        d_from = (datetime.strptime(opts['date_from'], '%Y-%m-%d').date()
                  if opts['date_from'] else RANGE_START)
        d_to = (datetime.strptime(opts['date_to'], '%Y-%m-%d').date()
                if opts['date_to'] else RANGE_END)

        try:
            entries, stats = build_plan(path, d_from, d_to)
        except FileNotFoundError as e:
            raise CommandError(f'读不到文件：{e}')
        except AssertionError as e:
            raise CommandError(f'生成阶段断言失败（数据或规则有问题）：{e}')

        self.stdout.write(f'台账 {path}')
        self.stdout.write(f'  区间 {d_from} → {d_to}，覆盖 {len(stats)} 个月')
        self._print_stats(stats, entries)

        # ── 幂等：本批次已写入的起点时刻 ──
        # ⚠️ 判重**必须带 import_batch**：区间内可能本来就有别的来源的记录
        #    （如 worklog 导入的、ATracker 原始的），那不是「重复」，不能因此跳过。
        #    否则「当天已有记录 → 静默不生成」——数据看着正常、实际缺一段。
        lo = timezone.make_aware(datetime.combine(d_from, datetime.min.time()))
        hi = timezone.make_aware(datetime.combine(d_to + timedelta(days=1),
                                                  datetime.min.time()))
        existing = set(TemporalTask.objects
                       .filter(task_name=task_name, import_batch=batch,
                               start_time__gte=lo, start_time__lt=hi)
                       .values_list('start_time', flat=True))
        todo, skipped = [], 0
        for e in entries:
            st, _ = e.times()
            if timezone.make_aware(st) in existing:
                skipped += 1
            else:
                todo.append(e)

        self.stdout.write(f'\n目标 task_name「{task_name}」，批次号「{batch}」')
        self.stdout.write(f'  本批次已存在 {len(existing)} 条；本次将新增 {len(todo)} 条，'
                          f'跳过（已存在）{skipped} 条')
        if opts['limit']:
            todo = todo[:opts['limit']]
            self.stdout.write(f'  --limit 生效，实际只写前 {len(todo)} 条')

        self.stdout.write('\n--- 将新增（前 15 条）---')
        for e in todo[:15]:
            st, en = e.times()
            self.stdout.write(f'  {e.day} 周{"一二三四五六日"[e.day.weekday()]} '
                              f'{st:%H:%M}→{en:%H:%M} {e.hours:5.2f}h  {KIND_LABEL[e.kind]}')
        if len(todo) > 15:
            self.stdout.write(f'  …其余 {len(todo) - 15} 条见 --report 导出的 CSV')

        if opts['report']:
            self._write_report(opts['report'], todo)

        if not opts['apply']:
            self.stdout.write(self.style.WARNING(
                '\n[干跑] 未写入任何数据。确认无误后加 --apply 落库。'))
            return

        # ── 落库 ──
        with transaction.atomic():
            for e in todo:
                self._create_one(task_name, batch, e)
            _ensure_task_meta([task_name])

        self.stdout.write(self.style.SUCCESS(
            f'\n[已写入] 新增 {len(todo)} 条，跳过重复 {skipped} 条。'))
        self._verify(task_name, batch, len(todo) + skipped, skipped)

    # ── 落库与校验 ────────────────────────────────────────────────────────
    @staticmethod
    def _create_one(task_name: str, batch: str, e) -> None:
        st, en = e.times()
        st, en = timezone.make_aware(st), timezone.make_aware(en)
        TemporalTask.objects.create(
            task_name=task_name,
            task_description=e.description(),
            start_time=st,
            end_time=en,
            duration=None,                  # 与既有记录一致：留 NULL
            notes='',                       # 与既有记录一致：空串而非 NULL
            tags=None,
            task_type=task_name,
            import_batch=batch,
            **build_time_fields(st, en),    # duration_hours + 日历年月周季
        )

    def _verify(self, task_name: str, batch: str, expected: int, skipped: int) -> None:
        qs = TemporalTask.objects.filter(task_name=task_name, import_batch=batch)
        n = qs.count()
        rows = list(qs.values_list('start_time', 'end_time', 'duration_hours'))
        exact = sum((en - st).total_seconds() / 3600
                    for st, en, _dh in rows if st and en)
        dh = sum(r[2] or 0 for r in rows)
        null_cal = qs.filter(mon__isnull=True).count()
        n_ot = qs.filter(task_description__contains='加班').count()
        n_work = qs.filter(task_description__contains='正常上班').count()

        self.stdout.write('\n--- 落库校验 ---')
        self.stdout.write(f'  import_batch="{batch}" 记录数 = {n}'
                          f'{"  ✅" if n == expected else f"  ❌ 应为 {expected}"}')
        self.stdout.write(f'  精确工时合计 = {exact:,.2f}h ｜ 库内 duration_hours 累计 '
                          f'{dh:,.2f}h（差 {abs(exact - dh):.2f}h 为逐条保留 2 位的舍入）')
        self.stdout.write(f'  加班记录 {n_ot} 条 ｜ 正常上班 {n_work} 条')
        self.stdout.write(f'  日历字段缺失 = {null_cal} 条'
                          f'{"  ✅" if null_cal == 0 else "  ❌"}')
        self.stdout.write(f'  跳过重复 = {skipped} 条（幂等：重跑应显示全部跳过）')
        self.stdout.write(f"\n回滚：DELETE FROM temporal_time_atracker_tasks_list "
                          f"WHERE import_batch='{batch}';")

    # ── 输出 ──────────────────────────────────────────────────────────────
    def _print_stats(self, stats, entries) -> None:
        w = self.stdout.write
        w(f"\n{'月份':<9}{'工作日':>5}{'候选':>5}{'台账h':>8}{'加班日':>6}"
          f"{'周末':>5}{'日均':>8}{'生成h':>8}  核对  分支")
        w('-' * 78)
        for s in stats:
            w(f'{s.year}-{s.month:02d}  {s.workdays:5d}{s.candidates:5d}'
              f'{s.target_hours:8.1f}{s.ot_days:6d}{s.weekend_ot_days:5d}'
              f'{s.weekday_avg:7.2f}h{s.generated_hours:8.2f}'
              f'  {"✅" if s.ok else "❌"}  {BRANCH_LABEL[s.branch]}')
        w('-' * 78)

        from collections import Counter
        kinds = Counter(e.kind for e in entries)
        ot_h = sum(e.ot for e in entries) / 60
        # 工时用**精确值**求和（不逐条 round）——库内 duration_hours 逐条保留 2 位，
        # 累计后会有约 0.04h 的舍入差，两者要能分开看，别混成一个数。
        total_h = sum((e.times()[1] - e.times()[0]).total_seconds() / 3600
                      for e in entries)
        w(f'记录数 = {len(entries)} 条（' + '、'.join(
            f'{KIND_LABEL[k]} {v}' for k, v in kinds.most_common()) + '）')
        w(f'加班合计 = {ot_h:,.2f}h ｜ 含正常工时合计 = {total_h:,.2f}h')
        w(f'月度核对 = {sum(1 for s in stats if s.ok)}/{len(stats)} 个月通过')

    def _write_report(self, out_path, todo) -> None:
        with open(out_path, 'w', newline='', encoding='utf-8-sig') as f:
            wr = csv.writer(f)
            wr.writerow(['日期', '星期', '类型', '开始', '结束', '时长h', '加班h', '内容'])
            for e in todo:
                st, en = e.times()
                wr.writerow([e.day.isoformat(), '一二三四五六日'[e.day.weekday()],
                             KIND_LABEL[e.kind], st.strftime('%H:%M'), en.strftime('%H:%M'),
                             e.hours,
                             (e.ot / 60) if e.ot else 0, e.description()])
        self.stdout.write(f'明细已写入 {out_path}')
