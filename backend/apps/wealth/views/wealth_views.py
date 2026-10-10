from datetime import date, datetime, timedelta

from django.conf import settings
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView, CreateAPIView
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from django.db.models import Case, Count, DateField, DecimalField, F, ProtectedError, Q, Sum, Value, When
from django.db.models.functions import Cast

# 账单侧赎回归属词表单一真源（与时间侧 L1 归因**同源不同轴**，见 constants 注释）
from apps.temporal.constants import PERIOD_TAG_CHOICES

from ..models import (
    WealthLifeWeekCalendar, WealthCurrentScenario, WealthScenarioHistory,
    WealthBillList, WealthLiabilityDetail, WealthReceivableDetail,
    WealthAssetAccount, WealthAssetSnapshot,
    WealthClassifyRule,
)
from ..serializers import (
    WeekCalendarSerializer, CurrentScenarioSerializer, ScenarioHistorySerializer,
    CoverageInputSerializer, BudgetInputSerializer, LifeSummarySerializer,
    MonthlyCalendarSerializer, DailyDetailSerializer, MonthlySummarySerializer,
    BillCreateSerializer, BillSerializer,
    MonthlyReviewSerializer, TrendDataSerializer, CategoryRankingSerializer,
    MonthlyListSerializer, CompareSerializer, BalanceInfoSerializer,
    CashFlowOverviewSerializer, AssetTrendItemSerializer,
    SnapshotListSerializer, CashFlowSnapshotSerializer,
    RegularListSerializer, RegularStatsSerializer, RegularFormSerializer,
    MatureProcessSerializer, ExpiringItemSerializer,
    LiabilityItemSerializer, LiabilitySummarySerializer, LiabilityFormSerializer,
    ReceivableItemSerializer, ReceivableSummarySerializer, ReceivableFormSerializer,
    AssetAccountItemSerializer, AssetAccountSummarySerializer, AssetAccountFormSerializer,
    SeedResultSerializer, AssetSnapshotRowSerializer, AssetSnapshotFormSerializer,
    ClassifyRuleItemSerializer, ClassifyRuleFormSerializer, ClassifyRuleSummarySerializer,
    SeedClassifyResultSerializer, ClassifyPreviewSerializer,
    ClassifySummarySerializer, UnclassifiedCandidatesSerializer,
    RatioMetaSerializer, RatioOverviewSerializer, RatioTrendSerializer,
)
from ..constants import (
    WINDOW_START_AGE, WINDOW_END_AGE, WINDOW_WEEKS,
    WINDOW_START_INDEX, WINDOW_END_INDEX,
    CLASSIFY_CANDIDATE_LIMIT,
)
from ..services.calendar_init import init_week_calendar_for_user, update_lived_status
from ..services.week_aggregator import (
    aggregate_weekly_net_income, get_net_level, current_age_week,
)
from ..services.coverage_calculator import calculate_coverage, calculate_daily_budget
from ..services.monthly_aggregator import (
    aggregate_monthly_days, get_daily_detail, calculate_monthly_summary,
)
from ..services.review_service import (
    get_monthly_review, get_trend_data, get_category_ranking,
    get_monthly_list, get_compare_data, generate_balance_info,
)
from ..services.cashflow_service import (
    get_cashflow_overview, get_asset_trend, get_snapshot_list,
    create_or_update_snapshot, copy_last_month,
    get_cashflow_by_yearmon,
)
from ..services.debt_service import (
    get_liability_list, get_liability_summary,
    get_receivable_list, get_receivable_summary,
)
from ..services.asset_service import (
    get_account_list, get_account_summary,
    create_account, update_account, delete_account, seed_asset_accounts,
    list_snapshots, get_snapshot_detail, get_snapshot_by_yearmon,
    save_snapshot, delete_snapshot,
)
from ..services.regular_service import (
    get_stats, get_regular_list, get_regular_detail,
    create_regular, update_regular, delete_regular,
    process_mature, get_expiring_regulars, get_expired_regulars,
    update_all_status, get_available_banks, calculate_interest,
    FLAG_ONGOING, FLAG_MATURED, FLAG_WITHDRAWN,
)
from ..services.classify_service import (
    get_rule_list, get_rule_summary,
    create_rule, update_rule, delete_rule, seed_classify_rules,
    preview_rule_impact,
    classify_summary, get_unclassified_candidates, available_periods,
)
from ..services.ratio_service import (
    get_ratio_overview, get_ratio_trend, available_anchor_months,
    resolve_asset_position,
)
from ..services.ratio_grade import all_ratio_meta


def calculate_current_age_week():
    """当前年龄与周数 —— **读周历表**，不按出生日期现算。

    旧实现用 `settings.WEALTH_BIRTH_DATE` + `today.isocalendar()[1]` 现算，
    而周历表的 `age_year` 是按日历年年序编的、周数以「当年第一个周一」为第 1 周 ——
    两把尺子在跨年处错开整整一年，推演起点因此落在历史终点之后 52 周，
    热力图 31/32 岁之间出现一条缺口。真源与理由详见
    `services/week_aggregator.current_age_week`。
    """
    return current_age_week()


class CurrentAgeWeekView(APIView):
    """当前年龄与周数（基于出生日期动态计算）"""

    def get(self, request):
        return Response(calculate_current_age_week())


class WeekCalendarView(ListAPIView):
    """周历列表 — 含聚合收支"""

    serializer_class = WeekCalendarSerializer
    queryset = WealthLifeWeekCalendar.objects.all().order_by('global_week_index')
    pagination_class = None  # heatmap needs all 3172 entries at once

    def get_queryset(self):
        update_lived_status()
        qs = super().get_queryset()
        user_id = self.request.query_params.get('user_id', 1)
        age = self.request.query_params.get('age')
        lived_only = self.request.query_params.get('lived_only', 'false')

        qs = qs.filter(user_id=user_id)
        if age:
            qs = qs.filter(age_year=age)
        if lived_only == 'true':
            qs = qs.filter(is_lived=True)

        # 聚合收支数据注入
        aggregated = aggregate_weekly_net_income(int(user_id))
        for obj in qs:
            week_data = aggregated.get(obj.global_week_index, {})
            obj._income = week_data.get('income', 0.0)
            obj._expense = week_data.get('expense', 0.0)
            obj._net = week_data.get('net', 0.0)
            obj._net_level = get_net_level(obj._net)

        return qs


