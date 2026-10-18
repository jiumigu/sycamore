"""一致性报告：常量表（种子） vs 数据库 `temporal_task_meta`（真源）

背景（v3.60.37，2026-10-12）：
`TASK_TO_L2` / `TASK_CATEGORY_MAPPING` 是**初始种子**，**只在「库里还没有该 task_name」
时生效**（`_ensure_task_meta` 建档、`migrate_temporal_categories` 回填），建完即永久退出运算。
真源是 `temporal_task_meta` —— 贡献图 / 时间统计 / 台账全部读库里的值。

⇒ 两边**可以合法地不一致**，但这不一致必须**看得见**。三类差异对应三种不同动作：

| 类 | 症状 | 该做什么 |
|---|---|---|
| **A 僵尸** | 常量表里的任务名库里没有 | 表过期 ⇒ 从常量表删掉 |
| **B 漂移** | 两边都有、值不同 | 要么库被手工改过、要么常量改完没同步 ⇒ **人看**，判哪个对 |
| **C 未收录** | 库里有、常量表没有 | 将来重建库会按「未归类」建档 ⇒ 补录进常量表 |

⚠️ 本命令**只读**：不写库、不改常量。用途是「改常量表 / 改映射之前先看一眼」。

🔴 判据备忘：`检查通过` **不等于**「两边相等」—— 它是「三类差异都为空」。
在种子/真源定位下，**允许**人工决定某一条长期不相等（命令只负责摆出来）。

Usage:
    python manage.py check_meta_consistency
    python manage.py check_meta_consistency --json
    python manage.py check_meta_consistency --strict   # 有任何差异则退出码 1
"""

import json
import sys

from django.core.management.base import BaseCommand
from django.db.models import Count, Sum

from apps.temporal.constants import (
    ACTIVITY_TYPE_PRESETS,
    ATTRIBUTION_CHOICES_LIST,
    TASK_CATEGORY_MAPPING,
    TASK_TO_L2,
)
from apps.temporal.models import TaskMeta, TemporalTask


