"""初始化物件资产的默认类别（家电 / 家具 / 数码 / 交通 / 家装 / 其他）。

用法（**本命令写库，请先确认已执行迁移 `wealth/0026_property`**）：

    # 0. 先看会写什么（不写任何数据）
    python manage.py wealth_seed_property_categories --dry-run

    # 1. 建类别（幂等，不动你自己改过的说明与排序）
    python manage.py wealth_seed_property_categories

    # 2. 把种子文案写回已有类别（会覆盖界面上的改动，慎用）
    python manage.py wealth_seed_property_categories --overwrite

幂等性
    唯一键是 (user_id, name)，故重复执行不会产生重复类别：
        overwrite=False（默认）→ 只补缺失的，**不动你自己改过的说明与排序**；
        overwrite=True          → 用种子文案覆盖同名的已有类别。
    手工新增的类别（不在种子里）两种情况都不受影响。

🔴 只种**类别**，不预设任何物件
    物件是用户自己的数据（他家里真有什么、花了多少钱），系统代猜就是编数据。
    这条与 `wealth_seed_classify_rules`（种的是「凭分类名即可判定的规则」）
    是同一条取舍：只种**不需要知道个人情况**的部分。

🔴 类别里**没有默认使用年限**
    `PROPERTY_CATEGORY_SEEDS` 里只有名称 / 图标 / 一句说明，刻意不给
    `default_lifespan_months`。理由：那是用户自己的判断，不是这件东西的固有属性。
    给一个「空调 10 年」的通用值，等于系统替他定了这件事。
    类别上那个字段是给用户**自己填**的，只用于预填表单，绝不兜底。

⚠️ 覆盖时也**不会**碰 `default_lifespan_months`（种子值里根本没有它）。
    会变的是图标、说明与排序 —— 就这三样，且 dry-run 会先念一遍。
"""

from django.core.management.base import BaseCommand
from django.db.utils import DatabaseError

from apps.wealth.constants import PROPERTY_CATEGORY_SEEDS
from apps.wealth.models import WealthProperty, WealthPropertyCategory
from apps.wealth.services import property_service


class Command(BaseCommand):
    help = '初始化物件资产的默认类别（只种类别，不预设任何物件）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--overwrite', action='store_true',
            help='用种子文案覆盖已存在的同名类别（图标 / 说明 / 排序）',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='只报告将要执行的动作，不写任何数据',
        )

    def handle(self, *args, **options):
        # 🔴 先探一下表在不在 —— 「迁移没跑」是可预期的部署状态，
        #    不该给用户一份 MySQL 的 traceback（那看着像数据出了事）。
        if not self._tables_ready():
            return

        if options['dry_run']:
            self._report_dry_run(options['overwrite'])
            return

        result = property_service.seed_property_categories(
            overwrite=options['overwrite'],
        )
        self.stdout.write(self.style.SUCCESS(
            f"类别：新建 {result['created']} 个，已存在保留 {result['skipped']} 个，"
            f"覆盖更新 {result['updated']} 个（种子定义共 {len(PROPERTY_CATEGORY_SEEDS)} 个）"
        ))
        self._report_state()

    def _tables_ready(self) -> bool:
        """物件资产的两张表在不在。

        ⚠️ 迁移 `wealth/0026_property` 按项目铁律**由用户手动执行**（AI 只写不跑），
           所以「命令先于迁移被执行」是常态，不是异常。
        """
        try:
            WealthPropertyCategory.objects.filter(user_id=1).exists()
            WealthProperty.objects.filter(user_id=1).exists()
            return True
        except DatabaseError as exc:
            self.stdout.write(self.style.ERROR(
                '物件资产的表还没建，命令没执行。'
                '请先执行迁移 `python manage.py migrate wealth`'
                '（本次新增的是 wealth/0026_property）。'
            ))
            self.stdout.write(f'（原始报错：{exc}）')
            return False

    # ── dry-run ────────────────────────────────────────────────

    def _report_dry_run(self, overwrite: bool):
        seed_names = [seed['name'] for seed in PROPERTY_CATEGORY_SEEDS]
        existing = set(
            WealthPropertyCategory.objects
            .filter(user_id=1)
            .values_list('name', flat=True)
        )
        to_create = [name for name in seed_names if name not in existing]
        to_keep = [name for name in seed_names if name in existing]

        self.stdout.write('[dry-run] 类别：')
        self.stdout.write(f'  将新建 {len(to_create)} 个：{to_create or "（无）"}')
        if overwrite:
            self.stdout.write(self.style.WARNING(
                f'  --overwrite 已开启：将把 {len(to_keep)} 个已有类别的'
                f'图标 / 说明 / 排序重置为种子值：{to_keep or "（无）"}'
            ))
        else:
            self.stdout.write(
                f'  将保留 {len(to_keep)} 个已存在的类别（不覆盖说明与排序）：'
                f'{to_keep or "（无）"}'
            )

        self.stdout.write('')
        self.stdout.write('[dry-run] 将写入的六个刻度（类别只装「用途」）：')
        for index, seed in enumerate(PROPERTY_CATEGORY_SEEDS, start=1):
            self.stdout.write(
                f'  {index}. {seed["name"]} —— {seed.get("note") or "（无说明）"}'
            )

        # 把「这次不会碰什么」也念出来 —— 覆盖的边界必须可见
        self.stdout.write('')
        self.stdout.write('[dry-run] 不会写入：')
        self.stdout.write('  · 任何物件（物件是用户自己的数据，不代猜）')
        self.stdout.write('  · 任何类别的默认使用年限（那是用户自己的判断，'
                          '类别上那个字段只用于预填表单）')

        self.stdout.write('')
        self._report_state()
        self.stdout.write('[dry-run] 未写入任何数据。去掉 --dry-run 才会实际执行。')

    # ── 现状 / 验收 ────────────────────────────────────────────

    def _report_state(self):
        """把「现在有多少类别、多少物件、多少已经算不出净值」摆出来

        最后一项是本模块最要紧的一个数：它说明有多少件家当因为缺字段
        而算不出净值 —— 那不是错误，是还没填，但**不报出来就没人会去填**。
        """
        categories = WealthPropertyCategory.objects.filter(user_id=1).count()
        items = WealthProperty.objects.filter(user_id=1).count()
        self.stdout.write('')
        self.stdout.write(f'[现状] 类别 {categories} 个，物件 {items} 件。')
        if not items:
            self.stdout.write(
                '下一步：打开「物件资产」页面点「新增物件」，'
                '或在页面里先核对类别是否合你的口径。'
            )
            return
        # 只统计「为什么算不出」，不在这里重算净值 —— 口径只有一个真源
        incomplete = (
            WealthProperty.objects
            .filter(user_id=1)
            .filter(purchase_amount__isnull=True).count()
            + WealthProperty.objects
            .filter(user_id=1, purchase_amount__isnull=False)
            .filter(purchase_date__isnull=True).count()
        )
        self.stdout.write(
            f'[现状] 其中 {incomplete} 件因缺金额 / 缺购买日期而算不出净值'
            f'（页面会显示「—」并说明原因，不会显示 ¥0）。'
        )