class WeeklySummaryView(RetrieveAPIView):
    """单周明细"""

    serializer_class = WeekCalendarSerializer
    queryset = WealthLifeWeekCalendar.objects.all()
    lookup_field = 'global_week_index'

    def retrieve(self, request, *args, **kwargs):
        update_lived_status()
        instance = self.get_object()
        aggregated = aggregate_weekly_net_income(instance.user_id)
        week_data = aggregated.get(instance.global_week_index, {})
        instance._income = week_data.get('income', 0.0)
        instance._expense = week_data.get('expense', 0.0)
        instance._net = week_data.get('net', 0.0)
        instance._net_level = get_net_level(instance._net)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class CurrentScenarioView(APIView):
    """当前推演状态 — 读写"""

    def get(self, request):
        scenario, _ = WealthCurrentScenario.objects.get_or_create(
            pk=1, defaults={
                'current_age': 30, 'current_week': 1,
                'current_cash': 0, 'daily_budget': 0,
            },
        )
        serializer = CurrentScenarioSerializer(scenario)
        return Response(serializer.data)

    def put(self, request):
        scenario, _ = WealthCurrentScenario.objects.get_or_create(
            pk=1, defaults={
                'current_age': 30, 'current_week': 1,
                'current_cash': 0, 'daily_budget': 0,
            },
        )
        serializer = CurrentScenarioSerializer(scenario, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CalculateCoverageView(CreateAPIView):
    """现金流推演计算"""

    serializer_class = CoverageInputSerializer

    def create(self, request, *args, **kwargs):
        serializer = CoverageInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        daily_interest_rate = float(data.get('daily_interest_rate', 0))
        coverage, support_weeks, end_age, end_week = calculate_coverage(
            start_age=data['current_age'],
            start_week=data['current_week'],
            cash=float(data['current_cash']),
            daily_budget=float(data['daily_budget']),
            daily_interest_rate=daily_interest_rate,
            max_age=WINDOW_END_AGE,  # 推演只算到计量窗口末端（60 岁）
        )

        # 保存到当前推演
        scenario_support = support_weeks if support_weeks is not None else 9999
        scenario, _ = WealthCurrentScenario.objects.get_or_create(pk=1)
        scenario.current_age = data['current_age']
        scenario.current_week = data['current_week']
        scenario.current_cash = data['current_cash']
        scenario.daily_budget = data['daily_budget']
        scenario.daily_interest_rate = daily_interest_rate
        scenario.support_weeks = scenario_support
        scenario.end_age = end_age
        scenario.end_week = end_week
        scenario.save()

        # 写入历史
        WealthScenarioHistory.objects.create(
            current_age=data['current_age'],
            current_week=data['current_week'],
            current_cash=data['current_cash'],
            daily_budget=data['daily_budget'],
            daily_interest_rate=daily_interest_rate,
            support_weeks=scenario_support,
            note='',
        )

        return Response({
            'coverage_weeks': coverage,
            'support_weeks': support_weeks,
            'end_age': end_age,
            'end_week': end_week,
            'daily_interest_rate': daily_interest_rate,
            # 计量窗口信息：前端据此显示「覆盖至 60 岁」而不是一个会跨出窗口的年数
            'window_start_age': WINDOW_START_AGE,
            'window_end_age': WINDOW_END_AGE,
            'window_weeks': WINDOW_WEEKS,
            'reached_window_end': end_age is None,
        })


class CalculateBudgetView(APIView):
    """现金流反算：给定本金与目标天数 → 每日可提取额。

    与正算 `CalculateCoverageView` 的关系是**互为反函数**，共用
    `calculate_daily_budget` / `calculate_coverage` 同一套现金流假设。

    🔴 与正算的关键差异：正算是「用户点一次按钮」的低频动作，会落
    `WealthCurrentScenario` + `WealthScenarioHistory`；反算则由前端**输入即算**
    高频触发（调「撑几年」时数字跟着动），故**必须是纯试算、零写库**。
    违反这条会把历史表灌满无意义的中间态记录。
    """

    def post(self, request):
        serializer = BudgetInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        cash = float(data['current_cash'])
        days = float(data['target_days'])
        daily_interest_rate = float(data.get('daily_interest_rate', 0))

        daily_budget = calculate_daily_budget(
            cash=cash, days=days, daily_interest_rate=daily_interest_rate,
        )

        return Response({
            'daily_budget': round(daily_budget, 2),
            'target_days': days,
            'current_cash': cash,
            'daily_interest_rate': daily_interest_rate,
        })


class LifeSummaryView(APIView):
    """人生总览统计"""

    def get(self, request):
        user_id = request.query_params.get('user_id', 1)
        aggregated = aggregate_weekly_net_income(int(user_id))

        # 只在**计量窗口**（19–60 岁）内统计：窗口外的 18 岁与 61–78 岁两段
        # 本就无记录，收支总额不受影响；但「已度过周数」这类计数型指标会随
        # 口径变化（18 岁起算 713 周 → 19 岁起算 661 周），结余周占比的分母同此。
        window = {
            idx: v for idx, v in aggregated.items()
            if WINDOW_START_INDEX <= idx <= WINDOW_END_INDEX
        }

        total_income = sum(v['income'] for v in window.values())
        total_expense = sum(v['expense'] for v in window.values())
        total_net = total_income - total_expense

        lived_weeks = len(window)
        surplus_weeks = sum(1 for v in window.values() if v['net'] > 0)
        deficit_weeks = sum(1 for v in window.values() if v['net'] < 0)

        surplus_rate = round(surplus_weeks / lived_weeks * 100, 1) if lived_weeks > 0 else 0.0

        data = {
            'total_income': round(total_income, 2),
            'total_expense': round(total_expense, 2),
            'total_net': round(total_net, 2),
            'surplus_rate': surplus_rate,
            'lived_weeks': lived_weeks,
            'surplus_weeks': surplus_weeks,
            'deficit_weeks': deficit_weeks,
            'window_start_age': WINDOW_START_AGE,
            'window_end_age': WINDOW_END_AGE,
            'window_weeks': WINDOW_WEEKS,
        }
        serializer = LifeSummarySerializer(data)
        return Response(serializer.data)


class BillsByWeekView(APIView):
    """按周查询账单明细

    ⚠️ 路径是 `bills/by_week/`，**不是** `bills/<pk>/` 下的子路径 ——
    它靠 `urls.py` 里「静态路径在前、DRF 路由器兜底」的顺序才不会被详情路由抢走。
    顺序一旦被改回去，这里会变成 404，而前端会把 404 显示成「本周无账单」。
    （v3.60.16 的现场，用例见 tests/test_bills_by_week.py）
    """

    def get(self, request):
        raw = request.query_params.get('week_index')
        user_id = request.query_params.get('user_id', 1)

        if not raw:
            return Response({'error': 'week_index is required'}, status=status.HTTP_400_BAD_REQUEST)

        # 索引是**整数**：响应里的 `week_index` 与前端 `BillsByWeekResponse.week_index: number`
        # 必须同为数字。之前直接把 query 里的字符串回传，声明与实际不符 —— 前端一旦用它
        # 做比较就会静默不等（'713' !== 713）。
        try:
            week_index = int(raw)
        except (TypeError, ValueError):
            return Response({'error': 'week_index must be an integer'},
                            status=status.HTTP_400_BAD_REQUEST)

        week = WealthLifeWeekCalendar.objects.filter(
            global_week_index=week_index, user_id=user_id
        ).first()
        if not week:
            return Response({'error': 'week not found'}, status=status.HTTP_404_NOT_FOUND)

        # wealth_bill_list 为外部遗留表（无 ORM 模型），原生 SQL 为唯一访问方式
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, transaction_type, category, subcategory, amount, date, notes AS note
                FROM wealth_bill_list
                WHERE user_id = %s
                  AND date >= %s AND date < %s
                ORDER BY date
            """, [user_id, week.week_start_date, week.week_end_date + timedelta(days=1)])

            columns = ['id', 'transaction_type', 'category', 'subcategory', 'amount', 'date', 'note']
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        return Response({
            'week_index': week_index,
            'week_start': week.week_start_date,
            'week_end': week.week_end_date,
            'bills': rows,
        })


class InitCalendarView(APIView):
    """初始化周历"""

    def post(self, request):
        user_id = request.data.get('user_id', 1)
        birth_date = request.data.get('birth_date')

        from datetime import date
        if birth_date:
            from datetime import date, datetime
            birth_date = datetime.strptime(birth_date, '%Y-%m-%d').date()
        else:
            from django.conf import settings
            birth_str = getattr(settings, 'WEALTH_BIRTH_DATE', '1995-01-01')
            birth_date = date.fromisoformat(birth_str)

        created = init_week_calendar_for_user(user_id, birth_date)
        updated = update_lived_status()

        return Response({
            'created': created,
            'marked_lived': updated,
            'total_weeks': 3172,
        })


class MonthlyCalendarView(APIView):
    """月度日历数据"""

    def get(self, request):
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        user_id = request.query_params.get('user_id', 1)

        if not year or not month:
            return Response({'error': 'year and month are required'}, status=status.HTTP_400_BAD_REQUEST)

        year, month = int(year), int(month)
        days = aggregate_monthly_days(int(user_id), year, month)
        data = {'year': year, 'month': month, 'days': days}
        serializer = MonthlyCalendarSerializer(data)
        return Response(serializer.data)


class DailyDetailView(APIView):
    """单日收支明细"""

    def get(self, request):
        date_str = request.query_params.get('date')
        user_id = request.query_params.get('user_id', 1)

        if not date_str:
            return Response({'error': 'date is required'}, status=status.HTTP_400_BAD_REQUEST)

        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        detail = get_daily_detail(int(user_id), target_date)
        serializer = DailyDetailSerializer(detail)
        return Response(serializer.data)


class MonthlySummaryView(APIView):
    """月度汇总统计"""

    def get(self, request):
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        user_id = request.query_params.get('user_id', 1)

        if not year or not month:
            return Response({'error': 'year and month are required'}, status=status.HTTP_400_BAD_REQUEST)

        summary = calculate_monthly_summary(int(user_id), int(year), int(month))
        serializer = MonthlySummarySerializer(summary)
        return Response(serializer.data)


class BillCreateView(CreateAPIView):
    """快速记账"""

    serializer_class = BillCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = BillCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        dt = data['date']
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO wealth_bill_list
                    (transaction_type, category, subcategory, project, account,
                     merchant, notes, amount, date, user_id,
                     year, month, day, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """, [
                data['transaction_type'],
                data.get('category', ''),
                data.get('subcategory', ''),
                data.get('project', ''),
                data.get('account', ''),
                data.get('merchant', ''),
                data.get('notes', ''),
                data['amount'],
                dt,
                request.data.get('user_id', 1),
                dt.year, dt.month, dt.day,
            ])
            bill_id = cursor.lastrowid

        return Response({
            'success': True,
            'bill_id': bill_id,
        }, status=status.HTTP_201_CREATED)


