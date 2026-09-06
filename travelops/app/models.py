from django.db import models


class Trip(models.Model):
    guide_id = models.IntegerField()
    name = models.CharField(max_length=255)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=50)

    def __str__(self):
        return self.name


class Location(models.Model):
    name = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()
    address = models.CharField(max_length=500)

    def __str__(self):
        return self.name


class ItineraryElement(models.Model):
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name='itinerary_elements'
    )
    type = models.CharField(max_length=50)
    name = models.CharField(max_length=255)

    start_location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='starting_elements'
    )

    end_location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ending_elements'
    )

    planned_start = models.DateTimeField()
    planned_end = models.DateTimeField()

    actual_start = models.DateTimeField(
        null=True,
        blank=True
    )

    actual_end = models.DateTimeField(
        null=True,
        blank=True
    )

    status = models.CharField(max_length=50)
    sequence = models.IntegerField()

    def __str__(self):
        return self.name


class Booking(models.Model):
    itinerary_element = models.ForeignKey(
        ItineraryElement,
        on_delete=models.CASCADE,
        related_name='bookings'
    )

    supplier_name = models.CharField(max_length=255)
    booking_reference = models.CharField(max_length=255)
    status = models.CharField(max_length=50)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.booking_reference


class Dependency(models.Model):
    from_element = models.ForeignKey(
        ItineraryElement,
        on_delete=models.CASCADE,
        related_name='outgoing_dependencies'
    )

    to_element = models.ForeignKey(
        ItineraryElement,
        on_delete=models.CASCADE,
        related_name='incoming_dependencies'
    )

    type = models.CharField(max_length=50)
    minimum_buffer = models.DurationField()

    def __str__(self):
        return f"{self.from_element} -> {self.to_element}"


class Event(models.Model):
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name='events'
    )
    type = models.CharField(max_length=50)
    source = models.CharField(max_length=50)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='events'
    )
    occurred_at = models.DateTimeField()
    reported_at = models.DateTimeField()
    severity = models.CharField(max_length=50)
    status = models.CharField(max_length=50)
    created_by = models.IntegerField()

    def __str__(self):
        return self.title


class Impact(models.Model):
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='impacts'
    )
    itinerary_element = models.ForeignKey(
        ItineraryElement,
        on_delete=models.CASCADE,
        related_name='impacts'
    )
    classification = models.CharField(max_length=50)
    status = models.CharField(max_length=50)
    severity = models.CharField(max_length=50)
    reason = models.TextField(blank=True)
    calculated_at = models.DateTimeField()

    def __str__(self):
        return f"{self.event} -> {self.itinerary_element}"


class Case(models.Model):
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name='cases'
    )
    primary_event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='primary_cases'
    )
    title = models.CharField(max_length=255)
    priority = models.CharField(max_length=50)
    status = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(
        null=True,
        blank=True
    )
    assigned_to = models.IntegerField(
        null=True,
        blank=True
    )

    def __str__(self):
        return self.title


class CaseImpact(models.Model):
    case = models.ForeignKey(
        Case,
        on_delete=models.CASCADE,
        related_name='case_impacts'
    )
    impact = models.ForeignKey(
        Impact,
        on_delete=models.CASCADE,
        related_name='case_impacts'
    )

    def __str__(self):
        return f"{self.case} -> {self.impact}"


class CaseAction(models.Model):
    case = models.ForeignKey(
        Case,
        on_delete=models.CASCADE,
        related_name='actions'
    )
    type = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=50)
    created_by = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.case}: {self.type}"


class ItineraryChange(models.Model):
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name='itinerary_changes'
    )
    itinerary_element = models.ForeignKey(
        ItineraryElement,
        on_delete=models.CASCADE,
        related_name='changes'
    )
    change_type = models.CharField(max_length=50)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    reason = models.TextField(blank=True)
    event = models.ForeignKey(
        Event,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='triggered_changes'
    )
    changed_by = models.IntegerField()
    changed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.itinerary_element}: {self.change_type}"


class AuditLog(models.Model):
    user_id = models.IntegerField()
    entity_type = models.CharField(max_length=50)
    entity_id = models.IntegerField()
    action = models.CharField(max_length=50)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.entity_type}:{self.entity_id} {self.action}"


class ReadinessAssessment(models.Model):
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name='readiness_assessments'
    )
    status = models.CharField(max_length=50)
    reason = models.TextField(blank=True)
    calculated_at = models.DateTimeField()

    def __str__(self):
        return f"{self.trip}: {self.status}"


class TripRisk(models.Model):
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name='trip_risks'
    )
    type = models.CharField(max_length=50)
    severity = models.CharField(max_length=50)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.trip}: {self.type}"


