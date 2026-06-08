from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'relationships', views.RelationshipViewSet, basename='relationship')
router.register(r'interactions', views.InteractionViewSet, basename='interaction')
router.register(r'stats', views.StatsViewSet, basename='stats')
router.register(r'reader-groups', views.ReaderGroupViewSet, basename='reader-group')
router.register(r'reader-interactions', views.ReaderInteractionViewSet, basename='reader-interaction')
router.register(r'conflicts', views.ConflictEventViewSet, basename='conflict')
router.register(r'reader-monthly-summaries', views.ReaderMonthlySummaryViewSet, basename='reader-monthly-summary')

urlpatterns = [
    path('', include(router.urls)),
]
