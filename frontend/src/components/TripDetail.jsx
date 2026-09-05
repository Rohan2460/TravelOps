import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getTrip, deleteTrip } from '../api/tripApi';

export default function TripDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: trip, isLoading, error } = useQuery({
    queryKey: ['trip', id],
    queryFn: () => getTrip(id),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteTrip,
    onSuccess: () => {
      queryClient.invalidateQueries(['trips']);
      navigate('/trips');
    },
  });

  if (isLoading) return <div className="p-6">Loading trip details...</div>;
  if (error) return <div className="p-6 text-red-500">Trip not found</div>;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-bold">{trip.name}</h1>
            <p className="text-gray-600">ID: {trip.id} | Guide: {trip.guide_id}</p>
          </div>
          <div className="flex gap-2">
            <button 
              onClick={() => navigate(`/trips/${id}/edit`)}
              className="bg-gray-200 px-4 py-2 rounded hover:bg-gray-300"
            >
              ✏️ Edit
            </button>
            <button 
              onClick={() => { if (window.confirm('Delete this trip?')) deleteMutation.mutate(id); }}
              className="bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600"
            >
              🗑️ Delete
            </button>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4 mt-4">
          <div>
            <span className="font-semibold">Start:</span> {new Date(trip.start_time).toLocaleString()}
          </div>
          <div>
            <span className="font-semibold">End:</span> {new Date(trip.end_time).toLocaleString()}
          </div>
          <div>
            <span className="font-semibold">Status:</span> 
            <span className={`ml-2 px-2 py-1 rounded text-xs ${
              trip.status === 'completed' ? 'bg-green-100 text-green-800' :
              trip.status === 'active' ? 'bg-blue-100 text-blue-800' :
              'bg-yellow-100 text-yellow-800'
            }`}>
              {trip.status}
            </span>
          </div>
        </div>
        {/* Itinerary Elements placeholder */}
        <div className="mt-8 border-t pt-6">
          <h2 className="text-xl font-bold mb-4">🗺️ Itinerary Elements</h2>
          <div className="bg-gray-50 p-4 rounded border border-dashed border-gray-300 text-gray-500 text-sm">
            💡 Itinerary elements will appear here after we build the nested serializers.
          </div>
        </div>
      </div>
    </div>
  );
}