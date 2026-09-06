from django.contrib.auth.models import Group, User
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .gemini_import import MAX_FILE_BYTES, resolve_mime_type
from .models import (
    Trip,
    Location,
    ItineraryElement,
    Booking,
    Dependency,
    Event,
    Impact,
    Case,
    CaseImpact,
    CaseAction,
    ItineraryChange,
    ReadinessAssessment,
    TripRisk,
    FlightStatusRecord,
    TrainStatusRecord,
    TrafficRouteRecord,
    WeatherRecord,
    GuidePosition,
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


class ItineraryElementSerializer(serializers.ModelSerializer):

    start_location = LocationSerializer(read_only=True)
    end_location = LocationSerializer(read_only=True)
    bookings = BookingSerializer(many=True, read_only=True)

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
            'bookings',
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


class ImpactSerializer(serializers.ModelSerializer):

    class Meta:
        model = Impact
        fields = [
            'id',
            'event',
            'itinerary_element',
            'classification',
            'status',
            'severity',
            'reason',
            'calculated_at',
        ]


class EventSerializer(serializers.ModelSerializer):

    location = LocationSerializer(read_only=True)
    impacts = ImpactSerializer(many=True, read_only=True)

    class Meta:
        model = Event
        fields = [
            'id',
            'trip',
            'type',
            'source',
            'title',
            'description',
            'location',
            'occurred_at',
            'reported_at',
            'severity',
            'status',
            'created_by',
            'impacts',
        ]


class CaseActionSerializer(serializers.ModelSerializer):

    class Meta:
        model = CaseAction
        fields = [
            'id',
            'case',
            'type',
            'description',
            'status',
            'created_by',
            'created_at',
            'completed_at',
        ]


class CaseImpactSerializer(serializers.ModelSerializer):

    impact = ImpactSerializer(read_only=True)

    class Meta:
        model = CaseImpact
        fields = [
            'id',
            'case',
            'impact',
        ]


class CaseSerializer(serializers.ModelSerializer):

    actions = CaseActionSerializer(many=True, read_only=True)
    case_impacts = CaseImpactSerializer(many=True, read_only=True)

    class Meta:
        model = Case
        fields = [
            'id',
            'trip',
            'primary_event',
            'title',
            'priority',
            'status',
            'created_at',
            'updated_at',
            'resolved_at',
            'assigned_to',
            'actions',
            'case_impacts',
        ]


class TripRiskSerializer(serializers.ModelSerializer):

    class Meta:
        model = TripRisk
        fields = [
            'id',
            'trip',
            'type',
            'severity',
            'reason',
            'status',
            'created_at',
            'updated_at',
        ]


class ReadinessAssessmentSerializer(serializers.ModelSerializer):

    class Meta:
        model = ReadinessAssessment
        fields = [
            'id',
            'trip',
            'status',
            'reason',
            'calculated_at',
        ]


class ReadinessWarningSerializer(serializers.Serializer):
    severity = serializers.CharField(read_only=True)
    reason = serializers.CharField(read_only=True)


class ReadinessCheckSerializer(serializers.Serializer):
    status = serializers.CharField(read_only=True)
    warnings = ReadinessWarningSerializer(many=True, read_only=True)


class TripElementMetricSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    sequence = serializers.IntegerField(read_only=True)
    type = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    start = serializers.CharField(read_only=True, allow_null=True)
    end = serializers.CharField(read_only=True, allow_null=True)
    planned_start = serializers.DateTimeField(read_only=True)
    planned_end = serializers.DateTimeField(read_only=True)
    planned_duration_minutes = serializers.IntegerField(read_only=True)
    actual_start = serializers.DateTimeField(read_only=True, allow_null=True)
    actual_end = serializers.DateTimeField(read_only=True, allow_null=True)
    actual_duration_minutes = serializers.IntegerField(
        read_only=True, allow_null=True
    )
    effective_end = serializers.DateTimeField(read_only=True)
    delay_minutes = serializers.IntegerField(read_only=True)
    started = serializers.BooleanField(read_only=True)
    booking_status = serializers.CharField(
        read_only=True, allow_null=True
    )


class ConnectionMetricSerializer(serializers.Serializer):
    from_id = serializers.IntegerField(read_only=True)
    from_name = serializers.CharField(read_only=True)
    to_id = serializers.IntegerField(read_only=True)
    to_name = serializers.CharField(read_only=True)
    type = serializers.CharField(read_only=True)
    from_arrival = serializers.DateTimeField(read_only=True)
    to_departure = serializers.DateTimeField(read_only=True)
    connection_minutes = serializers.IntegerField(read_only=True)
    minimum_buffer_minutes = serializers.IntegerField(read_only=True)
    free_buffer_minutes = serializers.IntegerField(read_only=True)
    delayed = serializers.BooleanField(read_only=True)
    kind = serializers.CharField(read_only=True)


class DeadlineMetricSerializer(serializers.Serializer):
    kind = serializers.CharField(read_only=True)
    element_id = serializers.IntegerField(read_only=True)
    element_name = serializers.CharField(read_only=True)
    deadline = serializers.DateTimeField(read_only=True)
    expected = serializers.DateTimeField(read_only=True, allow_null=True)
    satisfied = serializers.BooleanField(read_only=True)
    remaining_minutes = serializers.IntegerField(
        read_only=True, allow_null=True
    )
    buffer_minutes = serializers.IntegerField(
        read_only=True, allow_null=True
    )


class TimelineSerializer(serializers.Serializer):
    elements = TripElementMetricSerializer(many=True, read_only=True)
    connections = ConnectionMetricSerializer(many=True, read_only=True)
    deadlines = DeadlineMetricSerializer(many=True, read_only=True)


class ReadinessDetailSerializer(serializers.Serializer):
    status = serializers.CharField(read_only=True)
    phase = serializers.CharField(read_only=True)
    summary = serializers.ListField(child=serializers.CharField(), read_only=True)
    timeline = TimelineSerializer(read_only=True)
    checks = serializers.SerializerMethodField(read_only=True)

    def get_checks(self, analysis):
        return {
            name: ReadinessCheckSerializer(check).data
            for name, check in analysis["checks"].items()
        }


class ItineraryChangeSerializer(serializers.ModelSerializer):

    class Meta:
        model = ItineraryChange
        fields = [
            'id',
            'trip',
            'itinerary_element',
            'change_type',
            'old_value',
            'new_value',
            'reason',
            'event',
            'changed_by',
            'changed_at',
        ]


class TripDetailSerializer(serializers.ModelSerializer):

    itinerary_elements = ItineraryElementSerializer(many=True, read_only=True)
    dependencies = serializers.SerializerMethodField()
    events = EventSerializer(many=True, read_only=True)
    cases = CaseSerializer(many=True, read_only=True)
    trip_risks = TripRiskSerializer(many=True, read_only=True)
    itinerary_changes = ItineraryChangeSerializer(many=True, read_only=True)
    readiness_assessment = serializers.SerializerMethodField()

    def get_readiness_assessment(self, obj):
        latest = obj.readiness_assessments.order_by('-calculated_at').first()
        if latest is None:
            return None
        return ReadinessAssessmentSerializer(latest).data

    def get_dependencies(self, obj):
        seen = {}
        for element in obj.itinerary_elements.all():
            for dependency in element.outgoing_dependencies.all():
                seen[dependency.pk] = dependency
            for dependency in element.incoming_dependencies.all():
                seen[dependency.pk] = dependency
        ordered = sorted(seen.values(), key=lambda dependency: dependency.pk)
        return DependencySerializer(ordered, many=True).data

    class Meta:
        model = Trip
        fields = [
            'id',
            'guide_id',
            'name',
            'start_time',
            'end_time',
            'status',
            'itinerary_elements',
            'dependencies',
            'events',
            'cases',
            'trip_risks',
            'itinerary_changes',
            'readiness_assessment',
        ]


class TripSummarySerializer(serializers.ModelSerializer):

    readiness = serializers.CharField(read_only=True)
    open_cases = serializers.IntegerField(read_only=True)
    affected_elements = serializers.IntegerField(read_only=True)
    open_risks = serializers.IntegerField(read_only=True)
    nearest_departure = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Trip
        fields = [
            'id',
            'guide_id',
            'name',
            'start_time',
            'end_time',
            'status',
            'readiness',
            'open_cases',
            'affected_elements',
            'open_risks',
            'nearest_departure',
        ]


class TripWriteSerializer(serializers.ModelSerializer):

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
        read_only_fields = ['id']


class LocationInputField(serializers.Field):

    def to_internal_value(self, data):
        if isinstance(data, bool):
            raise serializers.ValidationError("Location must be an id or an object.")
        if isinstance(data, int):
            try:
                return Location.objects.get(pk=data)
            except Location.DoesNotExist:
                raise serializers.ValidationError(
                    f"Location id {data} does not exist."
                )
        if isinstance(data, dict):
            serializer = LocationSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            return {'_create': serializer.validated_data}
        raise serializers.ValidationError(
            "Location must be an existing id or an object with name, "
            "latitude, longitude and address."
        )


class BookingCreateSerializer(serializers.ModelSerializer):

    booking_reference = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    class Meta:
        model = Booking
        fields = [
            'supplier_name',
            'booking_reference',
            'status',
            'notes',
        ]


class ItineraryElementCreateSerializer(serializers.ModelSerializer):

    start_location = LocationInputField(required=False, allow_null=True)
    end_location = LocationInputField(required=False, allow_null=True)
    bookings = BookingCreateSerializer(many=True, required=False)

    class Meta:
        model = ItineraryElement
        fields = [
            'type',
            'name',
            'sequence',
            'planned_start',
            'planned_end',
            'status',
            'start_location',
            'end_location',
            'bookings',
        ]


class DependencyCreateSerializer(serializers.Serializer):
    from_element_index = serializers.IntegerField(min_value=0)
    to_element_index = serializers.IntegerField(min_value=0)
    type = serializers.CharField(max_length=50)
    minimum_buffer = serializers.DurationField()


class TripImportSerializer(serializers.Serializer):
    """Upload form for the document-import extract endpoint.

    Exposed to DRF's browsable API so the page renders a real file input.
    """

    file = serializers.FileField(write_only=True)
    model = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
    )

    def validate_file(self, value):
        if value.size > MAX_FILE_BYTES:
            raise serializers.ValidationError(
                f"File exceeds the {MAX_FILE_BYTES} byte limit."
            )
        mime_type = resolve_mime_type(
            getattr(value, "name", ""),
            getattr(value, "content_type", None),
        )
        if mime_type is None:
            raise serializers.ValidationError(
                "Unsupported file type. Accepted uploads are images "
                "(png, jpeg, webp) and PDFs."
            )
        value.import_mime_type = mime_type
        return value


