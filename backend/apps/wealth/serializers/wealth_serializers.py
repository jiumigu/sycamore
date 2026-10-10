import re

from rest_framework import serializers

from ..constants import (
    ASSET_CATEGORIES,
    CASHFLOW_CLASSES,
    CLASSIFY_RULE_FIELD_KEYS,
    EXPENSE_NATURES,
    INCOME_TYPES,
)
from ..models import (
    WealthBillList, WealthLifeWeekCalendar, WealthCurrentScenario, WealthScenarioHistory,
    WealthCashFlow, WealthBalanceList, WealthLiabilityDetail, WealthReceivableDetail,
    WealthAssetAccount, WealthClassifyRule,
)


class WeekCalendarSerializer(serializers.ModelSerializer):
    """周历序列化器 — 含聚合收支"""

    income = serializers.SerializerMethodField()
    expense = serializers.SerializerMethodField()
    net = serializers.SerializerMethodField()
    net_level = serializers.SerializerMethodField()

    class Meta:
        model = WealthLifeWeekCalendar
        fields = [
            'global_week_index', 'age_year', 'week_number',
            'week_start_date', 'week_end_date', 'is_lived',
            'income', 'expense', 'net', 'net_level',
        ]

    def get_income(self, obj) -> float:
        return getattr(obj, '_income', 0.0)

    def get_expense(self, obj) -> float:
        return getattr(obj, '_expense', 0.0)

    def get_net(self, obj) -> float:
        return getattr(obj, '_net', 0.0)

    def get_net_level(self, obj) -> str:
        return getattr(obj, '_net_level', 'zero')


class CurrentScenarioSerializer(serializers.ModelSerializer):
    """当前推演状态序列化器"""

    class Meta:
        model = WealthCurrentScenario
        fields = '__all__'
        read_only_fields = ['snapshot_time', 'support_weeks', 'end_age', 'end_week']


class ScenarioHistorySerializer(serializers.ModelSerializer):
    """推演历史序列化器"""

    class Meta:
        model = WealthScenarioHistory
        fields = '__all__'
        read_only_fields = ['snapshot_time']


class CoverageInputSerializer(serializers.Serializer):
    """推演输入参数"""
    current_age = serializers.IntegerField(min_value=18, max_value=78)
    current_week = serializers.IntegerField(min_value=1, max_value=52)
    current_cash = serializers.DecimalField(max_digits=14, decimal_places=2)
    daily_budget = serializers.DecimalField(max_digits=10, decimal_places=2)
    daily_interest_rate = serializers.DecimalField(max_digits=10, decimal_places=8, default=0)


class BudgetInputSerializer(serializers.Serializer):
    """反算输入参数：给定本金与目标天数，求每日可提取额

    与 CoverageInputSerializer 的差异：只收「净额」相关输入，不收年龄/周数
    （反算不需要起点位置，它算的是「从现在起 n 天」）。
    月被动收入折算仍由前端处理，后端只认净额——与正算保持同一分工。
    """
    current_cash = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)
    # 天数带小数（如 10.5 年 = 3835.44 天），由前端按单位换算后传入
    target_days = serializers.FloatField(min_value=1, max_value=200000)
    daily_interest_rate = serializers.DecimalField(max_digits=10, decimal_places=8, default=0)


class LifeSummarySerializer(serializers.Serializer):
    """人生总览"""
    total_income = serializers.FloatField()
    total_expense = serializers.FloatField()
    total_net = serializers.FloatField()
    surplus_rate = serializers.FloatField()
    lived_weeks = serializers.IntegerField()
    surplus_weeks = serializers.IntegerField()
    deficit_weeks = serializers.IntegerField()
    # 计量窗口（19–60 岁）—— 以上指标均在此窗口内统计
    window_start_age = serializers.IntegerField()
    window_end_age = serializers.IntegerField()
    window_weeks = serializers.IntegerField()


class DailyBillSerializer(serializers.Serializer):
    """单笔账单"""
    id = serializers.IntegerField()
    transaction_type = serializers.CharField()
    category = serializers.CharField()
    subcategory = serializers.CharField(allow_null=True)
    amount = serializers.FloatField()
    project = serializers.CharField(allow_null=True, required=False)
    account = serializers.CharField(allow_null=True, required=False)
    merchant = serializers.CharField(allow_null=True, required=False)
    notes = serializers.CharField(allow_null=True, required=False)
    date = serializers.DateTimeField()


class DailyDetailSerializer(serializers.Serializer):
    """单日明细"""
    income_total = serializers.FloatField()
    expense_total = serializers.FloatField()
    net = serializers.FloatField()
    income_list = DailyBillSerializer(many=True)
    expense_list = DailyBillSerializer(many=True)


class MonthlyDaySerializer(serializers.Serializer):
    """月度日历中的单日数据"""
    date = serializers.CharField()
    day = serializers.IntegerField()
    income = serializers.FloatField()
    expense = serializers.FloatField()
    net = serializers.FloatField()
    summary_text = serializers.CharField()
    color_level = serializers.CharField()


class MonthlyCalendarSerializer(serializers.Serializer):
    """月度日历"""
    year = serializers.IntegerField()
    month = serializers.IntegerField()
    days = MonthlyDaySerializer(many=True)


class MonthlySummarySerializer(serializers.Serializer):
    """月度汇总"""
    total_income = serializers.FloatField()
    total_expense = serializers.FloatField()
    balance = serializers.FloatField()
    avg_daily_expense = serializers.FloatField()
    max_daily_income = serializers.FloatField()
    max_daily_expense = serializers.FloatField()
    expense_top3 = serializers.ListField()
    income_top3 = serializers.ListField()


class BillCreateSerializer(serializers.Serializer):
    """快速记账"""
    transaction_type = serializers.ChoiceField(choices=['收入', '支出'])
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    category = serializers.CharField(max_length=50, allow_blank=True)
    subcategory = serializers.CharField(max_length=50, allow_blank=True, required=False)
    project = serializers.CharField(max_length=100, allow_blank=True, required=False)
    account = serializers.CharField(max_length=50, allow_blank=True, required=False)
    merchant = serializers.CharField(max_length=100, allow_blank=True, required=False)
    notes = serializers.CharField(allow_blank=True, required=False)
    date = serializers.DateTimeField()

