import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getTripAnalysis } from '../api/tripApi';
import {
  formatDateTime,
  formatMinutes,
  elementIcon,
  SEVERITY_STYLES,
  chip,
} from '../lib/format';

const STATUS_STYLES = {
  READY: 'bg-green-100 text-green-800',
  READY_WITH_WARNINGS: 'bg-amber-100 text-amber-800',
  NOT_READY: 'bg-red-100 text-red-800',
  UNKNOWN: 'bg-gray-100 text-gray-700',
};

const CONNECTION_KIND_STYLES = {
  ok: 'bg-green-100 text-green-800',
  tight: 'bg-amber-100 text-amber-800',
  infeasible: 'bg-red-100 text-red-800',
};

function CheckStatusChip({ status }) {
  return chip(status, STATUS_STYLES[status] || 'bg-gray-100 text-gray-700');
}

function WarningList({ warnings }) {
  if (!warnings || warnings.length === 0) {
    return <p className="text-xs text-gray-400">No warnings</p>;
  }
  return (
    <ul className="space-y-1.5 mt-2">
      {warnings.map((warning, index) => (
        <li key={index} className="flex items-start gap-2 text-sm">
          {chip(warning.severity, SEVERITY_STYLES[warning.severity] || 'bg-gray-100 text-gray-700')}
          <span className="text-gray-700">{warning.reason}</span>
        </li>
      ))}
    </ul>
  );
}

function CheckCard({ name, check }) {
  return (
    <div className={`border rounded-lg p-4 bg-white ${check.warnings?.length ? 'border-l-4 border-l-amber-400' : ''}`}>
      <div className="flex items-center justify-between">
        <h3 className="font-semibold capitalize">{name}</h3>
        <CheckStatusChip status={check.status} />
      </div>
      <WarningList warnings={check.warnings} />
    </div>
  );
}

