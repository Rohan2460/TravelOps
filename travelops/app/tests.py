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
from .analysis import analyze_trip

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