class Command(BaseCommand):
    help = '只读报告「常量表种子 vs 库真源」的三类差异（A 僵尸 / B 漂移 / C 未收录）'

    def add_arguments(self, parser):
        parser.add_argument('--json', action='store_true', help='以 JSON 输出（便于脚本消费）')
        parser.add_argument('--strict', action='store_true',
                            help='存在任何差异时以退出码 1 结束（便于挂进 CI / 提交前钩子）')

    def handle(self, *args, **options):
        payload = self._collect()
        if options['json']:
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            self._render(payload)

        if options['strict'] and not payload['ok']:
            sys.exit(1)

    # ──────────────────────────────────────────────────────────

    def _collect(self) -> dict:
        # 用量：每个 task_name 的条数与时长 —— 差异的**影响面**靠它说话
        usage = {}
        for row in (TemporalTask.objects.order_by()
                    .values('task_name')
                    .annotate(n=Count('id'), h=Sum('duration_hours'))):
            usage[row['task_name']] = (row['n'], round(float(row['h'] or 0), 2))

        db = {m.task_name: m for m in TaskMeta.objects.all()}
        valid_l2 = {p[0] for p in ACTIVITY_TYPE_PRESETS}
        valid_l1 = set(ATTRIBUTION_CHOICES_LIST)

        # ── A 僵尸：常量表有、库里没有 ──
        zombie = sorted(tn for tn in TASK_TO_L2 if tn not in db)

        # ── B 漂移：两边都有、值不同 ──
        drift = []
        for tn, (at, attr) in TASK_TO_L2.items():
            m = db.get(tn)
            if m is None:
                continue
            if (m.activity_type, m.default_attribution) != (at, attr):
                n, h = usage.get(tn, (0, 0.0))
                drift.append({
                    'task_name': tn,
                    'seed': [at, attr],
                    'db': [m.activity_type, m.default_attribution],
                    'is_system': bool(m.is_system),
                    'records': n,
                    'hours': h,
                })
        drift.sort(key=lambda d: -d['hours'])   # 影响大的排前面

        # ── C 未收录：库里有、常量表没有 ──
        missing = []
        for tn, m in db.items():
            if tn in TASK_TO_L2:
                continue
            n, h = usage.get(tn, (0, 0.0))
            missing.append({
                'task_name': tn,
                'db': [m.activity_type, m.default_attribution],
                'is_system': bool(m.is_system),
                'records': n,
                'hours': h,
                'via_legacy': tn in TASK_CATEGORY_MAPPING,   # 靠旧四分类表兜住的
            })
        missing.sort(key=lambda d: -d['hours'])

        # ── 值域越界 ──
        invalid = [{
            'task_name': m.task_name,
            'activity_type': m.activity_type,
            'default_attribution': m.default_attribution,
        } for m in db.values()
            if m.activity_type not in valid_l2
            or (m.default_attribution is not None
                and m.default_attribution not in valid_l1)]

        # ── 未归类桶 ──
        unclassified = sorted(
            (tn for tn, m in db.items()
             if m.activity_type == '未归类' or m.default_attribution is None),
            key=lambda tn: -usage.get(tn, (0, 0.0))[1],
        )

        ok = not (zombie or drift or missing or invalid or unclassified)
        return {
            'ok': ok,
            'seed_count': len(TASK_TO_L2),
            'db_count': len(db),
            'zombie': zombie,
            'drift': drift,
            'missing': missing,
            'invalid': invalid,
            'unclassified': unclassified,
        }

    # ──────────────────────────────────────────────────────────

    def _render(self, p: dict) -> None:
        w = self.stdout.write
        w(f'常量表种子 {p["seed_count"]} 条  ｜  库真源(temporal_task_meta) {p["db_count"]} 条')
        w('')

        # A
        if p['zombie']:
            w(self.style.WARNING(f'【A】僵尸 {len(p["zombie"])} 条 —— 常量表有、库里没有（建议从常量表删掉）'))
            for tn in p['zombie']:
                w(f'    · {tn}')
        else:
            w('【A】僵尸 0 条 ✓')

        # B
        if p['drift']:
            w(self.style.WARNING(f'【B】漂移 {len(p["drift"])} 条 —— 两边都有但值不同（需人工判哪个对）'))
            for d in p['drift']:
                seed = f'{d["seed"][0]}/{d["seed"][1]}'
                dbt = f'{d["db"][0]}/{d["db"][1]}'
                w(f'    · {d["task_name"]:12s} 种子={seed:22s} 库={dbt:22s}'
                  f'  {d["records"]:5d} 条 / {d["hours"]:9.2f}h')
        else:
            w('【B】漂移 0 条 ✓')

        # C
        if p['missing']:
            w(self.style.WARNING(
                f'【C】未收录 {len(p["missing"])} 条 —— 库里有、常量表没有（将来重建库会落「未归类」）'))
            for d in p['missing']:
                dbt = f'{d["db"][0]}/{d["db"][1]}'
                tag = '（旧四分类表可兜住）' if d['via_legacy'] else '（常量表完全没有）'
                w(f'    · {d["task_name"]:12s} 库={dbt:22s}'
                  f'  {d["records"]:5d} 条 / {d["hours"]:9.2f}h {tag}')
        else:
            w('【C】未收录 0 条 ✓')

        # D / E
        if p['invalid']:
            w(self.style.ERROR(f'【D】值域越界 {len(p["invalid"])} 条 —— 库中出现非法 L1/L2 值'))
            for d in p['invalid']:
                w(f'    · {d["task_name"]:12s} L2={d["activity_type"]!r} L1={d["default_attribution"]!r}')
        else:
            w('【D】值域越界 0 条 ✓')

        if p['unclassified']:
            w(self.style.WARNING(f'【E】未归类桶 {len(p["unclassified"])} 条 —— 需到映射编辑器补分类'))
            for tn in p['unclassified']:
                w(f'    · {tn}')
        else:
            w('【E】未归类桶 0 条 ✓')

        w('')
        if p['ok']:
            w(self.style.SUCCESS('结论：三类差异均为空 —— 种子与真源一致。'))
        else:
            w(self.style.WARNING(
                '结论：存在差异。⚠️ 这不必然是 bug —— 本表是「种子」、库是「真源」，'
                '两者**允许**不一致；但每一条都该有人看过并知道原因。'))
