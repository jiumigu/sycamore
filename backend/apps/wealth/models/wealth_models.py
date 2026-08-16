from django.db import models


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
    wageincome = models.FloatField(db_column='wageIncome', blank=True, null=True, verbose_name='工资收入')
    otherincome = models.FloatField(db_column='otherIncome', blank=True, null=True, verbose_name='其他收入')
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
