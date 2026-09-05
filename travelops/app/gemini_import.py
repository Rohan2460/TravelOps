"""
Trip import from documents via Gemini structured outputs.

The extraction schema mirrors the payload accepted by
``TripCreateSerializer`` (documented in API.md under "Trip create") so the
JSON returned by the model can be confirmed unchanged with the project's
create endpoint. A drift test keeps the two schemas in sync.
"""

from django.conf import settings
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

SUPPORTED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "application/pdf",
}

SUPPORTED_EXTENSIONS = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}

MAX_FILE_BYTES = 20 * 1024 * 1024

EXTRACTION_PROMPT = (
    "Extract the trip itinerary from the attached document and return it as "
    "JSON matching the provided schema exactly. Do not add markdown or "
    "comments. The itinerary_elements must be ordered by their appearance and "
    "use 1-based sequence numbers. planned_start, planned_end, start_time and "
    "end_time must be ISO-8601 datetimes (UTC, e.g. '2026-09-02T00:30:00Z'). "
    "start_location and end_location must be inline objects with name, "
    "latitude, longitude and address; use empty strings when a location "
    "cannot be determined from the document. bookings list supplier_name, "
    "booking_reference, status and notes. dependencies reference "
    "itinerary_elements by their zero-based index in the list and express "
    "minimum_buffer as an ISO-8601 duration (e.g. 'PT1H30M')."
)


class GeminiImportError(Exception):
    """Base error for the Gemini trip extraction service."""


class GeminiConfigurationError(GeminiImportError):
    """Gemini is not configured (missing API key / model)."""


class GeminiApiError(GeminiImportError):
    """The upstream Gemini call failed."""


class LocationExtraction(BaseModel):
    name: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    address: str = ""


class BookingExtraction(BaseModel):
    supplier_name: str = ""
    booking_reference: str = ""
    status: str = "confirmed"
    notes: str = ""


class DependencyExtraction(BaseModel):
    from_element_index: int = 0
    to_element_index: int = 0
    type: str = ""
    minimum_buffer: str = ""


class ElementExtraction(BaseModel):
    type: str = ""
    name: str = ""
    sequence: int = 0
    planned_start: str = ""
    planned_end: str = ""
    status: str = "scheduled"
    start_location: LocationExtraction = Field(default_factory=LocationExtraction)
    end_location: LocationExtraction = Field(default_factory=LocationExtraction)
    bookings: list[BookingExtraction] = Field(default_factory=list)


class TripExtraction(BaseModel):
    guide_id: int = 0
    name: str = ""
    start_time: str = ""
    end_time: str = ""
    status: str = "upcoming"
    itinerary_elements: list[ElementExtraction] = Field(default_factory=list)
    dependencies: list[DependencyExtraction] = Field(default_factory=list)


def resolve_mime_type(filename, content_type):
    """Return a supported mime type for the upload, or None.

    Trusts the supplied content type first, then falls back to the file
    extension so mis-declared uploads still get a chance to succeed.
    """
    candidate = content_type
    if candidate not in SUPPORTED_MIME_TYPES:
        candidate = None
        if filename:
            ext = "." + filename.rsplit(".", 1)[-1].lower()
            candidate = SUPPORTED_EXTENSIONS.get(ext)
    if candidate in SUPPORTED_MIME_TYPES:
        return candidate
    return None


def _empty_object(obj):
    return not obj.get("name")

def _drop_empty_bookings(elements):
    return [
        {
            **element,
            "bookings": [
                booking
                for booking in element["bookings"]
                if booking.get("supplier_name")
            ],
        }
        for element in elements
    ]


def _drop_unusable_dependencies(dependencies):
    return [
        dependency
        for dependency in dependencies
        if dependency.get("type") and dependency.get("minimum_buffer")
    ]


def _normalize(data, warnings):
    """Fill defaults and drop rows that can never be created.

    Locations with an empty name become null (the create serializer accepts
    null locations); bookings without a supplier and dependencies without a
    type/duration would always fail validation, so they are removed and
    reported as warnings for the human reviewer.
    """
    guide_id = data.get("guide_id")
    if not guide_id:
        warnings.append("guide_id not found; defaulted to 0.")
    data["guide_id"] = guide_id or 0

    elements = data.get("itinerary_elements", [])
    for element in elements:
        for key in ("start_location", "end_location"):
            if _empty_object(element.get(key, {})):
                element[key] = None

    before = len([
        booking
        for element in elements
        for booking in element["bookings"]
    ])
    elements = _drop_empty_bookings(elements)
    after = len([
        booking
        for element in elements
        for booking in element["bookings"]
    ])
    if after < before:
        warnings.append(f"{before - after} booking(s) without a supplier were dropped.")
    data["itinerary_elements"] = elements

    dependencies = data.get("dependencies", [])
    kept = _drop_unusable_dependencies(dependencies)
    if len(kept) < len(dependencies):
        warnings.append(
            f"{len(dependencies) - len(kept)} dependency(ies) without a type or "
            "duration were dropped."
        )
    data["dependencies"] = kept
    return data


def extract_trip(file_bytes, mime_type, filename="document", model=None):
    """Send the document to Gemini and return normalized trip JSON.

    Returns a tuple of the extracted trip payload (matching the
    ``TripCreateSerializer`` shape) and a list of normalization warnings.
    """
    if not settings.GEMINI_API_KEY:
        raise GeminiConfigurationError(
            "GEMINI_API_KEY is not configured in the environment."
        )
    model_name = model or settings.GEMINI_MODEL

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[
                types.Part.from_text(text=EXTRACTION_PROMPT),
                types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=TripExtraction,
            ),
        )
    except Exception as exc:
        raise GeminiApiError(str(exc)) from exc

    if response.parsed is None:
        raise GeminiApiError(
            "Gemini returned no structured output for the document."
        )

    warnings = []
    data = _normalize(response.parsed.model_dump(), warnings)
    return data, warnings