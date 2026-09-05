from django.urls import path

from .views import (
    TripListCreateView,
    TripUpdateView,
    LocationListCreateView,
    LocationUpdateView,
    ItineraryElementListCreateView,
    ItineraryElementUpdateView,
    BookingListCreateView,
    BookingUpdateView,
    DependencyListCreateView,
    DependencyUpdateView,
)

urlpatterns = [
    path(
        'trips/',
        TripListCreateView.as_view(),
        name='trip-list-create'
    ),
    path(
        'trips/<int:pk>/',
        TripUpdateView.as_view(),
        name='trip-update'
    ),

    path(
        'locations/',
        LocationListCreateView.as_view(),
        name='location-list-create'
    ),
    path(
        'locations/<int:pk>/',
        LocationUpdateView.as_view(),
        name='location-update'
    ),

    path(
        'itinerary-elements/',
        ItineraryElementListCreateView.as_view(),
        name='itinerary-element-list-create'
    ),
    path(
        'itinerary-elements/<int:pk>/',
        ItineraryElementUpdateView.as_view(),
        name='itinerary-element-update'
    ),

    path(
        'bookings/',
        BookingListCreateView.as_view(),
        name='booking-list-create'
    ),
    path(
        'bookings/<int:pk>/',
        BookingUpdateView.as_view(),
        name='booking-update'
    ),

    path(
        'dependencies/',
        DependencyListCreateView.as_view(),
        name='dependency-list-create'
    ),
    path(
        'dependencies/<int:pk>/',
        DependencyUpdateView.as_view(),
        name='dependency-update'
    ),
]