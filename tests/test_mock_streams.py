from mock_streams import MUMBAI_NODES, MockStreamEngine


def test_mock_snapshot_has_realistic_shape_and_bounds() -> None:
    telemetry, pings = MockStreamEngine(seed=11).snapshot()

    assert len(telemetry) == len(MUMBAI_NODES)
    assert 3 <= len(pings) <= 5
    assert {item.location for item in telemetry} == {str(node["location"]) for node in MUMBAI_NODES}
    assert all(item.rainfall_mm_per_hour >= 0 for item in telemetry)
    assert all(item.river_gauge_height_m > 0 for item in telemetry)
    assert all(item.text for item in pings)


def test_seeded_stream_is_reproducible_for_measurements() -> None:
    first = MockStreamEngine(seed=99).snapshot()
    second = MockStreamEngine(seed=99).snapshot()

    assert [item.model_dump(exclude={"timestamp"}) for item in first[0]] == [item.model_dump(exclude={"timestamp"}) for item in second[0]]
