from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/books/', include('apps.book.urls')),
    path('api/sugar/', include('apps.sugar.urls')),
    path('api/goals/', include('apps.goals.urls')),
    path('api/reward/', include('apps.reward.urls')),
    path('api/temporal/', include('apps.temporal.urls')),
    path('api/wealth/', include('apps.wealth.urls')),
    path('api/hobby/dance/', include('apps.dance.urls')),
    path('api/health/', include('apps.health.urls')),
    path('api/relation/', include('apps.relation.urls')),
    path('api/travel/', include('apps.travel.urls')),
    path('api/toolkit/', include('apps.toolkit.urls')),
    path('api/summary/', include('apps.summary.urls')),
    path('api/dams/', include('apps.dams.urls')),
    path('api/food/', include('apps.food.urls')),
    path('api/inbox/', include('apps.inbox.urls')),
    path('api/core/', include('apps.core.urls')),
    path('api/treasure/', include('apps.treasure.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
