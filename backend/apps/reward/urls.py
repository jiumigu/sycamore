from django.urls import path

from . import views

urlpatterns = [
    path('pool/', views.RewardPoolView.as_view(), name='reward-pool'),
    path('transactions/', views.RewardTransactionListView.as_view(), name='reward-transactions'),
    path('transactions/<int:pk>/', views.RewardTransactionDeleteView.as_view(), name='reward-transaction-delete'),
    path('stats/sources/', views.RewardSourceStatsView.as_view(), name='reward-stats-sources'),
    # 礼物清单
    path('gifts/', views.GiftListView.as_view(), name='reward-gift-list'),
    path('gifts/stats/', views.GiftStatsView.as_view(), name='reward-gift-stats'),
    path('gifts/<int:pk>/', views.GiftDetailView.as_view(), name='reward-gift-detail'),
    path('gifts/<int:pk>/redeem/', views.GiftRedeemView.as_view(), name='reward-gift-redeem'),
    path('gifts/<int:pk>/cancel/', views.GiftCancelView.as_view(), name='reward-gift-cancel'),
]
