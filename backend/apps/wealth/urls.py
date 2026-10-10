from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'bills', views.BillViewSet, basename='bills')
# 负债明细 / 应收借出逐笔台账（v3.58.20，P1-A）
router.register(r'debt/liabilities', views.LiabilityViewSet, basename='liabilities')
router.register(r'debt/receivables', views.ReceivableViewSet, basename='receivables')
# 资产科目主数据 / 资产快照（v3.58.21，P1-B）
router.register(r'asset/accounts', views.AssetAccountViewSet, basename='asset-accounts')
router.register(r'asset/snapshots', views.AssetSnapshotViewSet, basename='asset-snapshots')
# 账单项分类规则 / 归类结果（v3.58.22，P1-C）
router.register(r'classify/rules', views.ClassifyRuleViewSet, basename='classify-rules')
router.register(r'classify/results', views.ClassifyResultViewSet, basename='classify-results')
# 财务规划比率（v3.58.23，P2-A）
router.register(r'ratios', views.RatioViewSet, basename='ratios')
# 生存资源盘点（v3.59.0，P3-A）—— 物资台账，与上面金融口径的 asset/* 刻意分开命名
router.register(r'survival/categories', views.SurvivalCategoryViewSet, basename='survival-categories')
router.register(r'survival/units', views.SurvivalUnitViewSet, basename='survival-units')
router.register(r'survival/items', views.SurvivalItemViewSet, basename='survival-items')
# 必需品基准清单（v3.59.7）：基准项 CRUD + reconcile 对账 + seed 初始化。
# ⚠️ 与 survival/items 是**两条**路径，别合并 —— 一个是「本该有什么」（认知），
#    一个是「实际有多少」（库存）。合并后「我漏了牙膏」会被读成「牙膏数量是 0」。
router.register(r'survival/essentials', views.SurvivalEssentialViewSet, basename='survival-essentials')
router.register(r'survival/recipes', views.SurvivalRecipeViewSet, basename='survival-recipes')
# 组合（v3.59.13）—— 「分开登记、一起下锅」：几件物品声明成一份可复用的搭配，
# 供配方行引用。⚠️ 与 survival/essentials（基准项挂多件）是**两条**路径：
# 组内口径同源（取最小），但一个是「尺子上的一项」、一个是「一顿的搭配」。
router.register(r'survival/combos', views.SurvivalComboViewSet, basename='survival-combos')
# 盘点快照（二期）：列表 / 盘点 / 删除 / trend
router.register(r'survival/snapshots', views.SurvivalSnapshotViewSet, basename='survival-snapshots')
# 实盘盘点（v3.59.3）：工作表 / 提交 / 历史 / 删除
# ⚠️ 与上面的 snapshots 是**两条**路径，别合并成一个「盘点」入口 ——
#    一个是系统算结论、一个是人填实盘，语义完全不同。
router.register(r'survival/stocktakes', views.SurvivalStocktakeViewSet, basename='survival-stocktakes')
# 库存流水（v3.60.18）—— 库存**怎么变的**；同时是**改库存的唯一写口**。
# `summary/` 是 detail=False 的 action，DRF 把它排在 `flows/<pk>/` **之前**，
# 不会被主键抢（用例钉住 —— 被抢的症状是 404，看着像路由没注册）。
router.register(r'survival/flows', views.SurvivalFlowViewSet, basename='survival-flows')
# 物件资产（v3.60.0，P4-A）—— 耐用品台账
# ⚠️ 路径用 property/*，与 /wealth/cashflow 页里的「资产盘点」（asset/snapshots）**不是一回事**：
#    那条是钱的去向，这条是家里那台冰箱。
router.register(r'property/categories', views.PropertyCategoryViewSet, basename='property-categories')
router.register(r'property/items', views.PropertyItemViewSet, basename='property-items')

urlpatterns = [
    # 🔴 **路由器的动态路由必须排在最后。**
    #    DRF 的详情路由是「前缀/<pk>/」，`<pk>` 的默认正则 `[^/.]+` 能匹配**任何**
    #    一段不含斜杠的字符串。所以凡「前缀/xxx/」形式的静态路径，只要写在它后面，
    #    就会被它抢先接走（变成 `pk='xxx'`）→ 详情查不到 → **404**。
    #    v3.60.16 的现场：`bills/by_week/` 被 `bills/<pk>/` 吃掉，前端把 404
    #    静默当成「本周无账单」⇒ 同一个弹窗里「有收支数字、却没有明细」。
    #    ⇒ 判据：**静态路径在前，动态路由兜底**；新增静态路径时它也天然安全。
    # 物件资产：汇总卡 + 口径元信息（均只读、实时算）
    path('property/summary/', views.PropertySummaryView.as_view(), name='property-summary'),
    path('property/meta/', views.PropertyMetaView.as_view(), name='property-meta'),
    # 生存资源盘点：综合分析 + 口径元信息（均只读、实时算）
    path('survival/analysis/', views.SurvivalAnalysisView.as_view(), name='survival-analysis'),
    path('survival/meta/', views.SurvivalMetaView.as_view(), name='survival-meta'),
    path('survival/metrics/meta/', views.SurvivalMetricMetaView.as_view(), name='survival-metrics-meta'),
    path('age-week/', views.CurrentAgeWeekView.as_view(), name='current-age-week'),
    path('calendar/', views.WeekCalendarView.as_view(), name='week-calendar'),
    path('weekly_summary/<int:global_week_index>/', views.WeeklySummaryView.as_view(), name='weekly-summary'),
    path('scenario/current/', views.CurrentScenarioView.as_view(), name='current-scenario'),
    path('calculate_coverage/', views.CalculateCoverageView.as_view(), name='calculate-coverage'),
    # 反算：本金 + 目标天数 → 每日可提取额（纯试算，不写库）
    path('calculate_budget/', views.CalculateBudgetView.as_view(), name='calculate-budget'),
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
    # 🔴 路由器放**最后**（理由见本列表首行注释）：静态路径优先，动态路由兜底
    path('', include(router.urls)),
]
