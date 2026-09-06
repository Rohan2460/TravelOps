import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  getTrip,
  getTripAnalysis,
  getTripLiveStatus,
  getTripAlternatives,
} from '../api/tripApi';
import {
  formatDateTime,
  formatMinutes,
  elementIcon,
  SEVERITY_STYLES,
  chip,
} from '../lib/format';
import {
  alternativeEligible,
  buildTimeline,
  downstreamClosure,
  LIVE_STATUS_TONES,
  recommendationsForNode,
} from '../lib/timeline';

const TRIP_STATUS_STYLES = {
  active: 'bg-purple-100 text-purple-800',
  upcoming: 'bg-blue-100 text-blue-800',
  completed: 'bg-gray-200 text-gray-700',
};

const LIVE_STATUS_CHIPS = {
  valid: 'bg-green-100 text-green-800',
  at_risk: 'bg-amber-100 text-amber-800',
  disrupted: 'bg-red-100 text-red-800',
  unknown: 'bg-gray-100 text-gray-700',
};

const NODE_BORDER = {
  neutral: 'border-gray-200',
  green: 'border-green-500 bg-green-50/30',
  amber: 'border-amber-500 bg-amber-50/40',
  red: 'border-red-500 bg-red-50/40',
  gray: 'border-gray-300',
};

const MODE_ICONS = {
  driving: '🚗',
  transit: '🚇',
  walking: '🚶',
  bicycling: '🚲',
};

function nodeTone(node, mode) {
  if (mode !== 'live' || !node.live) return 'neutral';
  return LIVE_STATUS_TONES[node.live.status] || 'gray';
}

function statusLabel(node, mode) {
  if (mode === 'live' && node.live) return node.live.status;
  return node.status || '—';
}

function Subtitle({ node }) {
  if (node.type === 'hotel') return 'Check-in';
  if (node.start && node.end) return `${node.start} → ${node.end}`;
  return node.type.replace('_', ' ');
}

function NodeCard({ node, mode, selected, dimmed, onClick }) {
  const tone = nodeTone(node, mode);
  return (
    <button
      type="button"
      onClick={onClick}
      className={`relative w-[420px] rounded-lg border-2 bg-white p-3 shadow-sm text-left transition
        ${NODE_BORDER[tone]}
        ${selected ? 'ring-2 ring-blue-500' : 'hover:border-blue-300'}
        ${dimmed ? 'opacity-30' : ''}`}
    >
      <div className="flex items-start gap-2">
        <span className="text-2xl leading-none mt-0.5">
          {elementIcon[node.type] || '📍'}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <h3 className="font-semibold text-sm truncate">{node.name}</h3>
            {chip(
              statusLabel(node, mode),
              mode === 'live' && node.live
                ? LIVE_STATUS_CHIPS[node.live.status] || 'bg-gray-100 text-gray-700'
                : 'bg-gray-100 text-gray-600'
            )}
          </div>
          <p className="text-xs text-gray-500">
            <span className="capitalize">{node.type.replace('_', ' ')}</span>
            {' · '}
            <Subtitle node={node} />
          </p>
          <p className="text-xs text-gray-700 mt-1.5">
            {formatDateTime(node.plannedStart)}
            {formatDateTime(node.plannedEnd) !== formatDateTime(node.plannedStart) ? (
              <span className="text-gray-500"> → {formatDateTime(node.plannedEnd)}</span>
            ) : (
              ''
            )}
          </p>
          <p className="text-xs text-gray-500 mt-0.5">
            {node.delayMinutes > 0 && (
              <span className="text-red-600 font-medium mr-1">
                +{formatMinutes(node.delayMinutes)}
              </span>
            )}
            <span className="capitalize">
              {node.type.replace('_', ' ')} · {formatMinutes(node.plannedDurationMinutes)}
            </span>
            {node.distanceKm != null && (
              <span> · {Math.round(node.distanceKm)} km</span>
            )}
          </p>
        </div>
      </div>
    </button>
  );
}

function MarkerDot({ progress, onSelect }) {
  return (
    <button
      type="button"
      title={progress.stale ? 'GPS position is stale' : 'Current location'}
      onClick={onSelect}
      className={`absolute left-[-8px] h-4 w-4 rounded-full border-2 z-10 transition-transform
        ${progress.stale ? 'bg-gray-300 border-gray-400' : 'bg-blue-500 border-white'}
        hover:scale-125`}
      style={{ top: `calc(${progress.partial * 100}% - 8px)` }}
    />
  );
}

