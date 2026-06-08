from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'records', views.HealthRecordViewSet, basename='health')
router.register(r'weight/records', views.WeightViewSet, basename='weight')

urlpatterns = [
    path('', include(router.urls)),
    # 体重管理快捷路由
    path('weight/stats/', views.WeightViewSet.as_view({'get': 'stats'}), name='weight-stats'),
    path('weight/trend/', views.WeightViewSet.as_view({'get': 'trend'}), name='weight-trend'),
    path('weight/goal/', views.WeightViewSet.as_view({'get': 'goal', 'post': 'goal'}), name='weight-goal'),
    path('weight/milestones/', views.WeightViewSet.as_view({'get': 'milestones'}), name='weight-milestones'),
    path('weight/body-info/', views.WeightViewSet.as_view({'get': 'body_info', 'put': 'body_info'}), name='weight-body-info'),
]