class FlightStatusRecord(models.Model):
    """Latest flight-status snapshot ingested from a live flight feed."""

    itinerary_element = models.ForeignKey(
        ItineraryElement,
        on_delete=models.CASCADE,
        related_name='flight_status_records'
    )
    flight_number = models.CharField(max_length=50)
    date = models.CharField(max_length=20)
    origin_airport = models.CharField(max_length=50, blank=True)
    destination_airport = models.CharField(max_length=50, blank=True)
    scheduled_departure = models.DateTimeField(null=True, blank=True)
    estimated_departure = models.DateTimeField(null=True, blank=True)
    scheduled_arrival = models.DateTimeField(null=True, blank=True)
    estimated_arrival = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=50)
    gate = models.CharField(max_length=20, blank=True)
    terminal = models.CharField(max_length=20, blank=True)
    delay_minutes = models.IntegerField(default=0)
    delay_reason = models.TextField(blank=True)
    reported_at = models.DateTimeField()

    class Meta:
        ordering = ['-reported_at']

    def __str__(self):
        return f"{self.flight_number}: {self.status}"


class TrainStatusRecord(models.Model):
    """Latest train-status snapshot ingested from a live train feed."""

    itinerary_element = models.ForeignKey(
        ItineraryElement,
        on_delete=models.CASCADE,
        related_name='train_status_records'
    )
    train_number = models.CharField(max_length=50)
    date = models.CharField(max_length=20)
    origin_station = models.CharField(max_length=255, blank=True)
    destination_station = models.CharField(max_length=255, blank=True)
    current_station = models.CharField(max_length=255, blank=True)
    scheduled_time = models.DateTimeField(null=True, blank=True)
    estimated_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=50)
    platform = models.CharField(max_length=20, blank=True)
    delay_minutes = models.IntegerField(default=0)
    speed_kmh = models.FloatField(default=0.0)
    reported_at = models.DateTimeField()

    class Meta:
        ordering = ['-reported_at']

    def __str__(self):
        return f"{self.train_number}: {self.status}"


class TrafficRouteRecord(models.Model):
    """Latest traffic / route-condition snapshot for a road transfer."""

    itinerary_element = models.ForeignKey(
        ItineraryElement,
        on_delete=models.CASCADE,
        related_name='traffic_route_records'
    )
    origin = models.CharField(max_length=255, blank=True)
    destination = models.CharField(max_length=255, blank=True)
    departure_time = models.DateTimeField(null=True, blank=True)
    distance_km = models.FloatField(default=0.0)
    duration_minutes = models.FloatField(default=0.0)
    traffic_delay_minutes = models.FloatField(default=0.0)
    congestion_level = models.CharField(max_length=20)
    recommended_route = models.CharField(max_length=255, blank=True)
    incidents = models.JSONField(default=list, blank=True)
    checked_at = models.DateTimeField()

    class Meta:
        ordering = ['-checked_at']

    def __str__(self):
        return f"{self.itinerary_element}: {self.congestion_level}"


class WeatherRecord(models.Model):
    """Latest weather observation for a location or itinerary element."""

    itinerary_element = models.ForeignKey(
        ItineraryElement,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='weather_records'
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='weather_records'
    )
    date_time = models.DateTimeField()
    condition = models.CharField(max_length=100, blank=True)
    temperature_c = models.FloatField(null=True, blank=True)
    temperature_f = models.FloatField(null=True, blank=True)
    humidity_percent = models.FloatField(default=0.0)
    wind_speed_kmh = models.FloatField(default=0.0)
    precipitation_mm = models.FloatField(default=0.0)
    visibility_km = models.FloatField(default=0.0)
    warnings = models.JSONField(default=list, blank=True)
    checked_at = models.DateTimeField()

    class Meta:
        ordering = ['-checked_at']

    def __str__(self):
        return f"{self.condition} @ {self.location or self.itinerary_element}"


class GuidePosition(models.Model):
    """Live GPS position reported by the guide's device during an active trip."""

    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name='guide_positions'
    )
    itinerary_element = models.ForeignKey(
        ItineraryElement,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='guide_positions'
    )
    device_id = models.CharField(max_length=100)
    latitude = models.FloatField()
    longitude = models.FloatField()
    speed_kmh = models.FloatField(default=0.0)
    heading_deg = models.FloatField(default=0.0)
    altitude_m = models.FloatField(default=0.0)
    captured_at = models.DateTimeField()
    received_at = models.DateTimeField()

    class Meta:
        ordering = ['-captured_at']

    def __str__(self):
        return f"{self.device_id} @ {self.latitude},{self.longitude}"


class NodeStatus(models.Model):
    """Computed operational status snapshot for an itinerary element.

    Append-only history produced by the live analysis engine. The latest row
    per (trip, itinerary_element) represents the element's current state.
    """

    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name='node_statuses'
    )
    itinerary_element = models.ForeignKey(
        ItineraryElement,
        on_delete=models.CASCADE,
        related_name='node_statuses'
    )
    status = models.CharField(max_length=50)
    classification = models.CharField(max_length=50)
    severity = models.CharField(max_length=50)
    reason = models.TextField(blank=True)
    source_event = models.ForeignKey(
        Event,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='node_statuses'
    )
    case = models.ForeignKey(
        Case,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='node_statuses'
    )
    calculated_at = models.DateTimeField()

    class Meta:
        ordering = ['-calculated_at']
        indexes = [
            models.Index(
                fields=['trip', 'itinerary_element', '-calculated_at'],
                name='nodestatus_trip_elem_calc_idx',
            ),
        ]

    def __str__(self):
        return f"{self.itinerary_element}: {self.status} ({self.classification})"