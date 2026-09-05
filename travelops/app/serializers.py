from django.contrib.auth.models import Group, User
from rest_framework import serializers

from .models import (
    Trip,
    Location,
    ItineraryElement,
    Booking,
    Dependency,
)


class UserSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = User
        fields = [
            'url',
            'username',
            'email',
            'first_name',
            'last_name',
        ]


class GroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Group
        fields = ["url", "name"]


class TripSerializer(serializers.ModelSerializer):

    class Meta:
        model = Trip
        fields = [
            'id',
            'guide_id',
            'name',
            'start_time',
            'end_time',
            'status',
        ]


class LocationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Location
        fields = [
            'id',
            'name',
            'latitude',
            'longitude',
            'address',
        ]


class ItineraryElementSerializer(serializers.ModelSerializer):

    class Meta:
        model = ItineraryElement
        fields = [
            'id',
            'trip',
            'type',
            'name',
            'start_location',
            'end_location',
            'planned_start',
            'planned_end',
            'actual_start',
            'actual_end',
            'status',
            'sequence',
        ]


class BookingSerializer(serializers.ModelSerializer):

    class Meta:
        model = Booking
        fields = [
            'id',
            'itinerary_element',
            'supplier_name',
            'booking_reference',
            'status',
            'notes',
            'created_at',
            'updated_at',
        ]


class DependencySerializer(serializers.ModelSerializer):

    class Meta:
        model = Dependency
        fields = [
            'id',
            'from_element',
            'to_element',
            'type',
            'minimum_buffer',
        ]