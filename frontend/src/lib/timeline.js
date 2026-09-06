import { formatMinutes } from './format';

export const TRANSPORT_TYPES = new Set(['flight', 'train', 'road_transfer', 'ferry']);
export const GPS_STALE_MINUTES = 30;

export const LIVE_STATUS_TONES = {
  valid: 'green',
  at_risk: 'amber',
  disrupted: 'red',
  unknown: 'gray',
};

export function haversineKm(a, b) {
  if (!a || !b || a.latitude == null || b.latitude == null) return null;
  const toRad = (deg) => (deg * Math.PI) / 180;
  const earthKm = 6371;
  const dLat = toRad(b.latitude - a.latitude);
  const dLng = toRad(b.longitude - a.longitude);
  const lat1 = toRad(a.latitude);
  const lat2 = toRad(b.latitude);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * earthKm * Math.asin(Math.sqrt(h));
}

function parseDate(value) {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

function minutesBetween(a, b) {
  const from = parseDate(a);
  const to = parseDate(b);
  if (!from || !to) return null;
  return Math.round((to - from) / 60000);
}

function formatKm(km) {
  if (km === null || km === undefined) return null;
  return km >= 10 ? `${Math.round(km)} km` : `${km} km`;
}

export function downstreamClosure(dependencies, id) {
  const adjacency = new Map();
  for (const dep of dependencies || []) {
    if (!adjacency.has(dep.from_element)) adjacency.set(dep.from_element, new Set());
    adjacency.get(dep.from_element).add(dep.to_element);
  }
  const visited = new Set();
  const stack = [id];
  while (stack.length) {
    const current = stack.pop();
    if (visited.has(current)) continue;
    visited.add(current);
    for (const next of adjacency.get(current) || []) {
      if (!visited.has(next)) stack.push(next);
    }
  }
  visited.delete(id);
  return visited;
}

export function recommendationsForNode(cases, elementId) {
  const recommendations = [];
  for (const item of cases || []) {
    const linked = (item.nodes || []).some((node) => node.element_id === elementId);
    if (!linked) continue;
    for (const action of item.actions || []) {
      if (action.status === 'completed') continue;
      recommendations.push({
        case_id: item.id,
        case_title: item.title,
        ...action,
      });
    }
  }
  return recommendations;
}

export function alternativeEligible(node, connections) {
  if (!TRANSPORT_TYPES.has(node.type)) return false;
  if (!node.startLocation || !node.endLocation) return false;
  if (
    node.live &&
    (node.live.status === 'disrupted' || node.live.status === 'at_risk')
  ) {
    return true;
  }
  return (connections || []).some(
    (connection) =>
      (connection.from_id === node.id || connection.to_id === node.id) &&
      (connection.kind === 'infeasible' || connection.kind === 'tight')
  );
}

function latestTraffic(feeds, elementId) {
  const records = (feeds?.traffic || []).filter(
    (record) => record.element_id === elementId
  );
  return records.reduce((best, record) => {
    const bestAt = best ? parseDate(best.checked_at) : null;
    const recordAt = parseDate(record.checked_at);
    return bestAt === null || (recordAt && recordAt > bestAt) ? record : best;
  }, null);
}

function buildNodes(trip, analysis, live) {
  const metrics = new Map(
    (analysis?.timeline?.elements || []).map((element) => [element.id, element])
  );
  const liveNodes = new Map(
    (live?.nodes || []).map((node) => [node.element_id, node])
  );

  return (trip.itinerary_elements || [])
    .slice()
    .sort((a, b) => a.sequence - b.sequence)
    .map((element) => {
      const metric = metrics.get(element.id);
      const liveNode = liveNodes.get(element.id);
      const traffic = latestTraffic(live?.feeds, element.id);
      const startLocation = element.start_location;
      const endLocation = element.end_location;

      let distanceKm = null;
      if (TRANSPORT_TYPES.has(element.type)) {
        distanceKm =
          traffic?.distance_km ??
          haversineKm(startLocation, endLocation);
      }

      return {
        id: element.id,
        sequence: element.sequence,
        type: element.type,
        name: element.name,
        status: element.status,
        start: startLocation?.name || null,
        end: endLocation?.name || null,
        startLocation,
        endLocation,
        bookings: element.bookings || [],
        plannedStart: element.planned_start,
        plannedEnd: element.planned_end,
        actualStart: element.actual_start,
        actualEnd: element.actual_end,
        effectiveEnd: metric?.effective_end || element.planned_end,
        plannedDurationMinutes: metric?.planned_duration_minutes,
        actualDurationMinutes:
          metric?.actual_duration_minutes ?? (element.actual_duration_minutes ?? null),
        delayMinutes: metric?.delay_minutes ?? 0,
        started: metric?.started ?? !!element.actual_start,
        bookingStatus: metric?.booking_status ?? null,
        distanceKm,
        travelMinutes:
          traffic?.duration_minutes ??
          metric?.actual_duration_minutes ??
          metric?.planned_duration_minutes,
        metric,
        live: liveNode,
      };
    });
}

function buildSegments(nodes) {
  const segments = [];
  for (let index = 0; index < nodes.length - 1; index += 1) {
    const prev = nodes[index];
    const next = nodes[index + 1];
    const travel = TRANSPORT_TYPES.has(next.type);

    const gapMinutes = minutesBetween(prev.effectiveEnd, next.plannedStart);
    const fromDelay = prev.live?.status
      ? prev.delayMinutes
      : 0;

    let risk = 'ok';
    if (gapMinutes !== null && gapMinutes < 0) risk = 'missed';
    else if (fromDelay > 0 && prev.live) risk = 'delay';

    let label;
    if (travel) {
      const time = formatMinutes(next.travelMinutes);
      const distance = formatKm(next.distanceKm);
      label = distance ? `${time} · ${distance}` : time;
    } else if (gapMinutes !== null) {
      label =
        gapMinutes >= 120
          ? `${formatMinutes(gapMinutes)} free time`
          : `${formatMinutes(gapMinutes)} buffer`;
    } else {
      label = '—';
    }

    let labelLive = label;
    if (risk === 'delay') {
      labelLive = `Delay ${formatMinutes(fromDelay)}`;
    } else if (risk === 'missed') {
      labelLive = `Missed by ${formatMinutes(-gapMinutes)}`;
    }

    segments.push({
      index,
      fromId: prev.id,
      toId: next.id,
      travel,
      gapMinutes,
      fromDelay,
      risk,
      label,
      labelLive,
    });
  }
  return segments;
}

function buildProgress(nodes, live, now = Date.now()) {
  const gps = live?.feeds?.gps;
  if (!gps || !gps.itinerary_element_id) {
    return { present: false };
  }
  const index = nodes.findIndex((node) => node.id === gps.itinerary_element_id);
  if (index === -1) {
    return { present: false };
  }
  const reference =
    parseDate(gps.received_at) ?? parseDate(gps.captured_at) ?? new Date(now);
  const ageMinutes = Math.max(0, Math.round((now - reference) / 60000));

  const leg = nodes[index];
  const start = parseDate(leg.actualStart) ?? parseDate(leg.plannedStart);
  const end =
    parseDate(leg.actualEnd) ??
    parseDate(leg.effectiveEnd) ??
    parseDate(leg.plannedEnd);
  let partial = 0.5;
  if (start && end) {
    const span = end - start;
    if (span > 0) {
      partial = Math.max(0, Math.min(1, (now - start) / span));
    }
  }
  const isLast = index === nodes.length - 1;
  const segmentIndex = isLast ? Math.max(0, nodes.length - 2) : index;
  if (isLast) partial = 1;

  return {
    present: true,
    stale: ageMinutes > GPS_STALE_MINUTES,
    ageMinutes,
    segmentIndex,
    partial,
    isLast,
    gps,
  };
}

export function buildTimeline(trip, analysis, live) {
  const nodes = buildNodes(trip, analysis, live);
  return {
    nodes,
    segments: buildSegments(nodes),
    progress: buildProgress(nodes, live),
  };
}