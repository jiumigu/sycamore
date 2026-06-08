from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DatabaseBackupView, ProfileView, QuickRecordView, NotificationViewSet

router = DefaultRouter()
router.register(r'notifications', NotificationViewSet)

urlpatterns = [
    path('profile/', ProfileView.as_view()),
    path('backup/database/', DatabaseBackupView.as_view()),
    path('quick-record/', QuickRecordView.as_view()),
    path('', include(router.urls)),
]
