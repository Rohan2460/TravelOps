from datetime import timedelta
from copy import deepcopy
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import (
    Trip,
    Location,
    ItineraryElement,
    Booking,
    Dependency,
    Event,
    Impact,
    Case,
    CaseAction,
    CaseImpact,
    ReadinessAssessment,
    TripRisk,
    FlightStatusRecord,
    TrainStatusRecord,
    TrafficRouteRecord,
    WeatherRecord,
    GuidePosition,
    NodeStatus,
)
from .analysis import analyze_trip
from .gemini_import import GeminiApiError, GeminiConfigurationError
from . import routes
from .routes import RoutesApiError, RoutesConfigurationError
from .live_analysis import (
    AT_RISK,
    DIRECT,
    DISRUPTED,
    DOWNSTREAM,
    live_status_payload,
    recompute_live_status,
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


class ReadinessEngineTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.airport = Location.objects.create(
            name="Airport",
            latitude=0.0,
            longitude=0.0,
            address="airport address",
        )
        self.resort = Location.objects.create(
            name="Resort",
            latitude=0.0,
            longitude=0.0,
            address="resort address",
        )

    def _make_trip(self, start_delta=timedelta(hours=4), end_delta=timedelta(days=2)):
        return Trip.objects.create(
            guide_id=1,
            name="Readiness Trip",
            start_time=self.now + start_delta,
            end_time=self.now + end_delta,
            status="upcoming",
        )

    def _element(
        self,
        trip,
        element_type,
        sequence,
        start_delta,
        end_delta,
        start_location=None,
        end_location=None,
        actual_end=None,
        actual_start=None,
    ):
        return ItineraryElement.objects.create(
            trip=trip,
            type=element_type,
            name=f"{element_type}-{sequence}",
            start_location=start_location,
            end_location=end_location or start_location,
            planned_start=self.now + start_delta,
            planned_end=self.now + end_delta,
            actual_start=actual_start,
            actual_end=actual_end,
            status="valid",
            sequence=sequence,
        )

    def _booking(self, element, status="confirmed"):
        return Booking.objects.create(
            itinerary_element=element,
            supplier_name="Supplier",
            booking_reference=f"REF-{element.pk}",
            status=status,
        )

    def _dependency(self, from_element, to_element, buffer=timedelta(minutes=30)):
        from .models import Dependency
        return Dependency.objects.create(
            from_element=from_element,
            to_element=to_element,
            type="transfer",
            minimum_buffer=buffer,
        )

    def test_phase_is_upcoming_before_start_time(self):
        trip = self._make_trip()
        self.assertEqual(analyze_trip(trip, now=self.now)["phase"], "UPCOMING")

    def test_phase_is_active_at_or_after_start_time(self):
        trip = self._make_trip(start_delta=timedelta(hours=-1))
        self.assertEqual(analyze_trip(trip, now=self.now)["phase"], "ACTIVE")

    def test_unknown_when_no_itinerary_elements(self):
        trip = self._make_trip()
        result = analyze_trip(trip, now=self.now)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["summary"], ["No itinerary data available."])

    def test_ready_when_complete_and_feasible(self):
        trip = self._make_trip()
        flight = self._element(
            trip, "flight", 1,
            timedelta(hours=2), timedelta(hours=4),
            self.airport, self.airport,
        )
        transfer = self._element(
            trip, "road_transfer", 2,
            timedelta(hours=5), timedelta(hours=6),
            self.airport, self.resort,
        )
        self._booking(flight)
        self._booking(transfer)
        self._dependency(flight, transfer, buffer=timedelta(minutes=15))
        result = analyze_trip(trip, now=self.now)
        self.assertEqual(result["status"], "READY")
        self.assertEqual(
            result["checks"]["completeness"]["warnings"],
            [],
        )

    def test_not_ready_when_required_booking_missing(self):
        trip = self._make_trip()
        flight = self._element(
            trip, "flight", 1,
            timedelta(hours=2), timedelta(hours=4),
            self.airport, self.airport,
        )
        result = analyze_trip(trip, now=self.now)
        self.assertEqual(result["status"], "NOT_READY")
        self.assertTrue(
            any(
                w["severity"] == "critical"
                and "no booking" in w["reason"]
                for w in result["checks"]["completeness"]["warnings"]
            )
        )

    def test_ready_with_warnings_when_booking_unconfirmed(self):
        trip = self._make_trip()
        hotel = self._element(
            trip, "hotel", 1,
            timedelta(hours=2), timedelta(hours=4),
            self.resort, self.resort,
        )
        self._booking(hotel, status="pending")
        result = analyze_trip(trip, now=self.now)
        self.assertEqual(result["status"], "READY_WITH_WARNINGS")
        self.assertEqual(
            result["checks"]["completeness"]["warnings"][0]["severity"],
            "medium",
        )

    def test_ready_with_warnings_when_location_missing(self):
        trip = self._make_trip()
        flight = self._element(
            trip, "flight", 1,
            timedelta(hours=2), timedelta(hours=4),
            start_location=None, end_location=None,
        )
        self._booking(flight)
        result = analyze_trip(trip, now=self.now)
        self.assertEqual(result["status"], "READY_WITH_WARNINGS")
        self.assertTrue(
            any(
                w["severity"] == "medium" and "location" in w["reason"]
                for w in result["checks"]["completeness"]["warnings"]
            )
        )

    def test_not_ready_when_connection_infeasible(self):
        trip = self._make_trip()
        first = self._element(
            trip, "activity", 1,
            timedelta(hours=2), timedelta(hours=3),
            self.resort,
        )
        second = self._element(
            trip, "activity", 2,
            timedelta(hours=3), timedelta(hours=4),
            self.resort,
        )
        self._dependency(first, second, buffer=timedelta(hours=2))
        result = analyze_trip(trip, now=self.now)
        self.assertEqual(result["status"], "NOT_READY")
        self.assertEqual(
            result["checks"]["feasibility"]["warnings"][0]["severity"],
            "critical",
        )

    def test_ready_with_warnings_when_connection_tight(self):
        trip = self._make_trip()
        first = self._element(
            trip, "activity", 1,
            timedelta(hours=2), timedelta(hours=3),
            self.resort,
        )
        second = self._element(
            trip, "activity", 2,
            timedelta(hours=3, minutes=45), timedelta(hours=4, minutes=45),
            self.resort,
        )
        self._dependency(first, second, buffer=timedelta(minutes=30))
        result = analyze_trip(trip, now=self.now)
        self.assertEqual(result["status"], "READY_WITH_WARNINGS")
        self.assertEqual(
            result["checks"]["feasibility"]["warnings"][0]["severity"],
            "medium",
        )

    def test_feasibility_uses_actual_end_when_available(self):
        trip = self._make_trip()
        first = self._element(
            trip, "activity", 1,
            timedelta(hours=2), timedelta(hours=3),
            self.resort,
            actual_end=self.now + timedelta(hours=4),
        )
        second = self._element(
            trip, "activity", 2,
            timedelta(hours=3), timedelta(hours=4),
            self.resort,
        )
        self._dependency(first, second, buffer=timedelta(minutes=30))
        result = analyze_trip(trip, now=self.now)
        self.assertEqual(result["status"], "NOT_READY")
        self.assertEqual(
            result["checks"]["feasibility"]["warnings"][0]["severity"],
            "critical",
        )

    def test_open_external_event_raises_warnings(self):
        trip = self._make_trip()
        self._element(
            trip, "activity", 1,
            timedelta(hours=2), timedelta(hours=3),
            self.resort,
        )
        Event.objects.create(
            trip=trip,
            type="weather_warning",
            source="weather",
            title="Heavy rain warning",
            location=self.resort,
            occurred_at=self.now,
            reported_at=self.now,
            severity="high",
            status="open",
            created_by=1,
        )
        result = analyze_trip(trip, now=self.now)
        self.assertEqual(result["status"], "READY_WITH_WARNINGS")
        self.assertEqual(
            result["checks"]["external"]["warnings"][0]["severity"],
            "high",
        )

    def test_resolved_external_event_is_ignored(self):
        trip = self._make_trip()
        self._element(
            trip, "activity", 1,
            timedelta(hours=2), timedelta(hours=3),
            self.resort,
        )
        Event.objects.create(
            trip=trip,
            type="weather_warning",
            source="weather",
            title="Heavy rain warning",
            location=self.resort,
            occurred_at=self.now,
            reported_at=self.now,
            severity="high",
            status="resolved",
            created_by=1,
        )
        result = analyze_trip(trip, now=self.now)
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["checks"]["external"]["warnings"], [])

    def test_open_trip_risk_raises_warnings(self):
        trip = self._make_trip()
        self._element(
            trip, "activity", 1,
            timedelta(hours=2), timedelta(hours=3),
            self.resort,
        )
        TripRisk.objects.create(
            trip=trip,
            type="weather",
            severity="high",
            reason="Possible heavy snowfall.",
            status="open",
        )
        result = analyze_trip(trip, now=self.now)
        self.assertEqual(result["status"], "READY_WITH_WARNINGS")
        self.assertEqual(
            result["checks"]["risks"]["warnings"][0]["severity"],
            "high",
        )

    def test_delay_event_affects_expected_arrival(self):
        trip = self._make_trip()
        flight = self._element(
            trip, "flight", 1,
            timedelta(hours=2), timedelta(hours=3),
            self.airport, self.airport,
        )
        transfer = self._element(
            trip, "road_transfer", 2,
            timedelta(hours=3), timedelta(hours=4),
            self.airport, self.resort,
        )
        self._booking(flight)
        self._booking(transfer)
        self._dependency(flight, transfer, buffer=timedelta(minutes=30))
        event = Event.objects.create(
            trip=trip,
            type="flight_delay",
            source="flight_status",
            title="Flight delayed 90 minutes",
            location=self.airport,
            occurred_at=self.now,
            reported_at=self.now,
            severity="high",
            status="open",
            created_by=1,
        )
        Impact.objects.create(
            event=event,
            itinerary_element=flight,
            classification="direct",
            status="disrupted",
            severity="high",
            reason="Flight departed 90 minutes late",
            calculated_at=self.now,
        )
        result = analyze_trip(trip, now=self.now)
        self.assertEqual(result["status"], "NOT_READY")
        flight_metric = result["timeline"]["elements"][0]
        self.assertEqual(flight_metric["delay_minutes"], 90)
        self.assertEqual(
            flight_metric["effective_end"],
            flight.planned_end + timedelta(minutes=90),
        )
        connection = result["timeline"]["connections"][0]
        self.assertTrue(connection["delayed"])
        self.assertEqual(connection["kind"], "infeasible")

    def test_element_metrics_include_durations_and_locations(self):
        trip = self._make_trip()
        flight = self._element(
            trip, "flight", 1,
            timedelta(hours=2), timedelta(hours=4),
            self.airport, self.airport,
        )
        self._booking(flight)
        result = analyze_trip(trip, now=self.now)
        metric = result["timeline"]["elements"][0]
        self.assertEqual(metric["id"], flight.pk)
        self.assertEqual(metric["start"], "Airport")
        self.assertEqual(metric["end"], "Airport")
        self.assertEqual(metric["planned_duration_minutes"], 120)
        self.assertIsNone(metric["actual_duration_minutes"])
        self.assertFalse(metric["started"])
        self.assertEqual(metric["booking_status"], "confirmed")

    def test_active_trip_uses_actual_times(self):
        trip = self._make_trip(start_delta=timedelta(hours=-3))
        started_at = self.now + timedelta(hours=1)
        self._element(
            trip, "activity", 1,
            timedelta(hours=1), timedelta(hours=3),
            self.resort,
            actual_start=started_at,
            actual_end=self.now + timedelta(hours=2, minutes=30),
        )
        result = analyze_trip(trip, now=self.now)
        self.assertEqual(result["phase"], "ACTIVE")
        metric = result["timeline"]["elements"][0]
        self.assertEqual(metric["actual_duration_minutes"], 90)
        self.assertTrue(metric["started"])
        self.assertEqual(
            metric["effective_end"],
            self.now + timedelta(hours=2, minutes=30),
        )

    def test_connection_metrics_report_free_buffer(self):
        trip = self._make_trip()
        first = self._element(
            trip, "activity", 1,
            timedelta(hours=2), timedelta(hours=3),
            self.resort,
        )
        second = self._element(
            trip, "activity", 2,
            timedelta(hours=3), timedelta(hours=4),
            self.resort,
        )
        self._dependency(first, second, buffer=timedelta(minutes=45))
        result = analyze_trip(trip, now=self.now)
        connection = result["timeline"]["connections"][0]
        self.assertEqual(connection["connection_minutes"], 0)
        self.assertEqual(connection["minimum_buffer_minutes"], 45)
        self.assertEqual(connection["free_buffer_minutes"], -45)
        self.assertEqual(connection["kind"], "infeasible")

    def test_connection_metrics_are_tight_when_free_buffer_small(self):
        trip = self._make_trip()
        first = self._element(
            trip, "activity", 1,
            timedelta(hours=2), timedelta(hours=3),
            self.resort,
        )
        second = self._element(
            trip, "activity", 2,
            timedelta(hours=3, minutes=45), timedelta(hours=4, minutes=45),
            self.resort,
        )
        self._dependency(first, second, buffer=timedelta(minutes=30))
        result = analyze_trip(trip, now=self.now)
        connection = result["timeline"]["connections"][0]
        self.assertEqual(connection["connection_minutes"], 45)
        self.assertEqual(connection["free_buffer_minutes"], 15)
        self.assertEqual(connection["kind"], "tight")

    def test_deadline_metrics_for_hotel_checkin(self):
        trip = self._make_trip()
        transfer = self._element(
            trip, "road_transfer", 1,
            timedelta(hours=2), timedelta(hours=3),
            self.airport, self.resort,
        )
        hotel = self._element(
            trip, "hotel", 2,
            timedelta(hours=3), timedelta(hours=8),
            self.resort, self.resort,
        )
        self._booking(transfer)
        self._booking(hotel)
        self._dependency(transfer, hotel, buffer=timedelta(minutes=30))
        result = analyze_trip(trip, now=self.now)
        deadline = next(
            d for d in result["timeline"]["deadlines"]
            if d["kind"] == "hotel_checkin"
        )
        self.assertEqual(deadline["kind"], "hotel_checkin")
        self.assertEqual(deadline["element_id"], hotel.pk)
        self.assertTrue(deadline["satisfied"])
        self.assertEqual(deadline["buffer_minutes"], 0)

    def test_deadline_metrics_for_transport_departure(self):
        trip = self._make_trip()
        flight = self._element(
            trip, "flight", 1,
            timedelta(hours=2), timedelta(hours=4),
            self.airport, self.airport,
        )
        self._booking(flight)
        result = analyze_trip(trip, now=self.now)
        deadline = result["timeline"]["deadlines"][0]
        self.assertEqual(deadline["kind"], "transport_departure")
        self.assertEqual(deadline["element_id"], flight.pk)
        self.assertTrue(deadline["satisfied"])
        self.assertEqual(deadline["remaining_minutes"], 120)

    def test_analysis_shape_is_same_for_upcoming_and_active(self):
        upcoming = self._make_trip()
        self._element(
            upcoming, "activity", 1,
            timedelta(hours=2), timedelta(hours=3),
            self.resort,
        )
        active = self._make_trip(start_delta=timedelta(hours=-1))
        self._element(
            active, "activity", 1,
            timedelta(hours=2), timedelta(hours=3),
            self.resort,
        )
        upcoming_result = analyze_trip(upcoming, now=self.now)
        active_result = analyze_trip(active, now=self.now)
        for result in (upcoming_result, active_result):
            self.assertEqual(
                set(result.keys()),
                {"status", "phase", "summary", "timeline", "checks"},
            )
            self.assertEqual(
                set(result["timeline"].keys()),
                {"elements", "connections", "deadlines"},
            )
        self.assertEqual(upcoming_result["phase"], "UPCOMING")
        self.assertEqual(active_result["phase"], "ACTIVE")


