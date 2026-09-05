from django.contrib.auth.models import Group, User
from django.db.models import Count, OuterRef, Prefetch, Q, Subquery
from django.utils import timezone
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Case,
    Event,
    ItineraryChange,
    ItineraryElement,
    ReadinessAssessment,
    Trip,
    TripRisk,
)
from .analysis import analyze_trip
from .serializers import (
    UserSerializer,
    GroupSerializer,
    ReadinessDetailSerializer,
    TripCreateSerializer,
    TripDetailSerializer,
    TripSummarySerializer,
    TripWriteSerializer,
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


def trip_detail_queryset():
    elements = ItineraryElement.objects.order_by('sequence').select_related(
        'start_location', 'end_location'
    ).prefetch_related(
        'bookings',
        'outgoing_dependencies__from_element',
        'outgoing_dependencies__to_element',
        'incoming_dependencies__from_element',
        'incoming_dependencies__to_element',
    )
    events = Event.objects.select_related('location').prefetch_related(
        'impacts__itinerary_element',
    )
    cases = Case.objects.prefetch_related(
        'actions',
        'case_impacts__impact__itinerary_element',
    )
    itinerary_changes = ItineraryChange.objects.select_related('itinerary_element')

    return Trip.objects.prefetch_related(
        Prefetch('itinerary_elements', queryset=elements),
        Prefetch('events', queryset=events),
        Prefetch('cases', queryset=cases),
        Prefetch('trip_risks', queryset=TripRisk.objects.all()),
        Prefetch('readiness_assessments', queryset=ReadinessAssessment.objects.all()),
        Prefetch('itinerary_changes', queryset=itinerary_changes),
    )


def trip_summary_queryset():
    readiness_subquery = ReadinessAssessment.objects.filter(
        trip=OuterRef('pk')
    ).order_by('-calculated_at').values('status')[:1]

    nearest_subquery = ItineraryElement.objects.filter(
        trip=OuterRef('pk'),
        planned_start__gte=timezone.now(),
    ).order_by('planned_start').values('planned_start')[:1]

    return Trip.objects.annotate(
        readiness=Subquery(readiness_subquery),
        open_cases=Count(
            'cases',
            distinct=True,
            filter=Q(cases__status='open'),
        ),
        affected_elements=Count(
            'itinerary_elements',
            distinct=True,
            filter=Q(itinerary_elements__status__in=['disrupted', 'at_risk']),
        ),
        open_risks=Count(
            'trip_risks',
            distinct=True,
            filter=Q(trip_risks__status='open', trip_risks__severity='high'),
        ),
        nearest_departure=Subquery(nearest_subquery),
    ).order_by('start_time')


class TripListCreateView(generics.ListCreateAPIView):
    queryset = trip_summary_queryset()

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return TripSummarySerializer
        return TripCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        data = TripDetailSerializer(
            instance,
            context=self.get_serializer_context(),
        ).data
        return Response(data, status=status.HTTP_201_CREATED)


class TripUpdateView(generics.RetrieveUpdateDestroyAPIView):
    queryset = trip_detail_queryset()

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return TripDetailSerializer
        return TripWriteSerializer


class TripAnalysisView(APIView):
    """
    Returns a unified trip analysis for both upcoming and active trips.
    """

    def get(self, request, pk=None):
        try:
            trip = trip_detail_queryset().get(pk=pk)
        except Trip.DoesNotExist:
            return Response(
                {"detail": "Trip not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        analysis = analyze_trip(trip, now=timezone.now())
        return Response(ReadinessDetailSerializer(analysis).data)