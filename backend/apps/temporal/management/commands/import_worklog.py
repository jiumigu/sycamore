"""把工作日志 Excel 补记成「牛马工作」时间记录（v3.58.7）

用法
----
    # 默认干跑（只读，不写库）：打印将新增 / 将追加 / 待人工确认
    python manage.py import_worklog /path/to/工作记录.xlsx

    # 落库
    python manage.py import_worklog /path/to/工作记录.xlsx --apply

    # 常用开关
    --task-name 牛马工作     目标 task_name（默认「牛马工作」）
    --date-from / --date-to  只处理某区间
    --limit N                只处理前 N 条新增（冒烟用）
    --include-review         待人工确认的行也按兜底值写入（默认不写，只列清单）
    --report out.csv         把完整明细写成 CSV（UTF-8 BOM，Excel 可直接打开）

口径（用户 2026-09-18 拍板，详见 worklog_parser 模块头）
--------------------------------------------------------
- 工时两段：2023 ~ 2026-02-27 → 09:00–18:00；2026-03-02 起 → 08:00–17:45（**不扣午休**）。
- 加班日按「表内优先」把下班时间往后延；周末/法定节假日的加班直接用表内起止。
- **当天已有「牛马工作」记录 → 不新增，只把工作内容/备注追加到「任务说明」「附注」**。
- **规则 A（v3.58.8 / v3.58.9）**：当天只有**一段**碎片记录、且状态是工作日类时，
  把这条记录**补满当日标准工时窗口**：`开始 → min(原开始, 标准上班)`、
  `结束 → max(原结束, 标准下班)`。典型 `18:00→22:30` → `09:00→22:30`；
  `12:17→12:47` → `08:00→17:45`。已达标（两端都不缺）的记录**一律不动**，
  幂等就靠这个「达标判定」，不再看附注标记（否则第一次只补了开始的日子，
  第二次想补结束会被自己的标记挡住——**静默补不上**）。
  ⚠️ 会**改写已有记录的时间字段**（start_time / end_time / duration_hours / 日历字段），
  但**不动 `import_batch`** ——它保留原批次号，否则「按 `import_batch='worklog'` 回滚」
  会把原始 ATracker 记录一起删掉。
  ⚠️ 两条豁免：**非工作日**（周末/法定节假/调休，按表内实况记）与
  **备注明确写了「提前下班」的日子**（结束是实况不是记漏，见 `is_early_leave`）。
- **规则 B（v3.58.8）**：周末/法定节假/调休的加班若日志没给时段，按标准上下班窗口登记，不进待确认。
- 追加带 `[YYYY-MM-DD]` 标记：同一份日志重复导入不会重复追加（幂等）。
- 每条写入都带 `import_batch='worklog'`，日后可按它筛出来核对/回滚。

⚠️ 回滚注意：`DELETE ... WHERE import_batch='worklog'` **只回撤新增的记录**；
规则 A 改写过的原始记录（`import_batch` 仍是原批次）**删不掉、也回不到原来的开始时刻**——
只能从导入前的整表备份恢复。这就是为什么写前必备份。
"""
from __future__ import annotations

import csv
from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.temporal.models import TemporalTask
from apps.temporal.services import _ensure_task_meta, build_time_fields
from apps.temporal.worklog_parser import (
    WORKTIME_SWITCH,
    PlannedDay,
    build_plan,
    is_early_leave,
    is_offday,
    is_restday,
    read_worklog_rows,
    work_window,
)

DEFAULT_TASK_NAME = '牛马工作'
IMPORT_BATCH = 'worklog'
# 标准工时的两段（午休不计工时；2026-03-02 起下午不变、上午提前到 11:45）
NOON_OLD = time(12, 0)
NOON_NEW = time(11, 45)
AFTERNOON_START = time(13, 30)
MIN_GAP_MINUTES = 15        # 太短的碎片不补，避免造无意义记录


def _marker(day) -> str:
    return f'[{day.isoformat()}]'


