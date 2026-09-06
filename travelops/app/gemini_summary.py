"""
On-demand LLM trip summary via Gemini structured outputs.

The summary is computed on demand from the deterministic trip analysis
(``analyze_trip``) and the live operational snapshot
(``live_status_payload``). It never writes to the database and never
recommends silent itinerary or booking changes: the output supports a human
operator.

Error handling mirrors ``gemini_import``: a missing configuration raises
``GeminiConfigurationError`` and an upstream failure raises
``GeminiApiError``.
"""

from django.conf import settings
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from .analysis import analyze_trip
from .gemini_import import GeminiApiError, GeminiConfigurationError
from .live_analysis import live_status_payload

SUMMARY_PROMPT = (
    "You are an operations dashboard summarizer for a travel operator. "
    "Assess the current state of the trip from the JSON context below and "
    "return a concise summary matching the provided schema exactly. Do not "
    "invent facts. If nothing is wrong, say so in the summary. "
    "overall_assessment must be one of READY, READY_WITH_WARNINGS, "
    "NOT_READY, or UNKNOWN. affected_nodes must list every node whose status "
    "is not valid. recommended_actions must list only actions that are "
    "already recommended by the live analysis. risks must list only risks "
    "derived from the readiness checks, deadlines, or live status below."
)


class AffectedNode(BaseModel):
    element_id: int = 0
    element_name: str = ""
    status: str = "unknown"
    classification: str = "unaffected"
    severity: str = "low"
    reason: str = ""


class RecommendedAction(BaseModel):
    case_id: int | None = None
    type: str = ""
    description: str = ""


class RiskItem(BaseModel):
    severity: str = "low"
    description: str = ""


class TripSummaryResult(BaseModel):
    headline: str = "No disruption."
    phase: str = "UPCOMING"
    overall_assessment: str = "READY"
    summary: str = ""
    affected_nodes: list[AffectedNode] = Field(default_factory=list)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)


def _render_analysis_context(analysis):
    timeline = analysis.get("timeline", {})
    lines = [
        "READINESS",
        f"status: {analysis.get('status')}",
        f"phase: {analysis.get('phase')}",
        f"summary: {' | '.join(analysis.get('summary', []))}",
    ]
    for name, check in analysis.get("checks", {}).items():
        lines.append(f"check {name}: {check.get('status')}")
        for warning in check.get("warnings", []):
            lines.append(f"  - [{warning.get('severity')}] {warning.get('reason')}")
    for element in timeline.get("elements", []):
        lines.append(
            "element {id} seq {seq} {type} {name} delay={delay} "
            "status={booking}".format(
                id=element["id"],
                seq=element["sequence"],
                type=element["type"],
                name=element["name"],
                delay=element["delay_minutes"],
                booking=element.get("booking_status"),
            )
        )
    for connection in timeline.get("connections", []):
        lines.append(
            "connection {from_name} -> {to_name} kind={kind} "
            "free_buffer={free} connection_min={conn}".format(
                from_name=connection["from_name"],
                to_name=connection["to_name"],
                kind=connection["kind"],
                free=connection["free_buffer_minutes"],
                conn=connection["connection_minutes"],
            )
        )
    for deadline in timeline.get("deadlines", []):
        lines.append(
            "deadline {kind} {name} satisfied={satisfied}".format(
                kind=deadline["kind"],
                name=deadline.get("element_name", deadline["element_id"]),
                satisfied=deadline["satisfied"],
            )
        )
    return "\n".join(lines)


def _render_live_context(payload):
    lines = [
        "LIVE STATUS",
        f"phase: {payload['phase']}",
        "values filtered to non-valid statuses:",
    ]
    for node in payload["nodes"]:
        if node["status"] == "valid":
            continue
        lines.append(
            "node {id} seq {seq} {type} '{name}' status={status} "
            "class={classification} severity={severity}".format(
                id=node["element_id"],
                seq=node["sequence"],
                type=node["type"],
                name=node["element_name"],
                status=node["status"],
                classification=node["classification"],
                severity=node["severity"],
            )
        )
        lines.append(f"  reason: {node['reason']}")
    if payload["feeds"]:
        lines.append("recent feed signals:")
        for kind, records in payload["feeds"].items():
            if not records:
                continue
            lines.append(f"  - {kind}: {len(records)} snapshot(s)")
    for case in payload["cases"]:
        lines.append(
            "case {id} [{priority}] {title} status={status}".format(
                id=case["id"],
                priority=case["priority"],
                title=case["title"],
                status=case["status"],
            )
        )
        for action in case["actions"]:
            lines.append(
                "  action {type}: {description} (status={status})".format(
                    type=action["type"],
                    description=action["description"],
                    status=action["status"],
                )
            )
    counts = payload["summary"]
    lines.append(
        "counts: disrupted={disrupted} at_risk={at_risk} valid={valid} "
        "unknown={unknown} open_cases={open_cases} "
        "affected_bookings={affected_bookings}".format(**counts)
    )
    return "\n".join(lines)


def summarize_trip(trip, now=None, model=None):
    """Build and return a structured LLM summary for a trip.

    Returns the ``TripSummaryResult`` payload as a dict. Does not write to
    the database. Raises ``GeminiConfigurationError`` when Gemini is not
    configured and ``GeminiApiError`` when the upstream call fails.
    """
    if not settings.GEMINI_API_KEY:
        raise GeminiConfigurationError(
            "GEMINI_API_KEY is not configured in the environment."
        )
    model_name = model or settings.GEMINI_MODEL

    payload = live_status_payload(trip, now)
    analysis = analyze_trip(trip, now=payload["generated_at"])
    context = "\n\n".join([
        _render_analysis_context(analysis),
        _render_live_context(payload),
    ])

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[types.Part.from_text(text=SUMMARY_PROMPT + "\n\n" + context)],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=TripSummaryResult,
            ),
        )
    except Exception as exc:
        raise GeminiApiError(str(exc)) from exc

    if response.parsed is None:
        raise GeminiApiError(
            "Gemini returned no structured output for the trip summary."
        )
    return response.parsed.model_dump()