class BillSerializer(serializers.ModelSerializer):
    """账单明细（清单 CRUD：备注 notes / 商户 merchant / 必要性 necessity 可编辑）"""

    class Meta:
        model = WealthBillList
        fields = [
            'id', 'transaction_type', 'date', 'category', 'subcategory',
            'necessity', 'period_tag', 'project', 'account', 'amount', 'merchant', 'notes', 'user_id',
        ]
        read_only_fields = ['id', 'user_id']

    def validate(self, attrs: dict) -> dict:
        # 必要性标签仅对支出有意义：收入行一律清空兜底
        ttype = attrs.get('transaction_type') or getattr(self.instance, 'transaction_type', None)
        if ttype == '收入':
            attrs['necessity'] = ''
        # ⚠️ period_tag 不照搬 necessity 的清空逻辑：收入侧同样需要标记（离职尾款 / 稿费等性质不同）
        # 自动推导（窗口外）与人工修正在视图层/前端处理，序列化器仅透传
        return attrs

    def _fill_derived(self, validated_data: dict) -> dict:
        from django.utils import timezone
        now = timezone.now()
        validated_data.setdefault('created_at', now)
        validated_data.setdefault('updated_at', now)
        dt = validated_data.get('date')
        if dt is not None:
            validated_data.setdefault('year', dt.year)
            validated_data.setdefault('month', dt.month)
            validated_data.setdefault('day', dt.day)
        return validated_data

    def create(self, validated_data):
        return super().create(self._fill_derived(validated_data))

    def update(self, instance, validated_data):
        from django.utils import timezone
        validated_data['updated_at'] = timezone.now()
        return super().update(instance, validated_data)


# ─── 月度复盘序列化器 ───


class MonthlyReviewSerializer(serializers.Serializer):
    """月度复盘汇总"""
    year = serializers.IntegerField()
    month = serializers.IntegerField()
    month_name = serializers.CharField()
    income = serializers.FloatField()
    expense = serializers.FloatField()
    balance = serializers.FloatField()
    savings_rate = serializers.FloatField()
    avg_daily_expense = serializers.FloatField()
    max_daily_income = serializers.FloatField(allow_null=True)
    max_daily_expense = serializers.FloatField(allow_null=True)
    max_daily_income_detail = serializers.DictField(allow_null=True)
    max_daily_expense_detail = serializers.DictField(allow_null=True)
    deposit = serializers.FloatField(allow_null=True)
    # 余额的**来源**（2026-10-03）：'asset_snapshot' 资产盘点 / 'legacy' 历史手填 / None 无
    deposit_source = serializers.CharField(allow_null=True)
    deposit_as_of = serializers.CharField(allow_null=True)
    notes = serializers.CharField()
    from_balance_list = serializers.BooleanField()
    mom_change = serializers.DictField()


class TrendDataSerializer(serializers.Serializer):
    """趋势数据项"""
    yearmon = serializers.CharField()
    income = serializers.FloatField()
    expense = serializers.FloatField()
    balance = serializers.FloatField()
    savings_rate = serializers.FloatField()
    deposit = serializers.FloatField(allow_null=True)


class CategoryRankingSerializer(serializers.Serializer):
    """分类排行项"""
    category = serializers.CharField()
    amount = serializers.FloatField()
    percentage = serializers.FloatField()


class MonthlyListItemSerializer(serializers.Serializer):
    """历史复盘列表项"""
    yearmon = serializers.CharField()
    income = serializers.FloatField()
    expense = serializers.FloatField()
    balance = serializers.FloatField(allow_null=True)
    deposit = serializers.FloatField(allow_null=True)
    # 余额来源：'asset_snapshot'（取资产盘点该月净值）/ 'legacy'（历史手填）/ None（都没有）
    # 🔴 前端**按这个键**决定怎么标注，不按值猜。
    deposit_source = serializers.CharField(allow_null=True)
    deposit_as_of = serializers.CharField(allow_null=True)
    savings_rate = serializers.FloatField()
    notes = serializers.CharField()


class MonthlyListSerializer(serializers.Serializer):
    """历史复盘列表"""
    items = MonthlyListItemSerializer(many=True)
    total = serializers.IntegerField()
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()


class CompareSerializer(serializers.Serializer):
    """同比环比分析"""
    current = serializers.DictField()
    mom = serializers.DictField()
    yoy = serializers.DictField(allow_null=True)


class BalanceInfoSerializer(serializers.ModelSerializer):
    """月度复盘数据 CRUD —— **只服务「流」**（收入 / 支出 / 结余 / 备注）。

    ⚠️ 改这个类之前必读两条（详见
    `docs/wealth_balance_list-字段退役决策稿-20261003.md`）：

    1. 🔴 这里的 `balance` **不是** DB 列 `wealth_balance_list.balance`（流水余额），
       而是下面 `get_balance()` 返回的 `mbalance`（每月余额 = 收入 − 支出）。
       DB 那个 `balance` 列被本序列化器**完全遮蔽**，永不出现在响应体里 ——
       即「同名不同义」。前端 `MonthlyListItem.balance`（列表「结余」列）读的
       就是这里，**改名前先想清楚**。
    2. 🔴 余额类 / 存量类列已于 2026-10-03 **退役**，不再出现在 `fields` 里：
       `balance`（真身，流水余额）、`accumulationfund`（公积金）、`distance`（距离）、
       `borrow`（借贷）、`lend`（借出）、`realnum`（真正在手里的）。
       它们的真源已收口到「资产盘点」(`wealth_asset_snapshot` +
       `wealth_asset_snapshot_item`)。**别再顺手加回来** —— 加回来就等于重新
       开出第二个录入口，两个来源迟早对不上，而界面上看不出来。
       读取面在 `review_service`（余额以资产盘点为准，历史期次回落手填值）。

    `btime` / `user_id` 一并摘除：前端从不送、后端从不读
    （`btime` 在 2026-06 起的行上恒 NULL，`user_id` 全表 NULL）。
    将来若要做「复盘日期」，正确做法是**后端在保存时写入**、前端只读，
    而不是让表单多一个问用户的输入框。
    """

    income = serializers.SerializerMethodField()
    expense = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()
    notes = serializers.SerializerMethodField()

    class Meta:
        model = WealthBalanceList
        fields = ['yearmon', 'wageincome', 'otherincome', 'outmoney', 'mbalance',
                   # ⚠️ 这个 'balance' **必须留着**：它指的是上面声明的
                   # `balance = SerializerMethodField()`（返回 mbalance = 每月余额），
                   # **不是** DB 列 `wealth_balance_list.balance`。
                   # DRF 会断言「已声明的字段必须在 fields 里」—— 摘掉它直接 500。
                   'balance', 'total', 'remarks',
                   'income', 'expense', 'notes']
        extra_kwargs = {
            'wageincome': {'required': False, 'default': 0},
            'otherincome': {'required': False, 'default': 0},
            'outmoney': {'required': False, 'default': 0},
            'mbalance': {'required': False, 'default': 0},
            'remarks': {'required': False, 'allow_blank': True},
            # 历史手填值：**只读**。展示走 review_service（余额以资产盘点为准），
            # 这里封掉写入面 —— 修正历史请补一期资产盘点快照，别再开第二个录入口。
            'total': {'read_only': True},
        }

    def get_income(self, obj) -> float:
        return (obj.wageincome or 0) + (obj.otherincome or 0)

    def get_expense(self, obj) -> float:
        return obj.outmoney or 0

    def get_balance(self, obj) -> float:
        return obj.mbalance or 0

    def get_notes(self, obj) -> str:
        return obj.remarks or ''


