import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { extractTrip, confirmTrip } from '../api/tripApi';

const ELEMENT_TYPES = ['flight', 'train', 'road_transfer', 'ferry', 'hotel', 'activity'];
const ELEMENT_STATUSES = ['valid', 'scheduled', 'at_risk', 'disrupted', 'completed'];
const DEPENDENCY_TYPES = ['transfer', 'arrival', 'departure', 'day'];
const ACCEPTED_TYPES = '.png,.jpg,.jpeg,.webp,.pdf';

const inputClass = 'w-full border p-2 rounded text-sm';
const labelClass = 'block text-sm font-medium mb-1';

const emptyBooking = () => ({
  supplier_name: '',
  booking_reference: '',
  status: 'confirmed',
  notes: '',
});

const emptyElement = () => ({
  type: 'flight',
  name: '',
  planned_start: '',
  planned_end: '',
  status: 'valid',
  start_location: { name: '', latitude: '', longitude: '', address: '' },
  end_location: { name: '', latitude: '', longitude: '', address: '' },
  bookings: [],
});

const emptyDependency = () => ({
  from_index: 0,
  to_index: 1,
  type: 'transfer',
  buffer_hours: 0,
  buffer_minutes: 30,
});

function toDatetimeLocal(value) {
  if (!value) return '';
  const sanitized = `${value}`.slice(0, 16);
  return /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(sanitized) ? sanitized : '';
}

function durationToBuffer(minimumBuffer) {
  const match = /^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$/.exec(minimumBuffer || '');
  if (!match) return { buffer_hours: 0, buffer_minutes: 30 };
  const hours = Number(match[1] || 0);
  const minutes = Number(match[2] || 0) + Math.floor(Number(match[3] || 0) / 60);
  return { buffer_hours: hours, buffer_minutes: minutes };
}

function bufferToDuration(buffer_hours, buffer_minutes) {
  return `PT${buffer_hours}H${buffer_minutes}M`;
}

function extractedToForm(extracted) {
  const formData = {
    guide_id: extracted.guide_id ?? '',
    name: extracted.name || '',
    start_time: toDatetimeLocal(extracted.start_time),
    end_time: toDatetimeLocal(extracted.end_time),
    status: extracted.status || 'upcoming',
  };

  const elements = (extracted.itinerary_elements || []).map((element) => ({
    type: element.type || 'flight',
    name: element.name || '',
    planned_start: toDatetimeLocal(element.planned_start),
    planned_end: toDatetimeLocal(element.planned_end),
    status: element.status || 'valid',
    start_location: element.start_location
      ? { ...{ name: '', latitude: '', longitude: '', address: '' }, ...element.start_location }
      : { name: '', latitude: '', longitude: '', address: '' },
    end_location: element.end_location
      ? { ...{ name: '', latitude: '', longitude: '', address: '' }, ...element.end_location }
      : { name: '', latitude: '', longitude: '', address: '' },
    bookings: (element.bookings || []).map((booking) => ({
      supplier_name: booking.supplier_name || '',
      booking_reference: booking.booking_reference || '',
      status: booking.status || 'confirmed',
      notes: booking.notes || '',
    })),
  }));

  const dependencies = (extracted.dependencies || []).map((dep) => ({
    from_index: Number(dep.from_element_index) || 0,
    to_index: Number(dep.to_element_index) || 0,
    type: dep.type || 'transfer',
    ...durationToBuffer(dep.minimum_buffer),
  }));

  return { formData, elements, dependencies };
}

function normalizeLocation(loc) {
  if (!loc || typeof loc !== 'object') return null;
  const name = loc.name?.trim();
  if (!name) return null;
  const latitude = loc.latitude === '' || loc.latitude === null ? null : Number(loc.latitude);
  const longitude = loc.longitude === '' || loc.longitude === null ? null : Number(loc.longitude);
  return {
    name,
    latitude,
    longitude,
    address: (loc.address || '').trim(),
  };
}

