import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getTrips } from '../api/tripApi';

export default function TripList() {
  const { data: trips, isLoading, error } = useQuery({
    queryKey: ['trips'],
    queryFn: getTrips,
  });

  if (isLoading) return <div className="p-6">Loading trips...</div>;
  if (error) return <div className="p-6 text-red-500">Failed to load trips</div>;

  const tripArray = Array.isArray(trips) ? trips : [];

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">🚀 Active Trips</h1>
        <Link to="/trips/new" className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
          + Create New Trip
        </Link>
      </div>
      {tripArray.length === 0 ? (
        <div className="bg-gray-100 p-8 text-center rounded-lg">
          <p className="text-gray-600">No trips found. Create your first trip!</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {tripArray.map((trip) => (
            <Link key={trip.id} to={`/trips/${trip.id}`}>
              <div className="border rounded-lg shadow hover:shadow-lg transition bg-white p-5 cursor-pointer">
                <h2 className="text-xl font-semibold">{trip.name}</h2>
                <p className="text-gray-600 text-sm mt-1">ID: {trip.id}</p>
                <p className="text-gray-600 text-sm">Guide ID: {trip.guide_id}</p>
                <span className={`inline-block mt-3 px-3 py-1 text-xs font-semibold rounded-full ${
                  trip.status === 'completed' ? 'bg-green-100 text-green-800' :
                  trip.status === 'active' ? 'bg-blue-100 text-blue-800' :
                  'bg-yellow-100 text-yellow-800'
                }`}>
                  {trip.status || 'upcoming'}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}