# ─── 现金盘点序列化器 ───


class AccountSummarySerializer(serializers.Serializer):
    """资产汇总

    口径（v3.58.19 纠偏）：
        total / financial_assets = 活期账户 + 公积金
        total_assets             = financial_assets + 应收借出
        net_worth                = total_assets − 负债（与 realnum 同值，realnum 为兼容保留）
    """
    flow_total = serializers.FloatField()
    total = serializers.FloatField()
    financial_assets = serializers.FloatField()
    total_assets = serializers.FloatField()
    net_worth = serializers.FloatField()
    borrow = serializers.FloatField()
    lend = serializers.FloatField()
    realnum = serializers.FloatField()


class ExpenseEstimateMonthSerializer(serializers.Serializer):
    """三点估算窗口内**有支出记录**的某个月"""
    ym_key = serializers.IntegerField()
    year = serializers.IntegerField()
    month = serializers.IntegerField()
    amount = serializers.FloatField()


class ExpenseEstimateSerializer(serializers.Serializer):
    """应急金分母的三点估算底稿（PERT，v3.58.24）

        E = (O + 4M + P) ÷ 6

    O = 窗口内最小月支出（`optimistic`）、M = 中位数（`likely`）、
    P = 最大月支出（`pessimistic`）；`mean` 是算术平均，仅作对照、
    **不参与估算**（一并下发是为了让「三点估算 vs 简单平均」可比）。

    🔴 `value` 为 null 表示**算不出来**（窗口内有记录的月份不足
       `months_required`），不是 0 —— 0 是「月支出为零」这个结论，
       会推出「应急金月数无穷」，与「没有数据」完全相反。

    ⚠️ `detail` 里是**金额**，前端渲染必须走脱敏函数；
       `ym_keys` 含无记录的月份（新 → 旧），用于说明窗口覆盖范围。
    """
    value = serializers.FloatField(allow_null=True)
    optimistic = serializers.FloatField(allow_null=True)
    likely = serializers.FloatField(allow_null=True)
    pessimistic = serializers.FloatField(allow_null=True)
    mean = serializers.FloatField(allow_null=True)
    median = serializers.FloatField(allow_null=True)
    months_with_records = serializers.IntegerField()
    months_required = serializers.IntegerField()
    window_months = serializers.IntegerField()
    anchor_yearmon = serializers.CharField()
    ym_keys = serializers.ListField(child=serializers.IntegerField())
    detail = ExpenseEstimateMonthSerializer(many=True)
    reason = serializers.CharField(allow_null=True)


class HealthMetricsSerializer(serializers.Serializer):
    """资产健康指标

    应急金以「月数」判定（绝对金额阈值会与支出水平脱钩）：
        emergency_fund_months = emergency_fund ÷ expense_estimate.value
        emergency_gap         = max(目标金额 − 应急金, 0)
    分母 `expense_estimate.value` 为 null（窗口内有记录的月份不足）时，
    三个派生字段均为 null —— **不回落成 0**。

    🔴 v3.58.24 起分母换口径：由「近 3 个月算术平均」改为「近 12 个完整月
       支出的三点估算（PERT）」，计算在 `services/expense_estimate.py`，
       与比率面板的应急金月数**共用同一实现** —— 此前两处各算各的
       （一边 SQL 全量支出、一边分类台账已剔除转账），同一个指标在
       两张卡上会是两个数。

    🔴 v3.58.23 起**判定级别也由后端下发**（`emergency_months_level` /",
       `_level_label` / `_pct`，以及活期占比 / 负债率 / 公积金占比的
       `*_level` / `*_level_label`）：此前前端用 `months >= target / 2`、
       `ratio > 30 ? warn : ...` 一类表达式自己算警戒线，等于阈值仍由前端
       定义 —— 改后端常量不会改变界面结论，P0「把阈值搬回后端」这件事
       只做了一半。现在卡上四项的档位全部来自 `constants.RATIO_BANDS`，
       前端只上色、不做除法、不持有任何阈值数字。
    """
    emergency_fund = serializers.FloatField()
    emergency_fund_months = serializers.FloatField(allow_null=True)
    emergency_months_target = serializers.FloatField()
    emergency_months_level = serializers.CharField(allow_null=True)
    emergency_months_level_label = serializers.CharField(allow_null=True)
    emergency_months_pct = serializers.FloatField(allow_null=True)
    emergency_target_amount = serializers.FloatField(allow_null=True)
    emergency_gap = serializers.FloatField(allow_null=True)
    expense_estimate = ExpenseEstimateSerializer(allow_null=True)
    monthly_expense_window = serializers.IntegerField()
    expense_basis_yearmon = serializers.CharField(allow_null=True)
    liquidity_ratio = serializers.FloatField()
    liquidity_ratio_level = serializers.CharField(allow_null=True)
    liquidity_ratio_level_label = serializers.CharField(allow_null=True)
    debt_ratio = serializers.FloatField()
    debt_ratio_level = serializers.CharField(allow_null=True)
    debt_ratio_level_label = serializers.CharField(allow_null=True)
    debt_ratio_legacy = serializers.FloatField()
    provident_fund_ratio = serializers.FloatField()
    provident_fund_ratio_level = serializers.CharField(allow_null=True)
    provident_fund_ratio_level_label = serializers.CharField(allow_null=True)


class CashFlowOverviewSerializer(serializers.Serializer):
    """资产全景"""
    snapshot_date = serializers.CharField(allow_null=True)
    yearmon = serializers.CharField(allow_null=True)
    accounts = serializers.DictField()
    summary = AccountSummarySerializer()
    health_metrics = HealthMetricsSerializer()


class AssetTrendItemSerializer(serializers.Serializer):
    """资产趋势项"""
    yearmon = serializers.CharField()
    flow_total = serializers.FloatField()
    total = serializers.FloatField()
    financial_assets = serializers.FloatField()
    total_assets = serializers.FloatField()
    net_worth = serializers.FloatField()
    accumulationfund = serializers.FloatField()
    zplay = serializers.FloatField()
    wechat = serializers.FloatField()
    jianbank = serializers.FloatField()
    gongbank = serializers.FloatField()
    zhongbank = serializers.FloatField()
    nongbank = serializers.FloatField()
    borrow = serializers.FloatField()
    lend = serializers.FloatField()


