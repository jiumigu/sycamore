from rest_framework import serializers

from .models import WealthLifeWeekCalendar, WealthCurrentScenario, WealthScenarioHistory, WealthCashFlow, WealthBalanceList


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


class LifeSummarySerializer(serializers.Serializer):
    """人生总览"""
    total_income = serializers.FloatField()
    total_expense = serializers.FloatField()
    total_net = serializers.FloatField()
    surplus_rate = serializers.FloatField()
    lived_weeks = serializers.IntegerField()
    surplus_weeks = serializers.IntegerField()
    deficit_weeks = serializers.IntegerField()


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
    deposit_balance = serializers.FloatField(allow_null=True)
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
    """月度复盘数据 CRUD"""

    income = serializers.SerializerMethodField()
    expense = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()
    notes = serializers.SerializerMethodField()

    class Meta:
        model = WealthBalanceList
        fields = ['yearmon', 'wageincome', 'otherincome', 'outmoney', 'mbalance',
                   'balance', 'accumulationfund', 'total', 'remarks', 'distance',
                   'borrow', 'lend', 'realnum', 'user_id', 'btime',
                   'income', 'expense', 'notes']
        extra_kwargs = {
            'wageincome': {'required': False, 'default': 0},
            'otherincome': {'required': False, 'default': 0},
            'outmoney': {'required': False, 'default': 0},
            'mbalance': {'required': False, 'default': 0},
            'remarks': {'required': False, 'allow_blank': True},
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
    """资产汇总"""
    flow_total = serializers.FloatField()
    total = serializers.FloatField()
    borrow = serializers.FloatField()
    lend = serializers.FloatField()
    realnum = serializers.FloatField()


class HealthMetricsSerializer(serializers.Serializer):
    """资产健康指标"""
    emergency_fund = serializers.FloatField()
    liquidity_ratio = serializers.FloatField()
    debt_ratio = serializers.FloatField()
    provident_fund_ratio = serializers.FloatField()


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


class ReconcileItemSerializer(serializers.Serializer):
    """对账项"""
    yearmon = serializers.CharField()
    book_balance = serializers.FloatField()
    actual_total = serializers.FloatField()
    difference = serializers.FloatField()
    status = serializers.CharField()


class ReconcileSummarySerializer(serializers.Serializer):
    """对账汇总"""
    matched = serializers.IntegerField()
    mismatched = serializers.IntegerField()


class ReconcileSerializer(serializers.Serializer):
    """对账结果"""
    items = ReconcileItemSerializer(many=True)
    summary = ReconcileSummarySerializer()


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
