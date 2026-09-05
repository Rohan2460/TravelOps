import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getTrips } from '../api/tripApi';

const STATUS_STYLES = {
  active: 'bg-purple-100 text-purple-800',
  upcoming: 'bg-blue-100 text-blue-800',
  completed: 'bg-gray-200 text-gray-700',
};

const READINESS_STYLES = {
  ready: 'bg-green-100 text-green-800',
  attention: 'bg-amber-100 text-amber-800',
  incomplete: 'bg-red-100 text-red-800',
};

const FILTERS = ['all', 'upcoming', 'active', 'completed'];

function formatDateTime(value) {
  if (!value) return '—';
  return new Date(value).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function StatChip({ label, value, tone }) {
  return (
    <div className={`flex items-center gap-1 rounded px-2 py-0.5 text-xs ${tone}`}>
      <span className="font-semibold">{value}</span>
      <span>{label}</span>
    </div>
  );
}

export default function TripList() {
  const [filter, setFilter] = useState('all');

  const { data: trips, isLoading, error } = useQuery({
    queryKey: ['trips'],
    queryFn: getTrips,
  });

  if (isLoading) return <div className="p-6">Loading trips...</div>;
  if (error) return <div className="p-6 text-red-500">Failed to load trips</div>;

  const tripArray = Array.isArray(trips) ? trips : [];
  const filtered = filter === 'all'
    ? tripArray
    : tripArray.filter((t) => t.status === filter);

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold">🚀 Operator Dashboard</h1>
          <p className="text-gray-500 text-sm mt-1">
            Centralized view of trips and their operational readiness
          </p>
        </div>
        <Link to="/trips/new" className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
          + Create New Trip
        </Link>
      </div>

      <div className="flex gap-2 mb-6">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-1.5 rounded text-sm capitalize ${
              filter === f
                ? 'bg-blue-600 text-white'
                : 'bg-white border border-gray-300 hover:bg-gray-50'
            }`}
          >
            {f}
            {f !== 'all' && (
              <span className="ml-1 text-xs opacity-70">
                ({tripArray.filter((t) => t.status === f).length})
              </span>
            )}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="bg-white p-8 text-center rounded-lg border border-dashed border-gray-300">
          <p className="text-gray-600">No trips found. Create your first trip!</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filtered.map((trip) => (
            <Link key={trip.id} to={`/trips/${trip.id}`}>
              <div className="border rounded-lg shadow hover:shadow-lg transition bg-white p-5 cursor-pointer h-full flex flex-col">
                <div className="flex justify-between items-start gap-2">
                  <h2 className="text-xl font-semibold">{trip.name}</h2>
                  <span className={`inline-block px-3 py-1 text-xs font-semibold rounded-full shrink-0 ${
                    STATUS_STYLES[trip.status] || 'bg-blue-100 text-blue-800'
                  }`}>
                    {trip.status || 'upcoming'}
                  </span>
                </div>
                <p className="text-gray-600 text-sm mt-1">ID: {trip.id} · Guide: {trip.guide_id}</p>

                <div className="mt-3">
                  <span className="text-xs text-gray-500">Readiness</span>
                  <div>
                    {trip.readiness ? (
                      <span className={`inline-block px-3 py-1 text-xs font-semibold rounded-full ${
                        READINESS_STYLES[trip.readiness] || 'bg-gray-100 text-gray-700'
                      }`}>
                        {trip.readiness}
                      </span>
                    ) : (
                      <span className="inline-block px-3 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-500">
                        not assessed
                      </span>
                    )}
                  </div>
                </div>

                <div className="mt-4">
                  <span className="text-xs text-gray-500">Nearest departure</span>
                  <div className="text-sm font-medium">
                    {formatDateTime(trip.nearest_departure)}
                  </div>
                </div>

                <div className="mt-3 pt-3 border-t flex flex-wrap gap-2">
                  <StatChip
                    label="cases"
                    value={trip.open_cases}
                    tone={trip.open_cases > 0 ? 'bg-red-50 text-red-700' : 'bg-gray-50 text-gray-600'}
                  />
                  <StatChip
                    label="affected"
                    value={trip.affected_elements}
                    tone={trip.affected_elements > 0 ? 'bg-amber-50 text-amber-700' : 'bg-gray-50 text-gray-600'}
                  />
                  <StatChip
                    label="high risks"
                    value={trip.open_risks}
                    tone={trip.open_risks > 0 ? 'bg-orange-50 text-orange-700' : 'bg-gray-50 text-gray-600'}
                  />
                </div>

                <p className="text-gray-500 text-xs mt-3">
                  {formatDateTime(trip.start_time)} → {formatDateTime(trip.end_time)}
                </p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}