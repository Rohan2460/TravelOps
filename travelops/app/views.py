from django.conf import settings
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
from . import gemini_import
from . import gemini_summary
from .gemini_import import (
    GeminiApiError,
    GeminiConfigurationError,
)
from .live_analysis import (
    live_status_payload,
    recompute_live_status,
)
from .serializers import (
    UserSerializer,
    GroupSerializer,
    ReadinessDetailSerializer,
    FlightStatusCreateSerializer,
    GuidePositionCreateSerializer,
    LiveStatusDetailSerializer,
    TrafficRouteCreateSerializer,
    TrainStatusCreateSerializer,
    TripCreateSerializer,
    TripDetailSerializer,
    TripImportSerializer,
    TripSummaryResponseSerializer,
    TripSummarySerializer,
    TripWriteSerializer,
    WeatherCreateSerializer,
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


class TripImportExtractView(generics.GenericAPIView):
    """
    Accepts an image/PDF document and returns the Gemini-extracted trip
    payload (matching the TripCreateSerializer shape) plus a validation
    preview. Does not write to the database.

    The serializer_class makes the DRF browsable API render a file input
    form for this endpoint.
    """

    queryset = Trip.objects.none()
    serializer_class = TripImportSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        file_obj = serializer.validated_data['file']
        mime_type = file_obj.import_mime_type
        model = serializer.validated_data.get('model') or None

        try:
            data, warnings = gemini_import.extract_trip(
                file_obj.read(),
                mime_type,
                filename=getattr(file_obj, "name", "document"),
                model=model,
            )
        except GeminiConfigurationError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except GeminiApiError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        preview = TripCreateSerializer(data=data)
        valid = preview.is_valid()
        return Response({
            "model": model or settings.GEMINI_MODEL,
            "source_file": {
                "name": getattr(file_obj, "name", "document"),
                "mime_type": mime_type,
            },
            "extracted": data,
            "valid": valid,
            "errors": preview.errors or None,
            "warnings": warnings,
        })


class TripImportConfirmView(APIView):
    """
    Creates a trip from an extracted import payload. Accepts the same JSON
    body as POST /api/trips/ (TripCreateSerializer shape).
    """

    def post(self, request):
        serializer = TripCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        data = TripDetailSerializer(
            instance,
            context={"request": request},
        ).data
        return Response(data, status=status.HTTP_201_CREATED)


def _trip_or_404(pk):
    try:
        return trip_detail_queryset().get(pk=pk)
    except Trip.DoesNotExist:
        return None


class LiveFeedIngestMixin:
    """Shared POST behaviour for the live feed ingestion endpoints.

    Validates the payload, confirms the ``itinerary_element`` belongs to the
    trip in the URL, persists the snapshot record, then recomputes the live
    status and returns the resulting node statuses.
    """

    serializer_class = None
    requires_trip = False

    def post(self, request, pk=None):
        trip = _trip_or_404(pk)
        if trip is None:
            return Response(
                {"detail": "Trip not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        element = serializer.validated_data.get("itinerary_element")
        if element is not None and element.trip_id != trip.pk:
            return Response(
                {
                    "detail": "itinerary_element does not belong to this trip."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        save_kwargs = {"trip": trip} if self.requires_trip else {}
        record = serializer.save(**save_kwargs)
        result = recompute_live_status(trip)
        return Response(
            {
                "element_id": record.itinerary_element_id,
                "received": self.get_serializer(record).data,
                "statuses": result["statuses"],
                "case_id": result["case_id"],
                "phase": result["phase"],
                "affected_bookings": result["affected_bookings"],
            },
            status=status.HTTP_201_CREATED,
        )


class TripFlightStatusIngestView(LiveFeedIngestMixin, generics.GenericAPIView):
    """POST a flight-status snapshot for one of the trip's flight legs."""

    serializer_class = FlightStatusCreateSerializer


class TripTrainStatusIngestView(LiveFeedIngestMixin, generics.GenericAPIView):
    """POST a train-status snapshot for one of the trip's train legs."""

    serializer_class = TrainStatusCreateSerializer


class TripTrafficIngestView(LiveFeedIngestMixin, generics.GenericAPIView):
    """POST a traffic/route snapshot for a road transfer or ferry."""

    serializer_class = TrafficRouteCreateSerializer


class TripWeatherIngestView(LiveFeedIngestMixin, generics.GenericAPIView):
    """POST a weather snapshot for one of the trip's locations."""

    serializer_class = WeatherCreateSerializer


class TripGpsIngestView(LiveFeedIngestMixin, generics.GenericAPIView):
    """POST a guide GPS position ping during an active trip."""

    serializer_class = GuidePositionCreateSerializer
    requires_trip = True


class TripLiveStatusView(APIView):
    """
    Returns the current live operational status for a trip.

    Read-only view of the deterministic live engine; it does not write to
    the database.
    """

    def get(self, request, pk=None):
        trip = _trip_or_404(pk)
        if trip is None:
            return Response(
                {"detail": "Trip not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        payload = live_status_payload(trip, now=timezone.now())
        return Response(LiveStatusDetailSerializer(payload).data)


class TripSummaryView(APIView):
    """
    On-demand LLM summary of a trip's readiness and live operational status.

    Computed from the deterministic analysis and live snapshot; never writes
    to the database.
    """

    def get(self, request, pk=None):
        trip = _trip_or_404(pk)
        if trip is None:
            return Response(
                {"detail": "Trip not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            data = gemini_summary.summarize_trip(
                trip,
                now=timezone.now(),
                model=request.GET.get("model") or None,
            )
        except GeminiConfigurationError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except GeminiApiError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(
            {
                "model": request.GET.get("model") or settings.GEMINI_MODEL,
                "result": TripSummaryResponseSerializer(data).data,
            }
        )