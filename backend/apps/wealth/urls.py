from django.urls import path

from . import views

urlpatterns = [
    path('age-week/', views.CurrentAgeWeekView.as_view(), name='current-age-week'),
    path('calendar/', views.WeekCalendarView.as_view(), name='week-calendar'),
    path('weekly_summary/<int:global_week_index>/', views.WeeklySummaryView.as_view(), name='weekly-summary'),
    path('scenario/current/', views.CurrentScenarioView.as_view(), name='current-scenario'),
    path('calculate_coverage/', views.CalculateCoverageView.as_view(), name='calculate-coverage'),
    path('summary/', views.LifeSummaryView.as_view(), name='life-summary'),
    path('bills/by_week/', views.BillsByWeekView.as_view(), name='bills-by-week'),
    path('calendar/init/', views.InitCalendarView.as_view(), name='init-calendar'),
    # 月度日历
    path('monthly_calendar/', views.MonthlyCalendarView.as_view(), name='monthly-calendar'),
    path('daily_detail/', views.DailyDetailView.as_view(), name='daily-detail'),
    path('monthly_summary/', views.MonthlySummaryView.as_view(), name='monthly-summary'),
    path('bill/create/', views.BillCreateView.as_view(), name='bill-create'),
    # 月度复盘
    path('review/monthly_summary/', views.MonthlyReviewView.as_view(), name='review-monthly-summary'),
    path('review/trend/', views.TrendView.as_view(), name='review-trend'),
    path('review/category_ranking/', views.CategoryRankingView.as_view(), name='review-category-ranking'),
    path('review/monthly_list/', views.MonthlyListView.as_view(), name='review-monthly-list'),
    path('review/balance_list/', views.BalanceListView.as_view(), name='review-balance-list'),
    path('review/compare/', views.CompareView.as_view(), name='review-compare'),
    path('review/generate/', views.GenerateBalanceInfoView.as_view(), name='review-generate'),
    # 现金盘点
    path('cashflow/overview/', views.CashFlowOverviewView.as_view(), name='cashflow-overview'),
    path('cashflow/trend/', views.AssetTrendView.as_view(), name='cashflow-trend'),
    path('cashflow/snapshot/', views.SnapshotView.as_view(), name='cashflow-snapshot'),
    path('cashflow/snapshot/list/', views.SnapshotListView.as_view(), name='cashflow-snapshot-list'),
    path('cashflow/reconcile/', views.ReconcileView.as_view(), name='cashflow-reconcile'),
    path('cashflow/copy/', views.CopySnapshotView.as_view(), name='cashflow-copy'),
    # 定期存款
    path('regular/stats/', views.RegularStatsView.as_view(), name='regular-stats'),
    path('regular/expiring/', views.RegularExpiringView.as_view(), name='regular-expiring'),
    path('regular/list/', views.RegularListView.as_view(), name='regular-list'),
    path('regular/banks/', views.RegularBanksView.as_view(), name='regular-banks'),
    path('regular/update_status/', views.RegularUpdateStatusView.as_view(), name='regular-update-status'),
    path('regular/<int:pk>/', views.RegularDetailView.as_view(), name='regular-detail'),
    path('regular/<int:pk>/mature/', views.RegularMatureView.as_view(), name='regular-mature'),
    # CSV 导入
    path('import/csv/', views.BillImportView.as_view(), name='bill-import-csv'),
]