function serializeElement(element, index) {
  return {
    type: element.type,
    name: element.name.trim(),
    sequence: index + 1,
    planned_start: element.planned_start,
    planned_end: element.planned_end,
    status: element.status,
    start_location: normalizeLocation(element.start_location),
    end_location: normalizeLocation(element.end_location),
    bookings: (element.bookings || []).filter((b) => b.supplier_name?.trim()).map((b) => ({
      supplier_name: b.supplier_name.trim(),
      booking_reference: (b.booking_reference || '').trim(),
      status: b.status,
      notes: (b.notes || '').trim(),
    })),
  };
}

function serializeDependency(dep) {
  return {
    from_element_index: Number(dep.from_index),
    to_element_index: Number(dep.to_index),
    type: dep.type,
    minimum_buffer: bufferToDuration(Number(dep.buffer_hours) || 0, Number(dep.buffer_minutes) || 0),
  };
}

function LocationFields({ value, onChange, prefix }) {
  const update = (field, fieldValue) => {
    onChange({ ...value, [field]: fieldValue });
  };
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
      <input
        className={inputClass}
        placeholder={`${prefix} location name`}
        value={value.name || ''}
        onChange={(e) => update('name', e.target.value)}
      />
      <input
        className={inputClass}
        type="number"
        step="any"
        placeholder="latitude"
        value={value.latitude ?? ''}
        onChange={(e) => update('latitude', e.target.value)}
      />
      <input
        className={inputClass}
        type="number"
        step="any"
        placeholder="longitude"
        value={value.longitude ?? ''}
        onChange={(e) => update('longitude', e.target.value)}
      />
      <input
        className={inputClass}
        placeholder="address"
        value={value.address || ''}
        onChange={(e) => update('address', e.target.value)}
      />
    </div>
  );
}

