from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'files', views.DamsFileResourceViewSet, basename='dams-file')
router.register(r'access-logs', views.DamsAccessLogViewSet, basename='dams-access-log')

urlpatterns = [
    path('', include(router.urls)),
]
