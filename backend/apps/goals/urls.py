from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'goals', views.GoalViewSet, basename='goal')
router.register(r'milestones', views.MilestoneViewSet, basename='milestone')
router.register(r'actions', views.ActionViewSet, basename='action')
router.register(r'reviews', views.GoalReviewViewSet, basename='goalreview')
router.register(r'outputs', views.OutputRecordViewSet, basename='output')

urlpatterns = [
    path('', include(router.urls)),
]