export default function TripImport() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [file, setFile] = useState(null);
  const [model, setModel] = useState('');
  const [result, setResult] = useState(null);
  const [formData, setFormData] = useState(null);
  const [elements, setElements] = useState([]);
  const [dependencies, setDependencies] = useState([]);
  const [showPreview, setShowPreview] = useState(false);

  const extractMutation = useMutation({
    mutationFn: extractTrip,
    onSuccess: (data) => {
      setResult(data);
      const form = extractedToForm(data.extracted);
      setFormData(form.formData);
      setElements(form.elements);
      setDependencies(form.dependencies);
    },
  });

  const confirmMutation = useMutation({
    mutationFn: confirmTrip,
    onSuccess: (data) => {
      queryClient.invalidateQueries(['trips']);
      const id = data?.id;
      if (id) navigate(`/trips/${id}`);
    },
  });

  const payload = formData
    ? {
        ...formData,
        guide_id: Number(formData.guide_id),
        itinerary_elements: elements.map(serializeElement),
        dependencies: dependencies.map(serializeDependency),
      }
    : null;

  const handleExtract = (e) => {
    e.preventDefault();
    if (!file) return;
    extractMutation.mutate({ file, model: model.trim() || undefined });
  };

  const handleConfirm = (e) => {
    e.preventDefault();
    if (!payload) return;
    confirmMutation.mutate(payload);
  };

  const updateElement = (index, patch) => {
    setElements((prev) => prev.map((el, i) => (i === index ? { ...el, ...patch } : el)));
  };

  const updateBooking = (elementIndex, bookingIndex, patch) => {
    setElements((prev) => prev.map((el, i) => {
      if (i !== elementIndex) return el;
      const bookings = el.bookings.map((b, bi) => (bi === bookingIndex ? { ...b, ...patch } : b));
      return { ...el, bookings };
    }));
  };

  const updateDependency = (index, field, value) => {
    setDependencies((prev) => prev.map((dep, i) => (i === index ? { ...dep, [field]: value } : dep)));
  };

  const removeElement = (index) => {
    setElements((prev) => prev.filter((_, i) => i !== index));
    setDependencies((prev) => prev.map((d) => ({
      ...d,
      from_index: d.from_index > index ? d.from_index - 1 : d.from_index,
      to_index: d.to_index > index ? d.to_index - 1 : d.to_index,
    })));
  };

  const confirmError = confirmMutation.error?.response?.data;
  const extractError = extractMutation.error;
  const extractErrorMessage = extractError?.response?.data?.detail
    || (extractError?.response?.data
        ? JSON.stringify(extractError.response.data)
        : (extractError?.message || 'Unknown error'));

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h2 className="text-2xl font-bold mb-6">📥 Import Trip from Document</h2>

      <div className="bg-white shadow rounded-lg p-6 space-y-4">
        <h3 className="font-bold">1. Upload an itinerary document</h3>
        <p className="text-xs text-gray-500">
          PNG, JPEG, WEBP or PDF (max 20 MB). The document is sent to Gemini and never stored.
        </p>
        <form onSubmit={handleExtract} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>File</label>
              <input
                type="file"
                accept={ACCEPTED_TYPES}
                required
                className={inputClass}
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
            </div>
            <div>
              <label className={labelClass}>Model (optional)</label>
              <input
                type="text"
                className={inputClass}
                placeholder="e.g. gemini-3.5-flash-lite"
                value={model}
                onChange={(e) => setModel(e.target.value)}
              />
            </div>
          </div>
          <button
            type="submit"
            disabled={!file || extractMutation.isPending}
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {extractMutation.isPending ? 'Extracting...' : '🚀 Extract Trip'}
          </button>
        </form>
        {extractMutation.isError && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded p-3 text-sm">
            <p className="font-semibold">Extraction failed</p>
            <pre className="mt-1 whitespace-pre-wrap text-xs">{extractErrorMessage}</pre>
          </div>
        )}
      </div>

      {result && (
        <div className="mt-8 space-y-6">
          <div className="bg-white shadow rounded-lg p-6 space-y-3">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <h3 className="font-bold">2. Review the extracted itinerary</h3>
              {result.valid ? (
                <span className="px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800">Valid</span>
              ) : (
                <span className="px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-800">Needs review</span>
              )}
            </div>
            <p className="text-xs text-gray-500">
              Model: {result.model} · {result.source_file?.name} ({result.source_file?.mime_type})
            </p>
            {result.warnings?.map((warning, i) => (
              <p key={`w-${i}`} className="text-sm text-amber-700 bg-amber-50 rounded p-2">
                ⚠️ {warning}
              </p>
            ))}
            {!result.valid && result.errors && (
              <div className="text-sm text-red-700 bg-red-50 rounded p-3">
                <p className="font-semibold mb-1">Fix these fields before saving:</p>
                <pre className="whitespace-pre-wrap text-xs">{JSON.stringify(result.errors, null, 2)}</pre>
              </div>
            )}
          </div>

          {formData && (
            <div className="bg-white shadow rounded-lg p-6 space-y-6">
              <h3 className="font-bold">Trip details</h3>
              <div>
                <label className={labelClass}>Trip Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                  className={inputClass}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className={labelClass}>Guide ID</label>
                  <input
                    type="number"
                    value={formData.guide_id}
                    onChange={(e) => setFormData({ ...formData, guide_id: e.target.value })}
                    required
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className={labelClass}>Status</label>
                  <select
                    value={formData.status}
                    onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                    className={inputClass}
                  >
                    <option value="upcoming">Upcoming</option>
                    <option value="active">Active</option>
                    <option value="completed">Completed</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className={labelClass}>Start Time</label>
                  <input
                    type="datetime-local"
                    value={formData.start_time}
                    onChange={(e) => setFormData({ ...formData, start_time: e.target.value })}
                    required
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className={labelClass}>End Time</label>
                  <input
                    type="datetime-local"
                    value={formData.end_time}
                    onChange={(e) => setFormData({ ...formData, end_time: e.target.value })}
                    required
                    className={inputClass}
                  />
                </div>
              </div>
            </div>
          )}

          {formData && (
            <div className="bg-white shadow rounded-lg p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-bold">🗺️ Itinerary Elements</h3>
                <button
                  type="button"
                  onClick={() => setElements((prev) => [...prev, emptyElement()])}
                  className="bg-blue-600 text-white px-3 py-1 rounded text-sm hover:bg-blue-700"
                >
                  + Add Element
                </button>
              </div>

              {elements.map((element, index) => (
                <div key={index} className="border rounded-lg p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sm">Element #{index + 1}</span>
                    {elements.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeElement(index)}
                        className="text-red-600 text-sm hover:underline"
                      >
                        Remove
                      </button>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className={labelClass}>Type</label>
                      <select
                        className={inputClass}
                        value={element.type}
                        onChange={(e) => updateElement(index, { type: e.target.value })}
                      >
                        {ELEMENT_TYPES.map((type) => (
                          <option key={type} value={type}>{type.replace('_', ' ')}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className={labelClass}>Name</label>
                      <input
                        className={inputClass}
                        value={element.name}
                        onChange={(e) => updateElement(index, { name: e.target.value })}
                        placeholder="e.g. Flight AI-1049"
                        required
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className={labelClass}>Planned Start</label>
                      <input
                        type="datetime-local"
                        className={inputClass}
                        value={element.planned_start}
                        onChange={(e) => updateElement(index, { planned_start: e.target.value })}
                        required
                      />
                    </div>
                    <div>
                      <label className={labelClass}>Planned End</label>
                      <input
                        type="datetime-local"
                        className={inputClass}
                        value={element.planned_end}
                        onChange={(e) => updateElement(index, { planned_end: e.target.value })}
                        required
                      />
                    </div>
                  </div>

                  <div>
                    <label className={labelClass}>Status</label>
                    <select
                      className={inputClass}
                      value={element.status}
                      onChange={(e) => updateElement(index, { status: e.target.value })}
                    >
                      {ELEMENT_STATUSES.map((status) => (
                        <option key={status} value={status}>{status.replace('_', ' ')}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className={labelClass}>Start Location</label>
                    <LocationFields
                      value={element.start_location}
                      onChange={(loc) => updateElement(index, { start_location: loc })}
                      prefix="From"
                    />
                  </div>
                  <div>
                    <label className={labelClass}>End Location</label>
                    <LocationFields
                      value={element.end_location}
                      onChange={(loc) => updateElement(index, { end_location: loc })}
                      prefix="To"
                    />
                  </div>

                  <div>
                    <div className="flex items-center justify-between">
                      <label className={`${labelClass} mb-2`}>Bookings</label>
                      <button
                        type="button"
                        onClick={() => updateElement(index, {
                          bookings: [...element.bookings, emptyBooking()],
                        })}
                        className="text-blue-600 text-sm hover:underline"
                      >
                        + Add Booking
                      </button>
                    </div>
                    {element.bookings.map((booking, bookingIndex) => (
                      <div key={bookingIndex} className="bg-gray-50 border rounded p-3 mb-2">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-medium text-gray-600">
                            Booking #{bookingIndex + 1}
                          </span>
                          <button
                            type="button"
                            onClick={() => updateElement(index, {
                              bookings: element.bookings.filter((_, b) => b !== bookingIndex),
                            })}
                            className="text-red-600 text-xs hover:underline"
                          >
                            Remove
                          </button>
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                          <input
                            className={inputClass}
                            placeholder="Supplier name"
                            value={booking.supplier_name}
                            onChange={(e) => updateBooking(index, bookingIndex, { supplier_name: e.target.value })}
                          />
                          <input
                            className={inputClass}
                            placeholder="Booking reference"
                            value={booking.booking_reference}
                            onChange={(e) => updateBooking(index, bookingIndex, { booking_reference: e.target.value })}
                          />
                          <select
                            className={inputClass}
                            value={booking.status}
                            onChange={(e) => updateBooking(index, bookingIndex, { status: e.target.value })}
                          >
                            <option value="confirmed">Confirmed</option>
                            <option value="pending">Pending</option>
                          </select>
                          <input
                            className={inputClass}
                            placeholder="Notes"
                            value={booking.notes}
                            onChange={(e) => updateBooking(index, bookingIndex, { notes: e.target.value })}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {formData && (
            <div className="bg-white shadow rounded-lg p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-bold">🔗 Dependencies</h3>
                <button
                  type="button"
                  onClick={() => {
                    if (elements.length >= 2) {
                      setDependencies((prev) => [...prev, emptyDependency()]);
                    }
                  }}
                  className="bg-blue-600 text-white px-3 py-1 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
                  disabled={elements.length < 2}
                >
                  + Add Dependency
                </button>
              </div>
              <p className="text-xs text-gray-500">
                Dependencies reference itinerary elements by their index (element #1 = index 0).
              </p>
              {dependencies.length === 0 && (
                <p className="text-sm text-gray-400">No dependencies.</p>
              )}
              {dependencies.map((dep, index) => (
                <div key={index} className="border rounded-lg p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sm">Dependency #{index + 1}</span>
                    <button
                      type="button"
                      onClick={() => setDependencies((prev) => prev.filter((_, i) => i !== index))}
                      className="text-red-600 text-sm hover:underline"
                    >
                      Remove
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className={labelClass}>From element</label>
                      <select
                        className={inputClass}
                        value={dep.from_index}
                        onChange={(e) => updateDependency(index, 'from_index', Number(e.target.value))}
                      >
                        {elements.map((_, i) => (
                          <option key={i} value={i}>Element #{i + 1}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className={labelClass}>To element</label>
                      <select
                        className={inputClass}
                        value={dep.to_index}
                        onChange={(e) => updateDependency(index, 'to_index', Number(e.target.value))}
                      >
                        {elements.map((_, i) => (
                          <option key={i} value={i}>Element #{i + 1}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <div>
                      <label className={labelClass}>Type</label>
                      <select
                        className={inputClass}
                        value={dep.type}
                        onChange={(e) => updateDependency(index, 'type', e.target.value)}
                      >
                        {DEPENDENCY_TYPES.map((type) => (
                          <option key={type} value={type}>{type}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className={labelClass}>Buffer hours</label>
                      <input
                        type="number"
                        min="0"
                        className={inputClass}
                        value={dep.buffer_hours}
                        onChange={(e) => updateDependency(index, 'buffer_hours', Number(e.target.value))}
                      />
                    </div>
                    <div>
                      <label className={labelClass}>Buffer minutes</label>
                      <input
                        type="number"
                        min="0"
                        className={inputClass}
                        value={dep.buffer_minutes}
                        onChange={(e) => updateDependency(index, 'buffer_minutes', Number(e.target.value))}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {formData && (
            <div className="bg-white shadow rounded-lg p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-bold">3. Save the trip</h3>
                <button
                  type="button"
                  onClick={() => setShowPreview((prev) => !prev)}
                  className="text-blue-600 text-sm hover:underline"
                >
                  {showPreview ? 'Hide JSON preview' : 'Preview JSON'}
                </button>
              </div>
              {showPreview && (
                <pre className="bg-gray-900 text-green-300 text-xs rounded p-4 overflow-x-auto whitespace-pre-wrap">
                  {JSON.stringify(payload, null, 2)}
                </pre>
              )}
              {confirmError && (
                <div className="bg-red-50 border border-red-200 text-red-700 rounded p-3 text-sm">
                  <p className="font-semibold mb-1">Could not create the trip</p>
                  <pre className="whitespace-pre-wrap text-xs">{JSON.stringify(confirmError)}</pre>
                </div>
              )}
              <button
                type="button"
                disabled={confirmMutation.isPending}
                onClick={handleConfirm}
                className="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700 disabled:opacity-50"
              >
                {confirmMutation.isPending ? 'Creating...' : '🚀 Create Trip'}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}