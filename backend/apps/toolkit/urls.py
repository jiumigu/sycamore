from django.urls import path

from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'cities', views.CityCoordinateViewSet, basename='city-coordinate')
router.register(r'travel-routes', views.TravelRoutePresetViewSet, basename='travel-route')
router.register(r'environment-audits', views.EnvironmentAuditViewSet, basename='environment-audit')
router.register(r'career-energy-audits', views.CareerEnergyAuditViewSet, basename='career-energy-audit')

urlpatterns = [
    path('tools/', views.ToolListView.as_view(), name='toolkit-tools'),
    path('tools/<str:tool_key>/', views.ToolDetailView.as_view(), name='toolkit-tool-detail'),
    path('execute/', views.ExecuteToolView.as_view(), name='toolkit-execute'),
    path('convert_file/', views.FileToolUploadView.as_view(), name='toolkit-convert-file'),
    path('task/<int:execution_id>/', views.TaskStatusView.as_view(), name='toolkit-task-status'),
    path('history/', views.HistoryListView.as_view(), name='toolkit-history'),
    path('register/', views.RegisterToolsView.as_view(), name='toolkit-register'),
] + router.urls
