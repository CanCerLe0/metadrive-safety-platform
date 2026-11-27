import json
from pathlib import Path

import pytest

from safety_platform.domain.registry import ScenarioRegistry, validate_spec
from safety_platform.domain.templates import BuiltinScenarioType
from safety_platform.sim.builder import build_native
from safety_platform.sim.bundle import BundleIntegrityError
from safety_platform.sim.policy import PolicyConfig
from safety_platform.sim.runner import run_bundle
from tests.factories import spec_data


@pytest.fixture(scope="module")
def runner_bundle(tmp_path_factory):
    root = tmp_path_factory.mktemp("runner")
    return build_native(validate_spec(spec_data("front_brake")), root / "bundle")


def test_runner_replay_same_seed(runner_bundle):
    a = run_bundle(runner_bundle.directory, PolicyConfig(), seed=42)
    b = run_bundle(runner_bundle.directory, PolicyConfig(), seed=42)
    assert a.status == b.status == "completed"
    assert abs(a.min_ttc - b.min_ttc) < 1e-6
    assert a.steps == b.steps
    assert a.trajectory_path.is_file() and b.trajectory_path.is_file()
    one = json.loads(a.trajectory_path.read_text())
    two = json.loads(b.trajectory_path.read_text())
    assert one == two
    assert one["steps"] and one["steps"][0]["actors"]
    assert all("position" in step["ego"] and "velocity" in step["ego"] for step in one["steps"])
    assert a.event_occurred and a.valid
    assert a.policy_version and a.metadrive_sha


def test_stop_requested_returns_terminal_outcome(runner_bundle):
    calls = 0

    def stop():
        nonlocal calls
        calls += 1
        return calls > 5

    result = run_bundle(runner_bundle.directory, PolicyConfig(), seed=42, stop_requested=stop)
    assert result.status == "stopped"
    assert result.steps == 5
    assert not result.valid
    assert result.trajectory_path.is_file()


def test_bundle_is_verified_before_scenario_load(tmp_path: Path, runner_bundle):
    bundle = runner_bundle.directory
    original = bundle.joinpath("dataset_mapping.pkl").read_bytes()
    try:
        bundle.joinpath("dataset_mapping.pkl").write_bytes(b"tampered")
        with pytest.raises(BundleIntegrityError):
            run_bundle(bundle, PolicyConfig(), seed=42)
    finally:
        bundle.joinpath("dataset_mapping.pkl").write_bytes(original)


def test_event_check_uses_recorded_event_actor(runner_bundle):
    class EgoOnlyEvent(BuiltinScenarioType):
        def check_event(self, trajectory):
            return abs(float(trajectory["position"][0][0])) < 5

    registry = ScenarioRegistry()
    registry.register(EgoOnlyEvent("front_brake"))
    outcome = run_bundle(runner_bundle.directory, PolicyConfig(), seed=42, registry=registry)
    assert not outcome.event_occurred
    assert not outcome.valid


def test_policy_params_cannot_change_without_new_version():
    with pytest.raises(ValueError, match="new policy version"):
        PolicyConfig(lookahead_m=10.0)
