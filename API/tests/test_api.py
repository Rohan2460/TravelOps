from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_simulator_status():
    response = client.get("/api/v1/simulator/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "counts" in data

def test_itinerary_api():
    # Test GET itineraries
    response = client.get("/api/v1/itinerary")
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)

    # Test POST itinerary
    payload = {
        "trip_id": "TEST-TRIP",
        "item_type": "flight",
        "title": "Test Flight Item",
        "start_time": "2026-09-10T12:00:00Z"
    }
    response = client.post("/api/v1/itinerary", json=payload)
    assert response.status_code == 201
    created = response.json()
    assert created["title"] == "Test Flight Item"
    assert "itinerary_id" in created

def test_booking_api():
    response = client.get("/api/v1/booking/BK-99201")
    assert response.status_code == 200
    data = response.json()
    assert data["booking_ref"] == "BK-99201"

    # Test Status Update
    patch_res = client.patch("/api/v1/booking/BK-99201/status", json={"status": "MODIFIED", "notes": "Test change"})
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "MODIFIED"

def test_flight_status_api():
    response = client.get("/api/v1/flight-status?flight_number=AA100&date=2026-09-10")
    assert response.status_code == 200
    data = response.json()
    assert data["flight_number"] == "AA100"
    assert "status" in data

def test_train_status_api():
    response = client.get("/api/v1/train-status?train_number=Eurostar-9014&date=2026-09-15")
    assert response.status_code == 200
    data = response.json()
    assert data["train_number"] == "EUROSTAR-9014"

def test_traffic_routes_api():
    payload = {
        "origin": "JFK Airport",
        "destination": "Times Square",
        "departure_time": "09:00 AM",
        "travel_mode": "driving"
    }
    response = client.post("/api/v1/traffic-routes/calculate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "distance_km" in data
    assert "congestion_level" in data

def test_weather_api():
    response = client.get("/api/v1/weather/current?location=London")
    assert response.status_code == 200
    data = response.json()
    assert data["location"] == "London"
    assert "temperature_c" in data

def test_gps_api():
    payload = {
        "device_id": "TEST-DEV-99",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "timestamp": "2026-09-05T12:00:00Z"
    }
    response = client.post("/api/v1/gps/ping", json=payload)
    assert response.status_code == 201

    history_res = client.get("/api/v1/gps/TEST-DEV-99/history")
    assert history_res.status_code == 200
    assert history_res.json()["total_pings"] >= 1

def test_guide_report_api():
    payload = {
        "guide_id": "GUIDE-TEST",
        "location": "Paris",
        "report_type": "road_issue",
        "severity": "HIGH",
        "message": "Traffic detour required"
    }
    response = client.post("/api/v1/guide-reports", json=payload)
    assert response.status_code == 201

def test_location_api():
    response = client.get("/api/v1/location/geocode?query=Eiffel Tower")
    assert response.status_code == 200
    data = response.json()
    assert "latitude" in data

def test_historical_api():
    response = client.get("/api/v1/historical/weather?location=London")
    assert response.status_code == 200
    data = response.json()
    assert "historical_weather_avg_temp_c" in data
