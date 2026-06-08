from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('records', views.SugarRecordViewSet, basename='sugar-record')
router.register('energy', views.EnergyViewSet, basename='sugar-energy')
router.register('templates', views.SugarTemplateViewSet, basename='sugar-template')

urlpatterns = [
    path('categories/', views.SugarRecordViewSet.as_view({'get': 'categories'}), name='sugar-categories'),
]

urlpatterns += router.urls
