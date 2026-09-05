from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import (
    Trip,
    Location,
    ItineraryElement,
    Booking,
    Event,
    Impact,
    Case,
    CaseAction,
    CaseImpact,
    ReadinessAssessment,
    TripRisk,
)

NON_TRIP_ROUTES = [
    '/api/locations/',
    '/api/itinerary-elements/',
    '/api/bookings/',
    '/api/dependencies/',
    '/api/events/',
    '/api/impacts/',
    '/api/cases/',
    '/api/case-impacts/',
    '/api/case-actions/',
    '/api/itinerary-changes/',
    '/api/audit-logs/',
    '/api/readiness-assessments/',
    '/api/trip-risks/',
]


class TripApiTests(APITestCase):
    def setUp(self):
        now = timezone.now()
        self.trip = Trip.objects.create(
            guide_id=101,
            name="Kerala Monsoon Escape",
            start_time=now - timedelta(days=1),
            end_time=now + timedelta(days=4),
            status="active",
        )
        self.airport = Location.objects.create(
            name="Trivandrum Intl Airport (TRV)",
            latitude=8.4822,
            longitude=76.9201,
            address="Chacka, Thiruvananthapuram, Kerala",
        )
        self.resort = Location.objects.create(
            name="Kovalam Beach Resort",
            latitude=8.4004,
            longitude=76.9786,
            address="Lighthouse Beach, Kovalam, Kerala",
        )
        self.flight = ItineraryElement.objects.create(
            trip=self.trip,
            type="flight",
            name="Flight AI-1049 Delhi to Trivandrum",
            start_location=self.airport,
            end_location=self.airport,
            planned_start=now - timedelta(hours=12),
            planned_end=now - timedelta(hours=9),
            status="disrupted",
            sequence=1,
        )
        ItineraryElement.objects.create(
            trip=self.trip,
            type="road_transfer",
            name="Transfer Trivandrum Airport to Kovalam",
            start_location=self.airport,
            end_location=self.resort,
            planned_start=now + timedelta(days=1),
            planned_end=now + timedelta(days=1, hours=1),
            status="at_risk",
            sequence=2,
        )
        Booking.objects.create(
            itinerary_element=self.flight,
            supplier_name="Air India",
            booking_reference="AI-DEL-TRV-4412",
            status="confirmed",
        )
        self.event = Event.objects.create(
            trip=self.trip,
            type="flight_delay",
            source="flight_status",
            title="AI-1049 delayed",
            location=self.airport,
            occurred_at=now - timedelta(hours=12),
            reported_at=now - timedelta(hours=11),
            severity="high",
            status="open",
            created_by=101,
        )
        Case.objects.create(
            trip=self.trip,
            primary_event=self.event,
            title="AI-1049 delay case",
            priority="high",
            status="open",
        )
        TripRisk.objects.create(
            trip=self.trip,
            type="weather",
            severity="high",
            reason="Rain warning",
            status="open",
        )
        ReadinessAssessment.objects.create(
            trip=self.trip,
            status="attention",
            reason="Tight connection",
            calculated_at=now - timedelta(days=2),
        )

    def test_trip_list_returns_summary(self):
        response = self.client.get("/api/trips/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        trip = response.data[0]
        self.assertEqual(trip["name"], "Kerala Monsoon Escape")
        self.assertEqual(trip["status"], "active")
        self.assertNotIn("itinerary_elements", trip)
        self.assertEqual(trip["readiness"], "attention")
        self.assertEqual(trip["open_cases"], 1)
        self.assertEqual(trip["affected_elements"], 2)
        self.assertEqual(trip["open_risks"], 1)
        self.assertIsNotNone(trip["nearest_departure"])

    def test_trip_detail_returns_full_graph(self):
        response = self.client.get(f"/api/trips/{self.trip.pk}/")
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual(len(data["itinerary_elements"]), 2)
        flight = data["itinerary_elements"][0]
        self.assertEqual(flight["start_location"]["name"], "Trivandrum Intl Airport (TRV)")
        self.assertEqual(flight["bookings"][0]["booking_reference"], "AI-DEL-TRV-4412")
        self.assertEqual(len(data["events"]), 1)
        self.assertEqual(data["events"][0]["title"], "AI-1049 delayed")
        self.assertEqual(len(data["cases"]), 1)
        self.assertEqual(len(data["trip_risks"]), 1)
        self.assertEqual(data["readiness_assessment"]["status"], "attention")

    def test_trip_detail_supports_get(self):
        response = self.client.get(f"/api/trips/{self.trip.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.trip.pk)

    def test_trip_detail_supports_delete(self):
        response = self.client.delete(f"/api/trips/{self.trip.pk}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Trip.objects.filter(pk=self.trip.pk).exists())

    def test_trip_update_supports_put(self):
        response = self.client.put(
            f"/api/trips/{self.trip.pk}/",
            {
                "guide_id": 101,
                "name": "Kerala Monsoon Escape",
                "start_time": "2026-09-04T00:15:00Z",
                "end_time": "2026-09-07T18:00:00Z",
                "status": "completed",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "completed")

    def test_trip_create(self):
        response = self.client.post(
            "/api/trips/",
            {
                "guide_id": 200,
                "name": "Himalayan Yatra",
                "start_time": "2026-09-20T00:00:00Z",
                "end_time": "2026-09-27T23:00:00Z",
                "status": "upcoming",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "Himalayan Yatra")
        self.assertEqual(response.data["itinerary_elements"], [])

    def test_trip_create_full_nested_payload(self):
        response = self.client.post(
            "/api/trips/",
            {
                "guide_id": 300,
                "name": "Full Trip",
                "start_time": "2026-09-01T00:00:00Z",
                "end_time": "2026-09-05T00:00:00Z",
                "status": "upcoming",
                "itinerary_elements": [
                    {
                        "type": "flight",
                        "name": "Flight AI-1",
                        "sequence": 1,
                        "planned_start": "2026-09-02T00:30:00Z",
                        "planned_end": "2026-09-02T04:00:00Z",
                        "status": "valid",
                        "start_location": {
                            "name": "New Delhi Airport",
                            "latitude": 28.55,
                            "longitude": 77.1,
                            "address": "IGI Airport",
                        },
                        "end_location": {
                            "name": "Trivandrum Airport",
                            "latitude": 8.48,
                            "longitude": 76.92,
                            "address": "TRV",
                        },
                        "bookings": [
                            {
                                "supplier_name": "Air India",
                                "booking_reference": "AI-999",
                                "status": "confirmed",
                            }
                        ],
                    },
                    {
                        "type": "road_transfer",
                        "name": "Transfer",
                        "sequence": 2,
                        "planned_start": "2026-09-02T05:00:00Z",
                        "planned_end": "2026-09-02T06:00:00Z",
                        "status": "valid",
                        "start_location": 1,
                        "end_location": 1,
                    },
                ],
                "dependencies": [
                    {
                        "from_element_index": 0,
                        "to_element_index": 1,
                        "type": "transfer",
                        "minimum_buffer": "PT1H30M",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.data
        self.assertEqual(len(data["itinerary_elements"]), 2)

        flight = data["itinerary_elements"][0]
        self.assertEqual(flight["start_location"]["name"], "New Delhi Airport")
        self.assertEqual(flight["bookings"][0]["booking_reference"], "AI-999")

        self.assertEqual(
            Trip.objects.filter(name="Full Trip", guide_id=300).count(), 1
        )
        trip = Trip.objects.get(name="Full Trip")
        self.assertEqual(trip.itinerary_elements.count(), 2)
        self.assertEqual(Location.objects.filter(name="New Delhi Airport").count(), 1)
        self.assertEqual(trip.itinerary_elements.get(sequence=1).bookings.count(), 1)

        self.assertEqual(Location.objects.count(), 4)
        self.assertEqual(
            trip.itinerary_elements.get(sequence=2).start_location_id,
            self.airport.pk,
        )

    def test_trip_create_reuses_existing_location(self):
        response = self.client.post(
            "/api/trips/",
            {
                "guide_id": 301,
                "name": "Reuse Trip",
                "start_time": "2026-09-01T00:00:00Z",
                "end_time": "2026-09-05T00:00:00Z",
                "status": "upcoming",
                "itinerary_elements": [
                    {
                        "type": "hotel",
                        "name": "Hotel",
                        "sequence": 1,
                        "planned_start": "2026-09-02T00:00:00Z",
                        "planned_end": "2026-09-03T00:00:00Z",
                        "status": "valid",
                        "start_location": self.airport.pk,
                        "end_location": self.airport.pk,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        trip = Trip.objects.get(name="Reuse Trip")
        element = trip.itinerary_elements.get(sequence=1)
        self.assertEqual(element.start_location_id, self.airport.pk)

    def test_trip_create_invalid_location_id_returns_400_and_rolls_back(self):
        response = self.client.post(
            "/api/trips/",
            {
                "guide_id": 302,
                "name": "Bad Location Trip",
                "start_time": "2026-09-01T00:00:00Z",
                "end_time": "2026-09-05T00:00:00Z",
                "status": "upcoming",
                "itinerary_elements": [
                    {
                        "type": "hotel",
                        "name": "Hotel",
                        "sequence": 1,
                        "planned_start": "2026-09-02T00:00:00Z",
                        "planned_end": "2026-09-03T00:00:00Z",
                        "status": "valid",
                        "start_location": 9999,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Trip.objects.filter(name="Bad Location Trip").exists())

    def test_trip_create_out_of_range_dependency_returns_400_and_rolls_back(self):
        response = self.client.post(
            "/api/trips/",
            {
                "guide_id": 303,
                "name": "Bad Dep Trip",
                "start_time": "2026-09-01T00:00:00Z",
                "end_time": "2026-09-05T00:00:00Z",
                "status": "upcoming",
                "dependencies": [
                    {
                        "from_element_index": 0,
                        "to_element_index": 1,
                        "type": "transfer",
                        "minimum_buffer": "PT1H",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Trip.objects.filter(name="Bad Dep Trip").exists())


class ApiSurfaceTests(APITestCase):
    def test_non_trip_routes_are_removed(self):
        for route in NON_TRIP_ROUTES:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 404)


class DisruptionDetailTests(APITestCase):
    def setUp(self):
        self.trip = Trip.objects.create(
            guide_id=101,
            name="Kerala Monsoon Escape",
            start_time="2026-09-04T00:15:00Z",
            end_time="2026-09-07T18:00:00Z",
            status="active",
        )
        self.airport = Location.objects.create(
            name="Trivandrum Intl Airport (TRV)",
            latitude=8.4822,
            longitude=76.9201,
            address="Chacka, Thiruvananthapuram, Kerala",
        )
        self.element = ItineraryElement.objects.create(
            trip=self.trip,
            type="flight",
            name="Flight AI-1049",
            start_location=self.airport,
            end_location=self.airport,
            planned_start="2026-09-04T00:30:00Z",
            planned_end="2026-09-04T04:00:00Z",
            status="disrupted",
            sequence=1,
        )
        self.event = Event.objects.create(
            trip=self.trip,
            type="flight_delay",
            source="flight_status",
            title="AI-1049 delayed",
            location=self.airport,
            occurred_at="2026-09-04T01:15:00Z",
            reported_at="2026-09-04T01:20:00Z",
            severity="high",
            status="open",
            created_by=101,
        )
        self.impact = Impact.objects.create(
            event=self.event,
            itinerary_element=self.element,
            classification="direct",
            status="disrupted",
            severity="high",
            reason="Flight departed 2h late",
            calculated_at="2026-09-04T02:30:00Z",
        )
        self.case = Case.objects.create(
            trip=self.trip,
            primary_event=self.event,
            title="AI-1049 delay case",
            priority="high",
            status="open",
            resolved_at=None,
            assigned_to=5,
        )
        CaseAction.objects.create(
            case=self.case,
            type="contact_supplier",
            description="Spoke with airline",
            status="completed",
            created_by=101,
        )
        CaseImpact.objects.create(
            case=self.case,
            impact=self.impact,
        )

    def test_trip_detail_includes_impacts_and_case_actions(self):
        response = self.client.get(f"/api/trips/{self.trip.pk}/")
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual(data["events"][0]["impacts"][0]["classification"], "direct")
        case = data["cases"][0]
        self.assertEqual(case["assigned_to"], 5)
        self.assertEqual(case["actions"][0]["type"], "contact_supplier")
        self.assertEqual(case["case_impacts"][0]["impact"]["itinerary_element"], self.element.pk)


class DemoFixtureTest(TestCase):
    fixtures = ["demo_trips"]

    def test_demo_trips_loaded_from_fixture(self):
        self.assertEqual(Trip.objects.filter(pk__gte=100).count(), 3)
        self.assertEqual(Event.objects.filter(pk__gte=100).count(), 2)
        self.assertEqual(Case.objects.filter(pk__gte=100).count(), 1)