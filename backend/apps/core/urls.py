from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DatabaseBackupView, GlobalSearchView, ProfileView, QuickRecordView,
    NotificationViewSet, SystemPresetViewSet, MenuPreferenceViewSet, MenuGroupViewSet,
)

router = DefaultRouter()
router.register(r'notifications', NotificationViewSet)
router.register(r'presets', SystemPresetViewSet)
router.register(r'menus', MenuPreferenceViewSet, basename='menu-pref')
router.register(r'menu-groups', MenuGroupViewSet, basename='menu-group')

urlpatterns = [
    path('profile/', ProfileView.as_view()),
    path('backup/database/', DatabaseBackupView.as_view()),
    path('quick-record/', QuickRecordView.as_view()),
    path('search/', GlobalSearchView.as_view()),
    path('', include(router.urls)),
]
