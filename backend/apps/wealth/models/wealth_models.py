from django.db import models

from ..constants import (
    CASHFLOW_CLASS_CHOICES,
    CLASSIFY_RULE_FIELDS,
    EXPENSE_NATURE_CHOICES,
    INCOME_TYPE_CHOICES,
)


class WealthLifeWeekCalendar(models.Model):
    """周历基础表 — 每人 61年 × 52周 = 3172 条"""

    global_week_index = models.IntegerField(primary_key=True, verbose_name='全局周索引(0-3171)')
    age_year = models.IntegerField(verbose_name='年龄(18-78)')
    week_number = models.IntegerField(verbose_name='周数(1-52)')
    week_start_date = models.DateField(verbose_name='该周起始日期')
    week_end_date = models.DateField(verbose_name='该周结束日期')
    is_lived = models.BooleanField(default=False, verbose_name='是否已度过')
    user_id = models.IntegerField(default=1, verbose_name='用户ID')

    class Meta:
        db_table = 'wealth_life_week_calendar'
        verbose_name = '人生周历'
        verbose_name_plural = '人生周历'
        indexes = [
            models.Index(fields=['user_id', 'global_week_index']),
        ]

    def __str__(self):
        return f'第{self.global_week_index}周 (年龄{self.age_year} 第{self.week_number}周)'


class WealthCurrentScenario(models.Model):
    """当前推演状态 — 单例模式(id=1)"""

    snapshot_time = models.DateTimeField(auto_now=True, verbose_name='推演时间点')
    current_age = models.IntegerField(verbose_name='当前年龄(18-78)')
    current_week = models.IntegerField(verbose_name='当前周数(1-52)')
    current_cash = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='当前现金(元)')
    daily_budget = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='每日预算(元/天)')
    daily_interest_rate = models.DecimalField(max_digits=10, decimal_places=8, default=0, verbose_name='日利息率(小数)')
    support_weeks = models.IntegerField(default=0, verbose_name='可支撑周数')
    end_age = models.IntegerField(null=True, blank=True, verbose_name='资金耗尽时的年龄')
    end_week = models.IntegerField(null=True, blank=True, verbose_name='资金耗尽时的周数')

    class Meta:
        db_table = 'wealth_current_scenario'
        verbose_name = '当前推演状态'
        verbose_name_plural = '当前推演状态'

    def __str__(self):
        return f'年龄{self.current_age}岁第{self.current_week}周 · 现金{self.current_cash} · 日均{self.daily_budget}'


