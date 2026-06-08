from django.urls import path

from . import views

urlpatterns = [
    path('records/', views.TravelRecordListCreateView.as_view(), name='travel-records'),
    path('records/<int:pk>/', views.TravelRecordDetailView.as_view(), name='travel-record-detail'),
    path('map/data/', views.MapDataView.as_view(), name='travel-map-data'),
    path('stats/', views.TravelStatsView.as_view(), name='travel-stats'),
    path('provinces/', views.ProvinceListView.as_view(), name='travel-provinces'),
    path('years/', views.YearListView.as_view(), name='travel-years'),
]
