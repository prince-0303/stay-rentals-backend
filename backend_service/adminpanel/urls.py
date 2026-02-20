from django.urls import path
from . import views

urlpatterns = [
    # Users
    path('users/', views.AdminUserListView.as_view(), name='admin-users'),
    path('users/<int:user_id>/', views.AdminUserDetailView.as_view(), name='admin-user-detail'),
    path('users/<int:user_id>/block/', views.AdminUserBlockView.as_view(), name='admin-user-block'),

    # Listers
    path('listers/', views.AdminListerListView.as_view(), name='admin-listers'),
    path('listers/<int:user_id>/', views.AdminUserDetailView.as_view(), name='admin-lister-detail'),
    path('listers/<int:user_id>/block/', views.AdminUserBlockView.as_view(), name='admin-lister-block'),

    # KYC
    path('kyc/', views.AdminKYCListView.as_view(), name='admin-kyc-list'),
    path('kyc/', views.AdminKYCListView.as_view(), name='admin-kyc-list'),
    path('kyc/<uuid:user_id>/', AdminKYCDetailView.as_view(), name='admin-kyc-detail'),
    path('kyc/<uuid:user_id>/update-status/', AdminKYCStatusUpdateView.as_view(), name='admin-kyc-update-status'),
]