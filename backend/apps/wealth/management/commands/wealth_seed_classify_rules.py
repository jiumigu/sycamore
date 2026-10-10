"""按真实账单分类归纳出的种子规则初始化账单项分类规则。

用法（**本命令写库，请先确认已 migrate**）：

    # 0. 先看会写什么（不写任何数据）
    python manage.py wealth_seed_classify_rules --dry-run

    # 1. 建规则（幂等，不动界面上改过的规则）
    python manage.py wealth_seed_classify_rules

    # 2. 把种子值写回已有规则（会覆盖界面上的改动，慎用）
    python manage.py wealth_seed_classify_rules --overwrite

幂等性
    唯一键是 (user_id, rule_field, match_value)，故重复执行不会产生重复规则：
        overwrite=False（默认）→ 只补缺失的，**不动用户改过的规则**；
        overwrite=True          → 用种子值覆盖同键的已有规则。
    手工新增的规则（不在种子里）两种情况都不受影响。

为什么需要初始化这 25 条
    账单表只记「这笔钱在哪个分类」，不记「这笔钱是什么性质」。
    不先给整类一个默认，6588 行流水会全部落在「未归类」里，
    覆盖率恒为 0 —— 规则表再正确也看不出效果。
    种子规则的存在意义是「把显然的 80% 先归掉，把判断留给人」。

⚠️ 种子只覆盖**凭分类名即可判定、无需知道个人情况**的项。
   归属含糊的（其他收入 / 意外来钱 / 动车的通勤与出行之别 /
   无可救药的到底是什么）**刻意不种** —— 那些会出现在
   `/api/wealth/classify/results/unclassified/` 里，由人补规则，不由 AI 猜。
"""

from django.core.management.base import BaseCommand

from apps.wealth.constants import (
    CLASSIFY_SEED_RULES,
    CASHFLOW_CLASSES,
    EXPENSE_NATURES,
    INCOME_TYPES,
)
from apps.wealth.models import WealthBillList, WealthClassifyRule
from apps.wealth.services.classify_service import (
    available_periods,
    classify_summary,
    get_unclassified_candidates,
    seed_classify_rules,
)


class Command(BaseCommand):
    help = '初始化账单项分类规则（收入性质 / 支出刚性 / 现金流归集）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--overwrite', action='store_true',
            help='把种子值写回已存在的同键规则（会覆盖界面上的改动）',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='只报告将要执行的动作，不写任何数据',
        )
        parser.add_argument(
            '--user-id', type=int, default=1, help='用户 ID（默认 1）',
        )

    def handle(self, *args, **options):
        user_id = options['user_id']
        overwrite = options['overwrite']
        dry_run = options['dry_run']

        if dry_run:
            self._report_dry_run(user_id, overwrite)
            return

        result = seed_classify_rules(user_id=user_id, overwrite=overwrite)
        self.stdout.write(self.style.SUCCESS(
            f"规则：新建 {result['created']} 条，已存在保留 {result['skipped']} 条，"
            f"覆盖更新 {result['updated']} 条（种子定义共 {result['total']} 条）"
        ))
        self._report_coverage(user_id)

    # ── dry-run ────────────────────────────────────────────────

    def _report_dry_run(self, user_id, overwrite):
        keys = [(row[0], row[1]) for row in CLASSIFY_SEED_RULES]
        existing = {
            (field, value) for field, value in
            WealthClassifyRule.objects
            .filter(user_id=user_id)
            .values_list('rule_field', 'match_value')
        }
        to_create = [k for k in keys if k not in existing]
        to_keep = [k for k in keys if k in existing]

        self.stdout.write('[dry-run] 规则：')
        self.stdout.write(f'  将新建 {len(to_create)} 条：')
        for field, value in to_create:
            self.stdout.write(f'    · {field}={value}')
        if overwrite:
            self.stdout.write(self.style.WARNING(
                f'  --overwrite 已开启：将把 {len(to_keep)} 条已有规则重置为种子值：'
                f'{[f"{f}={v}" for f, v in to_keep] or "（无）"}'
            ))
        else:
            self.stdout.write(
                f'  将保留 {len(to_keep)} 条已存在的规则（不覆盖）：'
                f'{[f"{f}={v}" for f, v in to_keep] or "（无）"}'
            )

        self.stdout.write('')
        self.stdout.write('[dry-run] 规则维度分布（种子定义）：')
        # 种子元组顺序：(rule_field, match_value, income_type, expense_nature,
        #                 cashflow_class, priority, note)
        for label, index, allowed in (
            ('收入性质', 2, INCOME_TYPES),
            ('支出刚性', 3, EXPENSE_NATURES),
            ('现金流类别', 4, CASHFLOW_CLASSES),
        ):
            counts = {}
            for row in CLASSIFY_SEED_RULES:
                value = row[index]
                if value:
                    counts[value] = counts.get(value, 0) + 1
            parts = '，'.join(f'{k} {counts.get(k, 0)} 条' for k in allowed)
            self.stdout.write(f'  {label}：{parts}')

        self.stdout.write('')
        self._report_now_state(user_id)
        self.stdout.write('[dry-run] 未写入任何数据。去掉 --dry-run 才会实际执行。')

    def _report_now_state(self, user_id):
        """把「现在有多少钱没归类」摆出来 —— 这是建规则的理由，也是验收基线"""
        periods = available_periods(user_id)
        if not periods:
            self.stdout.write('[现状] 账单表还没有可用于归类的收支记录。')
            return
        total = WealthBillList.objects.filter(
            user_id=user_id, transaction_type__in=('收入', '支出'),
        ).count()
        self.stdout.write(f'[现状] 账单表共有 {total} 条收支记录，'
                          f'覆盖 {len(periods)} 期（最近 {periods[0]}）。')
        unclassified = get_unclassified_candidates(user_id=user_id, limit=5)
        self.stdout.write(
            f'[现状] 当前未归类 {unclassified["total_count"]} 条、'
            f'合计 {unclassified["total_amount"]} 元。'
        )
        for row in unclassified['items']:
            self.stdout.write(
                f'    · {row["category"]} / {row["subcategory"] or "（无子分类）"}：'
                f'{row["count"]} 条 {row["amount"]} 元'
                f'（建议建在 {row["suggested_field"]}={row["suggested_value"]}）'
            )

    # ── 写库后的验收提示 ───────────────────────────────────────

    def _report_coverage(self, user_id):
        periods = available_periods(user_id)
        if not periods:
            return
        summary = classify_summary(periods[0], user_id=user_id)
        coverage = summary['coverage']
        self.stdout.write('')
        self.stdout.write(f'[验收] {summary["period_label"]} 归类覆盖率：')
        self.stdout.write(f'  收入性质 {coverage["income_type"]:.2%}'
                          f'（未归类 {summary["income"]["unclassified"]} 元）')
        self.stdout.write(f'  支出刚性 {coverage["expense_nature"]:.2%}'
                          f'（未归类 {summary["expense"]["unclassified"]} 元）')
        self.stdout.write(f'  现金流类别 {coverage["cashflow_class"]:.2%}'
                          f'（未归类 {summary["cashflow"]["unclassified"]} 元）')
        self.stdout.write(
            '下一步：看 /api/wealth/classify/results/unclassified/ '
            '里金额最大的几项，逐条补规则；'
            '或用 `wealth_seed_classify_rules --dry-run` 复查维度分布。'
        )