class WealthScenarioHistory(models.Model):
    """推演历史记录"""

    snapshot_time = models.DateTimeField(auto_now_add=True, verbose_name='推演时间点')
    current_age = models.IntegerField(verbose_name='当前年龄')
    current_week = models.IntegerField(verbose_name='当前周数')
    current_cash = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='当前现金')
    daily_budget = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='每日预算')
    daily_interest_rate = models.DecimalField(max_digits=10, decimal_places=8, default=0, verbose_name='日利息率(小数)')
    support_weeks = models.IntegerField(default=0, verbose_name='可支撑周数')
    note = models.CharField(max_length=200, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'wealth_scenario_history'
        verbose_name = '推演历史'
        verbose_name_plural = '推演历史'
        ordering = ['-snapshot_time']

    def __str__(self):
        return f'{self.snapshot_time:%Y-%m-%d %H:%M} 现金{self.current_cash} 日均{self.daily_budget}'


class WealthCashFlow(models.Model):
    """现金盘点表 — 每月各账户余额快照"""

    baid = models.AutoField(primary_key=True, verbose_name='编号')
    yearmon = models.CharField(max_length=10, blank=True, null=True, verbose_name='年月')
    zplay = models.FloatField(blank=True, null=True, verbose_name='支付宝')
    wechat = models.FloatField(blank=True, null=True, verbose_name='微信')
    cash = models.FloatField(blank=True, null=True, verbose_name='现金')
    jianbank = models.FloatField(blank=True, null=True, verbose_name='建行')
    gongbank = models.FloatField(blank=True, null=True, verbose_name='工行')
    zhongbank = models.FloatField(blank=True, null=True, verbose_name='中国银行')
    nongbank = models.FloatField(blank=True, null=True, verbose_name='农村信用社')
    accumulationfund = models.FloatField(blank=True, null=True, verbose_name='公积金')
    lend = models.FloatField(blank=True, null=True, verbose_name='借出')
    borrow = models.FloatField(blank=True, null=True, verbose_name='负债')
    flow_total = models.FloatField(blank=True, null=True, verbose_name='总现金流')
    total = models.FloatField(blank=True, null=True, verbose_name='总额')
    btime = models.DateField(blank=True, null=True, verbose_name='复盘时间')
    remarks = models.CharField(max_length=255, blank=True, null=True, verbose_name='备注')
    realnum = models.FloatField(blank=True, null=True, verbose_name='真正在手里的')

    class Meta:
        managed = False
        db_table = 'wealth_cash_flow'
        verbose_name = '现金盘点'
        verbose_name_plural = '现金盘点'
        ordering = ['-yearmon']

    def __str__(self):
        return f'{self.yearmon} 现金流盘点'


class WealthBalanceList(models.Model):
    """月度收支复盘表 — 每月收支统计+存款汇总"""

    yearmon = models.CharField(primary_key=True, max_length=10, verbose_name='年月')
    wageincome = models.FloatField(blank=True, null=True, verbose_name='工资收入')
    otherincome = models.FloatField(blank=True, null=True, verbose_name='其他收入')
    outmoney = models.FloatField(blank=True, null=True, verbose_name='支出')
    mbalance = models.FloatField(blank=True, null=True, verbose_name='每月余额')
    btime = models.DateTimeField(blank=True, null=True, verbose_name='日期')
    balance = models.FloatField(blank=True, null=True, verbose_name='流水余额')
    accumulationfund = models.FloatField(blank=True, null=True, verbose_name='公积金')
    total = models.FloatField(blank=True, null=True, verbose_name='总存款')
    remarks = models.CharField(max_length=255, blank=True, null=True, verbose_name='备注')
    distance = models.FloatField(blank=True, null=True, verbose_name='距离')
    borrow = models.FloatField(blank=True, null=True, verbose_name='借贷')
    lend = models.FloatField(blank=True, null=True, verbose_name='借出')
    realnum = models.FloatField(blank=True, null=True, verbose_name='真正在手里的')
    user_id = models.IntegerField(blank=True, null=True, verbose_name='用户ID预留')

    class Meta:
        managed = False
        db_table = 'wealth_balance_list'
        verbose_name = '月度收支复盘'
        verbose_name_plural = '月度收支复盘'

    def __str__(self):
        return f'{self.yearmon} 收{self.income} 支{self.expense}'

    @property
    def income(self) -> float:
        return (self.wageincome or 0) + (self.otherincome or 0)

    @property
    def expense(self) -> float:
        return self.outmoney or 0

    @property
    def net_balance(self) -> float:
        return self.mbalance or 0

    @property
    def notes(self) -> str:
        return self.remarks or ''


class WealthRegularList(models.Model):
    """定期存款记录表"""

    id = models.AutoField(primary_key=True, verbose_name='编号')
    begin_date = models.DateField(verbose_name='存入日期')
    end_date = models.DateField(verbose_name='到期日期')
    value = models.FloatField(verbose_name='存款金额')
    flag = models.IntegerField(default=0, verbose_name='状态(0未到期/1已到期/2已取出)')
    interest = models.FloatField(blank=True, null=True, verbose_name='利息')
    remark = models.CharField(max_length=100, blank=True, null=True, verbose_name='备注')
    bankinfo = models.CharField(max_length=20, blank=True, null=True, verbose_name='银行')
    rate = models.FloatField(blank=True, null=True, verbose_name='年利率(%)')
    user_id = models.IntegerField(default=1, verbose_name='用户ID')

    class Meta:
        managed = False
        db_table = 'wealth_regular_list'
        verbose_name = '定期存款'
        verbose_name_plural = '定期存款'
        ordering = ['-end_date']

    def __str__(self):
        return f'{self.bankinfo or "未知银行"} {self.value}元 ({self.get_flag_display()})'

    @property
    def flag_label(self) -> str:
        return {0: '未到期', 1: '已到期', 2: '已取出'}.get(self.flag, '未知')

    @property
    def term_days(self) -> int:
        if self.begin_date and self.end_date:
            return (self.end_date - self.begin_date).days
        return 0

    @property
    def calculated_interest(self) -> float:
        """单利计算：本金 × 年利率 × (天数/365)"""
        if not all([self.value, self.rate, self.begin_date, self.end_date]):
            return 0.0
        days = self.term_days
        return round(self.value * (self.rate / 100) * (days / 365), 2)


class WealthBillList(models.Model):
    """账单明细（映射外部遗留表 wealth_bill_list，清单 CRUD 用）"""

    id = models.AutoField(primary_key=True)
    transaction_type = models.CharField(max_length=10, verbose_name='收支类型')
    date = models.DateTimeField(verbose_name='日期')
    category = models.CharField(max_length=50, blank=True, null=True, verbose_name='分类')
    subcategory = models.CharField(max_length=50, blank=True, null=True, verbose_name='子分类')
    necessity = models.CharField(max_length=10, blank=True, null=True, verbose_name='消费必要性(必要/可选/冲动)')
    period_tag = models.CharField(
        max_length=10, blank=True, null=True,
        verbose_name='赎回归属(为自己/过渡/为别人/不计入)',
    )
    project = models.CharField(max_length=100, blank=True, null=True, verbose_name='项目')
    account = models.CharField(max_length=50, blank=True, null=True, verbose_name='账户')
    account_currency = models.CharField(max_length=10, blank=True, null=True, verbose_name='币种')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='金额')
    member = models.CharField(max_length=50, blank=True, null=True, verbose_name='成员')
    merchant = models.CharField(max_length=100, blank=True, null=True, verbose_name='商户')
    notes = models.TextField(blank=True, null=True, verbose_name='备注')
    related_id = models.CharField(max_length=100, blank=True, null=True, verbose_name='关联ID')
    year = models.IntegerField(blank=True, null=True)
    month = models.IntegerField(blank=True, null=True)
    day = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True, auto_now_add=False)
    updated_at = models.DateTimeField(blank=True, null=True, auto_now_add=False)
    user_id = models.IntegerField(default=1)

    class Meta:
        managed = False
        db_table = 'wealth_bill_list'
        ordering = ['-date']
        verbose_name = '账单明细'
        verbose_name_plural = '账单明细'

    def __str__(self):
        return f'{self.transaction_type} {self.amount} {self.notes or ""}'


