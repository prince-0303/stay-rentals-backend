from django.db import models
from django.conf import settings
from cloudinary.models import CloudinaryField


class Property(models.Model):

    # Property Types
    APARTMENT = 'apartment'
    HOUSE = 'house'
    ROOM = 'room'
    VILLA = 'villa'
    PG = 'pg'
    HOSTEL = 'hostel'
    PROPERTY_TYPE_CHOICES = [
        (APARTMENT, 'Apartment'),
        (HOUSE, 'House'),
        (ROOM, 'Room'),
        (VILLA, 'Villa'),
        (PG, 'PG'),
        (HOSTEL, 'Hostel'),
    ]

    # Availability
    AVAILABLE = 'available'
    BOOKED = 'booked'
    UNAVAILABLE = 'unavailable'
    AVAILABILITY_CHOICES = [
        (AVAILABLE, 'Available'),
        (BOOKED, 'Booked'),
        (UNAVAILABLE, 'Unavailable'),
    ]

    # Room Type
    PRIVATE = 'private'
    SHARED = 'shared'
    CO_LIVING = 'co-living'
    ROOM_TYPE_CHOICES = [
        (PRIVATE, 'Private'),
        (SHARED, 'Shared'),
        (CO_LIVING, 'Co-living'),
    ]

    # Furnishing
    FURNISHED = 'furnished'
    SEMI_FURNISHED = 'semi_furnished'
    UNFURNISHED = 'unfurnished'
    FURNISHING_CHOICES = [
        (FURNISHED, 'Furnished'),
        (SEMI_FURNISHED, 'Semi Furnished'),
        (UNFURNISHED, 'Unfurnished'),
    ]

    # Preferred Tenants
    MALE = 'male'
    FEMALE = 'female'
    MIXED = 'mixed'
    COUPLE = 'couple'
    FAMILY = 'family'
    ANY = 'any'
    PREFERRED_TENANT_CHOICES = [
        (MALE, 'Male'),
        (FEMALE, 'Female'),
        (MIXED, 'Mixed'),
        (COUPLE, 'Couple'),
        (FAMILY, 'Family'),
        (ANY, 'Any'),
    ]

    # Core
    lister = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='properties'
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    property_type = models.CharField(max_length=20, choices=PROPERTY_TYPE_CHOICES)

    # Location
    address_line = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    nearest_landmarks = models.JSONField(default=list, blank=True)

    # Pricing
    rent_price = models.DecimalField(max_digits=10, decimal_places=2)

    # Room Details
    total_rooms = models.PositiveIntegerField(default=1)
    bathrooms = models.PositiveIntegerField(default=1)
    kitchens = models.PositiveIntegerField(default=0)
    room_type = models.CharField(max_length=10, choices=ROOM_TYPE_CHOICES, default=PRIVATE)
    furnishing_status = models.CharField(max_length=20, choices=FURNISHING_CHOICES, default=UNFURNISHED)
    floor_number = models.IntegerField(default=0)
    total_floors = models.PositiveIntegerField(default=1)

    # Preferences
    preferred_tenants = models.CharField(max_length=10, choices=PREFERRED_TENANT_CHOICES, default=ANY)
    pet_friendly = models.BooleanField(default=False)

    # Amenities
    amenities = models.JSONField(default=list, blank=True)

    # Status
    availability_status = models.CharField(max_length=20, choices=AVAILABILITY_CHOICES, default=AVAILABLE)
    is_active = models.BooleanField(default=True)
    is_blocked = models.BooleanField(default=False)
    blocked_reason = models.TextField(blank=True, null=True)
    blocked_at = models.DateTimeField(blank=True, null=True)

    # Future proofing
    extra_details = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'properties'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.city} ({self.lister.get_full_name()})"


class PropertyImage(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='images')
    image = CloudinaryField('image', folder='accommodation/properties/')
    is_primary = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'property_images'

    def __str__(self):
        return f"Image for {self.property.title} ({'Primary' if self.is_primary else 'Secondary'})"


class VisitSchedule(models.Model):

    PENDING = 'pending'
    CONFIRMED = 'confirmed'
    CANCELLED = 'cancelled'
    COMPLETED = 'completed'
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (CONFIRMED, 'Confirmed'),
        (CANCELLED, 'Cancelled'),
        (COMPLETED, 'Completed'),
    ]

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='visits')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='visit_requests')
    requested_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    user_note = models.TextField(blank=True, null=True)
    lister_note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'visit_schedules'
        ordering = ['-created_at']
        unique_together = ['property', 'user', 'requested_date']

    def __str__(self):
        return f"{self.user.get_full_name()} → {self.property.title} on {self.requested_date}"

#------------------------ REVIEWS------------------------------

class Review(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')

    # Ratings (1-5)
    overall_rating = models.PositiveSmallIntegerField()
    cleanliness = models.PositiveSmallIntegerField(default=3)
    value_for_money = models.PositiveSmallIntegerField(default=3)
    location = models.PositiveSmallIntegerField(default=3)
    owner_behaviour = models.PositiveSmallIntegerField(default=3)

    review_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'property_reviews'
        unique_together = ['property', 'user']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.get_full_name()} → {self.property.title} ({self.overall_rating}★)"


class UserPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='preference')

    preferred_city = models.CharField(max_length=100, blank=True)
    min_budget = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_budget = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    preferred_property_types = models.JSONField(default=list, blank=True)
    required_amenities = models.JSONField(default=list, blank=True)
    preferred_tenants = models.CharField(max_length=10, blank=True)
    pet_friendly = models.BooleanField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_preferences'

    def __str__(self):
        return f"{self.user.get_full_name()}'s preferences"


class SavedProperty(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_properties')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='saved_by')
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'saved_properties'
        unique_together = ['user', 'property']
        ordering = ['-saved_at']

    def __str__(self):
        return f"{self.user.get_full_name()} saved {self.property.title}"