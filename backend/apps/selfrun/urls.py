from django.urls import path

from . import views

# 🔴 顺序：字面路径（`current/` `close/` `copy/`）一律排在 `<int:pk>/` **之前** ——
#    虽然 `int` 转换器不会匹配它们，但排前面读起来不依赖这条隐式规则。
urlpatterns = [
    # ── T1 制定配置 ──────────────────────────────────────────
    path('templates/', views.TemplateListView.as_view(), name='selfrun-templates'),
    path('templates/<int:pk>/', views.TemplateDetailView.as_view(), name='selfrun-template-detail'),
    path('metrics/preview/', views.MetricPreviewView.as_view(), name='selfrun-metric-preview'),
    path('stages/copy/', views.StageCopyView.as_view(), name='selfrun-stage-copy'),
    path('stages/', views.StageListCreateView.as_view(), name='selfrun-stages'),
    path('stages/<int:pk>/pause/', views.StagePauseView.as_view(), name='selfrun-stage-pause'),
    path('stages/<int:pk>/resume/', views.StageResumeView.as_view(), name='selfrun-stage-resume'),
    path('stages/<int:pk>/summary/', views.StageSummaryView.as_view(), name='selfrun-stage-summary'),
    path('stages/<int:pk>/ledger/', views.StageLedgerView.as_view(), name='selfrun-stage-ledger'),
    path('stages/<int:pk>/ledger-config/', views.StageLedgerConfigView.as_view(),
         name='selfrun-stage-ledger-config'),
    path('stages/<int:pk>/close/', views.StageCloseView.as_view(), name='selfrun-stage-close'),
    path('stages/<int:pk>/', views.StageDetailView.as_view(), name='selfrun-stage-detail'),

    # 池注入标记（v3.64.26）= 在账单明细页给某笔收入打「中途注入」
    # ⚠️ 字面路径，排在 `<int:pk>/` 之前不影响，但读起来不依赖隐式规则
    path('pool-injects/', views.PoolInjectView.as_view(), name='selfrun-pool-injects'),

    # ── T1b 按期修订（「修订下一周 / 下一月」）────────────────
    # ⚠️ `metrics/<pk>/plans/` 必须排在 `metrics/<pk>/` **之前**（虽然前缀不同、
    #    并不真冲突，但读起来不该依赖这条隐式规则）。
    path('period-options/', views.PeriodOptionsView.as_view(), name='selfrun-period-options'),
    path('targets/', views.TargetsView.as_view(), name='selfrun-targets'),
    path('metrics/<int:pk>/plans/', views.MetricPlanView.as_view(), name='selfrun-metric-plans'),
    path('metrics/<int:pk>/plans/<int:plan_id>/', views.MetricPlanDetailView.as_view(),
         name='selfrun-metric-plan-detail'),

    # ── T2 执行 ──────────────────────────────────────────────
    path('periods/current/', views.CurrentPeriodView.as_view(), name='selfrun-period-current'),
    path('checkins/', views.CheckinListCreateView.as_view(), name='selfrun-checkins'),
    path('checkins/<int:pk>/', views.CheckinDetailView.as_view(), name='selfrun-checkin-detail'),
    path('metrics/<int:pk>/retire/', views.MetricRetireView.as_view(), name='selfrun-metric-retire'),
    path('metrics/<int:pk>/revive/', views.MetricReviveView.as_view(), name='selfrun-metric-revive'),
    path('metrics/<int:pk>/', views.MetricDetailView.as_view(), name='selfrun-metric-detail'),
    path('heartbeat/', views.HeartbeatView.as_view(), name='selfrun-heartbeat'),

    # ── T3 复盘 ──────────────────────────────────────────────
    path('periods/close/', views.PeriodCloseView.as_view(), name='selfrun-period-close'),
    path('periods/', views.PeriodListView.as_view(), name='selfrun-periods'),
    path('periods/<int:pk>/reopen/', views.PeriodReopenView.as_view(), name='selfrun-period-reopen'),
    path('periods/<int:pk>/', views.PeriodDetailView.as_view(), name='selfrun-period-detail'),

    # ── 跨模块（仪表盘小卡）──────────────────────────────────
    path('overview/', views.OverviewView.as_view(), name='selfrun-overview'),
]
