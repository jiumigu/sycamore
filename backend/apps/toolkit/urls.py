from django.urls import path

from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'cities', views.CityCoordinateViewSet, basename='city-coordinate')
router.register(r'travel-routes', views.TravelRoutePresetViewSet, basename='travel-route')
router.register(r'environment-audits', views.EnvironmentAuditViewSet, basename='environment-audit')
router.register(r'career-energy-audits', views.CareerEnergyAuditViewSet, basename='career-energy-audit')
router.register(r'decision-logs', views.DecisionLogViewSet, basename='decision-log')
router.register(r'health-self-checks', views.HealthSelfCheckViewSet, basename='health-self-check')
router.register(r'free-spending', views.FreeSpendingCalculatorViewSet, basename='free-spending')
router.register(r'hourly-wage', views.HourlyWageViewSet, basename='hourly-wage')
router.register(r'review-records', views.ReviewRecordViewSet, basename='review-record')
router.register(r'language-training', views.LanguageTrainingViewSet, basename='language-training')
router.register(r'quotes', views.QuoteViewSet, basename='quote')

urlpatterns = [
    path('tools/', views.ToolListView.as_view(), name='toolkit-tools'),
    path('tools/<str:tool_key>/', views.ToolDetailView.as_view(), name='toolkit-tool-detail'),
    path('execute/', views.ExecuteToolView.as_view(), name='toolkit-execute'),
    path('convert_file/', views.FileToolUploadView.as_view(), name='toolkit-convert-file'),
    path('task/<int:execution_id>/', views.TaskStatusView.as_view(), name='toolkit-task-status'),
    path('history/', views.HistoryListView.as_view(), name='toolkit-history'),
    path('register/', views.RegisterToolsView.as_view(), name='toolkit-register'),
    path('tags/', views.TagManagerView.as_view(), name='toolkit-tags'),
] + router.urls