class TripCreateSerializer(serializers.ModelSerializer):

    itinerary_elements = ItineraryElementCreateSerializer(
        many=True,
        required=False,
    )
    dependencies = DependencyCreateSerializer(
        many=True,
        required=False,
    )

    class Meta:
        model = Trip
        fields = [
            'guide_id',
            'name',
            'start_time',
            'end_time',
            'status',
            'itinerary_elements',
            'dependencies',
        ]

    def validate(self, attrs):
        elements = attrs.get('itinerary_elements', [])
        element_count = len(elements)
        for dependency in attrs.get('dependencies', []):
            if dependency['from_element_index'] >= element_count:
                raise serializers.ValidationError({
                    'dependencies': (
                        f"from_element_index {dependency['from_element_index']} "
                        "is out of range for itinerary_elements."
                    ),
                })
            if dependency['to_element_index'] >= element_count:
                raise serializers.ValidationError({
                    'dependencies': (
                        f"to_element_index {dependency['to_element_index']} "
                        "is out of range for itinerary_elements."
                    ),
                })
        return attrs

    def create(self, validated_data):
        elements_data = validated_data.pop('itinerary_elements', [])
        dependencies_data = validated_data.pop('dependencies', [])

        with transaction.atomic():
            trip = Trip.objects.create(**validated_data)

            element_map = []
            for item in elements_data:
                bookings_data = item.pop('bookings', [])
                start_location = item.pop('start_location', None)
                if isinstance(start_location, dict):
                    start_location = Location.objects.create(
                        **start_location['_create']
                    )
                end_location = item.pop('end_location', None)
                if isinstance(end_location, dict):
                    end_location = Location.objects.create(
                        **end_location['_create']
                    )

                element = ItineraryElement.objects.create(
                    trip=trip,
                    start_location=start_location,
                    end_location=end_location,
                    **item,
                )
                for booking_data in bookings_data:
                    Booking.objects.create(
                        itinerary_element=element,
                        **booking_data,
                    )
                element_map.append(element)

            for dependency in dependencies_data:
                Dependency.objects.create(
                    from_element=element_map[dependency['from_element_index']],
                    to_element=element_map[dependency['to_element_index']],
                    type=dependency['type'],
                    minimum_buffer=dependency['minimum_buffer'],
                )

        return trip


