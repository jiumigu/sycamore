from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ShowroomCaseViewSet,
    ShowroomMediaUploadView,
    ShowroomMetaView,
    ShowroomPreviewView,
    ShowroomProfileView,
    ShowroomSkillViewSet,
    ShowroomWorkViewSet,
)

router = DefaultRouter()
router.register('cases', ShowroomCaseViewSet, basename='showroom-case')
router.register('skills', ShowroomSkillViewSet, basename='showroom-skill')
router.register('works', ShowroomWorkViewSet, basename='showroom-work')

urlpatterns = [
    path('profile/', ShowroomProfileView.as_view()),
    path('preview/', ShowroomPreviewView.as_view()),
    path('meta/', ShowroomMetaView.as_view()),
    path('media/', ShowroomMediaUploadView.as_view()),
    path('', include(router.urls)),
]
