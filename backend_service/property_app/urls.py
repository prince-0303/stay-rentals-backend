from django.urls import path
from .views import (
    AIPropertySearchView, AIPropertyCompareView, RecommendationsView,
    PropertyListView, PropertyCreateView, PropertyDetailView, MyPropertiesView, PropertyImageUploadView, PropertyImageDeleteView, PropertyNearbySearchView, AdminPropertyListView, AdminPropertyBlockView, AdminPropertyToggleActiveView, AdminPropertyDeleteView, AdminVisitScheduleListView, 
    VisitScheduleCreateView, VisitScheduleListView, VisitScheduleManageView,
    PropertyReviewView, UserPreferenceView, SavedPropertyView,
)

urlpatterns = [
    # Public / User
    path('', PropertyListView.as_view(), name='property-list'),
    path('create/', PropertyCreateView.as_view(), name='property-create'),
    path('<int:pk>/', PropertyDetailView.as_view(), name='property-detail'),
    path('my/', MyPropertiesView.as_view(), name='my-properties'),
    path('search/nearby/', PropertyNearbySearchView.as_view(), name='property-nearby-search'),

    # Images
    path('<int:pk>/images/', PropertyImageUploadView.as_view(), name='property-image-upload'),
    path('<int:pk>/images/<int:image_id>/', PropertyImageDeleteView.as_view(), name='property-image-delete'),

    # Visit Schedules
    path('<int:pk>/visit/', VisitScheduleCreateView.as_view(), name='visit-create'),
    path('visits/', VisitScheduleListView.as_view(), name='visit-list'),
    path('visits/<int:pk>/manage/', VisitScheduleManageView.as_view(), name='visit-manage'),

    # Admin
    path('admin/all/', AdminPropertyListView.as_view(), name='admin-property-list'),
    path('admin/<int:pk>/block/', AdminPropertyBlockView.as_view(), name='admin-property-block'),
    path('admin/<int:pk>/toggle-active/', AdminPropertyToggleActiveView.as_view(), name='admin-property-toggle'),
    path('admin/<int:pk>/delete/', AdminPropertyDeleteView.as_view(), name='admin-property-delete'),
    path('admin/visits/', AdminVisitScheduleListView.as_view(), name='admin-visit-list'),

    # Reviews
    path('<int:pk>/reviews/', PropertyReviewView.as_view(), name='property-reviews'),

    # User Preferences
    path('preferences/', UserPreferenceView.as_view(), name='user-preferences'),

    # Saved Properties
    path('saved/', SavedPropertyView.as_view(), name='saved-properties'),
    path('<int:pk>/save/', SavedPropertyView.as_view(), name='save-property'),

    path('search/ai/', AIPropertySearchView.as_view(), name='ai-search'),
    path('compare/', AIPropertyCompareView.as_view(), name='ai-compare'),
    path('recommendations/', RecommendationsView.as_view(), name='recommendations'),
]