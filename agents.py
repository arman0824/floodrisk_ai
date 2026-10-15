"""LangGraph multi-agent pipeline with a deterministic no-key fallback."""

from __future__ import annotations

import re
from typing import Any, TypedDict

from models import (
    AgentTrace,
    DispatchSynthesis,
    ResourcePriority,
    SocialAnalysis,
    SocialPing,
    TelemetryAnalysis,
    TelemetryUpdate,
    VisionResult,
    utc_now,
)
from vision_processor import analyze_frame

try:
    from langgraph.graph import END, START, StateGraph

    LANGGRAPH_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only before dependency install
    END = START = None
    StateGraph = None
    LANGGRAPH_AVAILABLE = False


class FloodGraphState(TypedDict, total=False):
    """Exact contract between every graph node.

    The graph is intentionally sequential: telemetry writes
    ``telemetry_analysis``, social listening writes ``social_analysis``, and
    the synthesizer reads both keys plus ``vision_result``. Keeping these
    names explicit prevents opaque agent-to-agent message passing and makes
    the compiled graph inspectable in a demo.
    """

    telemetry_input: list[TelemetryUpdate]
    social_pings: list[SocialPing]
    vision_result: VisionResult | None
    telemetry_analysis: TelemetryAnalysis
    social_analysis: SocialAnalysis
    dispatch_output: DispatchSynthesis
    telemetry_trace: list[AgentTrace]
    social_trace: list[AgentTrace]
    synthesis_trace: list[AgentTrace]


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> int:
    return int(round(max(low, min(high, value))))


def _telemetry_score(item: TelemetryUpdate) -> int:
    rainfall = _clamp((item.rainfall_mm_per_hour - 20) / 110 * 100)
    gauge = _clamp((item.river_gauge_height_m - 1.5) / 3.0 * 100)
    wind = _clamp((item.wind_speed_kmh - 10) / 50 * 100)
    trend_bonus = 12 if item.gauge_trend == "rising" else (-4 if item.gauge_trend == "falling" else 0)
    return _clamp(rainfall * 0.48 + gauge * 0.38 + wind * 0.14 + trend_bonus)


def telemetry_agent(state: FloodGraphState) -> dict[str, Any]:
    telemetry = state.get("telemetry_input", [])
    node_scores = {item.location: _telemetry_score(item) for item in telemetry}
    ordered = sorted(node_scores.items(), key=lambda pair: pair[1], reverse=True)
    normalized = _clamp(max(node_scores.values(), default=0) * 0.65 + (sum(node_scores.values()) / max(1, len(node_scores))) * 0.35)
    affected = [location for location, score in ordered if score >= 45]
    findings = [
        f"{item.location}: {item.rainfall_mm_per_hour:.1f} mm/h rain, gauge {item.river_gauge_height_m:.2f} m ({item.gauge_trend})."
        for item in sorted(telemetry, key=_telemetry_score, reverse=True)[:3]
    ]
    monitoring = [f"Maintain 5-minute gauge watch at {location}." for location in affected[:3]]
    trace = [
        AgentTrace(
            agent="Telemetry Agent",
            event_type="observation",
            message=f"Parsed {len(telemetry)} weather and river-gauge updates for {telemetry[0].city if telemetry else 'Mumbai'}.",
            payload={"input_count": len(telemetry)},
        ),
        AgentTrace(
            agent="Telemetry Agent",
            event_type="analysis",
            message=f"Telemetry risk contribution is {normalized}/100; {len(affected)} nodes need active monitoring.",
            payload={"normalized_score": normalized, "node_scores": node_scores},
        ),
    ]
    return {
        "telemetry_analysis": TelemetryAnalysis(
            normalized_score=normalized,
            node_scores=node_scores,
            affected_locations=affected,
            findings=findings,
            recommended_monitoring=monitoring,
        ),
        "telemetry_trace": trace,
    }


_LOCATION_NAMES = ("Kurla", "Sion", "Dharavi", "Andheri East", "Bandra West")
_SEVERITY_WORDS: tuple[tuple[str, str], ...] = (
    ("Critical", "critical|trapped|rescue boats|children|elderly|first floor"),
    ("High", "sos|stranded|waist-deep|no power|flooded|rising fast"),
    ("Medium", "blocked|water|evacuation|help"),
)
_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}


def _location_from_text(text: str) -> str:
    for location in _LOCATION_NAMES:
        if location.lower() in text.lower():
            return location
    return "Unmapped sector"


