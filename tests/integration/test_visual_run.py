import json

import pytest

from safety_platform.domain.registry import validate_spec
from safety_platform.sim.builder import build_native
from safety_platform.sim.frames import LatestFrameSink
from safety_platform.sim.policy import PolicyConfig
from safety_platform.sim.runner import run_bundle
from tests.factories import spec_data


@pytest.mark.parametrize("template_id", ["cut_in", "front_brake", "lane_change"])
def test_visual_run_matches_headless_metrics(tmp_path, template_id):
    bundle = build_native(validate_spec(spec_data(template_id)), tmp_path / "bundle")
    plain = run_bundle(bundle.directory, PolicyConfig(), seed=42)
    sink = LatestFrameSink(tmp_path / "latest.jpg")
    visual = run_bundle(bundle.directory, PolicyConfig(), seed=42, frame_sink=sink, playback_rate=1000)
    assert visual.status == plain.status
    assert visual.event_occurred and visual.valid
    assert visual.steps == plain.steps
    assert visual.min_ttc == pytest.approx(plain.min_ttc, abs=1e-6)
    assert (visual.collision, visual.out_of_road, visual.completed) == (
        plain.collision, plain.out_of_road, plain.completed
    )
    assert json.loads(visual.trajectory_path.read_text()) == json.loads(plain.trajectory_path.read_text())
    assert 30 <= visual.frame_count <= 100
    assert sink.path.read_bytes().startswith(b"\xff\xd8")
    assert sink.last_sim_time_s > 0
    assert visual.render_mean_ms > 0


def test_pacing_handles_deadline_crossing_without_negative_sleep():
    from safety_platform.sim.frames import pace_to_deadline

    sleeps = []
    ticks = iter((9.99, 10.01))
    pace_to_deadline(10.0, clock=lambda: next(ticks), sleeper=sleeps.append)
    assert sleeps == [pytest.approx(0.01)]
