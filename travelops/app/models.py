from django.db import models

class Trip(models.Model):

    STATUS_CHOICES = [
        ('upcoming', 'Upcoming'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    guide_id = models.IntegerField()
    name = models.CharField(max_length=255)

    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='upcoming'
    )

    def __str__(self):
        return f"{self.reference} - {self.name}"