def _people_from_text(text: str) -> int:
    match = re.search(r"\b(\d+)\s+(?:people|persons|citizens|residents|families|commuters)", text.lower())
    if match:
        return int(match.group(1))
    for word, number in _NUMBER_WORDS.items():
        if re.search(rf"\b{word}\s+(?:people|persons|citizens|residents|families)", text.lower()):
            return number
    return 0


def _severity_from_text(text: str) -> str:
    lowered = text.lower()
    for severity, pattern in _SEVERITY_WORDS:
        if re.search(pattern, lowered):
            return severity
    return "Low"


def social_agent(state: FloodGraphState) -> dict[str, Any]:
    pings = state.get("social_pings", [])
    by_location: dict[str, str] = {}
    locations: list[str] = []
    stranded = 0
    findings: list[str] = []
    severity_order = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
    maximum = "Low"
    for ping in pings:
        location = _location_from_text(ping.text)
        severity = _severity_from_text(ping.text)
        by_location[location] = max(by_location.get(location, "Low"), severity, key=lambda value: severity_order[value])
        if location not in locations:
            locations.append(location)
        people = _people_from_text(ping.text)
        stranded += people
        if severity_order[severity] > severity_order[maximum]:
            maximum = severity
        findings.append(f"{location}: {severity} signal; extracted {people} stranded citizens.")
    severity_score = {"Low": 20, "Medium": 48, "High": 72, "Critical": 94}[maximum]
    volume_score = min(22, len(pings) * 5)
    people_score = min(20, stranded * 2)
    normalized = _clamp(severity_score * 0.58 + volume_score + people_score)
    negative_terms = ("sos", "stranded", "trapped", "flood", "rescue", "blocked", "no power")
    negative_count = sum(any(term in ping.text.lower() for term in negative_terms) for ping in pings)
    sentiment = "negative" if negative_count >= max(1, len(pings) // 2) else ("mixed" if pings else "neutral")
    prior = state.get("telemetry_analysis")
    trace = [
        AgentTrace(
            agent="Social Listening Agent",
            event_type="observation",
            message=f"Filtered {len(pings)} simulated SOS pings and extracted {len(locations)} locations.",
            payload={"ping_count": len(pings), "locations": locations},
        ),
        AgentTrace(
            agent="Social Listening Agent",
            event_type="handoff",
            message=f"Handoff to synthesizer: social score {normalized}/100; telemetry context available at {prior.normalized_score if prior else 0}/100.",
            payload={"stranded_citizens": stranded, "maximum_severity": maximum},
        ),
    ]
    return {
        "social_analysis": SocialAnalysis(
            normalized_score=normalized,
            locations=locations,
            stranded_citizens=stranded,
            maximum_severity=maximum,
            sentiment=sentiment,
            severity_by_location=by_location,
            findings=findings,
        ),
        "social_trace": trace,
    }


def _optional_llm_headline(dispatch: DispatchSynthesis) -> str:
    """Use OpenAI only when configured; otherwise retain local copy."""

    try:
        from config import get_settings

        settings = get_settings()
        if not settings.llm_enabled:
            return dispatch.headline
        from langchain_openai import ChatOpenAI

        model = ChatOpenAI(model=settings.openai_model, temperature=0, api_key=settings.openai_api_key)
        response = model.invoke(
            "Rewrite this flood operations headline in under 100 characters. Return only the headline.\n"
            + dispatch.headline
        )
        content = getattr(response, "content", "")
        return str(content).strip()[:100] or dispatch.headline
    except Exception:
        return dispatch.headline


def dispatch_synthesizer(state: FloodGraphState) -> dict[str, Any]:
    telemetry = state.get("telemetry_analysis") or TelemetryAnalysis(normalized_score=0)
    social = state.get("social_analysis") or SocialAnalysis(
        normalized_score=0,
        maximum_severity="Low",
        sentiment="neutral",
    )
    vision = state.get("vision_result") or analyze_frame(cycle=0)
    vision_score = _clamp(vision.flooding_depth_cm / 180 * 100)
    score = _clamp(telemetry.normalized_score * 0.50 + social.normalized_score * 0.30 + vision_score * 0.20, 1, 100)
    level = "Critical" if score >= 82 else ("High" if score >= 62 else ("Medium" if score >= 36 else "Low"))
    candidates = set(telemetry.affected_locations)
    candidates.update(location for location, severity in social.severity_by_location.items() if severity in {"High", "Critical"})
    if not candidates:
        candidates.update(telemetry.node_scores.keys())
    evacuation = sorted(candidates, key=lambda location: telemetry.node_scores.get(location, 0), reverse=True)[:3]
    affected = sorted(set(evacuation + social.locations))[:5]
    resources = [
        ResourcePriority(rank=1, resource="Swift-water rescue boats", destination=evacuation[0] if evacuation else "Kurla", reason="Highest combined gauge and distress signal", eta_minutes=12),
        ResourcePriority(rank=2, resource="Medical response unit", destination=evacuation[1] if len(evacuation) > 1 else "Sion", reason="Prepare for stranded residents and exposure injuries", eta_minutes=18),
        ResourcePriority(rank=3, resource="Portable warning sirens", destination=evacuation[2] if len(evacuation) > 2 else "Dharavi", reason="Extend evacuation reach during power disruption", eta_minutes=24),
    ]
    headline = f"{level.upper()} FLOOD WATCH: {', '.join(evacuation[:2]) or 'Mumbai low-lying sectors'}"
    actions = [
        f"Stage rescue boats near {evacuation[0] if evacuation else 'Kurla'}.",
        "Verify shelters and keep arterial roads clear for emergency vehicles.",
        "Recheck river gauges and social signals on the next five-minute cycle.",
    ]
    sms = f"MUMBAI FLOOD ALERT ({level}): Avoid {', '.join(affected[:3]) or 'low-lying roads'}. Move to higher ground and follow emergency crew instructions. Call 112 for urgent rescue."
    dispatch = DispatchSynthesis(
        risk_score=score,
        risk_level=level,
        headline=headline,
        rationale=f"Telemetry {telemetry.normalized_score}/100 + social distress {social.normalized_score}/100 + CCTV depth {vision.flooding_depth_cm} cm.",
        evacuation_zones=evacuation,
        affected_sectors=affected,
        resource_priority=resources,
        emergency_sms=sms,
        recommended_actions=actions,
        score_breakdown={"telemetry": telemetry.normalized_score, "social": social.normalized_score, "vision": vision_score},
    )
    dispatch.headline = _optional_llm_headline(dispatch)
    trace = [
        AgentTrace(
            agent="Dispatch Synthesizer",
            event_type="handoff",
            message="Received validated telemetry, social-listening, and vision outputs.",
            payload={"telemetry_score": telemetry.normalized_score, "social_score": social.normalized_score, "vision_depth_cm": vision.flooding_depth_cm},
        ),
        AgentTrace(
            agent="Dispatch Synthesizer",
            event_type="decision",
            message=f"Computed absolute risk score {score}/100 ({level}) and prioritized {len(resources)} response resources.",
            payload={"risk_score": score, "evacuation_zones": evacuation, "sms_ready": True},
        ),
    ]
    return {"dispatch_output": dispatch, "synthesis_trace": trace}


class _FallbackCompiledGraph:
    """Small compatibility shim if dependencies are not installed yet."""

    def invoke(self, state: FloodGraphState) -> dict[str, Any]:
        result: dict[str, Any] = dict(state)
        result.update(telemetry_agent(result))
        result.update(social_agent(result))
        result.update(dispatch_synthesizer(result))
        return result


def build_graph() -> Any:
    """Compile the explicit START -> telemetry -> social -> synth graph."""

    if not LANGGRAPH_AVAILABLE:
        return _FallbackCompiledGraph()
    workflow = StateGraph(FloodGraphState)
    workflow.add_node("telemetry_agent", telemetry_agent)
    workflow.add_node("social_agent", social_agent)
    workflow.add_node("dispatch_synthesizer", dispatch_synthesizer)
    workflow.add_edge(START, "telemetry_agent")
    workflow.add_edge("telemetry_agent", "social_agent")
    workflow.add_edge("social_agent", "dispatch_synthesizer")
    workflow.add_edge("dispatch_synthesizer", END)
    return workflow.compile()


def run_pipeline(
    telemetry: list[TelemetryUpdate],
    social_pings: list[SocialPing],
    vision: VisionResult | None = None,
    graph: Any | None = None,
) -> dict[str, Any]:
    compiled = graph or build_graph()
    state: FloodGraphState = {
        "telemetry_input": telemetry,
        "social_pings": social_pings,
        "vision_result": vision,
    }
    return dict(compiled.invoke(state))


def trace_for_state(state: dict[str, Any]) -> list[AgentTrace]:
    return [
        *state.get("telemetry_trace", []),
        *state.get("social_trace", []),
        *state.get("synthesis_trace", []),
    ]
