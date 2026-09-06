import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getTrip, deleteTrip } from '../api/tripApi';
import {
  formatDateTime,
  formatDuration,
  elementIcon,
  SEVERITY_STYLES,
  ELEMENT_STATUS_STYLES,
  chip,
} from '../lib/format';

const TRIP_STATUS_STYLES = {
  active: 'bg-purple-100 text-purple-800',
  upcoming: 'bg-blue-100 text-blue-800',
  completed: 'bg-gray-200 text-gray-700',
};

const READINESS_STYLES = {
  ready: 'bg-green-100 text-green-800',
  attention: 'bg-amber-100 text-amber-800',
  incomplete: 'bg-red-100 text-red-800',
};

const BOOKING_STYLES = {
  confirmed: 'bg-green-100 text-green-800',
  pending: 'bg-amber-100 text-amber-800',
};

const ACTION_STYLES = {
  completed: 'bg-green-100 text-green-800',
  pending: 'bg-amber-100 text-amber-800',
};

function Section({ title, count, children }) {
  return (
    <div className="mt-8 border-t pt-6">
      <h2 className="text-xl font-bold mb-4">
        {title}
        {typeof count === 'number' && (
          <span className="ml-2 text-sm font-normal text-gray-500">({count})</span>
        )}
      </h2>
      {children}
    </div>
  );
}

function Bookings({ bookings }) {
  if (!bookings || bookings.length === 0) {
    return <p className="text-xs text-gray-400">No bookings</p>;
  }
  return (
    <div className="space-y-2">
      {bookings.map((booking) => (
        <div key={booking.id} className="bg-gray-50 border rounded p-2 text-sm">
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium">{booking.supplier_name}</span>
            {chip(booking.status, BOOKING_STYLES[booking.status] || 'bg-gray-100 text-gray-700')}
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Ref: {booking.booking_reference || '—'}
            {booking.notes ? ` · ${booking.notes}` : ''}
          </p>
        </div>
      ))}
    </div>
  );
}

