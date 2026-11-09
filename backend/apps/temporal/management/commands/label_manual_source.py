"""给「没有来源标记」的历史时间记录补上来源（v3.64.34）

背景：`import_batch` 在「手工新增」这条写入路径上一直没写（v3.64.33 才补上），
于是 41 条记录停在空值，界面上归为「未标注」，和真正的「早期来源不明」混成一桶。
用户已逐条核实：这批记录**都是用「时间任务清单 → 手工新增」录入的**。

所以这里按 `manual` 补记 —— **有据可依，不是猜**。修复逻辑在
`services.label_unlabeled_source`（唯一实现、有测试），本命令只负责打印与开关。

Usage:
    python manage.py label_manual_source                    # 预演：只打印，不写库
    python manage.py label_manual_source --apply            # 真正写入
    python manage.py label_manual_source --apply --exclude 128,129

⚠️ 只动 `import_batch` 为空的行；任何已有来源（timer / csv / worklog …）一律不碰。
⚠️ 界面上「未标注」应当归零。它再冒出来说明有新写入方没登记 kind，别习惯它。
"""

from django.core.management.base import BaseCommand, CommandError

from apps.temporal.services import label_unlabeled_source

TARGET = 'manual'


class Command(BaseCommand):
    help = '把没有来源标记的历史记录补记为「手工录入」（默认只预演）'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='真正写库；不加就是预演')
        parser.add_argument('--exclude', default='', help='逗号分隔的记录 id，跳过这些行（逐行否决）')

    def handle(self, *args, **options):
        skip = set()
        raw = (options['exclude'] or '').strip()
        if raw:
            try:
                skip = {int(x) for x in raw.split(',') if x.strip()}
            except ValueError:
                raise CommandError('--exclude 只接受逗号分隔的数字 id')

        # 先预演：既拿到清单，也拿到「排除后还剩哪些 id」
        probe = label_unlabeled_source(TARGET, dry_run=True)
        rows = [r for r in probe['rows'] if r['id'] not in skip]

        if not probe['total']:
            self.stdout.write('没有需要补记的记录（库里已经没有来源为空的记录了）。')
            return
        self.stdout.write(f'没有来源标记的记录：{probe["total"]} 条')
        if skip:
            unknown = skip - {r['id'] for r in probe['rows']}
            if unknown:
                self.stdout.write(self.style.WARNING(
                    f'⚠️ 这些 id 不在待补记范围里，忽略：{sorted(unknown)}'))
            self.stdout.write(f'按 --exclude 跳过 {probe["total"] - len(rows)} 条，'
                              f'剩余 {len(rows)} 条。')

        with_desc = [r for r in rows if r['has_description']]
        for i, r in enumerate(rows, 1):
            mark = '  （有描述，可能是 import_worklog 回填的）' if r['has_description'] else ''
            self.stdout.write(f'  {i:>3}. {r["start"]}  {r["task_name"]:<8}{mark}')

        if not options['apply']:
            self.stdout.write(self.style.WARNING(
                f'预演：以上 {len(rows)} 条将标为「{probe["label"]}」，尚未写库。'
                f'确认无误后加 --apply。'))
            return

        if not rows:
            self.stdout.write('排除之后没有要改的记录，未写库。')
            return

        result = label_unlabeled_source(TARGET, ids=[r['id'] for r in rows], dry_run=False)
        self.stdout.write(self.style.SUCCESS(
            f'已写入：{result["updated"]} 条标为「{result["label"]}」。'))
        if with_desc:
            self.stdout.write(
                f'其中 {len(with_desc)} 条带描述 —— 若它们其实不是手工敲进去的，'
                f'用 `--exclude` 重跑前先手动核对（见 TECH-NOTES §159）。')