function Segment({ segment, progress, mode, onSelectGps }) {
  const isMarkerSegment =
    progress.present && progress.segmentIndex === segment.index;
  const done = progress.present && segment.index < progress.segmentIndex;
  const lineColor =
    segment.risk === 'missed'
      ? 'bg-red-400'
      : segment.risk === 'delay'
        ? 'bg-amber-400'
        : done
          ? 'bg-blue-500'
          : 'bg-gray-200';

  const label =
    mode === 'live' && segment.risk !== 'ok' ? segment.labelLive : segment.label;
  const labelTone =
    segment.risk === 'missed'
      ? 'bg-red-100 text-red-700 border-red-200'
      : segment.risk === 'delay'
        ? 'bg-amber-100 text-amber-700 border-amber-200'
        : 'bg-white text-gray-500 border-gray-200';

  return (
    <div className="relative pl-10 py-1">
      <div className="absolute left-0 top-0 bottom-0 w-[3px] rounded-full bg-gray-200 -ml-[1px]" />
      {isMarkerSegment ? (
        <>
          <div
            className="absolute left-0 top-0 w-[3px] rounded-full bg-blue-500 -ml-[1px]"
            style={{ height: `${progress.partial * 100}%` }}
          />
          <MarkerDot progress={progress} onSelect={onSelectGps} />
        </>
      ) : (
        <div className={`absolute left-0 top-0 bottom-0 w-[3px] rounded-full ${lineColor} -ml-[1px]`} />
      )}
      <div className="flex items-center h-9">
        <span
          className={`inline-block px-2 py-0.5 rounded-full border text-xs font-medium tracking-wide ${labelTone}`}
        >
          {label}
        </span>
      </div>
    </div>
  );
}

function RecommendationBranch({ node, recs, selected, onSelect }) {
  if (recs.length === 0) return null;
  return (
    <div className="absolute w-60" style={{ left: 'calc(50% + 234px)' }}>
      <div className="bg-amber-300 h-px w-10 mx-auto mb-1" />
      <button
        type="button"
        onClick={() => onSelect({ kind: 'rec', elementId: node.id })}
        className={`w-full text-left rounded-lg border-2 border-dashed border-amber-300 bg-amber-50 p-2 shadow-sm hover:bg-amber-100 transition
          ${selected ? 'ring-2 ring-amber-500' : ''}`}
      >
        <p className="text-[10px] font-bold uppercase tracking-wider text-amber-600">
          Recommended actions
        </p>
        <ul className="mt-1 space-y-0.5">
          {recs.slice(0, 3).map((rec) => (
            <li key={rec.case_id + rec.type} className="text-xs text-gray-700 truncate">
              • {rec.type.replace(/_/g, ' ')}
            </li>
          ))}
          {recs.length > 3 && (
            <li className="text-xs text-amber-600 font-medium">+{recs.length - 3} more</li>
          )}
        </ul>
      </button>
    </div>
  );
}

function RouteBranchQuery({ tripId, node, selected, onSelect }) {
  const [open, setOpen] = useState(false);
  const query = useQuery({
    queryKey: ['trip', 'alternatives', tripId, node.id],
    queryFn: () => getTripAlternatives(tripId, node.id),
    enabled: open,
    staleTime: 10 * 60 * 1000,
  });

  const isSelected = selected?.kind === 'alt' && selected.elementId === node.id;

  const handleClick = () => {
    setOpen(true);
    onSelect({ kind: 'alt', elementId: node.id });
  };

  let summary;
  if (!open && !query.data) {
    summary = <span className="text-xs text-gray-500">Tap to load options</span>;
  } else if (query.isLoading) {
    summary = <span className="text-xs text-gray-500">Loading…</span>;
  } else if (query.error) {
    const detail =
      query.error?.response?.data?.detail || (query.error?.message ?? 'unavailable');
    summary = (
      <span className="text-xs text-gray-500">
        {detail.split('.')[0]}
        {query.error?.response?.status === 503
          ? ' (configure GOOGLE_MAPS_API_KEY)'
          : ''}
      </span>
    );
  } else {
    const options = query.data?.alternatives || [];
    summary = (
      <ul className="mt-1 space-y-0.5">
        {options.slice(0, 2).map((option) => (
          <li key={option.mode} className="text-xs text-gray-700 truncate">
            {MODE_ICONS[option.mode] || '🛣️'} {option.mode} ·{' '}
            {Math.round(option.distance_km)} km · {formatMinutes(option.duration_minutes)}
          </li>
        ))}
        {options.length > 2 && (
          <li className="text-xs text-sky-600 font-medium">+{options.length - 2} more</li>
        )}
        {options.length === 0 && (
          <li className="text-xs text-gray-500">No surface route found</li>
        )}
      </ul>
    );
  }

  return (
    <div className="absolute top-8 w-60" style={{ left: 'calc(50% + 234px)' }}>
      <div className="bg-sky-200 h-px mx-auto w-10 mb-1" />
      <button
        type="button"
        onClick={handleClick}
        className={`w-full text-left rounded-lg border-2 border-dashed border-sky-300 bg-sky-50 p-2 shadow-sm hover:bg-sky-100 transition
          ${isSelected ? 'ring-2 ring-sky-500' : ''}`}
      >
        <p className="text-[10px] font-bold uppercase tracking-wider text-sky-600">
          Alternative route
        </p>
        {summary}
      </button>
    </div>
  );
}