function ItineraryElementRow({ element }) {
  const start = element.start_location;
  const end = element.end_location;
  return (
    <div className="border rounded-lg p-4 bg-white">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{elementIcon[element.type] || '📍'}</span>
          <div>
            <h3 className="font-semibold">{element.name}</h3>
            <p className="text-xs text-gray-500 capitalize">
              #{element.sequence} · {element.type.replace('_', ' ')}
            </p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          {chip(element.status, ELEMENT_STATUS_STYLES[element.status] || 'bg-gray-100 text-gray-700')}
          {element.actual_start && chip('started', 'bg-blue-100 text-blue-800')}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3 text-sm">
        <div>
          <span className="text-xs text-gray-500">Planned</span>
          <div className="font-medium">
            {formatDateTime(element.planned_start)} → {formatDateTime(element.planned_end)}
          </div>
        </div>
        {(element.actual_start || element.actual_end) && (
          <div>
            <span className="text-xs text-gray-500">Actual</span>
            <div className="font-medium">
              {formatDateTime(element.actual_start)} → {formatDateTime(element.actual_end)}
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3 text-sm">
        <div className="bg-gray-50 rounded p-2">
          <span className="text-xs text-gray-500">From</span>
          <div className="font-medium">{start?.name || '—'}</div>
          {start?.address && <div className="text-xs text-gray-500">{start.address}</div>}
        </div>
        <div className="bg-gray-50 rounded p-2">
          <span className="text-xs text-gray-500">To</span>
          <div className="font-medium">{end?.name || '—'}</div>
          {end?.address && <div className="text-xs text-gray-500">{end.address}</div>}
        </div>
      </div>

      <div className="mt-3">
        <Bookings bookings={element.bookings} />
      </div>
    </div>
  );
}

function Timetable({ elements }) {
  return (
    <div className="space-y-3">
      {elements.map((element) => (
        <ItineraryElementRow key={element.id} element={element} />
      ))}
    </div>
  );
}

function Dependencies({ dependencies }) {
  if (!dependencies || dependencies.length === 0) {
    return <p className="text-gray-500 text-sm">No dependencies defined.</p>;
  }
  return (
    <div className="space-y-2">
      {dependencies.map((dependency) => (
        <div key={dependency.id} className="border rounded p-3 bg-white text-sm flex flex-wrap items-center gap-2">
          <span className="font-medium">Element #{dependency.from_element}</span>
          <span>→</span>
          <span className="font-medium">#{dependency.to_element}</span>
          <span>{chip(dependency.type, 'bg-blue-100 text-blue-800')}</span>
          <span className="text-gray-500 text-xs">
            min buffer {formatDuration(dependency.minimum_buffer)}
          </span>
        </div>
      ))}
    </div>
  );
}

function ImpactRow({ impact, elementId }) {
  return (
    <div className="border-l-2 border-gray-200 pl-3 py-1">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium">Element #{impact.itinerary_element || elementId}</span>
        {chip(impact.classification, 'bg-gray-100 text-gray-700')}
        {chip(impact.status, ELEMENT_STATUS_STYLES[impact.status] || 'bg-gray-100 text-gray-700')}
        {chip(impact.severity, SEVERITY_STYLES[impact.severity] || 'bg-gray-100 text-gray-700')}
      </div>
      {impact.reason && <p className="text-xs text-gray-600 mt-1">{impact.reason}</p>}
    </div>
  );
}

function Events({ events }) {
  if (!events || events.length === 0) {
    return <p className="text-gray-500 text-sm">No events recorded.</p>;
  }
  return (
    <div className="space-y-3">
      {events.map((event) => (
        <div key={event.id} className="border rounded-lg p-4 bg-white">
          <div className="flex items-start justify-between gap-2 flex-wrap">
            <div>
              <h3 className="font-semibold">{event.title}</h3>
              <p className="text-xs text-gray-500 capitalize">
                {event.type.replace('_', ' ')} · source: {event.source}
                {event.location ? ` · @ ${event.location.name}` : ''}
              </p>
            </div>
            <div className="flex items-center gap-1">
              {chip(event.severity, SEVERITY_STYLES[event.severity] || 'bg-gray-100 text-gray-700')}
              {chip(event.status, 'bg-gray-100 text-gray-700')}
            </div>
          </div>
          {event.description && <p className="text-sm text-gray-600 mt-2">{event.description}</p>}
          <p className="text-xs text-gray-500 mt-2">
            Occurred {formatDateTime(event.occurred_at)} · Reported {formatDateTime(event.reported_at)}
          </p>
          <div className="mt-3 space-y-2">
            <p className="text-xs text-gray-500 font-semibold uppercase">Impacts</p>
            {event.impacts?.map((impact) => (
              <ImpactRow key={impact.id} impact={impact} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function Cases({ cases }) {
  if (!cases || cases.length === 0) {
    return <p className="text-gray-500 text-sm">No open cases.</p>;
  }
  return (
    <div className="space-y-3">
      {cases.map((item) => (
        <div key={item.id} className="border rounded-lg p-4 bg-white">
          <div className="flex items-start justify-between gap-2 flex-wrap">
            <div>
              <h3 className="font-semibold">{item.title}</h3>
              <p className="text-xs text-gray-500">
                Case #{item.id} · Priority {item.priority || '—'} · Assigned to {item.assigned_to || '—'}
                {item.primary_event ? ` · Event #${item.primary_event}` : ''}
              </p>
            </div>
            {chip(item.status, item.status === 'open' ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-700')}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">
            <div>
              <p className="text-xs text-gray-500 font-semibold uppercase mb-2">Actions</p>
              {item.actions?.length ? (
                <div className="space-y-2">
                  {item.actions.map((action) => (
                    <div key={action.id} className="bg-gray-50 border rounded p-2 text-sm">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">{action.type.replace('_', ' ')}</span>
                        {chip(action.status, ACTION_STYLES[action.status] || 'bg-gray-100 text-gray-700')}
                      </div>
                      {action.description && <p className="text-xs text-gray-600 mt-1">{action.description}</p>}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-gray-400">No actions</p>
              )}
            </div>
            <div>
              <p className="text-xs text-gray-500 font-semibold uppercase mb-2">Linked impacts</p>
              {item.case_impacts?.length ? (
                <div className="space-y-2">
                  {item.case_impacts.map((ci) => (
                    <ImpactRow key={ci.id} impact={ci.impact} />
                  ))}
                </div>
              ) : (
                <p className="text-xs text-gray-400">No linked impacts</p>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function TripRisks({ risks }) {
  if (!risks || risks.length === 0) {
    return <p className="text-gray-500 text-sm">No risks recorded.</p>;
  }
  return (
    <div className="space-y-2">
      {risks.map((risk) => (
        <div key={risk.id} className="border rounded p-3 bg-white text-sm flex items-center justify-between gap-2 flex-wrap">
          <div>
            <span className="font-medium capitalize">{risk.type}</span>
            {risk.reason && <p className="text-xs text-gray-600 mt-0.5">{risk.reason}</p>}
          </div>
          <div className="flex items-center gap-1">
            {chip(risk.severity, SEVERITY_STYLES[risk.severity] || 'bg-gray-100 text-gray-700')}
            {chip(risk.status, 'bg-gray-100 text-gray-700')}
          </div>
        </div>
      ))}
    </div>
  );
}

function ItineraryChanges({ changes }) {
  if (!changes || changes.length === 0) {
    return <p className="text-gray-500 text-sm">No changes recorded.</p>;
  }
  return (
    <div className="space-y-2">
      {changes.map((change) => (
        <div key={change.id} className="border rounded p-3 bg-white text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">Element #{change.itinerary_element}</span>
            {chip(change.change_type, 'bg-gray-100 text-gray-700')}
            {change.event ? <span className="text-xs text-gray-500">Event #{change.event}</span> : null}
            <span className="text-xs text-gray-500 ml-auto">{formatDateTime(change.changed_at)}</span>
          </div>
          <p className="text-xs mt-1">
            <span className="text-gray-400 line-through">{change.old_value || '—'}</span>
            <span className="mx-1">→</span>
            <span className="font-medium">{change.new_value || '—'}</span>
          </p>
          {change.reason && <p className="text-xs text-gray-600 mt-1">Reason: {change.reason}</p>}
        </div>
      ))}
    </div>
  );
}

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

  const readiness = trip.readiness_assessment;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <Link to="/trips" className="text-sm text-blue-600 hover:underline">← Back to dashboard</Link>

      <div className="bg-white shadow rounded-lg p-6 mt-3">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-bold">{trip.name}</h1>
            <p className="text-gray-600">ID: {trip.id} | Guide: {trip.guide_id}</p>
          </div>
          <div className="flex gap-2 flex-wrap justify-end">
            <Link
              to={`/trips/${id}/timeline`}
              className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
            >
              🗺️ Timeline
            </Link>
            <Link
              to={`/trips/${id}/analysis`}
              className="bg-emerald-600 text-white px-4 py-2 rounded hover:bg-emerald-700"
            >
              📊 Analysis
            </Link>
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
            <span className="font-semibold">Start:</span> {formatDateTime(trip.start_time)}
          </div>
          <div>
            <span className="font-semibold">End:</span> {formatDateTime(trip.end_time)}
          </div>
          <div>
            <span className="font-semibold">Status:</span>
            {chip(trip.status, TRIP_STATUS_STYLES[trip.status] || 'bg-gray-100 text-gray-700')}
          </div>
          <div>
            <span className="font-semibold">Readiness:</span>
            {readiness ? (
              chip(readiness.status, READINESS_STYLES[readiness.status] || 'bg-gray-100 text-gray-700')
            ) : (
              chip('not assessed', 'bg-gray-100 text-gray-500')
            )}
          </div>
        </div>

        {readiness?.reason && (
          <p className="text-sm text-gray-600 mt-3 bg-gray-50 rounded p-3">
            <span className="font-semibold">Assessment note:</span> {readiness.reason}
            <span className="text-xs text-gray-500 block mt-1">
              Calculated {formatDateTime(readiness.calculated_at)}
            </span>
          </p>
        )}
      </div>

      <Section title="🗺️ Itinerary Elements" count={trip.itinerary_elements?.length || 0}>
        {trip.itinerary_elements?.length ? (
          <Timetable elements={trip.itinerary_elements} />
        ) : (
          <p className="text-gray-500 text-sm">No itinerary elements.</p>
        )}
      </Section>

      <Section title="🔗 Dependencies" count={trip.dependencies?.length || 0}>
        <Dependencies dependencies={trip.dependencies} />
      </Section>

      <Section title="⚠️ Events & Impacts" count={trip.events?.length || 0}>
        <Events events={trip.events} />
      </Section>

      <Section title="📌 Cases & Actions" count={trip.cases?.length || 0}>
        <Cases cases={trip.cases} />
      </Section>

      <Section title="🛡️ Trip Risks" count={trip.trip_risks?.length || 0}>
        <TripRisks risks={trip.trip_risks} />
      </Section>

      <Section title="🕓 Itinerary Changes" count={trip.itinerary_changes?.length || 0}>
        <ItineraryChanges changes={trip.itinerary_changes} />
      </Section>
    </div>
  );
}