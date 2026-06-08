"""综合进度看板 — URL 路由"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'', views.SummaryViewSet, basename='summary')

urlpatterns = [
    path('', include(router.urls)),
]