def _extend_marker(day) -> str:
    """规则 A 的幂等标记（与「已导过跳过」用的 `[日期]` 分开，两者会同时出现在附注里）"""
    return f'[{day.isoformat()}] 时段补全'


def _append_text(old: str | None, block: str) -> str:
    old = (old or '').strip()
    return f'{old}\n{block}' if old else block


def _minutes(a: time, b: time) -> int:
    """同日内 a → b 的分钟数"""
    return (b.hour * 60 + b.minute) - (a.hour * 60 + a.minute)


class Command(BaseCommand):
    help = '把工作日志 Excel 补记成「牛马工作」时间记录（默认干跑，--apply 才写库）'

    def add_arguments(self, parser):
        parser.add_argument('path', help='工作日志 xlsx 路径')
        parser.add_argument('--apply', action='store_true', help='真正写入数据库（默认只干跑）')
        parser.add_argument('--task-name', default=DEFAULT_TASK_NAME, help='目标 task_name')
        parser.add_argument('--date-from', default=None, help='只处理 >= 该日期（YYYY-MM-DD）')
        parser.add_argument('--date-to', default=None, help='只处理 <= 该日期（YYYY-MM-DD）')
        parser.add_argument('--limit', type=int, default=0, help='只新增前 N 条（冒烟用，0=不限）')
        parser.add_argument('--include-review', action='store_true',
                            help='待人工确认的行也按兜底值写入（默认不写）')
        parser.add_argument('--fill-gaps', action='store_true',
                            help='「多段/已覆盖日」若没盖满标准工时，补一条缺口记录 '
                                 '（单段碎片日由规则 A 直接回补开始时刻，与此开关无关；默认关）')
        parser.add_argument('--report', default=None, help='明细 CSV 输出路径')

    # ── 主流程 ────────────────────────────────────────────────────────────
    def handle(self, *args, **opts):
        path = opts['path']
        task_name = opts['task_name']
        apply = opts['apply']

        try:
            rows = read_worklog_rows(path)
        except FileNotFoundError as e:
            raise CommandError(f'读不到文件：{e}')
        if not rows:
            raise CommandError('没解析到任何日志行——检查 sheet 名是否含「每日记录」')

        # 日期区间过滤
        d_from = datetime.strptime(opts['date_from'], '%Y-%m-%d').date() if opts['date_from'] else None
        d_to = datetime.strptime(opts['date_to'], '%Y-%m-%d').date() if opts['date_to'] else None
        if d_from or d_to:
            rows = [r for r in rows
                    if (d_from is None or r.day >= d_from) and (d_to is None or r.day <= d_to)]

        plan = build_plan(rows)
        included = [p for p in plan if p.action == 'include']
        skipped = [p for p in plan if p.action == 'skip']

        self.stdout.write(f'解析 {path}')
        self.stdout.write(f'  sheet 数 {len({r.sheet for r in rows})}，日志行 {len(rows)}，'
                          f'覆盖 {rows[0].day} → {rows[-1].day}')
        self.stdout.write(f'  纳入 {len(included)} 天，跳过 {len(skipped)} 天（请假/放假类）')

        # ── 判定「新增」还是「追加」，可选补缺口 ──
        creates: list[PlannedDay] = []
        appends: list[tuple[PlannedDay, TemporalTask]] = []
        extends: list[tuple[PlannedDay, TemporalTask, time, time]] = []   # (计划, 记录, 原开始, 新开始)
        gaps: list[tuple[PlannedDay, time, time]] = []
        already: list[PlannedDay] = []
        reviews: list[PlannedDay] = []

        for p in included:
            existing = self._existing_list(task_name, p.day)
            if not existing:
                if p.needs_review and not opts['include_review']:
                    reviews.append(p)
                else:
                    creates.append(p)
                continue
            target = existing[0]

            # 规则 A：单段碎片 + 工作日状态 → 补满标准工时窗口（两端）。
            # 放在「已导过跳过」**之前**判：那 95 天早就带 `[日期]` 标记了，
            # 若放到后面判，第二次跑就永远补不上（「已导过」与「补全」是两回事）。
            # 幂等靠 _extend_for 内部的**达标判定**（两端都不缺 → None），
            # 因此上次只补了开始、这次要补结束的日子仍会被放行。
            span = self._extend_for(p, existing)
            if span is not None:
                new_start, new_end = span
                extends.append((p, target, target.start_time.time(),
                                target.end_time.time(), new_start, new_end))

            if self._already_imported(target, p.day):
                already.append(p)          # 幂等：这份日志的这一天早导过了
                continue
            appends.append((p, target))
            # 已有记录往往只是当天的碎片（ATracker 那半段/加班那段）——
            # 标准工时没被覆盖的部分可以补成独立记录，否则这天工时就不全。
            # ⚠️ 规则 A 已经改写过时间的日子直接跳过，否则会与补全**重复计时**。
            if opts['fill_gaps'] and span is None and not is_offday(p.status):
                for a, b in self._gaps_for(p.day, existing):
                    gaps.append((p, a, b))

        if opts['limit']:
            creates = creates[:opts['limit']]

        self._print_plan(creates, appends, extends, gaps, already, reviews, skipped)

        if opts['report']:
            self._write_report(opts['report'], creates, appends, extends, gaps, reviews)

        if not apply:
            self.stdout.write(self.style.WARNING(
                '\n[干跑] 未写入任何数据。确认无误后加 --apply 落库。'))
            return

        # ── 落库 ──
        from django.db import transaction
        created = appended = extended = filled = 0
        with transaction.atomic():
            for p in creates:
                self._create_one(task_name, p)
                created += 1
            for p, obj in appends:
                self._append_one(obj, p)
                appended += 1
            # 补全排在追加之后：附注里的顺序才是「原备注 → 日志备注 → 时段补全」
            for p, obj, _os, _oe, new_start, new_end in extends:
                self._extend_one(obj, p, new_start, new_end)
                extended += 1
            for p, a, b in gaps:
                self._create_gap(task_name, p, a, b)
                filled += 1
            _ensure_task_meta([task_name])

        self.stdout.write(self.style.SUCCESS(
            f'\n[已写入] 新增 {created} 条，追加 {appended} 条，补全时段 {extended} 条，'
            f'补缺口 {filled} 条（跳过重复 {len(already)}，待确认未写 {len(reviews)}）'))
        if reviews:
            self.stdout.write('待人工确认的行未写入，确认后可用 --include-review 或手工补。')
        self.stdout.write('回滚新增：这些记录的 import_batch = "%s"' % IMPORT_BATCH)
        if extended:
            self.stdout.write(self.style.WARNING(
                f'⚠️ 其中 {extended} 条是**改写已有记录的起止时刻**（import_batch 未变、'
                f'DELETE 回滚删不掉）——要恢复原时刻只能从导入前的整表备份还原。'))

    # ── DB 读写细节 ───────────────────────────────────────────────────────
    @staticmethod
    def _existing_list(task_name: str, day) -> list[TemporalTask]:
        """当天（本地日 00:00–24:00）已有的该 task_name 记录，按开始时刻升序"""
        start = timezone.make_aware(datetime.combine(day, datetime.min.time()))
        end = start + timedelta(days=1)
        return list(TemporalTask.objects
                    .filter(task_name=task_name, start_time__gte=start, start_time__lt=end)
                    .order_by('start_time'))

    @staticmethod
    def _gaps_for(day, existing: list[TemporalTask]) -> list[tuple[time, time]]:
        """标准工时里没被已有记录覆盖的时段。

        实测（2026-09-18）：ATracker 里的「牛马工作」记录**很多是碎片**——只有下午那段
        （13:30→18:12）或只有加班那段（18:00→22:30）。若严格按「有记录就不新增」，
        这些天的上午/全天工时会静默丢失（95 天里 75 天如此，约 225h）。
        """
        std_start, std_end = work_window(day)
        noon = NOON_NEW if day >= WORKTIME_SWITCH else NOON_OLD
        segments = [(std_start, noon), (AFTERNOON_START, std_end)]
        covered = [(t.start_time.time(), t.end_time.time())
                   for t in existing if t.start_time and t.end_time]
        # 当天对标准工时毫无覆盖（例如只记了 18:00 之后的加班段）
        # → 按「一条 09:00–18:00」补，与其余日子的单条口径保持一致
        if not any(ca < std_end and cb > std_start for ca, cb in covered):
            return [(std_start, std_end)]
        out: list[tuple[time, time]] = []
        for a, b in segments:
            cur = a
            for ca, cb in sorted(covered):
                if cb <= cur or ca >= b:
                    continue
                if ca > cur:
                    out.append((cur, min(ca, b)))
                cur = max(cur, cb)
                if cur >= b:
                    break
            if cur < b:
                out.append((cur, b))
        return [(a, b) for a, b in out if _minutes(a, b) >= MIN_GAP_MINUTES]

    @staticmethod
    def _already_imported(obj: TemporalTask, day) -> bool:
        """幂等键：该日的 `[YYYY-MM-DD]` 标记是否已落在说明或附注里"""
        mk = _marker(day)
        return mk in (obj.task_description or '') or mk in (obj.notes or '')

    # ── 规则 A：单段碎片补满标准工时窗口 ──────────────────────────────────
    @staticmethod
    def _extend_for(p: PlannedDay, existing: list[TemporalTask]) -> tuple[time, time] | None:
        """当天只有一段「牛马工作」记录时，算出「补满标准工时窗口」后的起止。

        → 需要补则返回 `(新开始, 新结束)`；**已达标或不该补则返回 None**。

        区间口径：`开始 = min(原开始, 标准上班)`、`结束 = max(原结束, 标准下班)`——
        所以「只缺开始」（典型 `18:00→22:30` 的加班段）补成 `09:00→22:30`，
        「只缺结束」（典型午间碎片 `12:17→12:47`）补成 `08:00→17:45`，
        两端都缺就两端都补。**已达标的日子原样不动**，这就是本规则的幂等键。

        三处豁免：
        - 当天不是单段（多段的形态各异，交给 `--fill-gaps` 那条路）；
        - **非工作日**状态（周末 / 法定节假 / 调休）——本来就按表内实况记，不往标准窗口拉
          （用户 2026-09-18 拍板）；
        - 备注**明确写了提前下班**（`is_early_leave`）——结束早于标准下班是实况，
          补满等于篡改真实记录（用户 2026-09-18 二次拍板，样板 2025-01-25）。
        """
        if len(existing) != 1 or is_restday(p.status) or is_early_leave(p.note):
            return None
        obj = existing[0]
        if obj.start_time is None or obj.end_time is None:
            return None
        std_start, std_end = work_window(p.day)
        cur = (obj.start_time.time(), obj.end_time.time())
        target = (min(cur[0], std_start), max(cur[1], std_end))
        return target if target != cur else None

    def _extend_one(self, obj: TemporalTask, p: PlannedDay,
                    new_start: time, new_end: time):
        """把已有记录补满标准工时窗口，并重算时长与日历字段。

        ⚠️ **不写 `import_batch`** —— 保留原批次号，否则
        `DELETE ... WHERE import_batch='worklog'` 会把这条 ATracker 原始记录一起删掉。
        ⚠️ 附注要**重新读一次**再追加：紧接着的 `_append_one` 可能刚改过 notes，
        用循环里那份旧值会把它覆盖掉。
        ⚠️ 补全说明是**追加**而不是替换旧行：第一次「只补开始」留下的
        `[日期] 时段补全：…` 那一行保留着原始时刻（如 `原 12:17–12:47`），
        删掉它就把最早的原值弄丢了——留痕比整洁重要。
        """
        old_start, old_end = obj.start_time, obj.end_time
        # ⚠️ 先 make_aware 再算：`build_time_fields` 要相减，naive 与 aware 混用会 TypeError
        #    （`obj.end_time` 从库里读出来是 aware）
        new_start_dt = timezone.make_aware(datetime.combine(p.day, new_start))
        new_end_dt = timezone.make_aware(datetime.combine(p.day, new_end))
        fields = build_time_fields(new_start_dt, new_end_dt)   # duration_hours + 日历年月周季
        block = (f'{_extend_marker(p.day)}：{new_start:%H:%M}–{new_end:%H:%M}'
                 f'（原 {old_start:%H:%M}–{old_end:%H:%M}，按工作日志补全）')
        fresh_notes = (TemporalTask.objects
                       .filter(id=obj.id).values_list('notes', flat=True).first())
        TemporalTask.objects.filter(id=obj.id).update(
            start_time=new_start_dt,
            end_time=new_end_dt,
            duration_hours=fields['duration_hours'],
            year=fields['year'], mon=fields['mon'], day=fields['day'],
            week=fields['week'], quarter=fields['quarter'],
            notes=_append_text(fresh_notes, block),
            updated_at=timezone.now(),
        )

    def _create_one(self, task_name: str, p: PlannedDay):
        mk = _marker(p.day)
        fields = build_time_fields(p.start, p.end)      # 含 duration_hours + 日历年月周季
        TemporalTask.objects.create(
            task_name=task_name,
            task_description=f'{mk} {p.content}'.strip(),
            start_time=timezone.make_aware(p.start),
            end_time=timezone.make_aware(p.end),
            notes=f'{mk} {p.note}'.strip() if p.note else '',
            tags=None,
            task_type=task_name,
            import_batch=IMPORT_BATCH,
            **fields,
        )

    def _create_gap(self, task_name: str, p: PlannedDay, a: time, b: time):
        """补缺口记录：只补时间，不带工作内容（内容已追加到当天最早的已有记录上）"""
        start = datetime.combine(p.day, a)
        end = datetime.combine(p.day, b)
        fields = build_time_fields(start, end)
        TemporalTask.objects.create(
            task_name=task_name,
            task_description=f'{_marker(p.day)} 工作日志补记（{a:%H:%M}–{b:%H:%M}）',
            start_time=timezone.make_aware(start),
            end_time=timezone.make_aware(end),
            notes='', tags=None, task_type=task_name, import_batch=IMPORT_BATCH,
            **fields,
        )

    def _append_one(self, obj: TemporalTask, p: PlannedDay):
        mk = _marker(p.day)
        desc = _append_text(obj.task_description, f'{mk} {p.content}'.strip())
        notes = obj.notes or ''
        if p.note:
            notes = _append_text(notes, f'{mk} {p.note}'.strip())
        TemporalTask.objects.filter(id=obj.id).update(
            task_description=desc, notes=notes, updated_at=timezone.now())

    # ── 输出 ──────────────────────────────────────────────────────────────
    def _print_plan(self, creates, appends, extends, gaps, already, reviews, skipped):
        w = self.stdout.write
        w(self.style.MIGRATE_HEADING(
            f'\n将新增 {len(creates)} 条 ｜ 将追加 {len(appends)} 条 ｜ '
            f'将补全时段 {len(extends)} 条 ｜ 将补缺口 {len(gaps)} 条 ｜ '
            f'已导过跳过 {len(already)} 条 ｜ 待人工确认 {len(reviews)} 条'))

        if creates:
            w('\n--- 将新增（前 15 条）---')
            for p in creates[:15]:
                w(f'  {p.day} {p.start.strftime("%H:%M")}→{p.end.strftime("%H:%M")} '
                  f'{p.duration_hours:5.2f}h  [{p.status}] {p.overtime_source}')
            if len(creates) > 15:
                w(f'  …其余 {len(creates) - 15} 条见 --report 导出的 CSV')

        if extends:
            w(self.style.WARNING(
                f'\n--- 将补全时段（把单段碎片补满标准工时窗口；前 15 条）---'))
            for p, obj, old_start, old_end, new_start, new_end in extends[:15]:
                oh = _minutes(old_start, old_end) / 60 if old_end > old_start else 0.0
                nh = _minutes(new_start, new_end) / 60
                w(f'  {p.day} [{p.status}] {old_start:%H:%M}→{old_end:%H:%M}  ⇒  '
                  f'{new_start:%H:%M}→{new_end:%H:%M}  '
                  f'（{oh:.2f}h → {nh:.2f}h）  记录 #{obj.id}')
            if len(extends) > 15:
                w(f'  …其余 {len(extends) - 15} 条见 --report 导出的 CSV')

        if appends:
            w('\n--- 将追加文本（不新增记录、不动时间；前 15 条）---')
            for p, obj in appends[:15]:
                w(f'  {p.day} → 已有记录 #{obj.id}（{obj.start_time:%H:%M} 起）')
            if len(appends) > 15:
                w(f'  …其余 {len(appends) - 15} 条见 --report 导出的 CSV')

        if gaps:
            w('\n--- 将补缺口（已有记录没覆盖标准工时的那段；前 15 条）---')
            for p, a, b in gaps[:15]:
                w(f'  {p.day} {a:%H:%M}–{b:%H:%M}（{_minutes(a, b) / 60:.2f}h）')
            if len(gaps) > 15:
                w(f'  …其余 {len(gaps) - 15} 条见 --report 导出的 CSV')

        if reviews:
            w(self.style.WARNING('\n--- 待人工确认（默认不写入）---'))
            for p in reviews:
                w(f'  {p.day} [{p.status}] {p.start.strftime("%H:%M")}→'
                  f'{p.end.strftime("%H:%M")} {p.duration_hours}h :: {p.review_reason}')
                w(f'        备注/时长原文：{(p.note or "（空）")[:70]}')

        if skipped:
            from collections import Counter
            w(f'\n跳过 {len(skipped)} 天：' + '，'.join(
                f'{k} {v}' for k, v in Counter(p.skip_reason for p in skipped).most_common()))

    def _write_report(self, out_path, creates, appends, extends, gaps, reviews):
        with open(out_path, 'w', newline='', encoding='utf-8-sig') as f:
            wr = csv.writer(f)
            wr.writerow(['动作', '日期', '状态', '开始', '结束', '时长h',
                         '加班来源', '待确认原因', '工作内容', '备注', '来源行'])
            for p in creates:
                wr.writerow(['新增', p.day, p.status, p.start.strftime('%H:%M'),
                             p.end.strftime('%H:%M'), p.duration_hours,
                             p.overtime_source, p.review_reason, p.content, p.note, p.source])
            for p, obj, old_start, old_end, new_start, new_end in extends:
                wr.writerow(['补全时段', p.day, p.status, f'{new_start:%H:%M}',
                             f'{new_end:%H:%M}', round(_minutes(new_start, new_end) / 60, 2),
                             f'原 {old_start:%H:%M}→{old_end:%H:%M}，记录 #{obj.id}',
                             '', p.content, p.note, p.source])
            for p, _obj in appends:
                wr.writerow(['追加', p.day, p.status, p.start.strftime('%H:%M'),
                             p.end.strftime('%H:%M'), p.duration_hours,
                             p.overtime_source, p.review_reason, p.content, p.note, p.source])
            for p, a, b in gaps:
                wr.writerow(['补缺口', p.day, p.status, f'{a:%H:%M}', f'{b:%H:%M}',
                             round(_minutes(a, b) / 60, 2), '已有记录未覆盖标准工时',
                             '', p.content, p.note, p.source])
            for p in reviews:
                wr.writerow(['待确认', p.day, p.status, p.start.strftime('%H:%M'),
                             p.end.strftime('%H:%M'), p.duration_hours,
                             p.overtime_source, p.review_reason, p.content, p.note, p.source])
        self.stdout.write(f'明细已写入 {out_path}')