class SnapshotListItemSerializer(serializers.Serializer):
    """盘点历史项"""
    baid = serializers.IntegerField()
    yearmon = serializers.CharField(allow_null=True)
    btime = serializers.CharField(allow_null=True)
    flow_total = serializers.FloatField()
    total = serializers.FloatField()
    financial_assets = serializers.FloatField()
    total_assets = serializers.FloatField()
    net_worth = serializers.FloatField()
    zplay = serializers.FloatField()
    wechat = serializers.FloatField()
    cash = serializers.FloatField()
    jianbank = serializers.FloatField()
    gongbank = serializers.FloatField()
    zhongbank = serializers.FloatField()
    nongbank = serializers.FloatField()
    accumulationfund = serializers.FloatField()
    realnum = serializers.FloatField()
    borrow = serializers.FloatField()
    lend = serializers.FloatField()
    remarks = serializers.CharField()


class SnapshotListSerializer(serializers.Serializer):
    """盘点历史列表"""
    items = SnapshotListItemSerializer(many=True)
    total = serializers.IntegerField()
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()


class CashFlowSnapshotSerializer(serializers.ModelSerializer):
    """现金盘点快照 CRUD"""

    class Meta:
        model = WealthCashFlow
        fields = '__all__'


# ─── 定期存款序列化器 ───


class RegularListSerializer(serializers.Serializer):
    """定期存款列表/详情"""
    id = serializers.IntegerField()
    begin_date = serializers.CharField()
    end_date = serializers.CharField()
    value = serializers.FloatField()
    flag = serializers.IntegerField()
    flag_label = serializers.CharField()
    interest = serializers.FloatField(allow_null=True)
    remark = serializers.CharField(allow_null=True)
    bankinfo = serializers.CharField(allow_null=True)
    rate = serializers.FloatField(allow_null=True)
    term_days = serializers.IntegerField()
    calculated_interest = serializers.FloatField()


class RegularStatsSerializer(serializers.Serializer):
    """定期存款统计概览"""
    total_value = serializers.FloatField()
    total_interest = serializers.FloatField()
    ongoing_value = serializers.FloatField()
    matured_value = serializers.FloatField()
    withdrawn_value = serializers.FloatField()
    ongoing_count = serializers.IntegerField()
    matured_count = serializers.IntegerField()
    withdrawn_count = serializers.IntegerField()
    expiring_soon_count = serializers.IntegerField()
    expired_count = serializers.IntegerField()


class RegularFormSerializer(serializers.Serializer):
    """新增/编辑定期存款表单"""
    begin_date = serializers.DateField()
    end_date = serializers.DateField()
    value = serializers.FloatField(min_value=0)
    rate = serializers.FloatField(allow_null=True, required=False)
    bankinfo = serializers.CharField(allow_blank=True, required=False)
    remark = serializers.CharField(allow_blank=True, required=False)
    flag = serializers.IntegerField(required=False)
    interest = serializers.FloatField(allow_null=True, required=False)
    user_id = serializers.IntegerField(default=1, required=False)


class MatureProcessSerializer(serializers.Serializer):
    """到期处理表单"""
    action = serializers.ChoiceField(choices=['withdraw', 'renew', 'renew_all'])
    new_rate = serializers.FloatField(allow_null=True, required=False)
    new_end_date = serializers.DateField(allow_null=True, required=False)


class ExpiringItemSerializer(serializers.Serializer):
    """到期提醒项"""
    id = serializers.IntegerField()
    bankinfo = serializers.CharField(allow_null=True)
    value = serializers.FloatField()
    end_date = serializers.CharField()
    days_left = serializers.IntegerField()
    status = serializers.CharField()  # expired / due_soon_7 / due_soon_30 / normal



# ─── 负债明细 / 应收账龄序列化器（v3.58.20，P1-A）───


class LiabilityItemSerializer(serializers.Serializer):
    """负债明细项（含派生：已还本金 / 年利息成本 / 还款优先级）"""
    id = serializers.IntegerField()
    name = serializers.CharField()
    category = serializers.CharField()
    principal = serializers.FloatField()
    outstanding = serializers.FloatField()
    annual_rate = serializers.FloatField()
    start_date = serializers.CharField(allow_null=True)
    due_date = serializers.CharField(allow_null=True)
    repayment_method = serializers.CharField()
    monthly_payment = serializers.FloatField()
    status = serializers.CharField()
    remark = serializers.CharField(allow_blank=True)
    repaid_amount = serializers.FloatField()
    repaid_ratio = serializers.FloatField()
    annual_interest_cost = serializers.FloatField()
    remaining_months = serializers.IntegerField(allow_null=True)
    days_to_due = serializers.IntegerField(allow_null=True)
    priority_by_rate = serializers.IntegerField(allow_null=True)
    priority_by_balance = serializers.IntegerField(allow_null=True)
    created_at = serializers.CharField(allow_null=True)
    updated_at = serializers.CharField(allow_null=True)


class LiabilityCategorySerializer(serializers.Serializer):
    """负债分类分布项（仅统计在还）"""
    category = serializers.CharField()
    count = serializers.IntegerField()
    outstanding = serializers.FloatField()
    monthly_payment = serializers.FloatField()
    share = serializers.FloatField()


class PrepayFocusSerializer(serializers.Serializer):
    """「先还哪一笔」：雪崩法（利率序）与雪球法（余额序）各自的首笔"""
    by_rate = serializers.CharField(allow_null=True)
    by_balance = serializers.CharField(allow_null=True)


class LiabilitySummarySerializer(serializers.Serializer):
    """负债汇总（含与最新快照 borrow 的对账差）

    borrow_diff = 台账剩余本金合计 − 快照 borrow，正数表示台账多于快照。
    """
    as_of = serializers.CharField()
    count = serializers.IntegerField()
    active_count = serializers.IntegerField()
    settled_count = serializers.IntegerField()
    total_principal = serializers.FloatField()
    total_outstanding = serializers.FloatField()
    total_monthly_payment = serializers.FloatField()
    weighted_avg_rate = serializers.FloatField()
    highest_rate_item = serializers.DictField(allow_null=True)
    annual_interest_cost = serializers.FloatField()
    by_category = LiabilityCategorySerializer(many=True)
    prepay_focus = PrepayFocusSerializer()
    snapshot_borrow = serializers.FloatField(allow_null=True)
    borrow_diff = serializers.FloatField(allow_null=True)


