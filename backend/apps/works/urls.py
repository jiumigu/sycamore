from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CaptureViewSet,
    ChannelsView,
    ComposeView,
    OverviewView,
    WorkMediaUploadView,
    WorkMetaView,
    WorkViewSet,
)

router = DefaultRouter()
router.register(r'items', WorkViewSet, basename='work')
router.register(r'captures', CaptureViewSet, basename='capture')

urlpatterns = [
    path('overview/', OverviewView.as_view(), name='works-overview'),
    path('meta/', WorkMetaView.as_view(), name='works-meta'),
    path('compose/', ComposeView.as_view(), name='works-compose'),
    path('channels/', ChannelsView.as_view(), name='works-channels'),
    path('media/', WorkMediaUploadView.as_view(), name='works-media'),
    path('', include(router.urls)),
]
