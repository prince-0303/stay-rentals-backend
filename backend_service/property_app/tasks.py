from celery import shared_task
from django.conf import settings
import requests
from .models import Property

@shared_task
def sync_properties_to_vectorstore():
    properties = Property.objects.filter(is_active=True, is_blocked=False)

    payload = {"properties": [
        {
            "id": p.id,
            "title": p.title,
            "property_type": p.property_type,
            "room_type": p.room_type,
            "city": p.city,
            "state": p.state,
            "rent_price": str(p.rent_price),
            "amenities": p.amenities,
            "furnishing_status": p.furnishing_status,
            "preferred_tenants": p.preferred_tenants,
            "description": p.description,
        }
        for p in properties
    ]}

    try:
        response = requests.post(
            f"{settings.CHATBOT_SERVICE_URL}/api/recommendations/sync/",
            json=payload,
            timeout=60
        )
        return f"Synced {response.json().get('synced', 0)} properties"
    except Exception as e:
        return f"Sync failed: {e}"