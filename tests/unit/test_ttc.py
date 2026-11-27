import pytest

from safety_platform.sim.metrics import SafetyMetrics, VehicleState, compute_ttc


def state(x, y, vx, vy, heading=0.0):
    return VehicleState((x, y), (vx, vy), heading, 4.5, 1.8)


def test_ttc_closing_and_diverging():
    ego = state(0, 0, 12, 0)
    assert compute_ttc(ego, state(25, 0, 8, 0)) == pytest.approx(5.125)
    assert compute_ttc(ego, state(25, 0, 14, 0)) == 10
    assert compute_ttc(ego, state(80, 0, 8, 0)) == 10
    assert compute_ttc(ego, state(25, 4, 8, 0)) == 10


def test_ttc_rotated_boxes_and_actual_collision():
    ego = state(0, 0, 0, 0)
    crossing = state(0, 10, 0, -2, heading=1.5707963267948966)
    assert 0 < compute_ttc(ego, crossing) < 10
    metrics = SafetyMetrics()
    metrics.observe(ego, [state(30, 0, 0, 0)], collision=False)
    metrics.observe(ego, [state(0, 0, 0, 0)], collision=True)
    assert metrics.min_ttc == 0


def test_empty_traffic_preserves_running_ttc():
    ego = state(0, 0, 12, 0)
    metrics = SafetyMetrics()
    metrics.observe(ego, [], collision=False)
    assert metrics.min_ttc == 10
    metrics.observe(ego, [state(25, 0, 8, 0)], collision=False)
    metrics.observe(ego, [], collision=False)
    assert metrics.min_ttc == pytest.approx(5.125)