class FlightStatusCreateSerializer(serializers.ModelSerializer):
    """Ingestion payload for POST /api/trips/<pk>/live/flight-status/."""

    reported_at = serializers.DateTimeField(required=False)

    class Meta:
        model = FlightStatusRecord
        fields = [
            'itinerary_element',
            'flight_number',
            'date',
            'origin_airport',
            'destination_airport',
            'scheduled_departure',
            'estimated_departure',
            'scheduled_arrival',
            'estimated_arrival',
            'status',
            'gate',
            'terminal',
            'delay_minutes',
            'delay_reason',
            'reported_at',
        ]

    def create(self, validated_data):
        validated_data.setdefault('reported_at', timezone.now())
        return FlightStatusRecord.objects.create(**validated_data)


class TrainStatusCreateSerializer(serializers.ModelSerializer):
    """Ingestion payload for POST /api/trips/<pk>/live/train-status/."""

    reported_at = serializers.DateTimeField(required=False)
    speed_kmh = serializers.FloatField(required=False, default=0.0)

    class Meta:
        model = TrainStatusRecord
        fields = [
            'itinerary_element',
            'train_number',
            'date',
            'origin_station',
            'destination_station',
            'current_station',
            'scheduled_time',
            'estimated_time',
            'status',
            'platform',
            'delay_minutes',
            'speed_kmh',
            'reported_at',
        ]

    def create(self, validated_data):
        validated_data.setdefault('reported_at', timezone.now())
        return TrainStatusRecord.objects.create(**validated_data)


