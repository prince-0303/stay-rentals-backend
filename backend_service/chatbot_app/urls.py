from django.urls import path
from .views import FAQBotView

urlpatterns = [
    path("ask/", FAQBotView.as_view(), name="faq-bot-ask"),
]