# ══════════════════════════════════════════════════════════════
# 负债 / 应收逐笔台账（v3.58.20 起，P1-A）
#
# 与 wealth_cash_flow 的关系：快照里的 borrow / lend 是**每月盘点一次的汇总数**，
# 这两张新表是**逐笔台账**。两者口径不同步时由对账字段给出差额，
# **不自动改写快照**（快照是历史事实，不得回溯篡改）。
#
# 两张表均为 managed 新表（Django 建表/建索引），
# 不向任何 managed=False 的 ATracker 外部表加列。
# ══════════════════════════════════════════════════════════════


class WealthLiabilityDetail(models.Model):
    """负债明细表 — 每笔负债的本金、剩余、利率与还款方式

    关键字段口径：
        principal     借款本金（原始合同额）
        outstanding   剩余未还本金（月供还款后手工更新，派生「已还本金」）
        annual_rate   年利率(%)，用于算年利息成本与还款优先级
        monthly_payment 每月应还（算现金流压力；不参与余额推导）
    """

    CATEGORY_CHOICES = (
        ('信用卡', '信用卡'),
        ('消费贷', '消费贷'),
        ('房贷', '房贷'),
        ('车贷', '车贷'),
        ('亲友借款', '亲友借款'),
        ('其他', '其他'),
    )

    REPAYMENT_CHOICES = (
        ('等额本息', '等额本息'),
        ('等额本金', '等额本金'),
        ('先息后本', '先息后本'),
        ('随借随还', '随借随还'),
        ('一次性还本', '一次性还本'),
    )

    STATUS_CHOICES = (
        ('在还', '在还'),
        ('已结清', '已结清'),
    )

    id = models.AutoField(primary_key=True, verbose_name='编号')
    name = models.CharField(max_length=50, verbose_name='债务名/债权人')
    category = models.CharField(
        max_length=10, choices=CATEGORY_CHOICES, default='其他', verbose_name='负债类型',
    )
    principal = models.FloatField(default=0, verbose_name='借款本金')
    outstanding = models.FloatField(default=0, verbose_name='剩余未还本金')
    annual_rate = models.FloatField(default=0, verbose_name='年利率(%)')
    start_date = models.DateField(blank=True, null=True, verbose_name='起借日')
    due_date = models.DateField(blank=True, null=True, verbose_name='到期日')
    repayment_method = models.CharField(
        max_length=10, choices=REPAYMENT_CHOICES, default='等额本息', verbose_name='还款方式',
    )
    monthly_payment = models.FloatField(default=0, verbose_name='每月应还')
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='在还', verbose_name='状态',
    )
    remark = models.CharField(max_length=200, blank=True, null=True, verbose_name='备注')
    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        # 刻意不设 Meta.ordering：外部表 ordering 会被注入 SELECT 而使
        # values().distinct() / annotate() 静默失效（项目硬坑②）—— 排序一律在服务层显式给定
        db_table = 'wealth_liability_detail'
        verbose_name = '负债明细'
        verbose_name_plural = '负债明细'
        indexes = [
            models.Index(fields=['user_id', 'status']),
        ]

    def __str__(self):
        return f'{self.name} 剩余{self.outstanding} 年利率{self.annual_rate}%'


