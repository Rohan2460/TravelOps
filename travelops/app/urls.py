from django.urls import path

from .views import (
    TripListCreateView,
    TripUpdateView,
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
]