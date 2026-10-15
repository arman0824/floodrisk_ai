from agents import LANGGRAPH_AVAILABLE, FloodGraphState, build_graph, run_pipeline, social_agent
from mock_streams import create_demo_snapshot
from models import SocialPing
from vision_processor import analyze_frame


def test_explicit_graph_compiles_and_transfers_agent_outputs() -> None:
    telemetry, pings = create_demo_snapshot(seed=42)
    result = run_pipeline(telemetry, pings, vision=analyze_frame(cycle=1))

    assert LANGGRAPH_AVAILABLE
    assert result["telemetry_analysis"].normalized_score in range(101)
    assert result["social_analysis"].locations
    assert 1 <= result["dispatch_output"].risk_score <= 100
    assert result["dispatch_output"].emergency_sms
    assert len(result["telemetry_trace"]) >= 2
    assert len(result["social_trace"]) >= 2
    assert len(result["synthesis_trace"]) >= 2


def test_social_agent_extracts_location_people_and_criticality() -> None:
    pings = [
        SocialPing(ping_id="1", text="CRITICAL: 7 people trapped near Kurla, rescue boats needed."),
        SocialPing(ping_id="2", text="Road blocked in Sion; families need evacuation."),
    ]
    result = social_agent(FloodGraphState(social_pings=pings))
    analysis = result["social_analysis"]

    assert analysis.locations == ["Kurla", "Sion"]
    assert analysis.stranded_citizens == 7
    assert analysis.maximum_severity == "Critical"
    assert analysis.sentiment == "negative"


def test_graph_falls_back_to_local_vision_when_vision_is_missing() -> None:
    telemetry, pings = create_demo_snapshot(seed=4)
    result = run_pipeline(telemetry, pings)

    assert result["vision_result" ] is None
    assert result["dispatch_output"].risk_score >= 1
