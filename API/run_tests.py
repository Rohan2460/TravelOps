import requests

BASE_URL = "http://127.0.0.1:8000/api/v1"

def test_all():
    print("Testing Live FastAPI Endpoints on http://127.0.0.1:8000 ...")

    # 0. Simulator status
    r = requests.get(f"{BASE_URL}/simulator/status")
    print(f"0. Simulator Status: {r.status_code} - {r.json()}")
    assert r.status_code == 200

    # 1. Itinerary
    r = requests.get(f"{BASE_URL}/itinerary")
    print(f"1. Itinerary List: {r.status_code} - {len(r.json())} items")
    assert r.status_code == 200

    # 2. Booking Data
    r = requests.get(f"{BASE_URL}/booking/BK-99201")
    print(f"2. Booking Lookup: {r.status_code} - {r.json()['supplier']}")
    assert r.status_code == 200

    # 3. Flight Status
    r = requests.get(f"{BASE_URL}/flight-status?flight_number=AA100&date=2026-09-10")
    print(f"3. Flight Status: {r.status_code} - Status: {r.json()['status']}")
    assert r.status_code == 200

    # 4. Train Status
    r = requests.get(f"{BASE_URL}/train-status?train_number=Eurostar-9014&date=2026-09-15")
    print(f"4. Train Status: {r.status_code} - Status: {r.json()['status']}")
    assert r.status_code == 200

    # 5. Traffic & Routes
    r = requests.post(f"{BASE_URL}/traffic-routes/calculate", json={
        "origin": "JFK Airport", "destination": "Times Square", "departure_time": "08:30 AM", "travel_mode": "driving"
    })
    print(f"5. Traffic & Routes: {r.status_code} - Congestion: {r.json()['congestion_level']}")
    assert r.status_code == 200

    # 6. Weather
    r = requests.get(f"{BASE_URL}/weather/current?location=London")
    print(f"6. Weather: {r.status_code} - Temp: {r.json()['temperature_c']}°C")
    assert r.status_code == 200

    # 7. GPS Ping
    r = requests.post(f"{BASE_URL}/gps/ping", json={
        "device_id": "TEST-DEV-1", "latitude": 51.5074, "longitude": -0.1278, "timestamp": "2026-09-05T12:00:00Z"
    })
    print(f"7. GPS Ping: {r.status_code} - Position recorded")
    assert r.status_code == 201

    # 8. Guide Reports
    r = requests.get(f"{BASE_URL}/guide-reports")
    print(f"8. Guide Reports: {r.status_code} - {len(r.json())} reports")
    assert r.status_code == 200

    # 9. Geocoding
    r = requests.get(f"{BASE_URL}/location/geocode?query=Eiffel Tower")
    print(f"9. Geocode: {r.status_code} - Lat: {r.json()['latitude']}")
    assert r.status_code == 200

    # 10. Historical Data
    r = requests.get(f"{BASE_URL}/historical/weather?location=London")
    print(f"10. Historical Data: {r.status_code} - Risk: {r.json()['delay_risk_score']}")
    assert r.status_code == 200

    print("\nALL 10 API ENDPOINTS VERIFIED & WORKING PERFECTLY!")

if __name__ == "__main__":
    test_all()
