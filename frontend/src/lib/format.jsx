export function formatDateTime(value) {
  if (!value) return '—';
  return new Date(value).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatMinutes(minutes) {
  if (minutes === null || minutes === undefined) return '—';
  const abs = Math.abs(minutes);
  const h = Math.floor(abs / 60);
  const m = abs % 60;
  const sign = minutes < 0 ? '-' : '';
  if (h === 0) return `${sign}${m}m`;
  if (m === 0) return `${sign}${h}h`;
  return `${sign}${h}h ${m}m`;
}

export function parseDuration(value) {
  if (!value) return null;
  if (typeof value !== 'string') return null;
  const iso = value.match(/^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$/);
  if (iso) {
    const hours = Number(iso[1] || 0);
    const minutes = Number(iso[2] || 0);
    const seconds = Number(iso[3] || 0);
    return hours * 60 + minutes + Math.round(seconds / 60);
  }
  const parts = value.split(':').map(Number);
  if (parts.length === 3 && parts.every((n) => !Number.isNaN(n))) {
    return parts[0] * 60 + parts[1] + Math.round(parts[2] / 60);
  }
  const m = value.match(/(\d+)\s*(?:mins?|minutes?)/i);
  if (m) return Number(m[1]);
  const mc = value.match(/(\d+)h(?:\s*(\d+)m)?/i);
  if (mc) return Number(mc[1]) * 60 + Number(mc[2] || 0);
  return null;
}

export function formatDuration(value) {
  const minutes = parseDuration(value);
  return minutes === null ? '—' : formatMinutes(minutes);
}

export const elementIcon = {
  flight: '✈️',
  train: '🚆',
  road_transfer: '🚗',
  ferry: '⛴️',
  hotel: '🏨',
  activity: '🏖️',
};

export const SEVERITY_STYLES = {
  critical: 'bg-red-100 text-red-800',
  high: 'bg-orange-100 text-orange-800',
  medium: 'bg-amber-100 text-amber-800',
  low: 'bg-gray-100 text-gray-700',
};

export const ELEMENT_STATUS_STYLES = {
  valid: 'bg-green-100 text-green-800',
  at_risk: 'bg-amber-100 text-amber-800',
  disrupted: 'bg-red-100 text-red-800',
  completed: 'bg-gray-200 text-gray-700',
};

export function chip(text, className) {
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${className}`}>
      {text}
    </span>
  );
}