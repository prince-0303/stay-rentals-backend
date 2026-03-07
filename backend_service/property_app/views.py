import math
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from .tasks import sync_properties_to_vectorstore

from django.db.models.functions import TruncMonth
from datetime import timedelta
from .utils import geocode_address

from .models import Property, PropertyImage, VisitSchedule, Review, UserPreference, SavedProperty
from .serializers import (
    PropertyListSerializer, PropertyDetailSerializer, PropertyCreateUpdateSerializer, PropertyImageUploadSerializer,
    VisitScheduleSerializer, VisitScheduleManageSerializer,
    ReviewSerializer, UserPreferenceSerializer, SavedPropertySerializer,
)
from django.conf import settings
from django.db.models import Avg, Count, Sum
import requests as http_requests


# ─── Permissions Helpers ───────────────────────────────────────────────────────

def is_lister(user):
    try:
        return (
            user.role == 'lister' and
            user.kyc_status == 'approved' and
            not user.lister_profile.is_blocked
        )
    except Exception:
        return False

def is_admin(user):
    return user.role == 'admin'


# ─── Property Views ────────────────────────────────────────────────────────────

class PropertyListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Browse all active properties",
        parameters=[
            OpenApiParameter("city", OpenApiTypes.STR, description="Filter by city"),
            OpenApiParameter("property_type", OpenApiTypes.STR, description="Filter by type"),
            OpenApiParameter("preferred_tenants", OpenApiTypes.STR, description="Filter by tenant preference"),
            OpenApiParameter("pet_friendly", OpenApiTypes.BOOL, description="Filter pet friendly"),
            OpenApiParameter("min_price", OpenApiTypes.FLOAT, description="Minimum rent price"),
            OpenApiParameter("max_price", OpenApiTypes.FLOAT, description="Maximum rent price"),
        ],
        responses=PropertyListSerializer(many=True)
    )
    def get(self, request):
        queryset = Property.objects.filter(is_active=True, is_blocked=False)

        city = request.query_params.get('city')
        property_type = request.query_params.get('property_type')
        preferred_tenants = request.query_params.get('preferred_tenants')
        pet_friendly = request.query_params.get('pet_friendly')
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')

        if city:
            queryset = queryset.filter(city__icontains=city)
        if property_type:
            queryset = queryset.filter(property_type=property_type)
        if preferred_tenants:
            queryset = queryset.filter(preferred_tenants=preferred_tenants)
        if pet_friendly is not None:
            queryset = queryset.filter(pet_friendly=pet_friendly.lower() == 'true')
        if min_price:
            queryset = queryset.filter(rent_price__gte=min_price)
        if max_price:
            queryset = queryset.filter(rent_price__lte=max_price)

        serializer = PropertyListSerializer(queryset, many=True)
        return Response(serializer.data)


class PropertyCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Create a new property listing (Lister only)",
        request=PropertyCreateUpdateSerializer,
        responses=PropertyDetailSerializer
    )
    def post(self, request):
        if not is_lister(request.user):
            return Response(
                {"error": "Only verified listers can create properties."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = PropertyCreateUpdateSerializer(data=request.data)
        if serializer.is_valid():
            property = serializer.save(lister=request.user)
            lat, lng = geocode_address(
                property.address_line, property.city,
                property.state, property.pincode
            )
            if lat and lng:
                property.latitude = lat
                property.longitude = lng
                property.save(update_fields=['latitude', 'longitude'])
            sync_properties_to_vectorstore.delay()
            return Response(
                PropertyDetailSerializer(property).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PropertyDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get property details",
        responses=PropertyDetailSerializer
    )
    def get(self, request, pk):
        property = get_object_or_404(Property, pk=pk, is_blocked=False)
        serializer = PropertyDetailSerializer(property)
        return Response(serializer.data)

    @extend_schema(
        summary="Update a property listing (Lister only)",
        request=PropertyCreateUpdateSerializer,
        responses=PropertyDetailSerializer
    )
    def patch(self, request, pk):
        property = get_object_or_404(Property, pk=pk)

        if not is_lister(request.user) or property.lister != request.user:
            return Response(
                {"error": "You do not have permission to edit this property."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = PropertyCreateUpdateSerializer(property, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            sync_properties_to_vectorstore.delay()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(summary="Delete a property listing (Lister only)")
    def delete(self, request, pk):
        property = get_object_or_404(Property, pk=pk)

        if not is_lister(request.user) or property.lister != request.user:
            return Response(
                {"error": "You do not have permission to delete this property."},
                status=status.HTTP_403_FORBIDDEN
            )

        property.delete()
        sync_properties_to_vectorstore.delay()
        return Response({"message": "Property deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


class MyPropertiesView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get all properties of the logged in lister",
        responses=PropertyListSerializer(many=True)
    )
    def get(self, request):
        if not is_lister(request.user):
            return Response(
                {"error": "Only listers can access this."},
                status=status.HTTP_403_FORBIDDEN
            )
        properties = Property.objects.filter(lister=request.user)
        serializer = PropertyListSerializer(properties, many=True)
        return Response(serializer.data)


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in km between two coordinates."""
    R = 6371  # Earth's radius in km
    lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


class PropertyNearbySearchView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Search properties near a location",
        parameters=[
            OpenApiParameter("lat", OpenApiTypes.FLOAT, description="Latitude of search location", required=True),
            OpenApiParameter("lng", OpenApiTypes.FLOAT, description="Longitude of search location", required=True),
            OpenApiParameter("radius", OpenApiTypes.FLOAT, description="Search radius in km (default: 10)"),
            OpenApiParameter("property_type", OpenApiTypes.STR, description="Filter by property type"),
            OpenApiParameter("preferred_tenants", OpenApiTypes.STR, description="Filter by tenant preference"),
            OpenApiParameter("pet_friendly", OpenApiTypes.BOOL, description="Filter pet friendly"),
            OpenApiParameter("min_price", OpenApiTypes.FLOAT, description="Minimum rent price"),
            OpenApiParameter("max_price", OpenApiTypes.FLOAT, description="Maximum rent price"),
        ],
        responses=PropertyListSerializer(many=True)
    )
    def get(self, request):
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')

        if not lat or not lng:
            return Response(
                {"error": "lat and lng are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            lat = float(lat)
            lng = float(lng)
        except ValueError:
            return Response(
                {"error": "lat and lng must be valid numbers."},
                status=status.HTTP_400_BAD_REQUEST
            )

        radius = float(request.query_params.get('radius', 10))

        # Get all active properties that have coordinates
        queryset = Property.objects.filter(
            is_active=True,
            is_blocked=False,
            latitude__isnull=False,
            longitude__isnull=False
        )

        # Apply optional filters
        property_type = request.query_params.get('property_type')
        preferred_tenants = request.query_params.get('preferred_tenants')
        pet_friendly = request.query_params.get('pet_friendly')
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')

        if property_type:
            queryset = queryset.filter(property_type=property_type)
        if preferred_tenants:
            queryset = queryset.filter(preferred_tenants=preferred_tenants)
        if pet_friendly is not None:
            queryset = queryset.filter(pet_friendly=pet_friendly.lower() == 'true')
        if min_price:
            queryset = queryset.filter(rent_price__gte=min_price)
        if max_price:
            queryset = queryset.filter(rent_price__lte=max_price)

        # Filter by distance
        nearby = []
        for property in queryset:
            distance = haversine_distance(
                lat, lng,
                property.latitude,
                property.longitude
            )
            if distance <= radius:
                nearby.append({
                    'property': property,
                    'distance_km': round(distance, 2)
                })

        # Sort by distance
        nearby.sort(key=lambda x: x['distance_km'])

        # Serialize
        serializer = PropertyListSerializer(
            [item['property'] for item in nearby],
            many=True
        )

        # Attach distance to each result
        data = serializer.data
        for i, item in enumerate(data):
            item['distance_km'] = nearby[i]['distance_km']

        return Response({
            'count': len(data),
            'search_location': {'lat': lat, 'lng': lng},
            'radius_km': radius,
            'properties': data
        })
    
class PropertyReviewView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=ReviewSerializer(many=True))
    def get(self, request, pk):
        property = get_object_or_404(Property, pk=pk)
        reviews = property.reviews.all()
        return Response(ReviewSerializer(reviews, many=True).data)
    
    @extend_schema(request=ReviewSerializer, responses=ReviewSerializer)
    def post(self, request, pk):
        property = get_object_or_404(Property, pk=pk, is_active=True, is_blocked=False)

        if Review.objects.filter(property=property, user=request.user).exists():
            return Response(
                {"error": "You have already reviewed this property."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ReviewSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user, property=property)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(responses=None)
    def delete(self, request, pk):
        review = get_object_or_404(Review, property_id=pk, user=request.user)
        review.delete()
        return Response({"message": "Review deleted."}, status=status.HTTP_204_NO_CONTENT)


class UserPreferenceView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=UserPreferenceSerializer)
    def get(self, request):
        pref, _ = UserPreference.objects.get_or_create(user=request.user)
        return Response(UserPreferenceSerializer(pref).data)
    
    @extend_schema(request=UserPreferenceSerializer, responses=UserPreferenceSerializer)
    def patch(self, request):
        pref, _ = UserPreference.objects.get_or_create(user=request.user)
        serializer = UserPreferenceSerializer(pref, data=request.data, partial=True)
        if serializer.is_valid():
            updated = serializer.save()
            if any(f in request.data for f in ['address_line', 'city', 'state', 'pincode']):
                lat, lng = geocode_address(
                    updated.address_line, updated.city,
                    updated.state, updated.pincode
                )
                if lat and lng:
                    updated.latitude = lat
                    updated.longitude = lng
                    updated.save(update_fields=['latitude', 'longitude'])
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SavedPropertyView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=SavedPropertySerializer(many=True))
    def get(self, request):
        saved = SavedProperty.objects.filter(user=request.user).select_related('property')
        return Response(SavedPropertySerializer(saved, many=True).data)
    
    @extend_schema(responses=SavedPropertySerializer)
    def post(self, request, pk):
        property = get_object_or_404(Property, pk=pk, is_active=True, is_blocked=False)

        if SavedProperty.objects.filter(user=request.user, property=property).exists():
            return Response({"error": "Already saved."}, status=status.HTTP_400_BAD_REQUEST)

        saved = SavedProperty.objects.create(user=request.user, property=property)
        return Response(SavedPropertySerializer(saved).data, status=status.HTTP_201_CREATED)
    
    @extend_schema(responses=None)
    def delete(self, request, pk):
        saved = get_object_or_404(SavedProperty, user=request.user, property_id=pk)
        saved.delete()
        return Response({"message": "Removed from saved."}, status=status.HTTP_204_NO_CONTENT)
    

class AIPropertySearchView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="AI natural language property search",
        request={'application/json': {'type': 'object', 'properties': {'query': {'type': 'string'}}}},
        responses={'200': {'type': 'object'}}
    )
    def post(self, request):
        query = request.data.get("query")
        if not query:
            return Response({"error": "query is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            res = http_requests.post(
                f"{settings.CHATBOT_SERVICE_URL}/api/recommendations/search/",
                json={"query": query},
                timeout=30
            )
            data = res.json()
        except Exception:
            return Response({"error": "AI service unavailable."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        property_ids = data.get("property_ids", [])
        answer = data.get("answer", "")

        # Preserve ChromaDB relevance order
        properties = Property.objects.filter(
            id__in=property_ids,
            is_active=True,
            is_blocked=False
        )

        # Sort by ChromaDB relevance order
        id_order = {int(pid): i for i, pid in enumerate(property_ids) if pid}
        sorted_properties = sorted(properties, key=lambda p: id_order.get(p.id, 999))[:3]

        serializer = PropertyListSerializer(sorted_properties, many=True)
        return Response({
            "answer": answer,
            "recommended_id": property_ids[0] if property_ids else None,  # top match
            "properties": serializer.data
        })


class AIPropertyCompareView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request={'application/json': {'type': 'object', 'properties': {'property_ids': {'type': 'array'}, 'preference': {'type': 'string'}}}},
        responses={'200': {'type': 'object'}}
    )
    def post(self, request):
        property_ids = request.data.get("property_ids", [])
        preference = request.data.get("preference", "")

        if len(property_ids) < 2:
            return Response({"error": "Provide at least 2 property IDs."}, status=status.HTTP_400_BAD_REQUEST)

        properties = Property.objects.filter(id__in=property_ids, is_active=True, is_blocked=False).annotate(
            avg_rating=Avg('reviews__overall_rating'),
            avg_cleanliness=Avg('reviews__cleanliness'),
        )

        payload = [{
            "id": p.id,
            "title": p.title,
            "property_type": p.property_type,
            "room_type": p.room_type,
            "city": p.city,
            "state": p.state,
            "rent_price": str(p.rent_price),
            "amenities": p.amenities,
            "avg_rating": round(p.avg_rating, 1) if p.avg_rating else None,
            "avg_cleanliness": round(p.avg_cleanliness, 1) if p.avg_cleanliness else None,
        } for p in properties]

        try:
            res = http_requests.post(
                f"{settings.CHATBOT_SERVICE_URL}/api/recommendations/compare/",
                json={"properties": payload, "preference": preference},
                timeout=30
            )
            data = res.json()
        except Exception:
            return Response({"error": "AI service unavailable."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        serializer = PropertyListSerializer(properties, many=True)
        return Response({
            "recommendation": data.get("recommendation"),
            "properties": serializer.data
        })


class RecommendationsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={'200': {'type': 'object'}})
    def get(self, request):
        try:
            pref = request.user.preference
        except Exception:
            return Response({"error": "Set your preferences first."}, status=status.HTTP_400_BAD_REQUEST)

        queryset = Property.objects.filter(is_active=True, is_blocked=False).annotate(
            avg_rating=Avg('reviews__overall_rating'),
        )

        if pref.preferred_city:
            queryset = queryset.filter(city__icontains=pref.preferred_city)
        if pref.min_budget:
            queryset = queryset.filter(rent_price__gte=pref.min_budget)
        if pref.max_budget:
            queryset = queryset.filter(rent_price__lte=pref.max_budget)
        if pref.preferred_property_types:
            lower_types = [t.lower() for t in pref.preferred_property_types]
            queryset = queryset.filter(property_type__in=lower_types)
        if pref.preferred_tenants:
            queryset = queryset.filter(preferred_tenants=pref.preferred_tenants)
        if pref.pet_friendly is not None:
            queryset = queryset.filter(pet_friendly=pref.pet_friendly)

        # Score: higher rated first, then newest
        queryset = queryset.order_by('-avg_rating', '-created_at')[:20]

        serializer = PropertyListSerializer(queryset, many=True)
        return Response({"recommendations": serializer.data})
    

# ─── Property Image Views ──────────────────────────────────────────────────────

class PropertyImageUploadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Upload images for a property (Lister only)",
        request=PropertyImageUploadSerializer(many=True),
        responses=PropertyImageUploadSerializer(many=True)
    )
    def post(self, request, pk):
        property = get_object_or_404(Property, pk=pk)

        if not is_lister(request.user) or property.lister != request.user:
            return Response(
                {"error": "You do not have permission to upload images for this property."},
                status=status.HTTP_403_FORBIDDEN
            )

        images = request.FILES.getlist('images')
        is_primary_index = int(request.data.get('primary_index', 0))

        if not images:
            return Response({"error": "No images provided."}, status=status.HTTP_400_BAD_REQUEST)

        uploaded = []
        for i, image in enumerate(images):
            is_primary = i == is_primary_index
            if is_primary:
                PropertyImage.objects.filter(property=property, is_primary=True).update(is_primary=False)
            img = PropertyImage.objects.create(
                property=property,
                image=image,
                is_primary=is_primary
            )
            uploaded.append(img)

        serializer = PropertyImageUploadSerializer(uploaded, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PropertyImageDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Delete a property image (Lister only)")
    def delete(self, request, pk, image_id):
        property = get_object_or_404(Property, pk=pk)

        if not is_lister(request.user) or property.lister != request.user:
            return Response(
                {"error": "You do not have permission to delete this image."},
                status=status.HTTP_403_FORBIDDEN
            )

        image = get_object_or_404(PropertyImage, pk=image_id, property=property)
        image.delete()
        return Response({"message": "Image deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


# ─── Admin Property Views ──────────────────────────────────────────────────────

class AdminPropertyListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Admin - Get all properties with filters",
        parameters=[
            OpenApiParameter("city", OpenApiTypes.STR, description="Filter by city"),
            OpenApiParameter("property_type", OpenApiTypes.STR, description="Filter by type"),
            OpenApiParameter("availability_status", OpenApiTypes.STR, description="Filter by availability"),
            OpenApiParameter("is_active", OpenApiTypes.BOOL, description="Filter by active status"),
            OpenApiParameter("is_blocked", OpenApiTypes.BOOL, description="Filter by blocked status"),
            OpenApiParameter("lister_id", OpenApiTypes.INT, description="Filter by lister"),
        ],
        responses=PropertyListSerializer(many=True)
    )
    def get(self, request):
        if not is_admin(request.user):
            return Response({"error": "Admin access only."}, status=status.HTTP_403_FORBIDDEN)

        properties = Property.objects.select_related('lister').prefetch_related('images').all()

        city = request.query_params.get('city')
        property_type = request.query_params.get('property_type')
        availability_status = request.query_params.get('availability_status')
        is_active = request.query_params.get('is_active')
        is_blocked = request.query_params.get('is_blocked')
        lister_id = request.query_params.get('lister_id')

        if city:
            properties = properties.filter(city__icontains=city)
        if property_type:
            properties = properties.filter(property_type=property_type)
        if availability_status:
            properties = properties.filter(availability_status=availability_status)
        if is_active is not None:
            properties = properties.filter(is_active=is_active.lower() == 'true')
        if is_blocked is not None:
            properties = properties.filter(is_blocked=is_blocked.lower() == 'true')
        if lister_id:
            properties = properties.filter(lister_id=lister_id)

        serializer = PropertyListSerializer(properties, many=True)
        return Response({
            'count': properties.count(),
            'properties': serializer.data
        })


class AdminPropertyBlockView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Admin - Block or unblock a property",
        request=None,
        responses=PropertyDetailSerializer
    )
    def patch(self, request, pk):
        if not is_admin(request.user):
            return Response({"error": "Admin access only."}, status=status.HTTP_403_FORBIDDEN)

        property = get_object_or_404(Property, pk=pk)
        blocked_reason = request.data.get('blocked_reason', '')

        property.is_blocked = not property.is_blocked
        property.blocked_reason = blocked_reason if property.is_blocked else None
        property.blocked_at = timezone.now() if property.is_blocked else None
        property.save()

        state = "blocked" if property.is_blocked else "unblocked"
        return Response({"message": f"Property {state} successfully."})


class AdminPropertyToggleActiveView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Admin - Toggle property active status")
    def patch(self, request, pk):
        if not is_admin(request.user):
            return Response({"error": "Admin access only."}, status=status.HTTP_403_FORBIDDEN)

        property = get_object_or_404(Property, pk=pk)
        property.is_active = not property.is_active
        property.save()

        state = "activated" if property.is_active else "deactivated"
        return Response({"message": f"Property {state} successfully."})


class AdminPropertyDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Admin - Force delete a property")
    def delete(self, request, pk):
        if not is_admin(request.user):
            return Response({"error": "Admin access only."}, status=status.HTTP_403_FORBIDDEN)

        property = get_object_or_404(Property, pk=pk)
        property.delete()
        return Response({"message": "Property deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


# ─── Visit Schedule Views ──────────────────────────────────────────────────────

class VisitScheduleCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Request a visit for a property (User only)",
        request=VisitScheduleSerializer,
        responses=VisitScheduleSerializer
    )
    def post(self, request, pk):
        property = get_object_or_404(Property, pk=pk, is_active=True, is_blocked=False)

        serializer = VisitScheduleSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(user=request.user, property=property)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VisitScheduleListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get all visit requests — users see their own, listers see requests for their properties",
        responses=VisitScheduleSerializer(many=True)
    )
    def get(self, request):
        user = request.user
        if is_lister(user):
            visits = VisitSchedule.objects.filter(property__lister=user)
        else:
            visits = VisitSchedule.objects.filter(user=user)

        serializer = VisitScheduleSerializer(visits, many=True)
        return Response(serializer.data)


class VisitScheduleManageView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Lister confirms, cancels or completes a visit request",
        request=VisitScheduleManageSerializer,
        responses=VisitScheduleManageSerializer
    )
    def patch(self, request, pk):
        visit = get_object_or_404(VisitSchedule, pk=pk)
        
        # Check permissions: Lister can manage entirely, requester can only cancel
        is_owner = is_lister(request.user) and visit.property.lister == request.user
        is_requester_cancelling = (visit.user == request.user and request.data.get('status') == VisitSchedule.CANCELLED)
        
        if not (is_owner or is_requester_cancelling):
            return Response(
                {"error": "You do not have permission to manage this visit."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = VisitScheduleManageSerializer(visit, data=request.data, partial=True)
        if serializer.is_valid():
            previous_status = visit.status
            new_status = serializer.validated_data.get('status', previous_status)
            
            # Check if this is the user cancelling a previously un-cancelled request
            is_user_cancelling = (
                request.user == visit.user 
                and new_status == VisitSchedule.CANCELLED 
                and previous_status != VisitSchedule.CANCELLED
            )
            
            serializer.save()
            response_data = serializer.data
            
            # Apply penalty mapping
            if is_user_cancelling:
                request.user.cancellation_count += 1
                request.user.save(update_fields=['cancellation_count'])
                if request.user.cancellation_count >= 5:
                    response_data['warning'] = f"Warning: You have cancelled {request.user.cancellation_count} visit requests. Excessive cancellations may affect your account standing."
            
            return Response(response_data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class AdminVisitScheduleListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Admin - Get all visit schedules across the platform",
        parameters=[
            OpenApiParameter("status", OpenApiTypes.STR, description="Filter by status: pending, confirmed, cancelled, completed"),
            OpenApiParameter("property_id", OpenApiTypes.INT, description="Filter by property"),
            OpenApiParameter("user_id", OpenApiTypes.INT, description="Filter by user"),
        ],
        responses=VisitScheduleSerializer(many=True)
    )
    def get(self, request):
        if not is_admin(request.user):
            return Response({"error": "Admin access only."}, status=status.HTTP_403_FORBIDDEN)

        visits = VisitSchedule.objects.select_related(
            'property', 'user', 'property__lister'
        ).all().order_by('-created_at')

        status_filter = request.query_params.get('status')
        property_id = request.query_params.get('property_id')
        user_id = request.query_params.get('user_id')

        if status_filter:
            visits = visits.filter(status=status_filter)
        if property_id:
            visits = visits.filter(property_id=property_id)
        if user_id:
            visits = visits.filter(user_id=user_id)

        serializer = VisitScheduleSerializer(visits, many=True)
        return Response({
            'count': visits.count(),
            'visits': serializer.data
        })
    


class ListerDashboardAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_lister(request.user):
            return Response({"error": "Forbidden"}, status=403)

        user = request.user
        
        # 1. Basic Counts
        my_properties = Property.objects.filter(lister=user)
        total_listings = my_properties.count()
        
        # 2. Leads (Visit Schedules)
        leads = VisitSchedule.objects.filter(property__lister=user)
        total_leads = leads.count()
        pending_leads = leads.filter(status='pending').count()

        # 3. Growth Analysis (Leads per month for the last 6 months)
        six_months_ago = timezone.now() - timedelta(days=180)
        growth_data = (
            leads.filter(created_at__gte=six_months_ago)
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )

        return Response({
            "summary": {
                "total_listings": total_listings,
                "total_leads": total_leads,
                "pending_leads": pending_leads,
            },
            "growth": list(growth_data),
            "recent_leads": VisitScheduleSerializer(leads.order_by('-created_at')[:5], many=True).data
        })