# ═══════════════════════════════════════════════
# 月度复盘 API
# ═══════════════════════════════════════════════


class MonthlyReviewView(APIView):
    """月度复盘汇总"""

    def get(self, request):
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        user_id = request.query_params.get('user_id', 1)

        if not year or not month:
            return Response({'error': 'year and month are required'}, status=status.HTTP_400_BAD_REQUEST)

        data = get_monthly_review(int(user_id), int(year), int(month))
        serializer = MonthlyReviewSerializer(data)
        return Response(serializer.data)


class TrendView(APIView):
    """收支趋势数据"""

    def get(self, request):
        user_id = request.query_params.get('user_id', 1)
        months = request.query_params.get('months', 12)
        data = get_trend_data(int(user_id), int(months))
        serializer = TrendDataSerializer(data, many=True)
        return Response(serializer.data)


class CategoryRankingView(APIView):
    """分类排行"""

    def get(self, request):
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        tx_type = request.query_params.get('type', '支出')
        user_id = request.query_params.get('user_id', 1)

        if not year or not month:
            return Response({'error': 'year and month are required'}, status=status.HTTP_400_BAD_REQUEST)

        data = get_category_ranking(int(user_id), int(year), int(month), tx_type)
        serializer = CategoryRankingSerializer(data, many=True)
        return Response(serializer.data)


class MonthlyListView(APIView):
    """历史复盘列表"""

    def get(self, request):
        user_id = request.query_params.get('user_id', 1)
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 12))
        data = get_monthly_list(int(user_id), page, page_size)
        serializer = MonthlyListSerializer(data)
        return Response(serializer.data)


