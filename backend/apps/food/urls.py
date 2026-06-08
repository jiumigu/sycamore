from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('records', views.FoodRecordViewSet, basename='food')

urlpatterns = [
    *router.urls,
    # 快捷上传入口（同时也是 records/upload/ 的别名）
    path('upload/', views.FoodRecordViewSet.as_view({'post': 'upload'}), name='food-upload'),
]
