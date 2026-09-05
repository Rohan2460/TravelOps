from django.contrib.auth.models import Group, User
from rest_framework import permissions, viewsets, generics

from .models import (
    Trip,
    Location,
    ItineraryElement,
    Booking,
    Dependency,
)

from .serializers import (
    UserSerializer,
    GroupSerializer,
    TripSerializer,
    LocationSerializer,
    ItineraryElementSerializer,
    BookingSerializer,
    DependencySerializer,
)


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """

    queryset = User.objects.all().order_by("-date_joined")
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]


class GroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """

    queryset = Group.objects.all().order_by("name")
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated]


class TripListCreateView(generics.ListCreateAPIView):
    queryset = Trip.objects.all()
    serializer_class = TripSerializer


class TripUpdateView(generics.UpdateAPIView):
    queryset = Trip.objects.all()
    serializer_class = TripSerializer


class LocationListCreateView(generics.ListCreateAPIView):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer


class LocationUpdateView(generics.UpdateAPIView):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer


class ItineraryElementListCreateView(generics.ListCreateAPIView):
    queryset = ItineraryElement.objects.all()
    serializer_class = ItineraryElementSerializer


class ItineraryElementUpdateView(generics.UpdateAPIView):
    queryset = ItineraryElement.objects.all()
    serializer_class = ItineraryElementSerializer


class BookingListCreateView(generics.ListCreateAPIView):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer


class BookingUpdateView(generics.UpdateAPIView):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer


class DependencyListCreateView(generics.ListCreateAPIView):
    queryset = Dependency.objects.all()
    serializer_class = DependencySerializer


class DependencyUpdateView(generics.UpdateAPIView):
    queryset = Dependency.objects.all()
    serializer_class = DependencySerializer