function NodeRow({
  node,
  mode,
  selected,
  dimmed,
  related,
  tripId,
  live,
  analysis,
  onSelectNode,
}) {
  const recs =
    mode === 'live' ? recommendationsForNode(live.cases, node.id) : [];
  const eligible = alternativeEligible(node, analysis?.timeline?.connections || []);
  const tone = nodeTone(node, mode);
  const dotTone = {
    neutral: 'bg-gray-400',
    green: 'bg-green-500',
    amber: 'bg-amber-500',
    red: 'bg-red-500',
    gray: 'bg-gray-300',
  }[tone];

  return (
    <div className="relative pl-10 py-1">
      <span
        className={`absolute left-[-5px] top-5 h-2.5 w-2.5 rounded-full ${dotTone} border border-white`}
      />
      <NodeCard
        node={node}
        mode={mode}
        selected={selected?.kind === 'node' && selected.id === node.id}
        dimmed={dimmed && !related}
        onClick={() => onSelectNode({ kind: 'node', id: node.id })}
      />
      <RecommendationBranch
        node={node}
        recs={recs}
        selected={selected?.kind === 'rec' && selected.elementId === node.id}
        onSelect={onSelectNode}
      />
      {eligible && (
        <RouteBranchQuery
          tripId={tripId}
          node={node}
          selected={selected}
          onSelect={onSelectNode}
        />
      )}
    </div>
  );
}

function DetailField({ label, value, tone }) {
  return (
    <div className="bg-gray-50 rounded p-2">
      <span className="text-xs text-gray-500 block">{label}</span>
      <span className={`font-medium ${tone || ''}`}>{value}</span>
    </div>
  );
}