class LiabilityFormSerializer(serializers.ModelSerializer):
    """负债新增/编辑（金额非负、年利率 0–100、到期日不得早于起借日）"""

    class Meta:
        model = WealthLiabilityDetail
        fields = [
            'id', 'name', 'category', 'principal', 'outstanding', 'annual_rate',
            'start_date', 'due_date', 'repayment_method', 'monthly_payment',
            'status', 'remark',
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'name': {'required': True, 'allow_blank': False},
            'remark': {'required': False, 'allow_blank': True},
            'start_date': {'required': False, 'allow_null': True},
            'due_date': {'required': False, 'allow_null': True},
            'principal': {'required': False, 'min_value': 0},
            'outstanding': {'required': False, 'min_value': 0},
            'annual_rate': {'required': False, 'min_value': 0, 'max_value': 100},
            'monthly_payment': {'required': False, 'min_value': 0},
            'category': {'required': False},
            'repayment_method': {'required': False},
            'status': {'required': False},
        }

    def validate(self, attrs):
        start = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        due = attrs.get('due_date', getattr(self.instance, 'due_date', None))
        if start and due and due < start:
            raise serializers.ValidationError({'due_date': '到期日不得早于起借日'})
        return attrs


class ReceivableItemSerializer(serializers.Serializer):
    """应收借出明细项（含派生：未收回余额 / 账龄 / 逾期）"""
    id = serializers.IntegerField()
    counterparty = serializers.CharField()
    principal = serializers.FloatField()
    received = serializers.FloatField()
    outstanding = serializers.FloatField()
    recovery_ratio = serializers.FloatField()
    lend_date = serializers.CharField(allow_null=True)
    due_date = serializers.CharField(allow_null=True)
    annual_rate = serializers.FloatField()
    status = serializers.CharField()
    remark = serializers.CharField(allow_blank=True)
    aging_days = serializers.IntegerField(allow_null=True)
    aging_bucket = serializers.CharField()
    is_long_aging = serializers.BooleanField()
    is_overdue = serializers.BooleanField()
    overdue_days = serializers.IntegerField()
    annual_interest_income = serializers.FloatField()
    created_at = serializers.CharField(allow_null=True)
    updated_at = serializers.CharField(allow_null=True)


class AgingBucketSerializer(serializers.Serializer):
    """账龄分布桶（5 段固定 + 「未填借出日」，份额合计恒为 100%）"""
    bucket = serializers.CharField()
    count = serializers.IntegerField()
    amount = serializers.FloatField()
    share = serializers.FloatField()


class ReceivableSummarySerializer(serializers.Serializer):
    """应收汇总（含与最新快照 lend 的对账差）

    lend_diff = 未收回余额合计 − 快照 lend，正数表示台账多于快照。
    """
    as_of = serializers.CharField()
    count = serializers.IntegerField()
    active_count = serializers.IntegerField()
    bad_debt_count = serializers.IntegerField()
    total_lent = serializers.FloatField()
    total_received = serializers.FloatField()
    total_outstanding = serializers.FloatField()
    active_outstanding = serializers.FloatField()
    bad_debt_amount = serializers.FloatField()
    recovery_ratio = serializers.FloatField()
    overdue_count = serializers.IntegerField()
    overdue_amount = serializers.FloatField()
    max_overdue_days = serializers.IntegerField()
    long_aging_count = serializers.IntegerField()
    interest_income_annual = serializers.FloatField()
    interest_free_amount = serializers.FloatField()
    interest_free_ratio = serializers.FloatField()
    aging = AgingBucketSerializer(many=True)
    snapshot_lend = serializers.FloatField(allow_null=True)
    lend_diff = serializers.FloatField(allow_null=True)


class ReceivableFormSerializer(serializers.ModelSerializer):
    """应收借出新增/编辑（金额非负、年利率 0–100、约定还款日不得早于借出日）"""

    class Meta:
        model = WealthReceivableDetail
        fields = [
            'id', 'counterparty', 'principal', 'received', 'lend_date',
            'due_date', 'annual_rate', 'status', 'remark',
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'counterparty': {'required': True, 'allow_blank': False},
            'remark': {'required': False, 'allow_blank': True},
            'lend_date': {'required': False, 'allow_null': True},
            'due_date': {'required': False, 'allow_null': True},
            'principal': {'required': False, 'min_value': 0},
            'received': {'required': False, 'min_value': 0},
            'annual_rate': {'required': False, 'min_value': 0, 'max_value': 100},
            'status': {'required': False},
        }

    def validate(self, attrs):
        lend = attrs.get('lend_date', getattr(self.instance, 'lend_date', None))
        due = attrs.get('due_date', getattr(self.instance, 'due_date', None))
        if lend and due and due < lend:
            raise serializers.ValidationError({'due_date': '约定还款日不得早于借出日'})
        return attrs


# ─── 资产科目 / 资产快照序列化器（v3.58.21，P1-B）───


class AssetAccountItemSerializer(serializers.Serializer):
    """资产科目（读）"""
    id = serializers.IntegerField()
    code = serializers.CharField(allow_null=True)
    name = serializers.CharField()
    category = serializers.CharField()
    account_kind = serializers.CharField()
    institution = serializers.CharField(allow_blank=True)
    is_liquid = serializers.BooleanField()
    include_in_balance_sheet = serializers.BooleanField()
    sort = serializers.IntegerField()
    is_active = serializers.BooleanField()
    note = serializers.CharField(allow_blank=True)
    used_snapshot_count = serializers.IntegerField()
    created_at = serializers.CharField(allow_null=True)
    updated_at = serializers.CharField(allow_null=True)


class AssetCategoryStatSerializer(serializers.Serializer):
    """科目结构：按类别的科目数"""
    category = serializers.CharField()
    count = serializers.IntegerField()
    counted = serializers.IntegerField()
    liquid = serializers.IntegerField()


class AssetAccountSummarySerializer(serializers.Serializer):
    """科目结构汇总（主数据无金额，只统计结构）"""
    total = serializers.IntegerField()
    active_count = serializers.IntegerField()
    inactive_count = serializers.IntegerField()
    liquid_count = serializers.IntegerField()
    counted_count = serializers.IntegerField()
    excluded_count = serializers.IntegerField()
    used_count = serializers.IntegerField()
    by_category = AssetCategoryStatSerializer(many=True)