class WealthAssetAccount(models.Model):
    """资产科目主数据 — 替代 wealth_cash_flow 硬编码的 8 个物理列

    这张表存在的唯一理由：让「有哪些资产科目」从表结构里搬进数据里，
    新增「证券账户」「保险现金价值」只插一行，而不必对
    `managed = False` 的外部表执行 ALTER TABLE（项目铁律禁止）。

    关键字段口径：
        code        稳定映射键，旧表 8 列的列名（zplay / wechat / ... ）。
                    旧快照回填与双跑校验靠它逐科目对齐；手工新增的科目留空。
        category    资产类别（流动性/投资性/自用/应收）—— 回答「这是什么资产」
        is_liquid   是否 T+0 可取 —— 回答「能不能马上用」。
                    ⚠️ 与 category 是两个正交维度，公积金是
                    「category=流动性 但 is_liquid=False」的典型，
                    这不是数据错误，详见 constants.py 的说明。
        include_in_balance_sheet
                    是否计入资产负债表口径。自用资产（房/车）置 False：
                    计进去会让净资产看着漂亮却无法变现。
    """

    CATEGORY_CHOICES = (
        ('流动性', '流动性'),
        ('投资性', '投资性'),
        ('自用', '自用'),
        ('应收', '应收'),
    )

    id = models.AutoField(primary_key=True, verbose_name='编号')
    code = models.CharField(
        max_length=20, blank=True, null=True, verbose_name='映射码（旧表列名）',
    )
    name = models.CharField(max_length=50, verbose_name='科目名')
    category = models.CharField(
        max_length=10, choices=CATEGORY_CHOICES, default='流动性', verbose_name='资产类别',
    )
    account_kind = models.CharField(
        max_length=20, default='其他', verbose_name='账户形态',
    )
    institution = models.CharField(
        max_length=50, blank=True, null=True, verbose_name='机构',
    )
    is_liquid = models.BooleanField(default=False, verbose_name='是否T+0可取')
    include_in_balance_sheet = models.BooleanField(
        default=True, verbose_name='是否计入资产负债表',
    )
    sort = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    note = models.CharField(max_length=200, blank=True, null=True, verbose_name='备注')
    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        # 同 WealthLiabilityDetail：不设 Meta.ordering，排序交给服务层
        # （外部表 ordering 会被注入 SELECT 而静默破坏聚合/去重，项目硬坑②）
        db_table = 'wealth_asset_account'
        verbose_name = '资产科目'
        verbose_name_plural = '资产科目'
        # code 允许为 NULL（手工新增的科目无旧列可映射）；MySQL 唯一索引
        # 允许多个 NULL，因此新增科目之间不会互相冲突，而种子科目仍保证唯一。
        constraints = [
            models.UniqueConstraint(
                fields=['user_id', 'code'], name='wealth_asset_account_user_code_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['user_id', 'is_active'], name='wealth_acct_user_active_idx'),
        ]

    def __str__(self):
        return f'{self.name}（{self.category}）'


class WealthAssetSnapshot(models.Model):
    """资产快照头 — 每月一期，替代 wealth_cash_flow 的「一行装 8 科目」

    头只装**不随科目扩展的部分**：年月、盘点日，以及两项来自逐笔台账的
    汇总数（负债、应收借出）。科目余额全部下沉到 WealthAssetSnapshotItem。

    ⚠️ 刻意**不缓存**任何派生合计（总资产 / 净资产 …）：派生值一律由
    明细行实时汇总。缓存会制造第二个真源 —— 改动科目主数据（如把一个
    科目从「流动性」改为「投资性」）后，历史快照的缓存值就会与明细对不上。
    对应地，口径是：**金额是历史事实、不可变；分类是当前视角、随科目主数据
    联动**。这是有意的取舍，不是遗漏。
    """

    id = models.AutoField(primary_key=True, verbose_name='编号')
    yearmon = models.CharField(max_length=10, verbose_name='年月')
    snapshot_date = models.DateField(blank=True, null=True, verbose_name='盘点日期')
    borrow = models.FloatField(default=0, verbose_name='负债合计')
    lend = models.FloatField(default=0, verbose_name='应收借出合计')
    remarks = models.CharField(max_length=255, blank=True, null=True, verbose_name='备注')
    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'wealth_asset_snapshot'
        verbose_name = '资产快照'
        verbose_name_plural = '资产快照'
        constraints = [
            models.UniqueConstraint(
                fields=['user_id', 'yearmon'], name='wealth_asset_snap_user_yearmon_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.yearmon} 资产快照'


class WealthAssetSnapshotItem(models.Model):
    """资产快照明细行 — 一个科目一行

    account 用 on_delete=PROTECT：科目一旦被任何历史快照引用就**不可删除**，
    只能 is_active=False 停用。否则删科目会把历史快照悄悄挖空，
    往期净资产凭空变化 —— 那是最难查的一类账实不符。

    刻意不带 user_id：用户归属由 snapshot 唯一决定，
    明细行再存一份就是允许两者漂移。
    """

    id = models.AutoField(primary_key=True, verbose_name='编号')
    snapshot = models.ForeignKey(
        WealthAssetSnapshot, on_delete=models.CASCADE,
        related_name='items', verbose_name='所属快照',
    )
    account = models.ForeignKey(
        WealthAssetAccount, on_delete=models.PROTECT,
        related_name='snapshot_items', verbose_name='资产科目',
    )
    amount = models.FloatField(default=0, verbose_name='余额')

    class Meta:
        db_table = 'wealth_asset_snapshot_item'
        verbose_name = '资产快照明细'
        verbose_name_plural = '资产快照明细'
        constraints = [
            # 同一期快照里一个科目只能有一行 —— 否则 roll-up 会把同一笔钱算两遍
            models.UniqueConstraint(
                fields=['snapshot', 'account'], name='wealth_asset_item_snap_acct_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.snapshot_id} / {self.account_id} = {self.amount}'


class WealthReceivableDetail(models.Model):
    """应收借出明细表 — 每笔借出的本金、已收回、约定还款日

    关键字段口径：
        principal  借出本金
        received   已收回金额（未收回余额 = principal − received，下方不为负）
        lend_date  借出日 —— **账龄基准**，为空则该笔无法归桶（前端标「未填借出日」）
        due_date   约定还款日 —— 逾期判定基准；为空则不做逾期判定
    """

    STATUS_CHOICES = (
        ('在借', '在借'),
        ('已收回', '已收回'),
        ('呆账', '呆账'),
    )

    id = models.AutoField(primary_key=True, verbose_name='编号')
    counterparty = models.CharField(max_length=50, verbose_name='对方')
    principal = models.FloatField(default=0, verbose_name='借出本金')
    received = models.FloatField(default=0, verbose_name='已收回')
    lend_date = models.DateField(blank=True, null=True, verbose_name='借出日')
    due_date = models.DateField(blank=True, null=True, verbose_name='约定还款日')
    annual_rate = models.FloatField(default=0, verbose_name='年利率(%)')
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='在借', verbose_name='状态',
    )
    remark = models.CharField(max_length=200, blank=True, null=True, verbose_name='备注')
    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        # 同 WealthLiabilityDetail：不设 Meta.ordering，排序交给服务层
        db_table = 'wealth_receivable_detail'
        verbose_name = '应收借出明细'
        verbose_name_plural = '应收借出明细'
        indexes = [
            models.Index(fields=['user_id', 'status']),
        ]

    def __str__(self):
        return f'{self.counterparty} 借出{self.principal} 已收{self.received}'


# ══════════════════════════════════════════════════════════════
# 账单项分类规则（v3.58.22，P1-C）
#
# 一张规则表同时服务三个维度（收入性质 / 支出刚性 / 现金流归集），
# 而不是建三张 —— 三者都是「按特征给账单项打标签」，匹配机制同构，
# 合并后只需一套维护界面与一套匹配实现。
#
# 🔴 匹配逻辑的**单一真源**是 `services/classify_service.match_classify_rule`。
#    本模型只声明「匹配字段有哪些」，与它对应的是 constants.CLASSIFY_RULE_FIELDS。
#    加一个维度必须**同时改三处**：constants 的字段枚举 +
#    match_classify_rule 的取值分支 + 前端 AttrField 下拉。
#    （漏前端 = 选不到，漏后端 = 静默不生效 —— 与 redemption 归因外挂同款坑。）
#
# 🔴 分类结果**不落库**：账单表是 managed=False 外部表，加不了列，
#    且「分类是当前视角」—— 改规则本就应当回溯地改变往期报表。
#    因此改规则无历史包袱，但 UI 必须给「影响预览」。
# ══════════════════════════════════════════════════════════════


class WealthClassifyRule(models.Model):
    """账单项分类规则：把 (字段, 匹配值) 映射到三个维度的标签

    关键字段口径：
        rule_field   匹配哪个账单项字段 —— category / subcategory / merchant
        match_value  匹配值（精确相等，非模糊匹配、非正则）
        income_type  收入性质（主动/被动/一次性）—— 仅对收入行生效
        expense_nature 支出刚性（固定/可变）—— 仅对支出行生效
        cashflow_class 现金流类别（五类）—— 按收支方向各取一半
        priority     优先级，**数值大者胜**；默认按具体度自动取
                     （merchant 30 > subcategory 20 > category 10）

    ⚠️ 一条规则**可以只设三个标签中的一部分**，也可以一个都不设 ——
        后者是无意义的空规则，由序列化器拦下。
    ⚠️ 三个标签都可为空，是为了让「只想标收入性质」的规则不必被迫
        填一个它并不掌握的支出刚性 —— 猜测比留白更有害。
    """

    # 元组对来自 constants，此处不再写第二份字面量
    RULE_FIELD_CHOICES = CLASSIFY_RULE_FIELDS

    id = models.AutoField(primary_key=True, verbose_name='编号')
    rule_field = models.CharField(
        max_length=20, choices=RULE_FIELD_CHOICES, verbose_name='匹配字段',
    )
    match_value = models.CharField(max_length=100, verbose_name='匹配值')
    income_type = models.CharField(
        max_length=10, choices=INCOME_TYPE_CHOICES,
        blank=True, null=True, verbose_name='收入性质',
    )
    expense_nature = models.CharField(
        max_length=10, choices=EXPENSE_NATURE_CHOICES,
        blank=True, null=True, verbose_name='支出刚性',
    )
    cashflow_class = models.CharField(
        max_length=20, choices=CASHFLOW_CLASS_CHOICES,
        blank=True, null=True, verbose_name='现金流类别',
    )
    priority = models.IntegerField(default=0, verbose_name='优先级(重叠时取高)')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    note = models.CharField(max_length=200, blank=True, null=True, verbose_name='备注')
    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        # 同其他 managed 表：不设 Meta.ordering，排序交给服务层
        # （外部表 ordering 会被注入 SELECT 而静默破坏聚合/去重，项目硬坑②）
        db_table = 'wealth_classify_rule'
        verbose_name = '账单项分类规则'
        verbose_name_plural = '账单项分类规则'
        constraints = [
            # 同一用户下「同字段同匹配值」只允许一条 —— 否则优先级相同的
            # 两条规则谁生效取决于插入顺序，结果不可预测。
            models.UniqueConstraint(
                fields=['user_id', 'rule_field', 'match_value'],
                name='wealth_classify_user_field_value_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['user_id', 'is_active'], name='wealth_cls_user_active_idx'),
        ]

    def __str__(self):
        return f'{self.rule_field}={self.match_value} → {self.income_type or "-"}/' \
               f'{self.expense_nature or "-"}/{self.cashflow_class or "-"}'
