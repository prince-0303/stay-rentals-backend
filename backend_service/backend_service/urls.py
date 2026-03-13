from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/admin/', include('adminpanel.urls')),
    path('api/auth/', include('auth_app.urls')),
    path('api/profile/', include('profile_app.urls')),
    path('api/chatbot/', include('chatbot_app.urls')),
    path('api/properties/', include('property_app.urls')),
    path('api/notifications/', include('notifications_app.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/chat/', include('chat_app.urls')),
    path('api/payments/', include('payments_app.urls')),
]