class AssetAccountFormSerializer(serializers.ModelSerializer):
    """资产科目新增/编辑

    `code` 是 (user_id, code) 唯一键的一半，但模型上没写 unique=True
    （因为要允许多行 NULL），DRF 因此不会自动生成唯一性校验 ——
    必须手写 validate_code，否则重复的 code 会以 IntegrityError(500) 而不是
    400 的形式炸出来。
    """

    class Meta:
        model = WealthAssetAccount
        fields = [
            'id', 'code', 'name', 'category', 'account_kind', 'institution',
            'is_liquid', 'include_in_balance_sheet', 'sort', 'is_active', 'note',
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'name': {'required': True, 'allow_blank': False},
            'code': {'required': False, 'allow_null': True, 'allow_blank': True},
            'institution': {'required': False, 'allow_null': True, 'allow_blank': True},
            'note': {'required': False, 'allow_null': True, 'allow_blank': True},
        }

    def validate_category(self, value):
        if value not in ASSET_CATEGORIES:
            raise serializers.ValidationError(f'资产类别必须是 {" / ".join(ASSET_CATEGORIES)} 之一')
        return value

    def validate_code(self, value):
        """空串归一为 None —— 否则 '' 会占用一个唯一键位，第二个空 code 直接 500"""
        code = (value or '').strip() or None
        if not code:
            return None
        user_id = self.context.get('user_id', 1)
        qs = WealthAssetAccount.objects.filter(user_id=user_id, code=code)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(f'映射码 {code} 已被其他科目占用')
        return code


class SeedResultSerializer(serializers.Serializer):
    """初始化科目结果"""
    created = serializers.IntegerField()
    kept = serializers.IntegerField()
    updated = serializers.IntegerField()
    total = serializers.IntegerField()
    overwrite = serializers.BooleanField()


class AssetSnapshotItemRowSerializer(serializers.Serializer):
    """快照明细行（读，已带科目属性快照）"""
    account_id = serializers.IntegerField()
    code = serializers.CharField(allow_null=True)
    name = serializers.CharField()
    category = serializers.CharField()
    account_kind = serializers.CharField()
    is_liquid = serializers.BooleanField()
    include_in_balance_sheet = serializers.BooleanField()
    amount = serializers.FloatField()


class AssetSnapshotRowSerializer(serializers.Serializer):
    """快照（读）：头 + 汇总恒等式 + 可选明细行

    汇总字段由服务层 rollup_items 算出，**视图层不得再算一遍**。
    `items` 用 required=False：列表接口刻意不带明细（省流量），
    详情接口才有 —— 缺字段即省略，不会报错。
    """
    id = serializers.IntegerField()
    yearmon = serializers.CharField()
    snapshot_date = serializers.CharField(allow_null=True)
    lend = serializers.FloatField()
    remarks = serializers.CharField(allow_blank=True)
    # 应收类科目合计 − 快照头 lend：只报差额，不参与任何合计
    receivable_gap = serializers.FloatField()
    liquid_total = serializers.FloatField()
    category_totals = serializers.DictField(child=serializers.FloatField())
    financial_assets = serializers.FloatField()
    self_use_total = serializers.FloatField()
    total_assets = serializers.FloatField()
    borrow = serializers.FloatField()
    net_worth = serializers.FloatField()
    available_net_worth = serializers.FloatField()
    excluded_total = serializers.FloatField()
    counted_count = serializers.IntegerField()
    item_count = serializers.IntegerField()
    created_at = serializers.CharField(allow_null=True)
    updated_at = serializers.CharField(allow_null=True)
    items = AssetSnapshotItemRowSerializer(many=True, required=False)


class AssetSnapshotWriteItemSerializer(serializers.Serializer):
    """快照明细行（写）"""
    account_id = serializers.IntegerField(min_value=1)
    amount = serializers.FloatField(min_value=0)


class AssetSnapshotFormSerializer(serializers.Serializer):
    """快照新增/更新（按 yearmon 幂等，明细全删重建）

    这里只做**能给出字段级报错**的校验；跨表校验（科目是否存在 / 是否停用 /
    是否属于本人）留给服务层，避免同一规则在两处各写一遍。
    """

    yearmon = serializers.CharField(max_length=10)
    snapshot_date = serializers.DateField(required=False, allow_null=True)
    borrow = serializers.FloatField(required=False, min_value=0)
    lend = serializers.FloatField(required=False, min_value=0)
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=255)
    items = AssetSnapshotWriteItemSerializer(many=True, required=False)

    def validate_yearmon(self, value):
        if not re.fullmatch(r'\d{4}-\d{2}', value or ''):
            raise serializers.ValidationError('年月格式应为 YYYY-MM')
        return value

    def validate_items(self, value):
        ids = [i['account_id'] for i in value]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise serializers.ValidationError(f'同一科目只能出现一次，重复的科目 id：{dupes}')
        return value


# ══════════════════════════════════════════════════════════════
# 账单项分类规则（v3.58.22，P1-C）
#
# 汇总类字段由服务层 classify_service 算出，**视图层不得再算一遍**
# （与 P1-B 的 rollup_items 同一条纪律：口径只有一个出处）。
# ══════════════════════════════════════════════════════════════


class ClassifyRuleItemSerializer(serializers.Serializer):
    """分类规则（读）"""
    id = serializers.IntegerField()
    rule_field = serializers.CharField()
    match_value = serializers.CharField()
    income_type = serializers.CharField(allow_null=True)
    expense_nature = serializers.CharField(allow_null=True)
    cashflow_class = serializers.CharField(allow_null=True)
    priority = serializers.IntegerField()
    is_active = serializers.BooleanField()
    note = serializers.CharField(allow_blank=True)
    updated_at = serializers.DateTimeField()


