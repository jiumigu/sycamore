from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'oneday', views.OneDayPageViewSet, basename='oneday')
router.register(r'tasks', views.TemporalTaskViewSet, basename='tasks')

urlpatterns = [
    path('', include(router.urls)),
    path('weekly-tracking/', views.WeeklyTimeTrackingView.as_view()),
    path('weekly-tracking/refresh/', views.RefreshWeeklyCacheView.as_view()),
    path('open-logseq/', views.OpenLogseqView.as_view()),
]
