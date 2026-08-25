from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

plan_router = DefaultRouter()
plan_router.register(r'plans', views.TravelPlanViewSet, basename='travel-plan')

urlpatterns = [
    path('records/', views.TravelRecordListCreateView.as_view(), name='travel-records'),
    path('records/<int:pk>/', views.TravelRecordDetailView.as_view(), name='travel-record-detail'),
    path('map/data/', views.MapDataView.as_view(), name='travel-map-data'),
    path('stats/', views.TravelStatsView.as_view(), name='travel-stats'),
    path('provinces/', views.ProvinceListView.as_view(), name='travel-provinces'),
    path('years/', views.YearListView.as_view(), name='travel-years'),
    path('', include(plan_router.urls)),
]