class ClassifyRuleFormSerializer(serializers.ModelSerializer):
    """分类规则新增/编辑

    🔴 `(user_id, rule_field, match_value)` 是唯一键，但模型上没写 unique=True
       （它落在 Meta.constraints 里），DRF **不会**自动生成唯一性校验 ——
       必须手写 validate，否则重复规则会以 IntegrityError(500) 而非 400 炸出。
       这与 P1-B 的 AssetAccountFormSerializer.validate_code 是同一个坑，
       换了个表又踩一次：**凡是不以 `unique=True` 表达的唯一约束，都要手写校验**。

    🔴 三个标签至少要设一个：三个都空的规则命中之后什么都不做，
       是纯粹的死规则，只会在台账里制造「我明明建了规则却没生效」的困惑。
    """

    class Meta:
        model = WealthClassifyRule
        fields = [
            'id', 'rule_field', 'match_value', 'income_type', 'expense_nature',
            'cashflow_class', 'priority', 'is_active', 'note',
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'rule_field': {'required': True},
            'match_value': {'required': True, 'allow_blank': False},
            'income_type': {'required': False, 'allow_null': True, 'allow_blank': True},
            'expense_nature': {'required': False, 'allow_null': True, 'allow_blank': True},
            'cashflow_class': {'required': False, 'allow_null': True, 'allow_blank': True},
            'priority': {'required': False},
            'is_active': {'required': False},
            'note': {'required': False, 'allow_null': True, 'allow_blank': True},
        }

    def validate_rule_field(self, value):
        if value not in CLASSIFY_RULE_FIELD_KEYS:
            raise serializers.ValidationError(
                f'匹配字段必须是 {" / ".join(CLASSIFY_RULE_FIELD_KEYS)} 之一'
            )
        return value

    def validate_match_value(self, value):
        text = (value or '').strip()
        if not text:
            raise serializers.ValidationError('匹配值不能为空')
        return text

    def validate_income_type(self, value):
        return _validate_label(value, INCOME_TYPES, '收入性质')

    def validate_expense_nature(self, value):
        return _validate_label(value, EXPENSE_NATURES, '支出刚性')

    def validate_cashflow_class(self, value):
        return _validate_label(value, CASHFLOW_CLASSES, '现金流类别')

    def validate(self, attrs):
        """跨字段校验：唯一性 + 至少设一个标签。

        ⚠️ 更新（partial）时字段可能缺席，缺席的维度取实例上的现值 ——
           否则「只改备注」的请求会因为「没传 income_type」被判成死规则。
        """
        instance = self.instance
        field = attrs.get('rule_field', getattr(instance, 'rule_field', None))
        value = attrs.get('match_value', getattr(instance, 'match_value', None))
        value = (value or '').strip()

        user_id = self.context.get('user_id', 1)
        qs = WealthClassifyRule.objects.filter(
            user_id=user_id, rule_field=field, match_value=value,
        )
        if instance is not None:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {'match_value': f'「{field}={value}」已有一条规则，同字段同匹配值只能有一条'}
            )

        labels = []
        for key in ('income_type', 'expense_nature', 'cashflow_class'):
            current = attrs.get(key, getattr(instance, key, None))
            if (current or '').strip():
                labels.append(key)
        if not labels:
            raise serializers.ValidationError(
                {'detail': '至少要设置收入性质 / 支出刚性 / 现金流类别中的一个，'
                           '否则这条规则命中后什么都不会发生'}
            )
        return attrs


def _validate_label(value, allowed, label):
    """空串 → None；非枚举值 → 400。三个标签列共用一个校验实现。"""
    text = (value or '').strip()
    if not text:
        return None
    if text not in allowed:
        raise serializers.ValidationError(f'{label}必须是 {" / ".join(allowed)} 之一')
    return text


class ClassifyRuleSummarySerializer(serializers.Serializer):
    """规则结构汇总"""
    total = serializers.IntegerField()
    active = serializers.IntegerField()
    inactive = serializers.IntegerField()
    by_field = serializers.DictField(child=serializers.IntegerField())
    by_dimension = serializers.DictField(child=serializers.IntegerField())
    default_priority = serializers.DictField(child=serializers.IntegerField())
    field_specificity = serializers.DictField(child=serializers.IntegerField())


class SeedClassifyResultSerializer(serializers.Serializer):
    """初始化分类规则结果"""
    created = serializers.IntegerField()
    updated = serializers.IntegerField()
    skipped = serializers.IntegerField()
    total = serializers.IntegerField()
    overwrite = serializers.BooleanField()


class ClassifyPreviewSampleSerializer(serializers.Serializer):
    """影响预览里的样本行（前后标签对照）"""
    date = serializers.DateTimeField()
    category = serializers.CharField(allow_blank=True)
    subcategory = serializers.CharField(allow_blank=True)
    merchant = serializers.CharField(allow_blank=True)
    transaction_type = serializers.CharField()
    amount = serializers.FloatField()
    before = serializers.DictField(allow_null=True)
    after = serializers.DictField(allow_null=True)


class ClassifyPreviewSerializer(serializers.Serializer):
    """候选规则影响预览（不写库）"""
    rule_field = serializers.CharField()
    match_value = serializers.CharField()
    priority = serializers.IntegerField()
    matched_count = serializers.IntegerField()
    matched_amount = serializers.FloatField()
    changed_count = serializers.IntegerField()
    changed_amount = serializers.FloatField()
    by_transaction_type = serializers.DictField(child=serializers.IntegerField())
    samples = ClassifyPreviewSampleSerializer(many=True)
    period_label = serializers.CharField()


class ClassifyIncomeBlockSerializer(serializers.Serializer):
    total = serializers.FloatField()
    count = serializers.IntegerField()
    by_type = serializers.DictField(child=serializers.FloatField())
    unclassified = serializers.FloatField()


class ClassifyExpenseBlockSerializer(serializers.Serializer):
    total = serializers.FloatField()
    count = serializers.IntegerField()
    by_nature = serializers.DictField(child=serializers.FloatField())
    unclassified = serializers.FloatField()


class ClassifyCoverageSerializer(serializers.Serializer):
    """三个维度各自的覆盖率（分母各不相同，见服务层说明）"""
    income_type = serializers.FloatField()
    expense_nature = serializers.FloatField()
    cashflow_class = serializers.FloatField()


class ClassifyExcludedSerializer(serializers.Serializer):
    """被排除的收支类型 —— 显式列出，不静默丢弃"""
    transaction_type = serializers.CharField()
    count = serializers.IntegerField()
    amount = serializers.FloatField()


class ClassifySummarySerializer(serializers.Serializer):
    """归类汇总（三个维度 + 覆盖率 + 排除项）"""
    yearmon = serializers.CharField(allow_null=True)
    period_label = serializers.CharField()
    bill_count = serializers.IntegerField()
    bill_amount = serializers.FloatField()
    income = ClassifyIncomeBlockSerializer()
    expense = ClassifyExpenseBlockSerializer()
    cashflow = serializers.DictField(child=serializers.FloatField())
    coverage = ClassifyCoverageSerializer()
    excluded = ClassifyExcludedSerializer(many=True)


class UnclassifiedGroupSerializer(serializers.Serializer):
    """未归类候选（按 分类/子分类 聚合）"""
    category = serializers.CharField(allow_blank=True)
    subcategory = serializers.CharField(allow_blank=True)
    count = serializers.IntegerField()
    amount = serializers.FloatField()
    transaction_types = serializers.ListField(child=serializers.CharField())
    missing_dimensions = serializers.ListField(child=serializers.CharField())
    suggested_field = serializers.CharField()
    suggested_value = serializers.CharField(allow_blank=True)
    merchant_samples = serializers.ListField(child=serializers.CharField())