function NodeDetail({ node, mode, analysis, trip, live, close }) {
  const deadlines =
    analysis?.timeline?.deadlines?.filter((d) => d.element_id === node.id) || [];
  const relatedImpacts = [];
  for (const event of trip.events || []) {
    for (const impact of event.impacts || []) {
      if (impact.itinerary_element === node.id) {
        relatedImpacts.push({ event, impact });
      }
    }
  }
  const recs = recommendationsForNode(live?.cases, node.id);
  const isLive = mode === 'live' && node.live;

  return (
    <section className="space-y-4 p-5">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{elementIcon[node.type] || '📍'}</span>
          <div>
            <h2 className="text-lg font-bold leading-tight">{node.name}</h2>
            <p className="text-xs text-gray-500 capitalize">
              #{node.sequence} · {node.type.replace('_', ' ')}
            </p>
          </div>
        </div>
        {isLive ? (
          chip(
            node.live.status,
            LIVE_STATUS_CHIPS[node.live.status] || 'bg-gray-100 text-gray-700'
          )
        ) : (
          chip(node.status, 'bg-gray-100 text-gray-600')
        )}
      </div>

      {isLive && (
        <div className="bg-gray-50 rounded-lg p-3 border">
          <div className="flex flex-wrap gap-1.5">
            {chip(node.live.classification, 'bg-gray-100 text-gray-700')}
            {chip(
              node.live.severity,
              SEVERITY_STYLES[node.live.severity] || 'bg-gray-100 text-gray-700'
            )}
          </div>
          {node.live.reason && <p className="text-sm text-gray-700 mt-2">{node.live.reason}</p>}
          <p className="text-xs text-gray-500 mt-1">
            Calculated {formatDateTime(node.live.calculated_at)}
          </p>
        </div>
      )}

      <div>
        <h3 className="text-xs font-semibold text-gray-500 uppercase mb-1.5">Times</h3>
        <div className="grid grid-cols-1 gap-2 text-sm">
          <DetailField
            label="Planned"
            value={`${formatDateTime(node.plannedStart)} → ${formatDateTime(node.plannedEnd)}`}
          />
          <DetailField
            label="Duration"
            value={formatMinutes(node.plannedDurationMinutes)}
          />
          {node.actualStart && (
            <DetailField
              label="Actual"
              value={`${formatDateTime(node.actualStart)} → ${formatDateTime(node.actualEnd)}`}
            />
          )}
          <DetailField
            label="Effective end"
            value={formatDateTime(node.effectiveEnd)}
          />
          <DetailField
            label="Delay"
            value={node.delayMinutes > 0 ? `+${formatMinutes(node.delayMinutes)}` : '0'}
            tone={node.delayMinutes > 0 ? 'text-red-600' : 'text-gray-500'}
          />
        </div>
      </div>

      {(node.startLocation || node.endLocation) && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 uppercase mb-1.5">Locations</h3>
          <div className="space-y-2 text-sm">
            {node.startLocation && (
              <div className="bg-gray-50 rounded p-2">
                <span className="text-xs text-gray-500">From</span>
                <div className="font-medium">{node.startLocation.name}</div>
                <div className="text-xs text-gray-500">
                  {node.startLocation.address}
                  {node.startLocation.latitude != null &&
                    ` (${node.startLocation.latitude.toFixed(3)}, ${node.startLocation.longitude.toFixed(3)})`}
                </div>
              </div>
            )}
            {node.endLocation && (
              <div className="bg-gray-50 rounded p-2">
                <span className="text-xs text-gray-500">To</span>
                <div className="font-medium">{node.endLocation.name}</div>
                <div className="text-xs text-gray-500">
                  {node.endLocation.address}
                  {node.endLocation.latitude != null &&
                    ` (${node.endLocation.latitude.toFixed(3)}, ${node.endLocation.longitude.toFixed(3)})`}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <div>
        <h3 className="text-xs font-semibold text-gray-500 uppercase mb-1.5">
          Bookings ({node.bookings?.length || 0})
        </h3>
        {node.bookings?.length ? (
          <div className="space-y-2">
            {node.bookings.map((booking) => (
              <div key={booking.id} className="bg-gray-50 border rounded p-2 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{booking.supplier_name}</span>
                  {chip(
                    booking.status,
                    booking.status === 'confirmed'
                      ? 'bg-green-100 text-green-800'
                      : 'bg-amber-100 text-amber-800'
                  )}
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Ref: {booking.booking_reference || '—'}
                  {booking.notes ? ` · ${booking.notes}` : ''}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-gray-400">No bookings.</p>
        )}
      </div>

      {deadlines.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 uppercase mb-1.5">Deadlines</h3>
          <div className="space-y-2">
            {deadlines.map((deadline, index) => (
              <div key={index} className="bg-gray-50 border rounded p-2 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium capitalize">
                    {deadline.kind.replace('_', ' ')}
                  </span>
                  {deadline.satisfied ? (
                    chip('✓ satisfied', 'bg-green-100 text-green-800')
                  ) : (
                    chip('✗ missed', 'bg-red-100 text-red-800')
                  )}
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  {formatDateTime(deadline.deadline)}
                  {deadline.expected && ` · expected ${formatDateTime(deadline.expected)}`}
                  {deadline.remaining_minutes != null &&
                    ` · ${formatMinutes(deadline.remaining_minutes)} left`}
                  {deadline.buffer_minutes != null &&
                    ` · ${formatMinutes(deadline.buffer_minutes)} buffer`}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {isLive && recs.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 uppercase mb-1.5">
            Recommended actions
          </h3>
          <div className="space-y-2">
            {recs.map((rec) => (
              <div key={`${rec.case_id}-${rec.type}`} className="border-l-4 border-amber-400 pl-3 py-1">
                <div className="flex items-center gap-2 text-sm">
                  <span className="font-medium capitalize">{rec.type.replace(/_/g, ' ')}</span>
                  {chip(rec.status || 'recommended', 'bg-amber-100 text-amber-800')}
                </div>
                {rec.description && (
                  <p className="text-xs text-gray-600 mt-0.5">{rec.description}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {relatedImpacts.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 uppercase mb-1.5">
            Related events & impacts
          </h3>
          <div className="space-y-2">
            {relatedImpacts.map(({ event, impact }, index) => (
              <div key={index} className="border rounded p-2 bg-gray-50 text-sm">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="font-medium">{event.title}</span>
                  {chip(impact.classification, 'bg-gray-100 text-gray-700')}
                  {chip(
                    impact.severity,
                    SEVERITY_STYLES[impact.severity] || 'bg-gray-100 text-gray-700'
                  )}
                </div>
                {impact.reason && <p className="text-xs text-gray-600 mt-1">{impact.reason}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {isLive && node.live?.history?.length > 1 && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 uppercase mb-1.5">Status history</h3>
          <ul className="space-y-1">
            {node.live.history.slice(0, 5).map((row, index) => (
              <li key={index} className="flex items-center gap-2 text-xs">
                {chip(
                  row.status,
                  LIVE_STATUS_CHIPS[row.status] || 'bg-gray-100 text-gray-700'
                )}
                <span className="text-gray-600">{formatDateTime(row.calculated_at)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <button
        type="button"
        onClick={close}
        className="w-full border border-gray-300 rounded py-2 text-sm text-gray-600 hover:bg-gray-50"
      >
        Close
      </button>
    </section>
  );
}

function AlternativesDetail({ tripId, elementId, elementName, close }) {
  const query = useQuery({
    queryKey: ['trip', 'alternatives', tripId, elementId],
    queryFn: () => getTripAlternatives(tripId, elementId),
    enabled: true,
    staleTime: 10 * 60 * 1000,
  });

  let body;
  if (query.isLoading) {
    body = <p className="text-sm text-gray-500">Fetching route options…</p>;
  } else if (query.error) {
    body = (
      <div className="bg-red-50 border border-red-200 rounded p-3 text-sm text-red-700">
        {query.error?.response?.data?.detail || 'Route lookup failed.'}
      </div>
    );
  } else if (!query.data?.alternatives?.length) {
    body = (
      <p className="text-sm text-gray-500">
        No surface alternative found between the two locations.
      </p>
    );
  } else {
    body = (
      <div className="space-y-2">
        {query.data.alternatives.map((option, index) => (
          <div key={option.mode || index} className="bg-gray-50 border rounded p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="font-semibold">
                {MODE_ICONS[option.mode] || '🛣️'} {option.mode}
              </span>
              {chip(formatMinutes(option.duration_minutes), 'bg-sky-100 text-sky-800')}
            </div>
            <p className="text-xs text-gray-600 mt-1">
              {Math.round(option.distance_km)} km · dep {formatDateTime(option.departure_at)} · arr{' '}
              {formatDateTime(option.arrival_at)}
            </p>
            <p className="text-xs text-gray-500 mt-0.5">
              {option.duration_delta_minutes > 0
                ? `+${formatMinutes(option.duration_delta_minutes)} vs planned`
                : `${formatMinutes(option.duration_delta_minutes)} vs planned`}
            </p>
            {option.via?.length > 0 && (
              <p className="text-xs text-gray-500 mt-1 truncate">via {option.via[0]}</p>
            )}
          </div>
        ))}
        <p className="text-xs text-gray-400 pt-1">
          Operator recommendation only — no booking is changed automatically.
        </p>
      </div>
    );
  }

  return (
    <section className="space-y-4 p-5">
      <div>
        <h2 className="text-lg font-bold">Alternative routes</h2>
        <p className="text-xs text-gray-500 capitalize">{elementName}</p>
      </div>
      {body}
      <button
        type="button"
        onClick={close}
        className="w-full border border-gray-300 rounded py-2 text-sm text-gray-600 hover:bg-gray-50"
      >
        Close
      </button>
    </section>
  );
}

function RecommendationsDetail({ recs, nodeName, close }) {
  return (
    <section className="space-y-4 p-5">
      <div>
        <h2 className="text-lg font-bold">Recommended actions</h2>
        <p className="text-xs text-gray-500 capitalize">{nodeName}</p>
      </div>
      {recs.length ? (
        <div className="space-y-2">
          {recs.map((rec) => (
            <div
              key={`${rec.case_id}-${rec.type}`}
              className="border-l-4 border-amber-400 pl-3 py-1 bg-amber-50/40 rounded-r"
            >
              <div className="flex items-center gap-2 text-sm">
                <span className="font-medium capitalize">{rec.type.replace(/_/g, ' ')}</span>
                {chip(rec.status || 'recommended', 'bg-amber-100 text-amber-800')}
              </div>
              {rec.description && (
                <p className="text-xs text-gray-600 mt-0.5">{rec.description}</p>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-gray-500">No pending recommendations.</p>
      )}
      <p className="text-xs text-gray-400">
        Operator decision — TravelOps never books or cancels automatically.
      </p>
      <button
        type="button"
        onClick={close}
        className="w-full border border-gray-300 rounded py-2 text-sm text-gray-600 hover:bg-gray-50"
      >
        Close
      </button>
    </section>
  );
}

function GpsDetail({ progress, close }) {
  const gps = progress.gps || {};
  return (
    <section className="space-y-4 p-5">
      <div>
        <h2 className="text-lg font-bold">📍 Current location</h2>
        <p className="text-xs text-gray-500">Guide device telemetry</p>
      </div>
      <div className="space-y-2 text-sm">
        <DetailField label="Device" value={gps.device_id || '—'} />
        <DetailField
          label="Position"
          value={
            gps.latitude != null
              ? `${gps.latitude.toFixed(5)}, ${gps.longitude.toFixed(5)}`
              : '—'
          }
        />
        <DetailField
          label="Speed / heading"
          value={`${Math.round(gps.speed_kmh || 0)} km/h · ${Math.round(gps.heading_deg || 0)}°`}
        />
        <DetailField label="Captured" value={formatDateTime(gps.captured_at)} />
        <DetailField
          label="Updated"
          value={`${progress.ageMinutes} min ago${progress.stale ? ' (stale)' : ''}`}
          tone={progress.stale ? 'text-amber-600' : 'text-gray-700'}
        />
      </div>
      {progress.stale && (
        <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded p-2">
          This position is older than 30 minutes — treat it as an approximation, not a live fix.
        </p>
      )}
      <button
        type="button"
        onClick={close}
        className="w-full border border-gray-300 rounded py-2 text-sm text-gray-600 hover:bg-gray-50"
      >
        Close
      </button>
    </section>
  );
}

function DetailSidebar({ selection, nodes, mode, analysis, trip, live, tripId, onClose }) {
  const content = (() => {
    if (!selection) return null;

    if (selection.kind === 'gps') {
      return <GpsDetail progress={live._progress} close={onClose} />;
    }

    if (selection.kind === 'alt') {
      const node = nodes.find((n) => n.id === selection.elementId);
      return (
        <AlternativesDetail
          tripId={tripId}
          elementId={selection.elementId}
          elementName={node?.name || ''}
          close={onClose}
        />
      );
    }

    if (selection.kind === 'rec') {
      const node = nodes.find((n) => n.id === selection.elementId);
      const recs = recommendationsForNode(live?.cases, selection.elementId);
      return <RecommendationsDetail recs={recs} nodeName={node?.name || ''} close={onClose} />;
    }

    const node = nodes.find((n) => n.id === selection.id);
    if (!node) return null;
    return (
      <NodeDetail
        node={node}
        mode={mode}
        analysis={analysis}
        trip={trip}
        live={live}
        close={onClose}
      />
    );
  })();

  if (!content) return null;

  return (
    <>
      <div className="fixed inset-0 bg-black/25 z-40" onClick={onClose} />
      <aside className="fixed right-0 top-0 bottom-0 w-96 max-w-[90vw] bg-white shadow-xl z-50 overflow-y-auto">
        <div className="sticky top-0 flex items-center justify-between bg-white/95 backdrop-blur px-4 py-3 border-b">
          <span className="text-sm font-semibold text-gray-700">Details</span>
          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 rounded hover:bg-gray-100 text-gray-500 font-semibold"
            aria-label="Close details"
          >
            ✕
          </button>
        </div>
        {content}
      </aside>
    </>
  );
}

function ModeToggle({ mode, setMode }) {
  const option = (value, label) => (
    <button
      key={value}
      type="button"
      onClick={() => setMode(value)}
      className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
        mode === value ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'
      }`}
    >
      {label}
    </button>
  );
  return (
    <div className="inline-flex items-center gap-1 rounded-lg border border-gray-300 bg-gray-50 p-0.5">
      {option('normal', 'Normal itinerary')}
      {option('live', 'Live disruption')}
    </div>
  );
}

export default function TripTimeline() {
  const { id } = useParams();
  const [mode, setMode] = useState('normal');
  const [selected, setSelected] = useState(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ['trip', 'timeline', id],
    queryFn: async () => {
      const [trip, analysis, live] = await Promise.all([
        getTrip(id),
        getTripAnalysis(id),
        getTripLiveStatus(id),
      ]);
      return { trip, analysis, live };
    },
  });

  const timeline = useMemo(
    () => (data ? buildTimeline(data.trip, data.analysis, data.live) : null),
    [data]
  );

  const downstream = useMemo(
    () =>
      selected?.kind === 'node' && data
        ? downstreamClosure(data.trip.dependencies, selected.id)
        : new Set(),
    [selected, data]
  );

  if (isLoading) return <div className="p-6">Loading trip timeline…</div>;
  if (error) return <div className="p-6 text-red-500">Failed to load trip timeline</div>;

  const { trip, analysis, live } = data;
  const { nodes, segments, progress } = timeline;
  const liveWithProgress = { ...live, _progress: progress };

  const handleSelectNode = (next) =>
    setSelected((current) => {
      const currentKey = current?.elementId ?? current?.id;
      const nextKey = next.elementId ?? next.id;
      if (currentKey === nextKey) return null;
      return next;
    });

  if (nodes.length === 0) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <Link to={`/trips/${id}`} className="text-sm text-blue-600 hover:underline">
          ← Back to trip
        </Link>
        <div className="bg-white shadow rounded-lg p-8 mt-3 text-center">
          <h1 className="text-xl font-bold">{trip.name}</h1>
          <p className="text-gray-600 mt-2">This trip has no itinerary elements yet.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <div className="p-6 max-w-6xl mx-auto">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <Link to={`/trips/${id}`} className="text-sm text-blue-600 hover:underline">
              ← Back to trip
            </Link>
            <h1 className="text-2xl font-bold mt-1">🗺️ {trip.name}</h1>
            <p className="text-gray-500 text-sm">
              Trip #{trip.id}
              {' · '}
              {chip(trip.status, TRIP_STATUS_STYLES[trip.status] || 'bg-gray-100 text-gray-700')}
              {' · '}
              {chip(analysis.phase, 'bg-purple-100 text-purple-800')}
            </p>
          </div>
          <ModeToggle mode={mode} setMode={setMode} />
        </div>

        {mode === 'live' && analysis.phase !== 'ACTIVE' && (
          <p className="mt-3 text-xs text-gray-500 bg-amber-50 border border-amber-200 rounded p-2">
            Live status is computed from planned data for this trip — disruption feeds only
            arrive once the trip is active.
          </p>
        )}

        <div className="mt-6 bg-white rounded-lg border p-6">
          <div className="flex-1 min-w-0">
            {nodes.map((node, index) => (
              <div key={node.id}>
                {index > 0 && (
                  <Segment
                    segment={segments[index - 1]}
                    progress={progress}
                    mode={mode}
                    onSelectGps={() => setSelected({ kind: 'gps' })}
                  />
                )}
                <NodeRow
                  node={node}
                  mode={mode}
                  selected={selected}
                  dimmed={selected?.kind === 'node' && !downstream.has(node.id)}
                  related={node.id === relatedNodeId(selected)}
                  tripId={trip.id}
                  live={liveWithProgress}
                  analysis={analysis}
                  onSelectNode={handleSelectNode}
                />
              </div>
            ))}
          </div>
        </div>

        {mode === 'live' && progress.present && (
          <p className="mt-3 text-xs text-gray-500">
            {progress.stale
              ? `📍 You-are-here marker is stale (${progress.ageMinutes} min ago).`
              : '📍 You-are-here marker shows the traveller’s last known position.'}
          </p>
        )}
      </div>

      <DetailSidebar
        selection={selected}
        nodes={nodes}
        mode={mode}
        analysis={analysis}
        trip={trip}
        live={liveWithProgress}
        tripId={trip.id}
        onClose={() => setSelected(null)}
      />
    </div>
  );
}

function relatedNodeId(selected) {
  return selected?.elementId ?? selected?.id;
}