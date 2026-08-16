from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DatabaseBackupView, GlobalSearchView, ProfileView, QuickRecordView, NotificationViewSet, SystemPresetViewSet

router = DefaultRouter()
router.register(r'notifications', NotificationViewSet)
router.register(r'presets', SystemPresetViewSet)

urlpatterns = [
    path('profile/', ProfileView.as_view()),
    path('backup/database/', DatabaseBackupView.as_view()),
    path('quick-record/', QuickRecordView.as_view()),
    path('search/', GlobalSearchView.as_view()),
    path('', include(router.urls)),
]
