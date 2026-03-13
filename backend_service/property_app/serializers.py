from rest_framework import serializers
from .models import Property, PropertyImage, VisitSchedule
from django.utils import timezone
from .models import Property, PropertyImage, VisitSchedule, Review, UserPreference, SavedProperty


class PropertyImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = PropertyImage
        fields = ['id', 'image_url', 'is_primary', 'uploaded_at']

    def get_image_url(self, obj):
        return obj.image.url if obj.image else None


class PropertyImageUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyImage
        fields = ['id', 'image', 'is_primary']

    def validate(self, attrs):
        property = self.context.get('property')
        if attrs.get('is_primary'):
            # If this is set as primary, unset all others
            PropertyImage.objects.filter(
                property=property, is_primary=True
            ).update(is_primary=False)
        return attrs


class PropertyListSerializer(serializers.ModelSerializer):
    primary_image = serializers.SerializerMethodField()
    lister_name = serializers.SerializerMethodField()

    class Meta:
        model = Property
        fields = [
            'id', 'title', 'property_type', 'room_type',
            'city', 'state', 'latitude', 'longitude', 'rent_price', 'availability_status',
            'preferred_tenants', 'pet_friendly', 'furnishing_status',
            'is_active', 'primary_image', 'lister_name', 'created_at'
        ]

    def get_primary_image(self, obj):
        image = obj.images.filter(is_primary=True).first() or obj.images.first()
        return image.image.url if image else None

    def get_lister_name(self, obj):
        return obj.lister.get_full_name()


class PropertyDetailSerializer(serializers.ModelSerializer):
    images = PropertyImageSerializer(many=True, read_only=True)
    lister_name = serializers.SerializerMethodField()
    lister_id = serializers.SerializerMethodField()
    lister_is_online = serializers.SerializerMethodField()

    class Meta:
        model = Property
        fields = [
            'id', 'lister_id', 'lister_name', 'lister_is_online',
            'title', 'description', 'property_type',
            'address_line', 'city', 'state', 'pincode',
            'latitude', 'longitude', 'nearest_landmarks',
            'rent_price', 'total_rooms', 'bathrooms', 'kitchens',
            'room_type', 'furnishing_status',
            'floor_number', 'total_floors',
            'preferred_tenants', 'pet_friendly',
            'amenities', 'availability_status',
            'is_active', 'is_blocked',
            'extra_details', 'images',
            'created_at', 'updated_at'
        ]

    def get_lister_name(self, obj):
        return obj.lister.get_full_name()

    def get_lister_id(self, obj):
        return obj.lister.id

    def get_lister_is_online(self, obj):
        if not obj.lister.last_login:
            return False
        from django.utils import timezone
        diff = timezone.now() - obj.lister.last_login
        return diff.total_seconds() < 300

class PropertyCreateUpdateSerializer(serializers.ModelSerializer):
    description = serializers.CharField(required=False, allow_blank=True, default='')
    class Meta:
        model = Property
        fields = [
            'title', 'description', 'property_type',
            'address_line', 'city', 'state', 'pincode',
            'latitude', 'longitude', 'nearest_landmarks',
            'rent_price',
            'total_rooms', 'bathrooms', 'kitchens',
            'room_type', 'furnishing_status',
            'floor_number', 'total_floors',
            'preferred_tenants', 'pet_friendly',
            'amenities', 'availability_status',
            'extra_details'
        ]

    def validate_rent_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Rent price must be greater than 0.")
        return value

    def validate_total_rooms(self, value):
        if value <= 0:
            raise serializers.ValidationError("Total rooms must be at least 1.")
        return value


class VisitScheduleSerializer(serializers.ModelSerializer):
    property_title = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = VisitSchedule
        fields = [
            'id', 'property', 'property_title',
            'user_name', 'requested_date', 'status',
            'user_note', 'lister_note', 'created_at'
        ]
        read_only_fields = ['status', 'lister_note', 'property']

    def get_property_title(self, obj):
        return obj.property.title

    def get_user_name(self, obj):
        return obj.user.get_full_name()

    def validate_requested_date(self, value):
        if value < timezone.now().date():
            raise serializers.ValidationError("Visit date cannot be in the past.")
        return value

    def validate(self, attrs):
        user = self.context['request'].user
        property = attrs.get('property')
        requested_date = attrs.get('requested_date')

        # Check if user already has a visit request for this property on this date
        if VisitSchedule.objects.filter(
            property=property,
            user=user,
            requested_date=requested_date
        ).exists():
            raise serializers.ValidationError(
                "You already have a visit request for this property on this date."
            )
        return attrs


class VisitScheduleManageSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisitSchedule
        fields = ['id', 'status', 'lister_note']

    def validate_status(self, value):
        allowed = [VisitSchedule.CONFIRMED, VisitSchedule.CANCELLED, VisitSchedule.COMPLETED]
        if value not in allowed:
            raise serializers.ValidationError("Invalid status update.")
        return value
    
class ReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            'id', 'user_name', 'overall_rating', 'cleanliness',
            'value_for_money', 'location', 'owner_behaviour',
            'review_text', 'created_at'
        ]
        read_only_fields = ['user_name', 'created_at']

    def get_user_name(self, obj):
        return obj.user.get_full_name()

    def validate(self, attrs):
        for field in ['overall_rating', 'cleanliness', 'value_for_money', 'location', 'owner_behaviour']:
            value = attrs.get(field)
            if value and not (1 <= value <= 5):
                raise serializers.ValidationError({field: "Rating must be between 1 and 5."})
        return attrs


class UserPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreference
        fields = [
            'preferred_city', 'min_budget', 'max_budget',
            'preferred_property_types', 'required_amenities',
            'preferred_tenants', 'pet_friendly', 'updated_at'
        ]
        read_only_fields = ['updated_at']


class SavedPropertySerializer(serializers.ModelSerializer):
    property = PropertyListSerializer(read_only=True)

    class Meta:
        model = SavedProperty
        fields = ['id', 'property', 'saved_at']