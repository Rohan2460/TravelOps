from django.urls import path

from .views import (
    TripAnalysisView,
    TripImportConfirmView,
    TripImportExtractView,
    TripListCreateView,
    TripUpdateView,
)

urlpatterns = [
    path(
        'trips/import/extract/',
        TripImportExtractView.as_view(),
        name='trip-import-extract'
    ),
    path(
        'trips/import/confirm/',
        TripImportConfirmView.as_view(),
        name='trip-import-confirm'
    ),
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
        'trips/<int:pk>/analysis/',
        TripAnalysisView.as_view(),
        name='trip-analysis'
    ),
]