class TrafficRouteCreateSerializer(serializers.ModelSerializer):
    """Ingestion payload for POST /api/trips/<pk>/live/traffic/."""

    checked_at = serializers.DateTimeField(required=False)
    incidents = serializers.JSONField(required=False, default=list)

    class Meta:
        model = TrafficRouteRecord
        fields = [
            'itinerary_element',
            'origin',
            'destination',
            'departure_time',
            'distance_km',
            'duration_minutes',
            'traffic_delay_minutes',
            'congestion_level',
            'recommended_route',
            'incidents',
            'checked_at',
        ]

    def create(self, validated_data):
        validated_data.setdefault('checked_at', timezone.now())
        return TrafficRouteRecord.objects.create(**validated_data)


class WeatherCreateSerializer(serializers.ModelSerializer):
    """Ingestion payload for POST /api/trips/<pk>/live/weather/."""

    checked_at = serializers.DateTimeField(required=False)
    warnings = serializers.JSONField(required=False, default=list)

    class Meta:
        model = WeatherRecord
        fields = [
            'itinerary_element',
            'date_time',
            'condition',
            'temperature_c',
            'temperature_f',
            'humidity_percent',
            'wind_speed_kmh',
            'precipitation_mm',
            'visibility_km',
            'warnings',
            'checked_at',
        ]

    def create(self, validated_data):
        validated_data.setdefault('checked_at', timezone.now())
        return WeatherRecord.objects.create(**validated_data)


class GuidePositionCreateSerializer(serializers.ModelSerializer):
    """Ingestion payload for POST /api/trips/<pk>/live/gps/."""

    captured_at = serializers.DateTimeField(required=False)
    received_at = serializers.DateTimeField(required=False)

    class Meta:
        model = GuidePosition
        fields = [
            'itinerary_element',
            'device_id',
            'latitude',
            'longitude',
            'speed_kmh',
            'heading_deg',
            'altitude_m',
            'captured_at',
            'received_at',
        ]

    def create(self, validated_data):
        validated_data.setdefault('received_at', timezone.now())
        validated_data.setdefault('captured_at', validated_data['received_at'])
        return GuidePosition.objects.create(**validated_data)


