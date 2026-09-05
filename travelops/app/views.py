from django.contrib.auth.models import Group, User
from rest_framework import permissions, viewsets, generics

from app.serializers import GroupSerializer, UserSerializer, TripSerializer
from .models import Trip


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