class AnalysisApiTests(APITestCase):
    def setUp(self):
        self.trip = Trip.objects.create(
            guide_id=101,
            name="Kerala Monsoon Escape",
            start_time=timezone.now() - timedelta(days=1),
            end_time=timezone.now() + timedelta(days=4),
            status="active",
        )
        self.airport = Location.objects.create(
            name="Trivandrum Intl Airport (TRV)",
            latitude=8.4822,
            longitude=76.9201,
            address="Chacka, Thiruvananthapuram, Kerala",
        )
        ItineraryElement.objects.create(
            trip=self.trip,
            type="flight",
            name="Flight AI-1049",
            start_location=self.airport,
            end_location=self.airport,
            planned_start=timezone.now() - timedelta(hours=3),
            planned_end=timezone.now() - timedelta(hours=1),
            status="valid",
            sequence=1,
        )

    def test_analysis_endpoint_returns_full_analysis(self):
        response = self.client.get(f"/api/trips/{self.trip.pk}/analysis/")
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertIsInstance(data["status"], str)
        self.assertEqual(
            set(data.keys()),
            {"status", "phase", "summary", "timeline", "checks"},
        )
        self.assertEqual(
            set(data["timeline"].keys()),
            {"elements", "connections", "deadlines"},
        )
        self.assertEqual(
            set(data["checks"].keys()),
            {"completeness", "feasibility", "deadlines", "external", "risks"},
        )
        element = data["timeline"]["elements"][0]
        self.assertEqual(
            set(element.keys()),
            {
                "id", "sequence", "type", "name", "start", "end",
                "planned_start", "planned_end", "planned_duration_minutes",
                "actual_start", "actual_end", "actual_duration_minutes",
                "effective_end", "delay_minutes", "started", "booking_status",
            },
        )

    def test_analysis_endpoint_returns_404_for_missing_trip(self):
        response = self.client.get("/api/trips/99999/analysis/")
        self.assertEqual(response.status_code, 404)


