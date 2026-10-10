"""从旧表列定义生成资产科目，并把旧快照回填为新体系的快照明细。

用法（**本命令写库，请先确认已 migrate**）：

    # 0. 先看会做什么（不写任何数据）
    python manage.py wealth_seed_asset_accounts --dry-run

    # 1. 只建科目（幂等，不动界面上已改过的科目）
    python manage.py wealth_seed_asset_accounts

    # 2. 建科目 + 把全部旧快照回填成新体系的科目快照
    python manage.py wealth_seed_asset_accounts --with-snapshots

    # 3. 只回填某一期
    python manage.py wealth_seed_asset_accounts --with-snapshots --yearmon 2026-09

    # 4. 把种子值写回（会覆盖界面上改过的类别 / 流动性标记）
    python manage.py wealth_seed_asset_accounts --overwrite

幂等性
    科目：默认只补缺失的（overwrite=False），重复执行不会产生重复科目，
        也不会把用户在界面上调过的 category / is_liquid 冲回默认值。
    快照：按 yearmon 覆盖写入，重复执行不会产生重复期。

安全约定
    被旧快照引用的科目删不掉、回填也不会删任何旧数据 ——
    wealth_cash_flow 原样保留，新旧两套并行，靠
    `/api/wealth/asset/snapshots/compare/?yearmon=YYYY-MM` 做逐科目比对。
"""

from django.core.management.base import BaseCommand

from apps.wealth.constants import LEGACY_ASSET_ACCOUNTS
from apps.wealth.models import WealthAssetAccount, WealthCashFlow, WealthAssetSnapshot
from apps.wealth.services.asset_service import (
    backfill_from_legacy,
    seed_asset_accounts,
)


class Command(BaseCommand):
    help = '生成资产科目主数据（可选把旧快照回填为新体系快照明细）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--with-snapshots', action='store_true',
            help='同时把 wealth_cash_flow 的旧快照回填为新体系的科目快照',
        )
        parser.add_argument(
            '--yearmon', type=str, default=None,
            help='只处理指定年月（YYYY-MM），需与 --with-snapshots 同用',
        )
        parser.add_argument(
            '--overwrite', action='store_true',
            help='把种子值写回已存在的科目（会覆盖界面上改过的类别与流动性标记）',
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
        with_snapshots = options['with_snapshots']
        yearmon = options['yearmon']
        overwrite = options['overwrite']
        dry_run = options['dry_run']

        if yearmon and not with_snapshots:
            self.stdout.write(self.style.WARNING(
                '提示：--yearmon 只在 --with-snapshots 下生效，本次将仅处理科目。'
            ))

        if dry_run:
            self._report_dry_run(user_id, with_snapshots, yearmon, overwrite)
            return

        result = seed_asset_accounts(user_id=user_id, overwrite=overwrite)
        self.stdout.write(self.style.SUCCESS(
            f"科目：新建 {result['created']} 个，已存在保留 {result['kept']} 个，"
            f"覆盖更新 {result['updated']} 个（种子定义共 {result['total']} 个）"
        ))

        if not with_snapshots:
            self.stdout.write(
                '下一步：确认科目无误后，加 --with-snapshots 回填旧快照；'
                '或先在界面「资产科目」面板手工调整。'
            )
            return

        back = backfill_from_legacy(user_id=user_id, yearmon=yearmon)
        if not back['ok']:
            self.stdout.write(self.style.ERROR(
                f"回填已中止：缺少科目 {back['missing_accounts']}。"
                '请先执行不带 --with-snapshots 的本命令建出全部种子科目。'
            ))
            return
        self.stdout.write(self.style.SUCCESS(
            f"快照：扫描 {back['scanned']} 期，新建 {back['created']} 期，"
            f"覆盖 {back['updated']} 期"
        ))
        self.stdout.write(
            '验收：打开「资产盘点」页，资产趋势应显示回填后的期数，'
            '概览期别为最新一期。'
        )

    def _report_dry_run(self, user_id, with_snapshots, yearmon, overwrite):
        """只报告将要做什么 —— 写库前应当先看一眼"""
        codes = [row[0] for row in LEGACY_ASSET_ACCOUNTS]
        existing = set(
            WealthAssetAccount.objects.filter(user_id=user_id, code__in=codes)
            .values_list('code', flat=True)
        )
        to_create = [c for c in codes if c not in existing]
        to_keep = [c for c in codes if c in existing]

        self.stdout.write('[dry-run] 科目：')
        self.stdout.write(f'  将新建 {len(to_create)} 个：{to_create or "（无）"}')
        if overwrite:
            self.stdout.write(self.style.WARNING(
                f'  --overwrite 已开启：将把 {len(to_keep)} 个已有科目的类别 / '
                f'流动性标记重置为种子值：{to_keep or "（无）"}'
            ))
        else:
            self.stdout.write(f'  将保留 {len(to_keep)} 个已存在的科目（不覆盖）：{to_keep or "（无）"}')

        if not with_snapshots:
            self.stdout.write('[dry-run] 未指定 --with-snapshots，不会写入任何快照。')
            return

        qs = WealthCashFlow.objects.filter(yearmon__isnull=False)
        if yearmon:
            qs = qs.filter(yearmon=yearmon)
        months = list(qs.order_by('yearmon').values_list('yearmon', flat=True))
        existing_snaps = set(
            WealthAssetSnapshot.objects.filter(user_id=user_id, yearmon__in=months)
            .values_list('yearmon', flat=True)
        )
        self.stdout.write('[dry-run] 快照：')
        self.stdout.write(f'  将扫描 {len(months)} 期：{months or "（无）"}')
        self.stdout.write(f'  其中新建 {len(months) - len(existing_snaps)} 期，'
                          f'覆盖 {len(existing_snaps)} 期')
        if to_create:
            self.stdout.write(self.style.ERROR(
                f'  ⚠️ 仍有 {len(to_create)} 个科目待建，直接回填会中止。'
                '先执行不带 --with-snapshots 的本命令。'
            ))
        self.stdout.write('[dry-run] 未写入任何数据。去掉 --dry-run 才会实际执行。')
