from datetime import date, datetime, timedelta

from django.conf import settings
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView, CreateAPIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import WealthLifeWeekCalendar, WealthCurrentScenario, WealthScenarioHistory
from .serializers import (
    WeekCalendarSerializer, CurrentScenarioSerializer, ScenarioHistorySerializer,
    CoverageInputSerializer, LifeSummarySerializer,
    MonthlyCalendarSerializer, DailyDetailSerializer, MonthlySummarySerializer,
    BillCreateSerializer,
    MonthlyReviewSerializer, TrendDataSerializer, CategoryRankingSerializer,
    MonthlyListSerializer, CompareSerializer, BalanceInfoSerializer,
    CashFlowOverviewSerializer, AssetTrendItemSerializer,
    SnapshotListSerializer, CashFlowSnapshotSerializer, ReconcileSerializer,
    RegularListSerializer, RegularStatsSerializer, RegularFormSerializer,
    MatureProcessSerializer, ExpiringItemSerializer,
)
from .services.calendar_init import init_week_calendar_for_user, update_lived_status
from .services.week_aggregator import aggregate_weekly_net_income, get_net_level
from .services.coverage_calculator import calculate_coverage
from .services.monthly_aggregator import (
    aggregate_monthly_days, get_daily_detail, calculate_monthly_summary,
)
from .services.review_service import (
    get_monthly_review, get_trend_data, get_category_ranking,
    get_monthly_list, get_compare_data, generate_balance_info,
)
from .services.cashflow_service import (
    get_cashflow_overview, get_asset_trend, get_snapshot_list,
    reconcile, create_or_update_snapshot, copy_last_month,
    get_cashflow_by_yearmon,
)
from .services.regular_service import (
    get_stats, get_regular_list, get_regular_detail,
    create_regular, update_regular, delete_regular,
    process_mature, get_expiring_regulars, get_expired_regulars,
    update_all_status, get_available_banks, calculate_interest,
    FLAG_ONGOING, FLAG_MATURED, FLAG_WITHDRAWN,
)


def calculate_current_age_week():
    """计算当前周岁年龄和 ISO 周数"""
    today = date.today()
    birth_str = getattr(settings, 'WEALTH_BIRTH_DATE', '1994-10-01')
    birth = date.fromisoformat(birth_str)

    age = today.year - birth.year
    if (today.month, today.day) < (birth.month, birth.day):
        age -= 1

    return {
        'current_age': age,
        'current_week': today.isocalendar()[1],
        'birth_date': birth.isoformat(),
    }


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
        coverage, support_weeks, end_age, end_week = calculate_coverage(
            start_age=data['current_age'],
            start_week=data['current_week'],
            cash=float(data['current_cash']),
            daily_budget=float(data['daily_budget']),
        )

        # 保存到当前推演
        scenario, _ = WealthCurrentScenario.objects.get_or_create(pk=1)
        scenario.current_age = data['current_age']
        scenario.current_week = data['current_week']
        scenario.current_cash = data['current_cash']
        scenario.daily_budget = data['daily_budget']
        scenario.support_weeks = support_weeks
        scenario.end_age = end_age
        scenario.end_week = end_week
        scenario.save()

        # 写入历史
        WealthScenarioHistory.objects.create(
            current_age=data['current_age'],
            current_week=data['current_week'],
            current_cash=data['current_cash'],
            daily_budget=data['daily_budget'],
            support_weeks=support_weeks if isinstance(support_weeks, int) else 9999,
            note='',
        )

        return Response({
            'coverage_weeks': coverage,
            'support_weeks': support_weeks,
            'end_age': end_age,
            'end_week': end_week,
        })


class LifeSummaryView(APIView):
    """人生总览统计"""

    def get(self, request):
        user_id = request.query_params.get('user_id', 1)
        aggregated = aggregate_weekly_net_income(int(user_id))

        total_income = sum(v['income'] for v in aggregated.values())
        total_expense = sum(v['expense'] for v in aggregated.values())
        total_net = total_income - total_expense

        lived_weeks = sum(1 for v in aggregated.values())
        surplus_weeks = sum(1 for v in aggregated.values() if v['net'] > 0)
        deficit_weeks = sum(1 for v in aggregated.values() if v['net'] < 0)

        surplus_rate = round(surplus_weeks / lived_weeks * 100, 1) if lived_weeks > 0 else 0.0

        data = {
            'total_income': round(total_income, 2),
            'total_expense': round(total_expense, 2),
            'total_net': round(total_net, 2),
            'surplus_rate': surplus_rate,
            'lived_weeks': lived_weeks,
            'surplus_weeks': surplus_weeks,
            'deficit_weeks': deficit_weeks,
        }
        serializer = LifeSummarySerializer(data)
        return Response(serializer.data)


class BillsByWeekView(APIView):
    """按周查询账单明细"""

    def get(self, request):
        week_index = request.query_params.get('week_index')
        user_id = request.query_params.get('user_id', 1)

        if not week_index:
            return Response({'error': 'week_index is required'}, status=status.HTTP_400_BAD_REQUEST)

        week = WealthLifeWeekCalendar.objects.filter(
            global_week_index=week_index, user_id=user_id
        ).first()
        if not week:
            return Response({'error': 'week not found'}, status=status.HTTP_404_NOT_FOUND)

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

        return Response({'success': True, 'bill_id': bill_id}, status=status.HTTP_201_CREATED)


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

        from .models import WealthBalanceList
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

        from .models import WealthBalanceList
        existing = WealthBalanceList.objects.filter(yearmon=yearmon).first()
        serializer = BalanceInfoSerializer(existing, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED if not existing else status.HTTP_200_OK)

    def put(self, request):
        yearmon = request.data.get('yearmon')
        if not yearmon:
            return Response({'error': 'yearmon is required'}, status=status.HTTP_400_BAD_REQUEST)

        from .models import WealthBalanceList
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

        from .models import WealthCashFlow
        try:
            cf = WealthCashFlow.objects.get(baid=baid)
            cf.delete()
            return Response({'success': True})
        except WealthCashFlow.DoesNotExist:
            return Response({'error': 'record not found'}, status=status.HTTP_404_NOT_FOUND)


class ReconcileView(APIView):
    """账面与实际对账"""

    def get(self, request):
        yearmon = request.query_params.get('yearmon')
        user_id = request.query_params.get('user_id', 1)
        data = reconcile(int(user_id), yearmon)
        serializer = ReconcileSerializer(data)
        return Response(serializer.data)


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