class FeedsReceivedSerializer(serializers.Serializer):
    """The ingested record echoed back on success."""

    element_id = serializers.IntegerField(read_only=True)
    received = serializers.JSONField(read_only=True)
    statuses = serializers.ListField(
        child=serializers.JSONField(),
        read_only=True,
    )
    case_id = serializers.IntegerField(read_only=True, allow_null=True)
    phase = serializers.CharField(read_only=True)
    affected_bookings = serializers.ListField(
        child=serializers.IntegerField(),
        read_only=True,
    )


class LiveNodeHistorySerializer(serializers.Serializer):
    status = serializers.CharField(read_only=True)
    classification = serializers.CharField(read_only=True)
    severity = serializers.CharField(read_only=True)
    reason = serializers.CharField(read_only=True)
    calculated_at = serializers.DateTimeField(read_only=True)


class LiveNodeSerializer(serializers.Serializer):
    element_id = serializers.IntegerField(read_only=True)
    element_name = serializers.CharField(read_only=True)
    sequence = serializers.IntegerField(read_only=True)
    type = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    classification = serializers.CharField(read_only=True)
    severity = serializers.CharField(read_only=True)
    reason = serializers.CharField(read_only=True)
    calculated_at = serializers.DateTimeField(read_only=True)
    history = LiveNodeHistorySerializer(many=True, read_only=True)


class LiveFeedRecordSerializer(serializers.Serializer):
    element_id = serializers.IntegerField(read_only=True)
    values = serializers.JSONField(read_only=True)


class LiveFeedsSerializer(serializers.Serializer):
    flight = serializers.ListField(child=serializers.JSONField(), read_only=True)
    train = serializers.ListField(child=serializers.JSONField(), read_only=True)
    traffic = serializers.ListField(child=serializers.JSONField(), read_only=True)
    weather = serializers.ListField(child=serializers.JSONField(), read_only=True)
    gps = serializers.JSONField(read_only=True, allow_null=True)


class LiveActionSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    type = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    completed_at = serializers.DateTimeField(read_only=True, allow_null=True)


class LiveCaseSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    priority = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    primary_event_id = serializers.IntegerField(read_only=True, allow_null=True)
    nodes = LiveNodeSerializer(many=True, read_only=True)
    actions = LiveActionSerializer(many=True, read_only=True)


class LiveRecommendedActionSerializer(serializers.Serializer):
    case_id = serializers.IntegerField(read_only=True)
    type = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)


class LiveStatusSummarySerializer(serializers.Serializer):
    disrupted = serializers.IntegerField(read_only=True)
    at_risk = serializers.IntegerField(read_only=True)
    valid = serializers.IntegerField(read_only=True)
    unknown = serializers.IntegerField(read_only=True)
    open_cases = serializers.IntegerField(read_only=True)
    affected_bookings = serializers.IntegerField(read_only=True)


class LiveStatusDetailSerializer(serializers.Serializer):
    """Read-only view of ``live_status_payload``."""

    trip_id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    phase = serializers.CharField(read_only=True)
    generated_at = serializers.DateTimeField(read_only=True)
    nodes = LiveNodeSerializer(many=True, read_only=True)
    feeds = LiveFeedsSerializer(read_only=True)
    cases = LiveCaseSerializer(many=True, read_only=True)
    recommended_actions = LiveRecommendedActionSerializer(
        many=True, read_only=True
    )
    summary = LiveStatusSummarySerializer(read_only=True)


class SummaryAffectedNodeSerializer(serializers.Serializer):
    element_id = serializers.IntegerField(read_only=True)
    element_name = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    classification = serializers.CharField(read_only=True)
    severity = serializers.CharField(read_only=True)
    reason = serializers.CharField(read_only=True)


class SummaryRecommendedActionSerializer(serializers.Serializer):
    case_id = serializers.IntegerField(read_only=True, allow_null=True)
    type = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)


class SummaryRiskSerializer(serializers.Serializer):
    severity = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)


class TripSummaryResponseSerializer(serializers.Serializer):
    """Response shape of the on-demand LLM trip summary."""

    headline = serializers.CharField(read_only=True)
    phase = serializers.CharField(read_only=True)
    overall_assessment = serializers.CharField(read_only=True)
    summary = serializers.CharField(read_only=True)
    affected_nodes = SummaryAffectedNodeSerializer(many=True, read_only=True)
    recommended_actions = SummaryRecommendedActionSerializer(
        many=True, read_only=True
    )
    risks = SummaryRiskSerializer(many=True, read_only=True)