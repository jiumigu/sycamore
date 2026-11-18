from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'', views.BookViewSet, basename='book')

urlpatterns = [
    # 🔴 字面路径必须排在 router **之前**：它注册的是空前缀，
    #    详情正则是 `^(?P<pk>[^/.]+)/$` —— 排在后面的话
    #    `/api/books/reading-focus/` 会被当成 `pk='reading-focus'` 的详情请求，
    #    走进 retrieve 报 404，而错误信息完全看不出是这个原因。
    path('reading-focus/', views.ReadingFocusView.as_view()),
    path('reading-focus/candidates/', views.ReadingFocusCandidatesView.as_view()),
    path('reading-focus/switch/', views.ReadingFocusSwitchView.as_view()),
    path('', include(router.urls)),
]
