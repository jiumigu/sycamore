from django.urls import path

from . import views

urlpatterns = [
    path('', views.RedemptionConfigView.as_view(), name='redemption-config'),
    path('pause/', views.RedemptionPauseView.as_view(), name='redemption-pause'),
    path('resume/', views.RedemptionResumeView.as_view(), name='redemption-resume'),
    path('injects/', views.InjectListCreateView.as_view(), name='redemption-injects'),
    path('attr-rules/', views.AttrRuleListCreateView.as_view(), name='redemption-attr-rules'),
    path('attr-rules/<int:pk>/', views.AttrRuleDetailView.as_view(), name='redemption-attr-rule-detail'),
    path('stats/', views.RedemptionStatsView.as_view(), name='redemption-stats'),
    path('sync-scenario/', views.RedemptionSyncScenarioView.as_view(), name='redemption-sync-scenario'),
]