class ImportExtractionUnitTests(TestCase):
    """Unit tests for the Gemini extraction service in gemini_import."""

    def _payload(self):
        return {
            "guide_id": 0,
            "name": "Import Trip",
            "start_time": "2026-10-01T00:00:00Z",
            "end_time": "2026-10-08T00:00:00Z",
            "status": "upcoming",
            "itinerary_elements": [
                {
                    "type": "flight",
                    "name": "Flight AI-77",
                    "sequence": 1,
                    "planned_start": "2026-10-01T06:30:00Z",
                    "planned_end": "2026-10-01T10:00:00Z",
                    "status": "scheduled",
                    "start_location": {
                        "name": "Mumbai Airport",
                        "latitude": 19.0896,
                        "longitude": 72.8656,
                        "address": "Mumbai",
                    },
                    "end_location": {
                        "name": "",
                        "latitude": 0.0,
                        "longitude": 0.0,
                        "address": "",
                    },
                    "bookings": [
                        {
                            "supplier_name": "Air India",
                            "booking_reference": "AI-77",
                            "status": "confirmed",
                        },
                        {
                            "supplier_name": "",
                            "booking_reference": "",
                            "status": "",
                            "notes": "",
                        },
                    ],
                }
            ],
            "dependencies": [
                {
                    "from_element_index": 0,
                    "to_element_index": 1,
                    "type": "transfer",
                    "minimum_buffer": "PT1H30M",
                },
                {
                    "from_element_index": 0,
                    "to_element_index": 1,
                    "type": "",
                    "minimum_buffer": "",
                },
            ],
        }

    def test_extract_trip_calls_gemini_with_structured_output_schema(self):
        from . import gemini_import as gi

        payload = self._payload()
        parsed = gi.TripExtraction(**payload)
        fake_response = mock.Mock()
        fake_response.parsed = parsed

        with mock.patch("app.gemini_import.genai") as fake_genai, \
                self.settings(GEMINI_API_KEY="test-key"):
            fake_client = fake_genai.Client.return_value
            fake_client.models.generate_content.return_value = fake_response

            data, warnings = gi.extract_trip(
                b"pdf-bytes", "application/pdf", filename="itinerary.pdf"
            )

        call = fake_client.models.generate_content.call_args
        self.assertEqual(call.kwargs["model"], settings.GEMINI_MODEL)
        config = call.kwargs["config"]
        self.assertEqual(config.response_mime_type, "application/json")
        self.assertIs(config.response_schema, gi.TripExtraction)

        document_part = call.kwargs["contents"][1]
        self.assertEqual(document_part.inline_data.mime_type, "application/pdf")
        self.assertEqual(document_part.inline_data.data, b"pdf-bytes")

        self.assertEqual(data["name"], "Import Trip")
        element = data["itinerary_elements"][0]
        self.assertEqual(element["start_location"]["name"], "Mumbai Airport")
        self.assertIsNone(element["end_location"])
        self.assertEqual(len(element["bookings"]), 1)
        self.assertEqual(len(data["dependencies"]), 1)
        self.assertTrue(any("booking" in warning for warning in warnings))
        self.assertTrue(any("dependency" in warning for warning in warnings))

    def test_extract_trip_uses_requested_model_override(self):
        from . import gemini_import as gi

        fake_response = mock.Mock()
        fake_response.parsed = gi.TripExtraction(**self._payload())

        with mock.patch("app.gemini_import.genai") as fake_genai, \
                self.settings(GEMINI_API_KEY="test-key"):
            fake_client = fake_genai.Client.return_value
            fake_client.models.generate_content.return_value = fake_response

            gi.extract_trip(
                b"data", "image/png", model="gemini-2.5-flash-lite"
            )

        call = fake_client.models.generate_content.call_args
        self.assertEqual(call.kwargs["model"], "gemini-2.5-flash-lite")

    def test_extract_trip_raises_when_api_key_missing(self):
        from . import gemini_import as gi

        with self.settings(GEMINI_API_KEY=""):
            with self.assertRaises(gi.GeminiConfigurationError):
                gi.extract_trip(b"data", "application/pdf")

    def test_extract_trip_raises_when_parsed_output_missing(self):
        from . import gemini_import as gi

        fake_response = mock.Mock()
        fake_response.parsed = None

        with mock.patch("app.gemini_import.genai") as fake_genai, \
                self.settings(GEMINI_API_KEY="test-key"):
            fake_client = fake_genai.Client.return_value
            fake_client.models.generate_content.return_value = fake_response
            with self.assertRaises(gi.GeminiApiError):
                gi.extract_trip(b"data", "application/pdf")

    def test_extract_trip_wraps_gemini_errors(self):
        from . import gemini_import as gi

        with mock.patch("app.gemini_import.genai") as fake_genai, \
                self.settings(GEMINI_API_KEY="test-key"):
            fake_client = fake_genai.Client.return_value
            fake_client.models.generate_content.side_effect = \
                RuntimeError("upstream boom")
            with self.assertRaises(gi.GeminiApiError):
                gi.extract_trip(b"data", "application/pdf")

    def test_resolve_mime_type_accepts_supported_uploads(self):
        from .gemini_import import resolve_mime_type

        self.assertEqual(
            resolve_mime_type("scan.pdf", "application/pdf"), "application/pdf"
        )
        self.assertEqual(
            resolve_mime_type("photo.jpeg", "image/jpeg"), "image/jpeg"
        )
        self.assertEqual(
            resolve_mime_type("scan.png", "application/octet-stream"),
            "image/png",
        )
        self.assertIsNone(
            resolve_mime_type("notes.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        )

    def test_extraction_schema_mirrors_trip_create_serializer(self):
        from . import gemini_import as gi
        from .serializers import (
            BookingCreateSerializer,
            DependencyCreateSerializer,
            ItineraryElementCreateSerializer,
            LocationSerializer,
            TripCreateSerializer,
        )

        self.assertEqual(
            set(gi.TripExtraction.model_fields),
            set(TripCreateSerializer().fields),
        )
        self.assertEqual(
            set(gi.ElementExtraction.model_fields),
            set(ItineraryElementCreateSerializer().fields),
        )
        self.assertEqual(
            set(gi.BookingExtraction.model_fields),
            set(BookingCreateSerializer().fields),
        )
        self.assertEqual(
            set(gi.LocationExtraction.model_fields),
            set(LocationSerializer().fields) - {"id"},
        )
        self.assertEqual(
            set(gi.DependencyExtraction.model_fields),
            set(DependencyCreateSerializer().fields),
        )


class TripImportApiTests(APITestCase):
    full_payload = {
        "guide_id": 0,
        "name": "Imported Kerala Trip",
        "start_time": "2026-10-01T00:00:00Z",
        "end_time": "2026-10-08T00:00:00Z",
        "status": "upcoming",
        "itinerary_elements": [
            {
                "type": "flight",
                "name": "Flight AI-77",
                "sequence": 1,
                "planned_start": "2026-10-01T06:30:00Z",
                "planned_end": "2026-10-01T10:00:00Z",
                "status": "scheduled",
                "start_location": {
                    "name": "Mumbai Airport",
                    "latitude": 19.0896,
                    "longitude": 72.8656,
                    "address": "Mumbai",
                },
                "end_location": {
                    "name": "Trivandrum Airport",
                    "latitude": 8.4822,
                    "longitude": 76.9201,
                    "address": "TRV",
                },
                "bookings": [
                    {
                        "supplier_name": "Air India",
                        "booking_reference": "AI-77",
                        "status": "confirmed",
                    }
                ],
            },
            {
                "type": "road_transfer",
                "name": "Airport to Kovalam",
                "sequence": 2,
                "planned_start": "2026-10-01T11:00:00Z",
                "planned_end": "2026-10-01T12:00:00Z",
                "status": "scheduled",
                "start_location": {
                    "name": "Trivandrum Airport",
                    "latitude": 8.4822,
                    "longitude": 76.9201,
                    "address": "TRV",
                },
                "end_location": {
                    "name": "Kovalam",
                    "latitude": 8.4004,
                    "longitude": 76.9786,
                    "address": "Kovalam Beach",
                },
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
    }

    def _extract_patch(self, payload=None, warnings=None):
        payload = self.full_payload if payload is None else payload
        return mock.patch(
            "app.views.gemini_import.extract_trip",
            return_value=(dict(payload), warnings or []),
        )

    def test_extract_requires_file_upload(self):
        response = self.client.post("/api/trips/import/extract/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("file", response.data)

    def test_extract_rejects_unsupported_file_type(self):
        notes = SimpleUploadedFile("notes.txt", b"plain text", content_type="text/plain")
        response = self.client.post(
            "/api/trips/import/extract/",
            {"file": notes},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported file type", response.data["file"][0])

    def test_extract_rejects_oversized_file(self):
        with mock.patch("app.serializers.MAX_FILE_BYTES", 100):
            oversized = SimpleUploadedFile(
                "large.pdf", b"x" * 200, content_type="application/pdf"
            )
            response = self.client.post(
                "/api/trips/import/extract/",
                {"file": oversized},
                format="multipart",
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("byte limit", response.data["file"][0])

    def test_extract_returns_structured_payload_and_preview(self):
        itinerary = SimpleUploadedFile(
            "itinerary.pdf", b"pdf-bytes", content_type="application/pdf"
        )
        with self._extract_patch(warnings=["1 booking(s) dropped."]):
            response = self.client.post(
                "/api/trips/import/extract/",
                {"file": itinerary},
                format="multipart",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["model"], settings.GEMINI_MODEL)
        self.assertEqual(response.data["source_file"]["mime_type"], "application/pdf")
        self.assertEqual(response.data["extracted"]["name"], "Imported Kerala Trip")
        self.assertEqual(
            len(response.data["extracted"]["itinerary_elements"]), 2
        )
        self.assertTrue(response.data["valid"])
        self.assertIsNone(response.data["errors"])
        self.assertEqual(response.data["warnings"], ["1 booking(s) dropped."])

    def test_extract_surfaces_validation_errors_in_preview(self):
        broken = dict(self.full_payload)
        broken["name"] = ""
        itinerary = SimpleUploadedFile(
            "itinerary.png", b"png-bytes", content_type="image/png"
        )
        with self._extract_patch(payload=broken):
            response = self.client.post(
                "/api/trips/import/extract/",
                {"file": itinerary},
                format="multipart",
            )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["valid"])
        self.assertIn("name", response.data["errors"])

    def test_extract_without_api_key_returns_503(self):
        itinerary = SimpleUploadedFile(
            "itinerary.pdf", b"pdf-bytes", content_type="application/pdf"
        )
        with mock.patch(
            "app.views.gemini_import.extract_trip",
            side_effect=GeminiConfigurationError(
                "GEMINI_API_KEY is not configured in the environment."
            ),
        ):
            response = self.client.post(
                "/api/trips/import/extract/",
                {"file": itinerary},
                format="multipart",
            )
        self.assertEqual(response.status_code, 503)

    def test_extract_maps_upstream_gemini_error_to_502(self):
        itinerary = SimpleUploadedFile(
            "itinerary.pdf", b"pdf-bytes", content_type="application/pdf"
        )
        with mock.patch(
            "app.views.gemini_import.extract_trip",
            side_effect=GeminiApiError("upstream boom"),
        ):
            response = self.client.post(
                "/api/trips/import/extract/",
                {"file": itinerary},
                format="multipart",
            )
        self.assertEqual(response.status_code, 502)
        self.assertIn("upstream boom", response.data["detail"])

    def test_confirm_creates_trip_from_extracted_payload(self):
        response = self.client.post(
            "/api/trips/import/confirm/",
            self.full_payload,
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "Imported Kerala Trip")
        self.assertEqual(len(response.data["itinerary_elements"]), 2)

        trip = Trip.objects.get(name="Imported Kerala Trip")
        self.assertEqual(trip.itinerary_elements.count(), 2)
        self.assertEqual(
            trip.itinerary_elements.get(sequence=1).bookings.count(), 1
        )
        self.assertEqual(
            trip.itinerary_elements.get(sequence=2).incoming_dependencies.count(),
            1,
        )
        self.assertEqual(Location.objects.count(), 4)

    def test_confirm_creates_trip_when_booking_reference_is_blank(self):
        payload = deepcopy(self.full_payload)
        payload["itinerary_elements"][0]["bookings"][0]["booking_reference"] = ""

        response = self.client.post(
            "/api/trips/import/confirm/",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        booking = Booking.objects.get(
            itinerary_element__trip__name="Imported Kerala Trip"
        )
        self.assertEqual(booking.booking_reference, "")

    def test_confirm_with_invalid_payload_returns_400(self):
        broken = dict(self.full_payload)
        broken["name"] = ""
        response = self.client.post(
            "/api/trips/import/confirm/",
            broken,
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Trip.objects.filter(
            name="Imported Kerala Trip"
        ).exists() is False)


def _active_trip(now):
    trip = Trip.objects.create(
        guide_id=101,
        name="Live Kerala Trip",
        start_time=now - timedelta(days=1),
        end_time=now + timedelta(days=4),
        status="active",
    )
    airport = Location.objects.create(
        name="Trivandrum Intl Airport (TRV)",
        latitude=8.4822,
        longitude=76.9201,
        address="Chacka, Thiruvananthapuram, Kerala",
    )
    resort = Location.objects.create(
        name="Kovalam Beach Resort",
        latitude=8.4004,
        longitude=76.9786,
        address="Lighthouse Beach, Kovalam, Kerala",
    )
    return trip, airport, resort


def _live_chain(trip, now, airport, resort, buffer=timedelta(minutes=30)):
    flight = ItineraryElement.objects.create(
        trip=trip,
        type="flight",
        name="Flight AI-999",
        start_location=airport,
        end_location=airport,
        planned_start=now + timedelta(hours=2),
        planned_end=now + timedelta(hours=4),
        status="valid",
        sequence=1,
    )
    transfer = ItineraryElement.objects.create(
        trip=trip,
        type="road_transfer",
        name="Transfer Airport to Resort",
        start_location=airport,
        end_location=resort,
        planned_start=now + timedelta(hours=5),
        planned_end=now + timedelta(hours=6),
        status="valid",
        sequence=2,
    )
    Dependency.objects.create(
        from_element=flight,
        to_element=transfer,
        type="transfer",
        minimum_buffer=buffer,
    )
    Booking.objects.create(
        itinerary_element=flight,
        supplier_name="Air India",
        booking_reference="AI-DEL-TRV-4412",
        status="confirmed",
    )
    return flight, transfer


class LiveEngineTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.trip, self.airport, self.resort = _active_trip(self.now)
        self.flight, self.transfer = _live_chain(
            self.trip, self.now, self.airport, self.resort
        )

    def _flight_payload(self, status="DELAYED", minutes=90):
        flight = self.flight
        return {
            "itinerary_element": flight.pk,
            "flight_number": "AI-999",
            "date": self.now.date().isoformat(),
            "origin_airport": "DEL",
            "destination_airport": "TRV",
            "scheduled_departure": flight.planned_start.isoformat(),
            "estimated_departure": (
                flight.planned_start + timedelta(minutes=minutes)
            ).isoformat(),
            "scheduled_arrival": flight.planned_end.isoformat(),
            "estimated_arrival": (
                flight.planned_end + timedelta(minutes=minutes)
            ).isoformat(),
            "status": status,
            "gate": "B1",
            "terminal": "1",
            "delay_minutes": minutes,
            "delay_reason": "Air traffic control hold",
        }

    def _ingest_flight(self, **overrides):
        data = self._flight_payload()
        data.pop("itinerary_element", None)
        data.update(overrides)
        FlightStatusRecord.objects.create(
            itinerary_element=self.flight,
            reported_at=self.now,
            **data,
        )

    def test_feed_delay_disrupts_leg_and_marks_connection_at_risk(self):
        self._ingest_flight()
        result = recompute_live_status(self.trip, now=self.now)
        marks = {m["element_id"]: m for m in result["statuses"]}

        flight_mark = marks[self.flight.pk]
        self.assertEqual(flight_mark["status"], DISRUPTED)
        self.assertEqual(flight_mark["classification"], DIRECT)
        self.assertEqual(flight_mark["severity"], "high")

        transfer_mark = marks[self.transfer.pk]
        self.assertEqual(transfer_mark["status"], AT_RISK)
        self.assertEqual(transfer_mark["classification"], DOWNSTREAM)
        self.assertIn("Insufficient connection", transfer_mark["reason"])

        self.assertEqual(result["affected_bookings"], [self.flight.bookings.get().pk])
        self.assertEqual(
            FlightStatusRecord.objects.filter(
                itinerary_element=self.flight
            ).count(),
            1,
        )

    def test_recompute_is_idempotent_for_events_cases_and_actions(self):
        self._ingest_flight()
        recompute_live_status(self.trip, now=self.now)
        recompute_live_status(self.trip, now=self.now)

        self.assertEqual(
            Event.objects.filter(
                trip=self.trip, source="flight_status", status="open"
            ).count(),
            1,
        )
        self.assertEqual(Case.objects.filter(trip=self.trip).count(), 1)
        self.assertEqual(
            NodeStatus.objects.filter(trip=self.trip).count(),
            4,
        )
        self.assertEqual(
            FlightStatusRecord.objects.filter(
                itinerary_element=self.flight
            ).count(),
            1,
        )
        case = Case.objects.get(trip=self.trip)
        self.assertGreaterEqual(case.actions.count(), 4)
        actions = case.actions.values_list("type", flat=True)
        self.assertIn("contact_supplier", actions)
        self.assertIn("monitor", actions)
        self.assertIn("leave_earlier", actions)
        self.assertIn("alternate_route", actions)

    def test_cancelled_flight_recommends_change_transportation(self):
        self._ingest_flight(status="CANCELLED")
        recompute_live_status(self.trip, now=self.now)
        case = Case.objects.get(trip=self.trip)
        self.assertIn(
            "change_transportation",
            case.actions.values_list("type", flat=True),
        )
        node = live_status_payload(self.trip, now=self.now)
        flight_node = next(
            n for n in node["nodes"] if n["element_id"] == self.flight.pk
        )
        self.assertEqual(flight_node["status"], DISRUPTED)

    def test_traffic_advisory_marks_direct_at_risk(self):
        TrafficRouteRecord.objects.create(
            itinerary_element=self.transfer,
            origin="TRV",
            destination="Kovalam",
            congestion_level="MODERATE",
            traffic_delay_minutes=15,
            duration_minutes=60,
            checked_at=self.now,
        )
        recompute_live_status(self.trip, now=self.now)
        payload = live_status_payload(self.trip, now=self.now)
        transfer_node = next(
            n for n in payload["nodes"]
            if n["element_id"] == self.transfer.pk
        )
        self.assertEqual(transfer_node["status"], AT_RISK)
        self.assertEqual(transfer_node["classification"], DIRECT)
        self.assertEqual(transfer_node["severity"], "low")

    def test_weather_watch_marks_direct_at_risk_with_reason(self):
        WeatherRecord.objects.create(
            itinerary_element=self.transfer,
            location=self.resort,
            date_time=self.now,
            condition="Heavy Showers",
            warnings=["Torrential rain advisory"],
            checked_at=self.now,
        )
        recompute_live_status(self.trip, now=self.now)
        payload = live_status_payload(self.trip, now=self.now)
        transfer_node = next(
            n for n in payload["nodes"]
            if n["element_id"] == self.transfer.pk
        )
        self.assertEqual(transfer_node["status"], AT_RISK)
        self.assertEqual(transfer_node["classification"], DIRECT)
        self.assertEqual(transfer_node["severity"], "high")
        self.assertIn("Weather advisory", transfer_node["reason"])

    def test_healthy_trip_marks_elements_valid(self):
        payload = live_status_payload(self.trip, now=self.now)
        statuses = {n["element_id"]: n["status"] for n in payload["nodes"]}
        self.assertEqual(statuses[self.flight.pk], "valid")
        self.assertEqual(statuses[self.transfer.pk], "valid")
        self.assertEqual(payload["summary"]["disrupted"], 0)
        self.assertEqual(payload["summary"]["at_risk"], 0)
        self.assertEqual(payload["summary"]["valid"], 2)

    def test_live_status_payload_is_read_only(self):
        before_nodes = NodeStatus.objects.count()
        before_events = Event.objects.count()
        live_status_payload(self.trip, now=self.now)
        self.assertEqual(NodeStatus.objects.count(), before_nodes)
        self.assertEqual(Event.objects.count(), before_events)

    def test_gps_feed_appears_in_payload(self):
        GuidePosition.objects.create(
            trip=self.trip,
            itinerary_element=self.flight,
            device_id="device-1",
            latitude=8.4822,
            longitude=76.9201,
            captured_at=self.now,
            received_at=self.now,
        )
        payload = live_status_payload(self.trip, now=self.now)
        self.assertEqual(payload["feeds"]["gps"]["device_id"], "device-1")
        self.assertEqual(
            payload["feeds"]["gps"]["itinerary_element_id"], self.flight.pk
        )


class LiveIngestApiTests(APITestCase):
    def setUp(self):
        self.now = timezone.now()
        self.trip, self.airport, self.resort = _active_trip(self.now)
        self.flight, self.transfer = _live_chain(
            self.trip, self.now, self.airport, self.resort
        )

    def _iso(self, value):
        return value.isoformat()

    def test_flight_status_ingestion_returns_statuses(self):
        response = self.client.post(
            f"/api/trips/{self.trip.pk}/live/flight-status/",
            {
                "itinerary_element": self.flight.pk,
                "flight_number": "AI-999",
                "date": self.now.date().isoformat(),
                "status": "DELAYED",
                "scheduled_departure": self._iso(self.flight.planned_start),
                "estimated_departure": self._iso(
                    self.flight.planned_start + timedelta(minutes=90)
                ),
                "scheduled_arrival": self._iso(self.flight.planned_end),
                "estimated_arrival": self._iso(
                    self.flight.planned_end + timedelta(minutes=90)
                ),
                "delay_minutes": 90,
                "delay_reason": "Air traffic control hold",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["element_id"], self.flight.pk)
        self.assertEqual(response.data["phase"], "ACTIVE")
        marks = {m["element_id"]: m for m in response.data["statuses"]}
        self.assertEqual(marks[self.flight.pk]["status"], DISRUPTED)
        self.assertEqual(marks[self.flight.pk]["classification"], DIRECT)
        self.assertEqual(marks[self.transfer.pk]["status"], AT_RISK)
        self.assertEqual(marks[self.transfer.pk]["classification"], DOWNSTREAM)
        self.assertEqual(
            response.data["affected_bookings"],
            [self.flight.bookings.get().pk],
        )

    def test_flight_ingestion_rejects_element_from_other_trip(self):
        other, other_airport, _ = _active_trip(self.now)
        other_flight, _ = _live_chain(
            other, self.now, other_airport, self.resort
        )
        response = self.client.post(
            f"/api/trips/{self.trip.pk}/live/flight-status/",
            {
                "itinerary_element": other_flight.pk,
                "flight_number": "AI-999",
                "date": self.now.date().isoformat(),
                "status": "ON_TIME",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("itinerary_element", response.data["detail"].lower())

    def test_train_status_ingestion(self):
        response = self.client.post(
            f"/api/trips/{self.trip.pk}/live/train-status/",
            {
                "itinerary_element": self.flight.pk,
                "train_number": "ICE-502",
                "date": self.now.date().isoformat(),
                "origin_station": "Berlin Hbf",
                "destination_station": "Munich Hbf",
                "status": "DELAYED",
                "scheduled_time": self._iso(self.flight.planned_start),
                "estimated_time": self._iso(
                    self.flight.planned_start + timedelta(minutes=30)
                ),
                "delay_minutes": 30,
                "platform": "3",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            TrainStatusRecord.objects.filter(
                itinerary_element=self.flight
            ).count(),
            1,
        )

    def test_traffic_ingestion(self):
        response = self.client.post(
            f"/api/trips/{self.trip.pk}/live/traffic/",
            {
                "itinerary_element": self.transfer.pk,
                "origin": "TRV",
                "destination": "Kovalam",
                "departure_time": self._iso(self.transfer.planned_start),
                "distance_km": 15.0,
                "duration_minutes": 60,
                "traffic_delay_minutes": 15,
                "congestion_level": "MODERATE",
                "recommended_route": "Scenic Bypass",
                "incidents": [{"incident_type": "congestion", "description": "x"}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            TrafficRouteRecord.objects.filter(
                itinerary_element=self.transfer
            ).count(),
            1,
        )
        marks = {m["element_id"]: m for m in response.data["statuses"]}
        self.assertEqual(marks[self.transfer.pk]["status"], AT_RISK)
        self.assertEqual(marks[self.transfer.pk]["classification"], DIRECT)

    def test_weather_ingestion(self):
        response = self.client.post(
            f"/api/trips/{self.trip.pk}/live/weather/",
            {
                "itinerary_element": self.transfer.pk,
                "date_time": self._iso(self.now),
                "condition": "Thunderstorm",
                "temperature_c": 26.0,
                "humidity_percent": 80.0,
                "wind_speed_kmh": 40.0,
                "precipitation_mm": 20.0,
                "visibility_km": 3.0,
                "warnings": ["Torrential rain advisory"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            WeatherRecord.objects.filter(
                itinerary_element=self.transfer
            ).count(),
            1,
        )
        marks = {m["element_id"]: m for m in response.data["statuses"]}
        self.assertEqual(marks[self.transfer.pk]["status"], AT_RISK)
        self.assertEqual(marks[self.transfer.pk]["classification"], DIRECT)

    def test_gps_ingestion(self):
        response = self.client.post(
            f"/api/trips/{self.trip.pk}/live/gps/",
            {
                "itinerary_element": self.flight.pk,
                "device_id": "device-1",
                "latitude": 8.4822,
                "longitude": 76.9201,
                "speed_kmh": 54.0,
                "captured_at": self._iso(self.now),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            GuidePosition.objects.filter(trip=self.trip).count(), 1
        )

    def test_ingestion_404_for_missing_trip(self):
        response = self.client.post(
            "/api/trips/99999/live/flight-status/",
            {"itinerary_element": self.flight.pk, "status": "ON_TIME"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_live_status_endpoint_shape(self):
        self.client.post(
            f"/api/trips/{self.trip.pk}/live/flight-status/",
            {
                "itinerary_element": self.flight.pk,
                "flight_number": "AI-999",
                "date": self.now.date().isoformat(),
                "status": "DELAYED",
                "delay_minutes": 90,
                "scheduled_departure": self._iso(self.flight.planned_start),
                "scheduled_arrival": self._iso(self.flight.planned_end),
            },
            format="json",
        )
        response = self.client.get(
            f"/api/trips/{self.trip.pk}/live-status/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.data.keys()),
            {
                "trip_id", "name", "phase", "generated_at", "nodes",
                "feeds", "cases", "recommended_actions", "summary",
            },
        )
        by_element = {n["element_id"]: n for n in response.data["nodes"]}
        self.assertEqual(by_element[self.flight.pk]["status"], DISRUPTED)
        self.assertEqual(by_element[self.transfer.pk]["status"], AT_RISK)
        self.assertEqual(
            response.data["summary"]["affected_bookings"], 1
        )
        self.assertEqual(response.data["feeds"]["gps"], None)

    def test_live_status_404_for_missing_trip(self):
        response = self.client.get("/api/trips/99999/live-status/")
        self.assertEqual(response.status_code, 404)


FAKE_ROUTE = {
    "legs": [
        {
            "distanceMeters": 18200,
            "duration": "3300s",
            "steps": [
                {
                    "navigationInstruction": {
                        "instructions": "Head south on NH 66"
                    }
                },
            ],
        },
    ],
}


class RouteAlternativesUnitTests(TestCase):
    def setUp(self):
        routes.clear_cache()
        self.now = timezone.now()
        self.trip, self.airport, self.resort = _active_trip(self.now)
        self.flight, self.transfer = _live_chain(
            self.trip, self.now, self.airport, self.resort
        )

    def tearDown(self):
        routes.clear_cache()

    def test_element_alternatives_requires_api_key(self):
        with self.settings(GOOGLE_MAPS_API_KEY=""):
            with self.assertRaises(RoutesConfigurationError):
                routes.element_alternatives(self.trip, self.transfer)

    def test_element_alternatives_maps_directions_routes(self):
        with mock.patch(
            "app.routes._directions", return_value=[dict(FAKE_ROUTE)]
        ) as fake_directions, self.settings(
            GOOGLE_MAPS_API_KEY="test-key"
        ):
            alternatives = routes.element_alternatives(
                self.trip, self.transfer
            )

        modes = [option["mode"] for option in alternatives]
        self.assertEqual(modes, ["driving", "transit"])
        option = alternatives[0]
        self.assertEqual(option["distance_km"], 18.2)
        self.assertEqual(option["duration_minutes"], 55)
        self.assertEqual(option["duration_delta_minutes"], -5)
        self.assertEqual(option["departure_at"], self.transfer.planned_start)
        self.assertEqual(
            option["arrival_at"],
            self.transfer.planned_start + timedelta(minutes=55),
        )
        self.assertEqual(option["via"], ["Head south on NH 66"])
        self.assertEqual(fake_directions.call_count, 2)  # driving + transit

    def test_element_alternatives_caches_per_mode(self):
        with mock.patch(
            "app.routes._directions", return_value=[dict(FAKE_ROUTE)]
        ) as fake_directions, self.settings(
            GOOGLE_MAPS_API_KEY="test-key"
        ):
            routes.element_alternatives(self.trip, self.transfer)
            routes.element_alternatives(self.trip, self.transfer)

        self.assertEqual(fake_directions.call_count, 2)

    def test_element_alternatives_rejects_invalid_legs(self):
        hotel = ItineraryElement.objects.create(
            trip=self.trip,
            type="hotel",
            name="Kovalam Beach Resort",
            start_location=None,
            end_location=None,
            planned_start=self.now,
            planned_end=self.now + timedelta(days=1),
            status="valid",
            sequence=3,
        )
        with self.assertRaises(ValueError):
            routes.element_alternatives(self.trip, hotel)

        no_locations = ItineraryElement.objects.create(
            trip=self.trip,
            type="road_transfer",
            name="Blind Transfer",
            start_location=None,
            end_location=None,
            planned_start=self.now,
            planned_end=self.now + timedelta(hours=1),
            status="valid",
            sequence=4,
        )
        with self.assertRaises(ValueError):
            routes.element_alternatives(self.trip, no_locations)

    def test_element_alternatives_wraps_upstream_error(self):
        with mock.patch(
            "app.routes._directions",
            side_effect=RoutesApiError("directions went boom"),
        ) as fake_directions, self.settings(
            GOOGLE_MAPS_API_KEY="test-key"
        ):
            with self.assertRaises(RoutesApiError):
                routes.element_alternatives(self.trip, self.transfer)
        self.assertEqual(fake_directions.call_count, 1)


class TripAlternativesApiTests(APITestCase):
    def setUp(self):
        self.now = timezone.now()
        self.trip, self.airport, self.resort = _active_trip(self.now)
        self.flight, self.transfer = _live_chain(
            self.trip, self.now, self.airport, self.resort
        )
        self.url = (
            f"/api/trips/{self.trip.pk}/alternatives/{self.transfer.pk}/"
        )

    def test_alternatives_endpoint_shape(self):
        payload = [
            {
                "mode": "driving",
                "distance_km": 18.2,
                "duration_minutes": 55,
                "duration_delta_minutes": -5,
                "departure_at": self.transfer.planned_start,
                "arrival_at": self.transfer.planned_start
                + timedelta(minutes=55),
                "via": ["Head south on NH 66"],
            }
        ]
        with mock.patch(
            "app.views.routes.element_alternatives", return_value=payload
        ):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.data.keys()), {"element_id", "element_name",
                                        "alternatives"}
        )
        self.assertEqual(response.data["alternatives"][0]["mode"], "driving")

    def test_alternatives_404_for_missing_trip(self):
        response = self.client.get(
            f"/api/trips/99999/alternatives/{self.transfer.pk}/"
        )
        self.assertEqual(response.status_code, 404)

    def test_alternatives_404_for_missing_element(self):
        response = self.client.get(
            f"/api/trips/{self.trip.pk}/alternatives/99999/"
        )
        self.assertEqual(response.status_code, 404)

    def test_alternatives_rejects_element_from_other_trip(self):
        other, other_airport, _ = _active_trip(self.now)
        other_flight, other_transfer = _live_chain(
            other, self.now, other_airport, self.resort
        )
        response = self.client.get(
            f"/api/trips/{self.trip.pk}/alternatives/{other_transfer.pk}/"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("itinerary_element", response.data["detail"].lower())

    def test_alternatives_rejects_non_transport_element(self):
        hotel = ItineraryElement.objects.create(
            trip=self.trip,
            type="hotel",
            name="Kovalam Beach Resort",
            start_location=self.resort,
            end_location=self.resort,
            planned_start=self.now + timedelta(days=1),
            planned_end=self.now + timedelta(days=2),
            status="valid",
            sequence=3,
        )
        response = self.client.get(
            f"/api/trips/{self.trip.pk}/alternatives/{hotel.pk}/"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("transport", response.data["detail"].lower())

    def test_alternatives_returns_503_without_api_key(self):
        with mock.patch(
            "app.views.routes.element_alternatives",
            side_effect=RoutesConfigurationError(
                "GOOGLE_MAPS_API_KEY is not configured in the environment."
            ),
        ):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 503)

    def test_alternatives_returns_502_on_upstream_error(self):
        with mock.patch(
            "app.views.routes.element_alternatives",
            side_effect=RoutesApiError("directions went boom"),
        ):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 502)


class TripSummaryUnitTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.trip, self.airport, self.resort = _active_trip(self.now)
        self.flight, self.transfer = _live_chain(
            self.trip, self.now, self.airport, self.resort
        )

    def test_summarize_trip_uses_structured_output_schema(self):
        from . import gemini_summary as gs

        fake_response = mock.Mock()
        fake_response.parsed = gs.TripSummaryResult(
            headline="No disruption.",
            phase="ACTIVE",
            overall_assessment="READY",
            summary="The trip is on plan.",
            affected_nodes=[],
            recommended_actions=[],
            risks=[],
        )

        with mock.patch("app.gemini_summary.genai") as fake_genai, \
                self.settings(GEMINI_API_KEY="test-key"):
            fake_client = fake_genai.Client.return_value
            fake_client.models.generate_content.return_value = fake_response

            result = gs.summarize_trip(self.trip, now=self.now)

        call = fake_client.models.generate_content.call_args
        self.assertEqual(call.kwargs["model"], settings.GEMINI_MODEL)
        config = call.kwargs["config"]
        self.assertEqual(config.response_mime_type, "application/json")
        self.assertIs(config.response_schema, gs.TripSummaryResult)
        self.assertIn("LIVE STATUS", call.kwargs["contents"][0].text)
        self.assertEqual(result["overall_assessment"], "READY")

    def test_summarize_trip_raises_when_api_key_missing(self):
        from . import gemini_summary as gs

        with self.settings(GEMINI_API_KEY=""):
            with self.assertRaises(gs.GeminiConfigurationError):
                gs.summarize_trip(self.trip, now=self.now)

    def test_summarize_trip_raises_when_parsed_output_missing(self):
        from . import gemini_summary as gs

        fake_response = mock.Mock()
        fake_response.parsed = None
        with mock.patch("app.gemini_summary.genai") as fake_genai, \
                self.settings(GEMINI_API_KEY="test-key"):
            fake_client = fake_genai.Client.return_value
            fake_client.models.generate_content.return_value = fake_response
            with self.assertRaises(gs.GeminiApiError):
                gs.summarize_trip(self.trip, now=self.now)

    def test_summarize_trip_wraps_gemini_errors(self):
        from . import gemini_summary as gs

        with mock.patch("app.gemini_summary.genai") as fake_genai, \
                self.settings(GEMINI_API_KEY="test-key"):
            fake_client = fake_genai.Client.return_value
            fake_client.models.generate_content.side_effect = \
                RuntimeError("upstream boom")
            with self.assertRaises(gs.GeminiApiError):
                gs.summarize_trip(self.trip, now=self.now)


class TripSummaryApiTests(APITestCase):
    def setUp(self):
        self.now = timezone.now()
        self.trip, _, _ = _active_trip(self.now)

    def test_summary_endpoint_without_api_key_returns_503(self):
        with mock.patch(
            "app.views.gemini_summary.summarize_trip",
            side_effect=GeminiConfigurationError(
                "GEMINI_API_KEY is not configured in the environment."
            ),
        ):
            response = self.client.get(
                f"/api/trips/{self.trip.pk}/summary/"
            )
        self.assertEqual(response.status_code, 503)

    def test_summary_endpoint_returns_structured_result(self):
        summary_payload = {
            "headline": "Smooth sailing.",
            "phase": "ACTIVE",
            "overall_assessment": "READY",
            "summary": "All legs are on plan.",
            "affected_nodes": [],
            "recommended_actions": [],
            "risks": [],
        }
        with mock.patch(
            "app.views.gemini_summary.summarize_trip",
            return_value=dict(summary_payload),
        ):
            response = self.client.get(
                f"/api/trips/{self.trip.pk}/summary/"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["model"], settings.GEMINI_MODEL)
        self.assertEqual(
            response.data["result"]["overall_assessment"], "READY"
        )

    def test_summary_endpoint_maps_upstream_error_to_502(self):
        with mock.patch(
            "app.views.gemini_summary.summarize_trip",
            side_effect=GeminiApiError("upstream boom"),
        ):
            response = self.client.get(
                f"/api/trips/{self.trip.pk}/summary/"
            )
        self.assertEqual(response.status_code, 502)
        self.assertIn("upstream boom", response.data["detail"])

    def test_summary_endpoint_404_for_missing_trip(self):
        response = self.client.get("/api/trips/99999/summary/")
        self.assertEqual(response.status_code, 404)