class BalanceListView(APIView):
    """月度复盘数据 CRUD"""

    def get(self, request):
        yearmon = request.query_params.get('yearmon')
        if not yearmon:
            return Response({'error': 'yearmon is required'}, status=status.HTTP_400_BAD_REQUEST)

        from ..models import WealthBalanceList
        try:
            bi = WealthBalanceList.objects.get(yearmon=yearmon)
            serializer = BalanceInfoSerializer(bi)
            return Response(serializer.data)
        except WealthBalanceList.DoesNotExist:
            return Response(None, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        yearmon = request.data.get('yearmon')
        if not yearmon:
            return Response({'error': 'yearmon is required'}, status=status.HTTP_400_BAD_REQUEST)

        from ..models import WealthBalanceList
        existing = WealthBalanceList.objects.filter(yearmon=yearmon).first()
        serializer = BalanceInfoSerializer(existing, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED if not existing else status.HTTP_200_OK)

    def put(self, request):
        yearmon = request.data.get('yearmon')
        if not yearmon:
            return Response({'error': 'yearmon is required'}, status=status.HTTP_400_BAD_REQUEST)

        from ..models import WealthBalanceList
        try:
            bi = WealthBalanceList.objects.get(yearmon=yearmon)
        except WealthBalanceList.DoesNotExist:
            return Response({'error': 'record not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = BalanceInfoSerializer(bi, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CompareView(APIView):
    """同比环比分析"""

    def get(self, request):
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        user_id = request.query_params.get('user_id', 1)

        if not year or not month:
            return Response({'error': 'year and month are required'}, status=status.HTTP_400_BAD_REQUEST)

        data = get_compare_data(int(user_id), int(year), int(month))
        serializer = CompareSerializer(data)
        return Response(serializer.data)


class GenerateBalanceInfoView(APIView):
    """生成复盘数据（从账单聚合到 balance_list）"""

    def post(self, request):
        year = request.data.get('year')
        month = request.data.get('month')
        user_id = request.data.get('user_id', 1)

        if not year or not month:
            return Response({'error': 'year and month are required'}, status=status.HTTP_400_BAD_REQUEST)

        obj = generate_balance_info(int(user_id), int(year), int(month))
        serializer = BalanceInfoSerializer(obj)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ═══════════════════════════════════════════════
# 现金盘点 API
# ═══════════════════════════════════════════════


class CashFlowOverviewView(APIView):
    """资产全景"""

    def get(self, request):
        yearmon = request.query_params.get('yearmon')
        if yearmon:
            data = get_cashflow_by_yearmon(yearmon)
        else:
            data = get_cashflow_overview()

        if not data:
            return Response({'error': 'no cash flow data found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CashFlowOverviewSerializer(data)
        return Response(serializer.data)


class AssetTrendView(APIView):
    """资产趋势"""

    def get(self, request):
        user_id = request.query_params.get('user_id', 1)
        months = int(request.query_params.get('months', 12))
        data = get_asset_trend(int(user_id), months)
        serializer = AssetTrendItemSerializer(data, many=True)
        return Response(serializer.data)


class SnapshotListView(APIView):
    """盘点历史列表"""

    def get(self, request):
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 12))
        data = get_snapshot_list(page, page_size)
        serializer = SnapshotListSerializer(data)
        return Response(serializer.data)


class SnapshotView(APIView):
    """盘点快照 CRUD"""

    def post(self, request):
        obj = create_or_update_snapshot(request.data)
        serializer = CashFlowSnapshotSerializer(obj)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def put(self, request):
        obj = create_or_update_snapshot(request.data)
        serializer = CashFlowSnapshotSerializer(obj)
        return Response(serializer.data)

    def delete(self, request):
        baid = request.data.get('baid') or request.query_params.get('baid')
        if not baid:
            return Response({'error': 'baid is required'}, status=status.HTTP_400_BAD_REQUEST)

        from ..models import WealthCashFlow
        try:
            cf = WealthCashFlow.objects.get(baid=baid)
            cf.delete()
            return Response({'success': True})
        except WealthCashFlow.DoesNotExist:
            return Response({'error': 'record not found'}, status=status.HTTP_404_NOT_FOUND)


class CopySnapshotView(APIView):
    """复制上月数据"""

    def post(self, request):
        yearmon = request.data.get('yearmon')
        if not yearmon:
            return Response({'error': 'yearmon is required'}, status=status.HTTP_400_BAD_REQUEST)

        obj = copy_last_month(yearmon)
        if not obj:
            return Response({'error': 'no previous month data found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CashFlowSnapshotSerializer(obj)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ═══════════════════════════════════════════════
# 定期存款 API
# ═══════════════════════════════════════════════


class RegularStatsView(APIView):
    """定期存款统计概览"""

    def get(self, request):
        data = get_stats()
        serializer = RegularStatsSerializer(data)
        return Response(serializer.data)


class RegularExpiringView(APIView):
    """到期提醒列表"""

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        expired = get_expired_regulars()
        expiring = get_expiring_regulars(days)
        today = date.today()

        items = []
        for r in expired:
            items.append({
                'id': r.id,
                'bankinfo': r.bankinfo,
                'value': r.value,
                'end_date': r.end_date.isoformat(),
                'days_left': (r.end_date - today).days,
                'status': 'expired',
            })
        for r in expiring:
            days_left = (r.end_date - today).days
            status = 'due_soon_7' if days_left <= 7 else 'due_soon_30'
            items.append({
                'id': r.id,
                'bankinfo': r.bankinfo,
                'value': r.value,
                'end_date': r.end_date.isoformat(),
                'days_left': days_left,
                'status': status,
            })

        serializer = ExpiringItemSerializer(items, many=True)
        return Response(serializer.data)


class RegularListView(APIView):
    """定期存款列表（支持筛选）"""

    def get(self, request):
        bankinfo = request.query_params.get('bankinfo') or None
        flag_raw = request.query_params.get('flag')
        flag = int(flag_raw) if flag_raw is not None else None
        keyword = request.query_params.get('keyword') or None

        records = get_regular_list(bankinfo, flag, keyword)
        serializer = RegularListSerializer(records, many=True)
        return Response(serializer.data)


class RegularDetailView(APIView):
    """定期存款 CRUD"""

    def get(self, request, pk: int):
        obj = get_regular_detail(pk)
        if not obj:
            return Response({'error': 'record not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = RegularListSerializer(obj)
        return Response(serializer.data)

    def post(self, request, pk: int | None = None):
        serializer = RegularFormSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = create_regular(serializer.validated_data)
        out = RegularListSerializer(obj)
        return Response(out.data, status=status.HTTP_201_CREATED)

    def put(self, request, pk: int):
        serializer = RegularFormSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        obj = update_regular(pk, serializer.validated_data)
        if not obj:
            return Response({'error': 'record not found'}, status=status.HTTP_404_NOT_FOUND)
        out = RegularListSerializer(obj)
        return Response(out.data)

    def delete(self, request, pk: int):
        ok = delete_regular(pk)
        if not ok:
            return Response({'error': 'record not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'success': True})


class RegularMatureView(APIView):
    """到期处理（取出/续存）"""

    def post(self, request, pk: int):
        serializer = MatureProcessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        obj = process_mature(
            pk,
            action=data['action'],
            new_rate=data.get('new_rate'),
            new_end_date=data.get('new_end_date'),
        )
        if not obj:
            return Response({'error': 'record not found'}, status=status.HTTP_404_NOT_FOUND)
        out = RegularListSerializer(obj)
        return Response(out.data)


class RegularBanksView(APIView):
    """银行列表"""

    def get(self, request):
        banks = get_available_banks()
        return Response(banks)


class RegularUpdateStatusView(APIView):
    """批量更新到期状态"""

    def post(self, request):
        count = update_all_status()
        return Response({'updated_count': count})


# ═══════════════════════════════════════════════
# CSV 导入
# ═══════════════════════════════════════════════


class BillImportView(APIView):
    """导入随手记 CSV 账单"""

    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [AllowAny]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': '请上传文件'}, status=status.HTTP_400_BAD_REQUEST)

        import csv
        import io
        from datetime import datetime

        file_data = file.read().decode('utf-8-sig')
        reader = csv.reader(io.StringIO(file_data))
        rows = list(reader)

        if len(rows) < 3:
            return Response({'error': 'CSV 文件格式不正确'}, status=status.HTTP_400_BAD_REQUEST)

        user_id = request.data.get('user_id', 1)
        created = 0
        skipped = 0
        duplicated = 0
        errors = []

        from django.db import connection

        for i, row in enumerate(rows[2:], start=3):
            if len(row) < 8:
                skipped += 1
                continue

            try:
                transaction_type = row[0].strip()
                date_str = row[1].strip()
                category = row[2].strip() if len(row) > 2 else ''
                subcategory = row[3].strip() if len(row) > 3 else ''
                account = row[5].strip() if len(row) > 5 else ''
                amount_str = row[7].strip() if len(row) > 7 else ''
                merchant = row[9].strip() if len(row) > 9 else ''
                notes = row[10].strip() if len(row) > 10 else ''

                if not date_str or not amount_str:
                    skipped += 1
                    continue

                dt = datetime.strptime(date_str[:19], '%Y-%m-%d %H:%M:%S')
                amount = abs(float(amount_str))

                # 按交易日期+金额+类型判断是否已存在
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT COUNT(*) FROM wealth_bill_list WHERE date = %s AND amount = %s AND transaction_type = %s",
                        [dt, amount, transaction_type],
                    )
                    exists = cursor.fetchone()[0] > 0

                if exists:
                    duplicated += 1
                    continue

                with connection.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO wealth_bill_list
                            (transaction_type, category, subcategory, project, account,
                             merchant, notes, amount, date, user_id,
                             year, month, day, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    """, [
                        transaction_type,
                        category,
                        subcategory,
                        '',
                        account,
                        merchant,
                        notes,
                        amount,
                        dt,
                        user_id,
                        dt.year, dt.month, dt.day,
                    ])
                created += 1
            except Exception as e:
                skipped += 1
                errors.append(f'第{i}行: {str(e)}')

        return Response({
            'created': created,
            'skipped': skipped,
            'duplicated': duplicated,
            'total': created + skipped + duplicated,
            'errors': errors[:10],
        })


def _build_contrib_response(rows):
    """rows: [(date, value), ...] → 贡献图统一响应"""
    data = [{'date': d.isoformat(), 'value': round(float(v), 2)} for d, v in rows]
    min_year = min((d.year for d, _ in rows), default=datetime.now().year)
    max_year = max((d.year for d, _ in rows), default=datetime.now().year)
    summary = {
        'total_days': len(data),
        'max_date': max(data, key=lambda x: x['value'])['date'] if data else None,
        'max_value': max((abs(x['value']) for x in data), default=0),
    }
    return {'min_year': min_year, 'max_year': max_year, 'data': data, 'summary': summary}


class BillViewSet(viewsets.ModelViewSet):
    """账单清单 CRUD（列表/新增/编辑/删除，备注 notes 可编辑）"""

    queryset = WealthBillList.objects.all()
    serializer_class = BillSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    # 子分类必须一起搜：列表里「分类」是大类（食品酒水），真正的消费细类（早午晚餐）
    # 只在 subcategory 上；漏了它，用户搜一个真实存在的子分类会静默返回 0 条。
    search_fields = ['notes', 'merchant', 'category', 'subcategory']
    ordering = ['-date']

    def get_queryset(self):
        qs = super().get_queryset().filter(user_id=1)
        params = self.request.query_params
        date_from = params.get('date_from')
        if date_from:
            # datetime 区间直接比较（规避 __date 触发 CONVERT_TZ 时区转换返回 NULL）
            qs = qs.filter(date__gte=datetime.combine(datetime.strptime(date_from, '%Y-%m-%d').date(), datetime.min.time()))
        date_to = params.get('date_to')
        if date_to:
            qs = qs.filter(date__lte=datetime.combine(datetime.strptime(date_to, '%Y-%m-%d').date(), datetime.max.time()))
        ttype = params.get('transaction_type')
        if ttype:
            qs = qs.filter(transaction_type=ttype)
        category = params.get('category')
        if category:
            qs = qs.filter(category=category)
        necessity = params.get('necessity')
        if necessity:
            if necessity == 'unmarked':
                # 未标记：NULL 或空串统一视为未分类
                qs = qs.filter(Q(necessity__isnull=True) | Q(necessity=''))
            else:
                qs = qs.filter(necessity=necessity)
        period_tag = params.get('period_tag')
        if period_tag:
            if period_tag == 'unmarked':
                qs = qs.filter(Q(period_tag__isnull=True) | Q(period_tag=''))
            else:
                qs = qs.filter(period_tag=period_tag)
        return qs

    @action(detail=False, methods=['post'], url_path='batch-necessity')
    def batch_necessity(self, request):
        """批量标记必要性：POST {ids:[...], necessity:'必要'|'可选'|'冲动'}（仅支出行生效）"""
        ids = request.data.get('ids') or []
        necessity = (request.data.get('necessity') or '').strip()
        if not isinstance(ids, list) or not ids:
            return Response({'error': 'ids 必填（数组）'}, status=status.HTTP_400_BAD_REQUEST)
        if necessity not in {'必要', '可选', '冲动'}:
            return Response({'error': 'necessity 仅支持 必要/可选/冲动'}, status=status.HTTP_400_BAD_REQUEST)
        updated = WealthBillList.objects.filter(
            user_id=1, id__in=ids, transaction_type='支出',
        ).update(necessity=necessity)
        return Response({'updated': updated})

    @action(detail=False, methods=['get'], url_path='necessity_stats')
    def necessity_stats(self, request):
        """必要性小结：支出按 必要/可选/冲动/未标记 分组的笔数与金额（可叠加日期/分类筛选）"""
        params = self.request.query_params
        qs = WealthBillList.objects.filter(user_id=1, transaction_type='支出')
        date_from = params.get('date_from')
        if date_from:
            qs = qs.filter(date__gte=datetime.combine(datetime.strptime(date_from, '%Y-%m-%d').date(), datetime.min.time()))
        date_to = params.get('date_to')
        if date_to:
            qs = qs.filter(date__lte=datetime.combine(datetime.strptime(date_to, '%Y-%m-%d').date(), datetime.max.time()))
        category = params.get('category')
        if category:
            qs = qs.filter(category=category)

        rows = (
            qs.values('necessity')
            .annotate(cnt=Count('id'), total=Sum('amount'))
        )
        bucket = {n: {'count': 0, 'total': 0.0} for n in ('必要', '可选', '冲动', 'unmarked')}
        for r in rows:
            n = r['necessity'] or ''
            key = n if n in bucket else 'unmarked'
            bucket[key]['count'] = r['cnt']
            bucket[key]['total'] = round(float(r['total'] or 0), 2)
        # 金额按支出为正数口径返回
        return Response({
            'summary': [
                {'necessity': k, 'count': v['count'], 'total': v['total']}
                for k, v in bucket.items()
            ],
            'grand_count': sum(v['count'] for v in bucket.values()),
            'grand_total': round(sum(v['total'] for v in bucket.values()), 2),
        })

    @action(detail=False, methods=['post'], url_path='batch-period-tag')
    def batch_period_tag(self, request):
        """批量标记赎回归属：POST {ids:[...], period_tag:'为自己'|'过渡'|'为别人'|'不计入'}（收入/支出均生效）"""
        ids = request.data.get('ids') or []
        period_tag = (request.data.get('period_tag') or '').strip()
        if not isinstance(ids, list) or not ids:
            return Response({'error': 'ids 必填（数组）'}, status=status.HTTP_400_BAD_REQUEST)
        if period_tag not in PERIOD_TAG_CHOICES:
            return Response(
                {'error': 'period_tag 仅支持 ' + '/'.join(PERIOD_TAG_CHOICES)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # 与 batch-necessity 不同：此处不做 transaction_type='支出' 限制，收入也要标
        updated = WealthBillList.objects.filter(
            user_id=1, id__in=ids,
        ).update(period_tag=period_tag)
        return Response({'updated': updated})

    @action(detail=False, methods=['get'], url_path='period_tag_stats')
    def period_tag_stats(self, request):
        """赎回归属小结：按 为自己/过渡/为别人/不计入/未标记 分组的笔数与金额（收入支出合计）"""
        params = self.request.query_params
        qs = WealthBillList.objects.filter(user_id=1)
        date_from = params.get('date_from')
        if date_from:
            qs = qs.filter(date__gte=datetime.combine(datetime.strptime(date_from, '%Y-%m-%d').date(), datetime.min.time()))
        date_to = params.get('date_to')
        if date_to:
            qs = qs.filter(date__lte=datetime.combine(datetime.strptime(date_to, '%Y-%m-%d').date(), datetime.max.time()))
        category = params.get('category')
        if category:
            qs = qs.filter(category=category)

        rows = (
            qs.values('period_tag')
            .annotate(cnt=Count('id'), total=Sum('amount'))
        )
        bucket = {n: {'count': 0, 'total': 0.0} for n in (*PERIOD_TAG_CHOICES, 'unmarked')}
        for r in rows:
            n = r['period_tag'] or ''
            key = n if n in bucket else 'unmarked'
            bucket[key]['count'] = r['cnt']
            bucket[key]['total'] = round(float(r['total'] or 0), 2)
        return Response({
            'summary': [
                {'period_tag': k, 'count': v['count'], 'total': v['total']}
                for k, v in bucket.items()
            ],
            'grand_count': sum(v['count'] for v in bucket.values()),
            'grand_total': round(sum(v['total'] for v in bucket.values()), 2),
        })

    @action(detail=False, methods=['get'])
    def daily_detail(self, request):
        # 每日明细：按日期查当日所有账单
        from datetime import datetime

        date_str = request.query_params.get('date')
        if not date_str:
            return Response({'error': 'date 参数必填'}, status=400)
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'date 格式 YYYY-MM-DD'}, status=400)
        ws = datetime.combine(d, datetime.min.time())
        we = datetime.combine(d, datetime.max.time())
        qs = WealthBillList.objects.filter(date__gte=ws, date__lte=we).order_by('date')
        items = [{
            'id': b.id,
            'time': b.date.isoformat() if b.date else None,
            'transaction_type': b.transaction_type,
            'category': b.category or '',
            'merchant': b.merchant or '',
            'amount': float(b.amount or 0),
            'notes': b.notes or '',
        } for b in qs]
        income = round(sum(x['amount'] for x in items if x['transaction_type'] == '收入'), 2)
        expense = round(sum(x['amount'] for x in items if x['transaction_type'] == '支出'), 2)
        return Response({
            'date': date_str,
            'income': income,
            'expense': expense,
            'items': items,
        })

    @action(detail=False, methods=["get"])
    def contrib(self, request):
        """贡献图：单日收支净值（收入 - 支出）聚合"""
        rows = list(
            WealthBillList.objects
            .annotate(d=Cast('date', DateField()))
            .values('d')
            .annotate(
                v=Sum(
                    Case(
                        When(transaction_type='收入', then=F('amount')),
                        When(transaction_type='支出', then=-F('amount')),
                        default=Value(0),
                        output_field=DecimalField(max_digits=14, decimal_places=2),
                    )
                )
            )
            .order_by('d')
            .values_list('d', 'v')
        )
        resp = _build_contrib_response(rows)
        return Response(resp)

    def perform_create(self, serializer):
        serializer.save(user_id=1)


# ══════════════════════════════════════════════════════════════
# 负债明细 / 应收账龄（v3.58.20，P1-A）
#
# 两个 ViewSet 的 list 一律返回**裸数组**（显式 pagination_class = None）：
# 前端按数组消费，被全局分页包成 {count, results} 会静默显示为空（项目硬坑③）。
# 筛选参数只作用于列表；summary 恒为全量口径 —— 局部筛选下的汇总会误导。
# ══════════════════════════════════════════════════════════════


def _pick_item(items: list[dict], pk: int) -> dict:
    """从服务层列表里取出指定 id 的项（新增/编辑后回传完整派生字段）"""
    for item in items:
        if item['id'] == pk:
            return item
    return {}


class LiabilityViewSet(viewsets.ModelViewSet):
    """负债逐笔台账 CRUD + 汇总 + 快照对账"""

    queryset = WealthLiabilityDetail.objects.all()
    serializer_class = LiabilityFormSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return WealthLiabilityDetail.objects.filter(user_id=1)

    def list(self, request, *args, **kwargs):
        items = get_liability_list()
        status_filter = request.query_params.get('status')
        if status_filter:
            items = [i for i in items if i['status'] == status_filter]
        category = request.query_params.get('category')
        if category:
            items = [i for i in items if i['category'] == category]
        return Response(LiabilityItemSerializer(items, many=True).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save(user_id=1)
        return Response(
            _pick_item(get_liability_list(), obj.id), status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.pop('partial', False),
        )
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(_pick_item(get_liability_list(), obj.id))

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        pk = instance.id
        instance.delete()
        return Response({'deleted': pk})

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """汇总：剩余本金 / 月供 / 加权平均利率 / 分类分布 / 与快照 borrow 对账差"""
        return Response(LiabilitySummarySerializer(get_liability_summary()).data)


class ReceivableViewSet(viewsets.ModelViewSet):
    """应收借出逐笔台账 CRUD + 汇总 + 账龄分布"""

    queryset = WealthReceivableDetail.objects.all()
    serializer_class = ReceivableFormSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return WealthReceivableDetail.objects.filter(user_id=1)

    def list(self, request, *args, **kwargs):
        items = get_receivable_list()
        status_filter = request.query_params.get('status')
        if status_filter:
            items = [i for i in items if i['status'] == status_filter]
        bucket = request.query_params.get('aging_bucket')
        if bucket:
            items = [i for i in items if i['aging_bucket'] == bucket]
        return Response(ReceivableItemSerializer(items, many=True).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save(user_id=1)
        return Response(
            _pick_item(get_receivable_list(), obj.id), status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.pop('partial', False),
        )
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(_pick_item(get_receivable_list(), obj.id))

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        pk = instance.id
        instance.delete()
        return Response({'deleted': pk})

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """汇总：未收回 / 回收率 / 账龄分布 / 逾期 / 无息占比 / 与快照 lend 对账差"""
        return Response(ReceivableSummarySerializer(get_receivable_summary()).data)


# ══════════════════════════════════════════════════════════════
# 资产科目主数据 / 资产快照（v3.58.21，P1-B）
#
# 两个端点的列表形态刻意不同，各有理由：
#   · 科目 → **裸数组**（主数据，量小，前端整表渲染）
#   · 快照 → **裸数组 + limit**（月度数据，两年 24 期；粒度上分页器只是噪声）
# 两者都显式 pagination_class = None —— 被 DRF 全局分页包成 {count, results}
# 时前端按数组消费会**静默显示为空**（项目硬坑③）。
#
# 写入一律走服务层（asset_service），视图只做协议转换：
# 校验失败的服务层异常在这里统一转成 400，不泄漏成 500。
# ══════════════════════════════════════════════════════════════


class AssetAccountViewSet(viewsets.ModelViewSet):
    """资产科目主数据 CRUD + 结构汇总 + 初始化种子科目"""

    queryset = WealthAssetAccount.objects.all()
    serializer_class = AssetAccountFormSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return WealthAssetAccount.objects.filter(user_id=1)

    def get_serializer_context(self):
        """把 user_id 交给序列化器 —— validate_code 的唯一性校验需要它"""
        context = super().get_serializer_context()
        context['user_id'] = 1
        return context

    def list(self, request, *args, **kwargs):
        include_inactive = str(
            request.query_params.get('include_inactive', '')
        ).lower() in ('1', 'true', 'yes')
        rows = get_account_list(include_inactive=include_inactive)
        return Response(AssetAccountItemSerializer(rows, many=True).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = create_account(serializer.validated_data)
        return Response(AssetAccountItemSerializer(row).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.pop('partial', False),
        )
        serializer.is_valid(raise_exception=True)
        row = update_account(instance.id, serializer.validated_data)
        return Response(AssetAccountItemSerializer(row).data)

    def destroy(self, request, *args, **kwargs):
        """删除科目 —— 被历史快照引用时转为 400 并引导改「停用」。

        不能让 ProtectedError 冒成 500：那是可预期的业务约束，
        且用户需要一句能照做的提示，而不是一个堆栈。
        """
        instance = self.get_object()
        try:
            pk = delete_account(instance.id)
        except ProtectedError:
            return Response(
                {'detail': '该科目已被历史快照引用，不能删除；请改为「停用」（is_active=false）'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({'deleted': pk})

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """科目结构汇总：各类别科目数、流动性科目数、计表 / 不计表科目数"""
        return Response(AssetAccountSummarySerializer(get_account_summary()).data)

    @action(detail=False, methods=['post'])
    def seed(self, request):
        """从旧表列定义生成种子科目（幂等）。

        overwrite=false（默认）：只补缺失的，不动用户已改过的科目。
        """
        overwrite = str(request.data.get('overwrite', '')).lower() in ('1', 'true', 'yes')
        result = seed_asset_accounts(overwrite=overwrite)
        return Response(SeedResultSerializer(result).data)


class AssetSnapshotViewSet(viewsets.ViewSet):
    """资产快照：按 yearmon 幂等保存（明细行全删重建）+ 与旧口径双跑校验"""

    permission_classes = [AllowAny]

    def list(self, request):
        raw_limit = request.query_params.get('limit') or 24
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            limit = 24
        year = request.query_params.get('year') or None
        rows = list_snapshots(limit=limit, year=year)
        return Response(AssetSnapshotRowSerializer(rows, many=True).data)

    def create(self, request):
        serializer = AssetSnapshotFormSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            row = save_snapshot(serializer.validated_data)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AssetSnapshotRowSerializer(row).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        row = get_snapshot_detail(int(pk))
        if not row:
            return Response({'detail': '快照不存在'}, status=status.HTTP_404_NOT_FOUND)
        return Response(AssetSnapshotRowSerializer(row).data)

    def update(self, request, *args, **kwargs):
        """更新一期快照。

        **不允许改年月**：年月是这一期快照的身份，改年月等于换一期，
        语义上应删除重建。放行「改名」会让明细行跟着悄悄搬到另一期，
        历史账面出现无法解释的迁移 —— 宁可报错也不做这种魔法。
        """
        snapshot = WealthAssetSnapshot.objects.filter(id=kwargs.get('pk'), user_id=1).first()
        if not snapshot:
            return Response({'detail': '快照不存在'}, status=status.HTTP_404_NOT_FOUND)
        serializer = AssetSnapshotFormSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        if payload['yearmon'] != snapshot.yearmon:
            return Response(
                {'detail': f'不能修改快照年月（当前 {snapshot.yearmon}）；'
                           '如需换期请删除后重建'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            row = save_snapshot(payload)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AssetSnapshotRowSerializer(row).data)

    def destroy(self, request, *args, **kwargs):
        snapshot = WealthAssetSnapshot.objects.filter(id=kwargs.get('pk'), user_id=1).first()
        if not snapshot:
            return Response({'detail': '快照不存在'}, status=status.HTTP_404_NOT_FOUND)
        pk = delete_snapshot(snapshot.id)
        return Response({'deleted': pk})

    @action(detail=False, methods=['get'])
    def by_yearmon(self, request):
        """按年月取一期（含明细行）—— 编辑弹窗回填用"""
        yearmon = request.query_params.get('yearmon')
        if not yearmon:
            return Response({'detail': '缺少 yearmon 参数'}, status=status.HTTP_400_BAD_REQUEST)
        row = get_snapshot_by_yearmon(yearmon)
        if not row:
            return Response({'detail': '快照不存在'}, status=status.HTTP_404_NOT_FOUND)
        return Response(AssetSnapshotRowSerializer(row).data)


# ══════════════════════════════════════════════════════════════
# 账单项分类规则 / 归类结果（v3.58.22，P1-C）
#
# 分成两个 ViewSet 不是形式主义，而是因为它们是两类东西：
#   · 分类规则 —— 主数据，可增删改，裸数组；
#   · 归类结果 —— **派生结果，只读、实时算、无主键**。
# 把结果挂到规则 ViewSet 的 detail 路由上会误导人以为结果可以「保存」。
#
# 两个列表端点都显式 pagination_class = None —— 被 DRF 全局分页包成
# {count, results} 时前端按数组消费会**静默显示为空**（项目硬坑③）。
#
# 写入一律走服务层（classify_service），视图只做协议转换：
# 校验失败的服务层异常在这里转 400，不泄漏成 500。
# ══════════════════════════════════════════════════════════════


class ClassifyRuleViewSet(viewsets.ModelViewSet):
    """账单项分类规则：CRUD + 结构汇总 + 初始化种子 + 影响预览"""

    queryset = WealthClassifyRule.objects.all()
    serializer_class = ClassifyRuleFormSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return WealthClassifyRule.objects.filter(user_id=1)

    def get_serializer_context(self):
        """把 user_id 交给序列化器 —— 手写的唯一性校验需要它"""
        context = super().get_serializer_context()
        context['user_id'] = 1
        return context

    def list(self, request, *args, **kwargs):
        include_inactive = str(
            request.query_params.get('include_inactive', '')
        ).lower() in ('1', 'true', 'yes')
        rows = get_rule_list(include_inactive=include_inactive)
        return Response(ClassifyRuleItemSerializer(rows, many=True).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = create_rule(serializer.validated_data)
        return Response(ClassifyRuleItemSerializer(row).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.pop('partial', False),
        )
        serializer.is_valid(raise_exception=True)
        row = update_rule(instance.id, serializer.validated_data)
        return Response(ClassifyRuleItemSerializer(row).data)

    def destroy(self, request, *args, **kwargs):
        """删除规则。

        ⚠️ 这里**刻意没有** PROTECT 型保护（与资产科目不同）：分类结果不落库，
           删规则不破坏任何历史记录，只改变当前视角。
           但「往回看历史报表数字变了」仍会让人困惑，故响应里明确提示
           可改用「停用」—— 停用同样能追溯原因，且可一键恢复。
        """
        instance = self.get_object()
        pk = delete_rule(instance.id)
        return Response({
            'deleted': pk,
            'hint': '规则已删除；往期报表的分类结果会随之重算。'
                    '若只是想暂时不生效，建议改为「停用」。',
        })

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """规则结构汇总：各匹配字段的规则数、各维度覆盖条数、默认优先级"""
        return Response(ClassifyRuleSummarySerializer(get_rule_summary()).data)

    @action(detail=False, methods=['post'])
    def seed(self, request):
        """按真实分类归纳的种子规则初始化（幂等）"""
        overwrite = str(request.data.get('overwrite', '')).lower() in ('1', 'true', 'yes')
        return Response(SeedClassifyResultSerializer(seed_classify_rules(overwrite=overwrite)).data)

    @action(detail=False, methods=['post'])
    def preview(self, request):
        """候选规则影响预览（**不写库**）：命中多少、会改动多少、前后标签对照"""
        yearmon = request.data.get('yearmon') or request.query_params.get('yearmon')
        try:
            result = preview_rule_impact(request.data, yearmon=yearmon)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ClassifyPreviewSerializer(result).data)

    @action(detail=False, methods=['get'])
    def periods(self, request):
        """有账单数据的年月列表（倒序裸数组）—— 前端选择期下拉用"""
        return Response(available_periods())


class ClassifyResultViewSet(viewsets.ViewSet):
    """归类结果（只读）：某期三维度汇总 + 覆盖率 + 未归类候选"""

    permission_classes = [AllowAny]
    pagination_class = None

    def list(self, request):
        """GET /classify/results/?yearmon=YYYY-MM（不传 = 全周期）"""
        yearmon = request.query_params.get('yearmon') or None
        return Response(ClassifySummarySerializer(classify_summary(yearmon)).data)

    @action(detail=False, methods=['get'])
    def unclassified(self, request):
        """未归类候选清单 —— 回答「下一条规则该建在哪儿」"""
        yearmon = request.query_params.get('yearmon') or None
        raw_limit = request.query_params.get('limit')
        limit = CLASSIFY_CANDIDATE_LIMIT
        if raw_limit:
            try:
                limit = max(1, int(raw_limit))
            except (TypeError, ValueError):
                limit = CLASSIFY_CANDIDATE_LIMIT
        rows = get_unclassified_candidates(yearmon=yearmon, limit=limit)
        return Response(UnclassifiedCandidatesSerializer(rows).data)


# ══════════════════════════════════════════════════════════════
# 比率体系（v3.58.23，P2-A）
#
# 只读 ViewSet：比率是**派生结果**，没有主键、不可写、实时算 ——
# 挂成 ModelViewSet 会误导人以为结果可以「保存」。
# 判定区间与级别全部后端算好（含 bands 本身），视图不做任何除法或比较，
# 只做协议转换。
# ══════════════════════════════════════════════════════════════


class RatioViewSet(viewsets.ViewSet):
    """财务规划比率：总览 + 月度趋势 + 可选锚定月"""

    permission_classes = [AllowAny]
    # 显式关闭分页：被 DRF 全局分页包成 {count, results} 时，
    # 前端按数组消费会**静默显示为空**（项目硬坑③）。
    pagination_class = None

    def list(self, request):
        """GET /ratios/?yearmon=YYYY-MM —— 六项比率总览（不传 = 最新一期）"""
        anchor = request.query_params.get('yearmon') or None
        data = get_ratio_overview(anchor_yearmon=anchor)
        return Response(RatioOverviewSerializer(data).data)

    @action(detail=False, methods=['get'])
    def trend(self, request):
        """GET /ratios/trend/?months=12 —— 逐月比率序列（值已算好）"""
        raw = request.query_params.get('months')
        try:
            months = max(1, min(int(raw), 36)) if raw else 12
        except (TypeError, ValueError):
            months = 12
        return Response(RatioTrendSerializer(get_ratio_trend(months=months)).data)

    @action(detail=False, methods=['get'])
    def anchors(self, request):
        """GET /ratios/anchors/ —— 可作为锚定月的年月（倒序裸数组）

        候选来自**资产快照的期别**而非账单期别：锚定月决定的是「看哪一期」，
        选一个没有快照的月份只会得到一屏「数据不足」。
        """
        return Response(available_anchor_months())

    @action(detail=False, methods=['get'])
    def asset_position(self, request):
        """GET /ratios/asset-position/?yearmon=YYYY-MM —— 单期资产位置

        `carry_forward` 默认开：本月未盘点时取上一期，并回 `carried=True`。
        关掉时按期精确命中，没有就返回 404 语义的 200 + available=False ——
        「这一期没有盘点」不是错误，是可预期状态，不该用 404 表达。
        """
        yearmon = request.query_params.get('yearmon') or None
        carry = str(request.query_params.get('carry_forward', '1')).lower() not in (
            '0', 'false', 'no',
        )
        return Response(resolve_asset_position(yearmon, carry_forward=carry))

    @action(detail=False, methods=['get'])
    def meta(self, request):
        """GET /ratios/meta/ —— 九项指标的**口径元信息**（裸数组）

        公式 / 口径说明 / 判定区间都从这里来，前端据此画气泡提示，
        **不另写一份口径文案** —— 两处文案迟早不一致，而且没人会发现。

        ⚠️ 覆盖九项而非六项：资产健康指标卡上的活期占比 / 负债率 /
           公积金占比也在判定线总表里，卡片的气泡提示要取它们。
        返回裸数组（同 anchors）：被全局分页包成 `{count, results}`
        时前端按数组消费会**静默变空**。
        """
        return Response(RatioMetaSerializer(all_ratio_meta(), many=True).data)
