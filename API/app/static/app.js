document.addEventListener('DOMContentLoaded', () => {
    const API_BASE = '/api/v1';

    // Tab Switching Logic
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            const targetTab = document.getElementById(`tab-${btn.dataset.tab}`);
            if (targetTab) {
                targetTab.classList.add('active');
            }
        });
    });

    // Helper: Display Inspector Response
    function displayResponse(data, status = 200, elapsedMs = 0) {
        const jsonViewer = document.getElementById('response-json-viewer');
        const statusPill = document.getElementById('resp-status-code');
        const timeEl = document.getElementById('resp-time');

        jsonViewer.textContent = JSON.stringify(data, null, 2);
        timeEl.textContent = `${elapsedMs} ms`;

        if (status >= 200 && status < 300) {
            statusPill.textContent = `HTTP ${status} OK`;
            statusPill.className = 'status-code-pill pill-success';
        } else {
            statusPill.textContent = `HTTP ${status} ERROR`;
            statusPill.className = 'status-code-pill pill-error';
        }
    }

    // Helper: API Request Wrapper
    async function apiCall(endpoint, method = 'GET', body = null, isFormData = false) {
        const start = performance.now();
        const options = { method };

        if (body) {
            if (isFormData) {
                options.body = body;
            } else {
                options.headers = { 'Content-Type': 'application/json' };
                options.body = JSON.stringify(body);
            }
        }

        try {
            const res = await fetch(`${API_BASE}${endpoint}`, options);
            const elapsed = Math.round(performance.now() - start);
            const data = await res.json();
            displayResponse(data, res.status, elapsed);
            refreshStats();
            return { ok: res.ok, status: res.status, data };
        } catch (err) {
            const elapsed = Math.round(performance.now() - start);
            displayResponse({ error: err.message }, 500, elapsed);
            return { ok: false, status: 500, data: null };
        }
    }

    // Refresh Server Stats
    async function refreshStats() {
        try {
            const res = await fetch(`${API_BASE}/simulator/status`);
            const json = await res.json();
            if (json.counts) {
                document.getElementById('count-itineraries').textContent = json.counts.itineraries || 0;
                document.getElementById('count-bookings').textContent = json.counts.bookings || 0;
                document.getElementById('count-flights').textContent = json.counts.flights || 0;
                document.getElementById('count-trains').textContent = json.counts.trains || 0;
                document.getElementById('count-reports').textContent = json.counts.guide_reports || 0;
                document.getElementById('count-gps').textContent = json.counts.gps_logs || 0;
            }
        } catch (e) {
            console.error('Failed to fetch simulator stats:', e);
        }
    }

    // Seed Button
    document.getElementById('seed-btn').addEventListener('click', async () => {
        await apiCall('/simulator/seed', 'POST');
        loadAllTables();
    });

    // -------------------------------------------------------------
    // TAB 1: ITINERARY
    // -------------------------------------------------------------
    async function loadItineraries() {
        const res = await fetch(`${API_BASE}/itinerary`);
        const data = await res.json();
        const tbody = document.querySelector('#table-itineraries tbody');
        tbody.innerHTML = '';
        (data || []).forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><code>${item.itinerary_id}</code></td>
                <td>${item.trip_id}</td>
                <td><span class="badge badge-info">${item.item_type}</span></td>
                <td>${item.title}</td>
                <td>${item.supplier || '-'}</td>
                <td><span class="badge badge-success">${item.status}</span></td>
            `;
            tbody.appendChild(tr);
        });
    }

    document.getElementById('btn-refresh-itineraries').addEventListener('click', loadItineraries);

    document.getElementById('form-itinerary').addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
            trip_id: document.getElementById('itin-trip-id').value,
            item_type: document.getElementById('itin-type').value,
            title: document.getElementById('itin-title').value,
            start_time: document.getElementById('itin-start').value,
            origin_location: document.getElementById('itin-origin').value,
            status: 'CONFIRMED'
        };
        const res = await apiCall('/itinerary', 'POST', payload);
        if (res.ok) loadItineraries();
    });

    document.getElementById('btn-upload-itinerary').addEventListener('click', async () => {
        const fileInput = document.getElementById('itinerary-file-input');
        if (!fileInput.files.length) {
            alert('Please select a CSV, XLSX, or JSON file to import.');
            return;
        }
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        const res = await apiCall('/itinerary/import', 'POST', formData, true);
        if (res.ok) loadItineraries();
    });

    // -------------------------------------------------------------
    // TAB 2: BOOKING DATA
    // -------------------------------------------------------------
    async function loadBookings() {
        const res = await fetch(`${API_BASE}/booking`);
        const data = await res.json();
        const tbody = document.querySelector('#table-bookings tbody');
        tbody.innerHTML = '';
        (data || []).forEach(b => {
            const badgeClass = b.status === 'CONFIRMED' ? 'badge-success' : b.status === 'CANCELLED' ? 'badge-danger' : 'badge-warning';
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><code>${b.booking_ref}</code></td>
                <td>${b.supplier}</td>
                <td>${b.passenger_name}</td>
                <td>${b.service_type}</td>
                <td><span class="badge ${badgeClass}">${b.status}</span></td>
                <td>${b.total_amount ? `${b.total_amount} ${b.currency}` : '-'}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    document.getElementById('btn-lookup-booking').addEventListener('click', async () => {
        const ref = document.getElementById('booking-ref-input').value.trim();
        if (ref) {
            await apiCall(`/booking/${ref}`, 'GET');
        }
    });

    document.getElementById('form-update-booking').addEventListener('submit', async (e) => {
        e.preventDefault();
        const ref = document.getElementById('booking-ref-input').value.trim();
        const status = document.getElementById('booking-new-status').value;
        const notes = document.getElementById('booking-notes').value;
        const res = await apiCall(`/booking/${ref}/status`, 'PATCH', { status, notes });
        if (res.ok) loadBookings();
    });

    // -------------------------------------------------------------
    // TAB 3: FLIGHT STATUS
    // -------------------------------------------------------------
    async function loadFlights() {
        const res = await fetch(`${API_BASE}/flight-status/all`);
        const data = await res.json();
        const tbody = document.querySelector('#table-flights tbody');
        tbody.innerHTML = '';
        (data || []).forEach(f => {
            const badgeClass = f.status === 'ON_TIME' ? 'badge-success' : f.status === 'DELAYED' ? 'badge-danger' : 'badge-info';
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><code>${f.flight_number}</code></td>
                <td>${f.date}</td>
                <td>${f.origin_airport} ➔ ${f.destination_airport}</td>
                <td><span class="badge ${badgeClass}">${f.status}</span></td>
                <td>${f.gate || '-'}</td>
                <td>${f.delay_minutes ? `${f.delay_minutes} min` : '0 min'}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    document.getElementById('form-flight').addEventListener('submit', async (e) => {
        e.preventDefault();
        const flightNo = document.getElementById('flight-no').value;
        const date = document.getElementById('flight-date').value;
        const orig = document.getElementById('flight-orig').value;
        const dest = document.getElementById('flight-dest').value;

        const url = `/flight-status?flight_number=${encodeURIComponent(flightNo)}&date=${encodeURIComponent(date)}&origin_airport=${encodeURIComponent(orig)}&destination_airport=${encodeURIComponent(dest)}`;
        const res = await apiCall(url, 'GET');
        if (res.ok) loadFlights();
    });

    // -------------------------------------------------------------
    // TAB 4: TRAIN STATUS
    // -------------------------------------------------------------
    async function loadTrains() {
        const res = await fetch(`${API_BASE}/train-status/all`);
        const data = await res.json();
        const tbody = document.querySelector('#table-trains tbody');
        tbody.innerHTML = '';
        (data || []).forEach(t => {
            const badgeClass = t.status === 'RUNNING' || t.status === 'ON_TIME' ? 'badge-success' : 'badge-warning';
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><code>${t.train_number}</code></td>
                <td>${t.date}</td>
                <td>${t.origin_station} ➔ ${t.destination_station}</td>
                <td><span class="badge ${badgeClass}">${t.status}</span></td>
                <td>${t.platform}</td>
                <td>${t.speed_kmh ? `${t.speed_kmh} km/h` : '-'}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    document.getElementById('form-train').addEventListener('submit', async (e) => {
        e.preventDefault();
        const trainNo = document.getElementById('train-no').value;
        const date = document.getElementById('train-date').value;
        const orig = document.getElementById('train-orig').value;
        const dest = document.getElementById('train-dest').value;

        const url = `/train-status?train_number=${encodeURIComponent(trainNo)}&date=${encodeURIComponent(date)}&origin_station=${encodeURIComponent(orig)}&destination_station=${encodeURIComponent(dest)}`;
        const res = await apiCall(url, 'GET');
        if (res.ok) loadTrains();
    });

    // -------------------------------------------------------------
    // TAB 5: TRAFFIC & ROUTES
    // -------------------------------------------------------------
    document.getElementById('form-traffic').addEventListener('submit', async (e) => {
        e.preventDefault();
        const body = {
            origin: document.getElementById('traffic-orig').value,
            destination: document.getElementById('traffic-dest').value,
            departure_time: document.getElementById('traffic-dep-time').value,
            travel_mode: document.getElementById('traffic-mode').value
        };

        const res = await apiCall('/traffic-routes/calculate', 'POST', body);
        if (res.ok && res.data) {
            const card = document.getElementById('traffic-results-card');
            const data = res.data;
            card.innerHTML = `
                <h3>Route & Traffic Analysis</h3>
                <div class="stat-card" style="margin-top:10px;">
                    <span class="stat-label">Congestion Index</span>
                    <span class="stat-value" style="color:${data.congestion_level === 'LOW' ? '#10b981' : '#f43f5e'}">${data.congestion_level}</span>
                </div>
                <p><strong>Distance:</strong> ${data.distance_km} km</p>
                <p><strong>Duration:</strong> ${data.duration_minutes} mins (Traffic Delay: +${data.traffic_delay_minutes} mins)</p>
                <p><strong>Recommended Route:</strong> ${data.recommended_route}</p>
                ${data.incidents.length ? `<p><strong>Incidents:</strong> ${data.incidents.map(i => i.description).join(', ')}</p>` : ''}
            `;
        }
    });

    // -------------------------------------------------------------
    // TAB 6: WEATHER
    // -------------------------------------------------------------
    document.getElementById('form-weather').addEventListener('submit', async (e) => {
        e.preventDefault();
        const loc = document.getElementById('weather-location').value;
        const dt = document.getElementById('weather-datetime').value;
        let url = `/weather/current?location=${encodeURIComponent(loc)}`;
        if (dt) url += `&date_time=${encodeURIComponent(dt)}`;

        const res = await apiCall(url, 'GET');
        if (res.ok && res.data) {
            const card = document.getElementById('weather-results-card');
            const w = res.data;
            card.innerHTML = `
                <h3>Weather in ${w.location}</h3>
                <div class="stat-card" style="margin-top:10px;">
                    <span class="stat-label">Temperature</span>
                    <span class="stat-value">${w.temperature_c}°C / ${w.temperature_f}°F</span>
                </div>
                <p><strong>Condition:</strong> ${w.condition}</p>
                <p><strong>Humidity:</strong> ${w.humidity_percent}% | <strong>Wind Speed:</strong> ${w.wind_speed_kmh} km/h</p>
                <p><strong>Precipitation:</strong> ${w.precipitation_mm} mm | <strong>Visibility:</strong> ${w.visibility_km} km</p>
                ${w.warnings.length ? `<div style="color:#f43f5e; margin-top:8px;">⚠️ ${w.warnings.join('<br>⚠️ ')}</div>` : ''}
            `;
        }
    });

    // -------------------------------------------------------------
    // TAB 7: GPS LOCATION
    // -------------------------------------------------------------
    document.getElementById('form-gps-ping').addEventListener('submit', async (e) => {
        e.preventDefault();
        const devId = document.getElementById('gps-device-id').value;
        const payload = {
            device_id: devId,
            latitude: parseFloat(document.getElementById('gps-lat').value),
            longitude: parseFloat(document.getElementById('gps-lng').value),
            timestamp: new Date().toISOString(),
            speed_kmh: parseFloat(document.getElementById('gps-speed').value),
            heading_deg: parseFloat(document.getElementById('gps-heading').value)
        };
        const res = await apiCall('/gps/ping', 'POST', payload);
        if (res.ok) fetchGpsHistory(devId);
    });

    async function fetchGpsHistory(devId) {
        const res = await fetch(`${API_BASE}/gps/${encodeURIComponent(devId)}/history`);
        if (!res.ok) return;
        const data = await res.json();
        const tbody = document.querySelector('#table-gps tbody');
        tbody.innerHTML = '';
        (data.history || []).forEach(g => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${g.timestamp.split('T')[1] || g.timestamp}</td>
                <td>${g.latitude}</td>
                <td>${g.longitude}</td>
                <td>${g.speed_kmh} km/h</td>
            `;
            tbody.appendChild(tr);
        });
    }

    document.getElementById('btn-fetch-gps').addEventListener('click', () => {
        const devId = document.getElementById('gps-device-id').value;
        fetchGpsHistory(devId);
    });

    // -------------------------------------------------------------
    // TAB 8: GUIDE REPORTS
    // -------------------------------------------------------------
    async function loadGuideReports() {
        const res = await fetch(`${API_BASE}/guide-reports`);
        const data = await res.json();
        const tbody = document.querySelector('#table-guide-reports tbody');
        tbody.innerHTML = '';
        (data || []).forEach(r => {
            const badgeClass = r.severity === 'CRITICAL' || r.severity === 'HIGH' ? 'badge-danger' : 'badge-warning';
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><code>${r.report_id}</code></td>
                <td>${r.guide_id}</td>
                <td>${r.location}</td>
                <td>${r.report_type}</td>
                <td><span class="badge ${badgeClass}">${r.severity}</span></td>
                <td>${r.message}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    document.getElementById('form-guide').addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
            guide_id: document.getElementById('guide-id').value,
            location: document.getElementById('guide-location').value,
            report_type: document.getElementById('guide-type').value,
            severity: document.getElementById('guide-severity').value,
            message: document.getElementById('guide-message').value
        };
        const res = await apiCall('/guide-reports', 'POST', payload);
        if (res.ok) loadGuideReports();
    });

    // -------------------------------------------------------------
    // TAB 9: LOCATION DATA (GEOCODING)
    // -------------------------------------------------------------
    document.getElementById('form-geocode').addEventListener('submit', async (e) => {
        e.preventDefault();
        const q = document.getElementById('geocode-query').value;
        const res = await apiCall(`/location/geocode?query=${encodeURIComponent(q)}`, 'GET');
        if (res.ok && res.data) {
            renderLocationCard(res.data);
        }
    });

    document.getElementById('form-reverse-geocode').addEventListener('submit', async (e) => {
        e.preventDefault();
        const lat = document.getElementById('rev-lat').value;
        const lng = document.getElementById('rev-lng').value;
        const res = await apiCall(`/location/reverse-geocode?latitude=${lat}&longitude=${lng}`, 'GET');
        if (res.ok && res.data) {
            renderLocationCard(res.data);
        }
    });

    function renderLocationCard(l) {
        const card = document.getElementById('location-results-card');
        card.innerHTML = `
            <h3>${l.place_name}</h3>
            <p><strong>Address:</strong> ${l.address}</p>
            <p><strong>Coordinates:</strong> Lat ${l.latitude}, Lng ${l.longitude}</p>
            <p><strong>City/Country:</strong> ${l.city}, ${l.country} (${l.postal_code || '-'})</p>
            ${l.points_of_interest.length ? `<p><strong>Nearby POIs:</strong> ${l.points_of_interest.join(', ')}</p>` : ''}
        `;
    }

    // -------------------------------------------------------------
    // TAB 10: HISTORICAL DATA
    // -------------------------------------------------------------
    document.getElementById('form-historical').addEventListener('submit', async (e) => {
        e.preventDefault();
        const loc = document.getElementById('hist-location').value;
        const from = document.getElementById('hist-from').value;
        const to = document.getElementById('hist-to').value;
        const res = await apiCall(`/historical/weather?location=${encodeURIComponent(loc)}&date_from=${from}&date_to=${to}`, 'GET');
        if (res.ok && res.data) {
            const card = document.getElementById('historical-results-card');
            const h = res.data;
            card.innerHTML = `
                <h3>Historical Trends for ${h.location}</h3>
                <div class="stat-card" style="margin-top:10px;">
                    <span class="stat-label">Delay Risk Score</span>
                    <span class="stat-value" style="color:${h.delay_risk_score === 'LOW' ? '#10b981' : '#f59e0b'}">${h.delay_risk_score}</span>
                </div>
                <p><strong>Historical Avg Temp:</strong> ${h.historical_weather_avg_temp_c}°C</p>
                <p><strong>Historical Total Rainfall:</strong> ${h.historical_rainfall_mm} mm</p>
                <p><strong>Historical Avg Traffic Delay:</strong> ${h.historical_avg_traffic_delay_mins} mins</p>
            `;
        }
    });

    // Helper: Load all tables on startup
    function loadAllTables() {
        refreshStats();
        loadItineraries();
        loadBookings();
        loadFlights();
        loadTrains();
        loadGuideReports();
        fetchGpsHistory('DEV-TOUR-101');
    }

    loadAllTables();
});
