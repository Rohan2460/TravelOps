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