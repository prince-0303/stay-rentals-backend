from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('stats/', views.AdminDashboardStatsView.as_view(), name='admin-stats'),
    path('charts/', views.AdminDashboardChartsView.as_view(), name='admin-charts'),

    # Users
    path('users/', views.AdminUserListView.as_view(), name='admin-users'),
    path('users/<int:user_id>/', views.AdminUserDetailView.as_view(), name='admin-user-detail'),
    path('users/<int:user_id>/block/', views.AdminUserBlockView.as_view(), name='admin-user-block'),

    # Listers
    path('listers/', views.AdminListerListView.as_view(), name='admin-listers'),
    path('listers/<int:user_id>/', views.AdminListerDetailView.as_view(), name='admin-lister-detail'),
    path('listers/<int:user_id>/block/', views.AdminUserBlockView.as_view(), name='admin-lister-block'),

    # KYC
    path('kyc/', views.AdminKYCListView.as_view(), name='admin-kyc-list'),
    path('kyc/<int:user_id>/', views.AdminKYCActionView.as_view(), name='admin-kyc-action'),

    path('earnings/', views.AdminEarningsOverviewView.as_view(), name='admin-earnings'),
    path('earnings/<int:lister_id>/', views.AdminListerEarningsDetailView.as_view(), name='admin-lister-earnings'),

    path('occupancy/', views.AdminOccupancyView.as_view(), name='admin-occupancy'),
]