class UnclassifiedCandidatesSerializer(serializers.Serializer):
    """未归类候选清单（含总额，便于显示「还有多少钱没归类」）"""
    yearmon = serializers.CharField(allow_null=True)
    period_label = serializers.CharField()
    total_count = serializers.IntegerField()
    total_amount = serializers.FloatField()
    items = UnclassifiedGroupSerializer(many=True)


# ══════════════════════════════════════════════════════════════
# 比率体系（v3.58.23，P2-A）
#
# 这些序列化器**只做形状声明，不做任何计算**：
# 分子分母、判定区间、级别全由 ratio_service 算好后原样透传 ——
# 「口径只有一个出处」这条纪律在比率上是双向的：
#   前端不重算（避免两处实现漂移）；
#   视图层也不重算（序列化器更不该算）。
# ══════════════════════════════════════════════════════════════


class RatioLegSerializer(serializers.Serializer):
    """比率的分子 / 分母 —— 让「这个数怎么来的」有据可查"""
    label = serializers.CharField()
    value = serializers.FloatField(allow_null=True)


class RatioMetaSerializer(serializers.Serializer):
    """比率的**口径元信息** —— 气泡提示的数据源（v3.58.24）

    与 `RatioItemSerializer` 的区别：那一份带**这一期的值**，
    这一份只有「这个指标是什么、怎么算、分几档」——
    与期别无关，故可以一次取回、长期复用。

    🔴 `note` 是口径说明（分子分母怎么取、什么情况下算不出），
       与 `formula` 一样**只从 `constants.RATIO_BANDS` 来**。
       前端不要在组件里另写一份口径文案 —— 那个数字一变，
       界面上的说明就会开始撒谎，而且没人会发现。

    ⚠️ 本接口覆盖**九项**（六项比率 + 卡片专用三项），
       比 `RATIO_ORDER` 多 —— 后者是「比率面板展示哪些」，
       不是「总表里有哪些」。
    """
    key = serializers.CharField()
    label = serializers.CharField()
    unit = serializers.CharField()
    direction = serializers.CharField()
    formula = serializers.CharField()
    note = serializers.ListField(child=serializers.CharField())
    bands = serializers.ListField(child=serializers.ListField(), allow_null=True)
    target = serializers.FloatField(allow_null=True)


class RatioItemSerializer(serializers.Serializer):
    """单项比率

    `bands` 是**区间本身**（`[下界, 上界|null, level, 中文标签]` 的数组），
    一并下发的目的是让前端能画刻度，而**不必复制任何阈值数字** ——
    这一条是 P2-A 的核心：阈值从此只在 constants.RATIO_BANDS 里存在一份。
    `available=False` 时 `value` 必为 null，`reason` 说明为什么算不出来。
    """
    key = serializers.CharField()
    label = serializers.CharField()
    unit = serializers.CharField()
    direction = serializers.CharField()
    formula = serializers.CharField()
    note = serializers.ListField(child=serializers.CharField())
    value = serializers.FloatField(allow_null=True)
    bands = serializers.ListField(child=serializers.ListField(), allow_null=True)
    target = serializers.FloatField(allow_null=True)
    level = serializers.CharField(allow_null=True)
    level_label = serializers.CharField(allow_null=True)
    numerator = RatioLegSerializer(allow_null=True)
    denominator = RatioLegSerializer(allow_null=True)
    available = serializers.BooleanField()
    reason = serializers.CharField(allow_null=True)
    hint = serializers.CharField(allow_blank=True)
    extra = serializers.DictField()


class RatioGapSerializer(serializers.Serializer):
    """不可用比率的原因清单（含补救动作）"""
    key = serializers.CharField()
    label = serializers.CharField()
    reason = serializers.CharField(allow_null=True)
    hint = serializers.CharField(allow_blank=True)


class RatioAssetPositionSerializer(serializers.Serializer):
    """比率用到的资产位置 —— 让「分子取自哪一期、哪张表」可见

    `carried=True` 表示「这个数取自更早的一期」（本月尚未盘点）。
    不显示这个标记的话，用户会以为本月已经盘点过。
    `available=False` 时其余金额字段为 null，由 `reason` 说明原因 ——
    形状保持一致，前端不必为「有/无数据」写两套取值分支。
    """
    available = serializers.BooleanField()
    yearmon = serializers.CharField(allow_null=True)
    snapshot_date = serializers.DateField(allow_null=True)
    source = serializers.CharField(allow_null=True)
    liquid = serializers.FloatField(allow_null=True)
    receivable = serializers.FloatField(allow_null=True)
    financial_assets = serializers.FloatField(allow_null=True)
    self_use_total = serializers.FloatField(allow_null=True)
    total_assets = serializers.FloatField(allow_null=True)
    borrow = serializers.FloatField(allow_null=True)
    net_worth = serializers.FloatField(allow_null=True)
    carried = serializers.BooleanField()
    reason = serializers.CharField(allow_null=True)


class LiabilityStateSerializer(serializers.Serializer):
    """负债台账状态 —— 让 DTI 的「为什么不可用」说准"""
    total = serializers.IntegerField()
    active = serializers.IntegerField()
    state = serializers.CharField()


class RatioOverviewSerializer(serializers.Serializer):
    """比率总览"""
    anchor_yearmon = serializers.CharField()
    asset_source = serializers.CharField(allow_null=True)
    asset_source_label = serializers.CharField()
    asset_position = RatioAssetPositionSerializer()
    liability_state = LiabilityStateSerializer()
    windows = serializers.DictField()
    ratios = RatioItemSerializer(many=True)
    gaps = RatioGapSerializer(many=True)


class RatioTrendPointSerializer(serializers.Serializer):
    """趋势上的一个点 —— `available=False` 表示该月算不出（不是 0）"""
    ym = serializers.CharField()
    value = serializers.FloatField(allow_null=True)
    level = serializers.CharField(allow_null=True)
    level_label = serializers.CharField(allow_null=True)
    available = serializers.BooleanField()


class RatioTrendExcludedSerializer(serializers.Serializer):
    """不参与趋势的比率及原因"""
    key = serializers.CharField()
    label = serializers.CharField()
    reason = serializers.CharField()


class RatioTrendSerializer(serializers.Serializer):
    """比率趋势

    ⚠️ `series` 的每个点带 `available` 而不是用 0 填空：
       趋势图上「这个月没盘点」必须画成断点，画成 0 会被读成
       「这个月净值没变化」——那是完全相反的两个结论。
    """
    months = serializers.ListField(child=serializers.CharField())
    asset_source = serializers.CharField(allow_null=True)
    series = serializers.DictField(child=serializers.ListField())
    excluded = RatioTrendExcludedSerializer(many=True)
