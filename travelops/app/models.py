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