function ElementsPanel({ elements }) {
  return (
    <div className="overflow-x-auto border rounded-lg bg-white">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
          <tr>
            <th className="px-3 py-2 text-left">Seq</th>
            <th className="px-3 py-2 text-left">Element</th>
            <th className="px-3 py-2 text-left">Route</th>
            <th className="px-3 py-2 text-left">Planned</th>
            <th className="px-3 py-2 text-left">Duration</th>
            <th className="px-3 py-2 text-left">Actual</th>
            <th className="px-3 py-2 text-left">Effective end</th>
            <th className="px-3 py-2 text-left">Delay</th>
            <th className="px-3 py-2 text-left">Booking</th>
          </tr>
        </thead>
        <tbody>
          {elements.map((element) => (
            <tr key={element.id} className="border-t">
              <td className="px-3 py-2">{element.sequence}</td>
              <td className="px-3 py-2">
                <span className="mr-1">{elementIcon[element.type] || '📍'}</span>
                <span className="font-medium">{element.name}</span>
              </td>
              <td className="px-3 py-2 text-xs text-gray-500">
                {element.start || '—'} → {element.end || '—'}
              </td>
              <td className="px-3 py-2 text-xs whitespace-nowrap">
                {formatDateTime(element.planned_start)}
                <span className="block text-gray-400">{formatDateTime(element.planned_end)}</span>
              </td>
              <td className="px-3 py-2 text-xs">
                {formatMinutes(element.planned_duration_minutes)}
                {element.actual_duration_minutes !== null && element.actual_duration_minutes !== undefined && (
                  <span className="block text-gray-400">actual {formatMinutes(element.actual_duration_minutes)}</span>
                )}
              </td>
              <td className="px-3 py-2 text-xs whitespace-nowrap">
                {element.actual_start ? (
                  <>
                    {formatDateTime(element.actual_start)}
                    <span className="block text-gray-400">{formatDateTime(element.actual_end)}</span>
                  </>
                ) : (
                  <span className="text-gray-400">—</span>
                )}
              </td>
              <td className="px-3 py-2 text-xs">{formatDateTime(element.effective_end)}</td>
              <td className="px-3 py-2">
                {element.delay_minutes > 0 ? (
                  chip(`+${formatMinutes(element.delay_minutes)}`, 'bg-red-100 text-red-800')
                ) : (
                  <span className="text-xs text-gray-400">0</span>
                )}
              </td>
              <td className="px-3 py-2">
                {element.booking_status ? (
                  chip(element.booking_status, element.booking_status === 'confirmed' ? 'bg-green-100 text-green-800' : 'bg-amber-100 text-amber-800')
                ) : (
                  <span className="text-xs text-gray-400">none</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ConnectionsPanel({ connections }) {
  if (!connections || connections.length === 0) {
    return <p className="text-sm text-gray-500">No dependencies to analyze.</p>;
  }
  return (
    <div className="space-y-2">
      {connections.map((connection) => (
        <div
          key={`${connection.from_id}-${connection.to_id}`}
          className="border rounded-lg p-3 bg-white flex flex-wrap items-center gap-3 text-sm"
        >
          <div className="flex-1 min-w-[220px]">
            <div className="font-medium">
              {connection.from_name || `#${connection.from_id}`}
              <span className="mx-2 text-gray-400">→</span>
              {connection.to_name || `#${connection.to_id}`}
            </div>
            <div className="text-xs text-gray-500 mt-0.5">
              {connection.type} · arr {formatDateTime(connection.from_arrival)} · dep {formatDateTime(connection.to_departure)}
              {connection.delayed && chip('delayed', 'bg-red-100 text-red-800 ml-1')}
            </div>
          </div>
          <div className="text-xs text-gray-600">
            Connection: <span className="font-semibold">{formatMinutes(connection.connection_minutes)}</span>
          </div>
          <div className="text-xs text-gray-600">
            Min buffer: <span className="font-semibold">{formatMinutes(connection.minimum_buffer_minutes)}</span>
          </div>
          <div className="text-xs">
            Free: <span className={`font-semibold ${connection.free_buffer_minutes < 0 ? 'text-red-700' : connection.free_buffer_minutes < 30 ? 'text-amber-700' : 'text-green-700'}`}>
              {formatMinutes(connection.free_buffer_minutes)}
            </span>
          </div>
          {chip(connection.kind, CONNECTION_KIND_STYLES[connection.kind] || 'bg-gray-100 text-gray-700')}
        </div>
      ))}
    </div>
  );
}

function DeadlinesPanel({ deadlines }) {
  if (!deadlines || deadlines.length === 0) {
    return <p className="text-sm text-gray-500">No deadlines to report.</p>;
  }
  return (
    <div className="overflow-x-auto border rounded-lg bg-white">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
          <tr>
            <th className="px-3 py-2 text-left">Kind</th>
            <th className="px-3 py-2 text-left">Element</th>
            <th className="px-3 py-2 text-left">Deadline</th>
            <th className="px-3 py-2 text-left">Expected arrival</th>
            <th className="px-3 py-2 text-left">Result</th>
            <th className="px-3 py-2 text-left">Detail</th>
          </tr>
        </thead>
        <tbody>
          {deadlines.map((deadline, index) => (
            <tr key={index} className="border-t">
              <td className="px-3 py-2 text-xs capitalize">{deadline.kind.replace('_', ' ')}</td>
              <td className="px-3 py-2">
                <span className="font-medium">#{deadline.element_id}</span> {deadline.element_name}
              </td>
              <td className="px-3 py-2 text-xs">{formatDateTime(deadline.deadline)}</td>
              <td className="px-3 py-2 text-xs">
                {deadline.expected ? formatDateTime(deadline.expected) : '—'}
              </td>
              <td className="px-3 py-2">
                {deadline.satisfied ? (
                  chip('✓ satisfied', 'bg-green-100 text-green-800')
                ) : (
                  chip('✗ missed', 'bg-red-100 text-red-800')
                )}
              </td>
              <td className="px-3 py-2 text-xs">
                {deadline.remaining_minutes !== null && deadline.remaining_minutes !== undefined && (
                  <span>remaining {formatMinutes(deadline.remaining_minutes)}</span>
                )}
                {deadline.buffer_minutes !== null && deadline.buffer_minutes !== undefined && (
                  <span>buffer {formatMinutes(deadline.buffer_minutes)}</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function TripAnalysis() {
  const { id } = useParams();

  const { data: analysis, isLoading, error } = useQuery({
    queryKey: ['trip-analysis', id],
    queryFn: () => getTripAnalysis(id),
  });

  if (isLoading) return <div className="p-6">Running trip analysis...</div>;
  if (error) return <div className="p-6 text-red-500">Failed to load analysis</div>;

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <Link to={`/trips/${id}`} className="text-sm text-blue-600 hover:underline">← Back to trip</Link>

      <div className="bg-white shadow rounded-lg p-6 mt-3">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-2xl font-bold">📊 Trip Readiness Analysis</h1>
            <p className="text-gray-500 text-sm mt-1">Trip #{id} · computed live on demand</p>
          </div>
          <div className="flex items-center gap-2">
            {chip(analysis.phase, analysis.phase === 'ACTIVE' ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800')}
            {chip(analysis.status, STATUS_STYLES[analysis.status] || 'bg-gray-100 text-gray-700')}
          </div>
        </div>

        {analysis.summary?.length > 0 && (
          <div className="mt-4 bg-gray-50 border rounded-lg p-4">
            <p className="text-xs text-gray-500 font-semibold uppercase mb-2">Findings</p>
            <ul className="space-y-1">
              {analysis.summary.map((reason, index) => (
                <li key={index} className="text-sm text-gray-700 flex gap-2">
                  <span className="text-amber-500">▸</span>
                  {reason}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="mt-8">
        <h2 className="text-xl font-bold mb-4">🕓 Timeline</h2>
        <div className="space-y-4">
          <div>
            <h3 className="font-semibold text-sm text-gray-600 mb-2">Elements ({analysis.timeline?.elements?.length || 0})</h3>
            <ElementsPanel elements={analysis.timeline?.elements || []} />
          </div>
          <div>
            <h3 className="font-semibold text-sm text-gray-600 mb-2">Connections ({analysis.timeline?.connections?.length || 0})</h3>
            <ConnectionsPanel connections={analysis.timeline?.connections || []} />
          </div>
          <div>
            <h3 className="font-semibold text-sm text-gray-600 mb-2">Deadlines ({analysis.timeline?.deadlines?.length || 0})</h3>
            <DeadlinesPanel deadlines={analysis.timeline?.deadlines || []} />
          </div>
        </div>
      </div>

      <div className="mt-8">
        <h2 className="text-xl font-bold mb-4">✅ Checks</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Object.entries(analysis.checks || {}).map(([name, check]) => (
            <CheckCard key={name} name={name} check={check} />
          ))}
        </div>
      </div>
    </div>
  );
}