import json
import pickle
import hashlib
from pathlib import Path

import pytest

from safety_platform.domain.registry import ScenarioRegistry, validate_spec
from safety_platform.domain.templates import BuiltinScenarioType
from safety_platform.sim.builder import build_native
from safety_platform.sim.bundle import BundleIntegrityError
from safety_platform.sim.policy import PolicyConfig
from safety_platform.sim.runner import run_bundle
from metadrive.scenario.utils import read_scenario_data
from metadrive.scenario.scenario_description import ScenarioDescription as SD
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
    assert one["status"] == a.status
    assert one["termination_reason"] == a.termination_reason
    assert one == two
    assert one["steps"] and one["steps"][0]["actors"]
    assert all("position" in step["ego"] and "velocity" in step["ego"] for step in one["steps"])
    assert a.event_occurred and a.valid
    assert a.policy_version and a.metadrive_sha


def test_runner_rejects_seed_that_disagrees_with_bundle(runner_bundle):
    with pytest.raises(ValueError, match="bundle seed"):
        run_bundle(runner_bundle.directory, PolicyConfig(), seed=999)


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
    evidence = json.loads(result.trajectory_path.read_text())
    assert evidence["status"] == "stopped"
    assert evidence["termination_reason"] == "stop_requested"


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


def test_registered_checker_receives_native_track_fields(tmp_path):
    class HeadingEvent(BuiltinScenarioType):
        def check_event(self, trajectory):
            assert len(trajectory["heading"]) == len(trajectory["valid"])
            assert trajectory["length"].shape[1] == 1
            return bool(trajectory["valid"].sum() > 50 and
                        abs(float(trajectory["heading"][0])) < 1)

    registry = ScenarioRegistry()
    registry.register(HeadingEvent("front_brake"))
    bundle = build_native(validate_spec(spec_data("front_brake"), registry=registry),
                          tmp_path / "heading", registry=registry)
    result = run_bundle(bundle.directory, PolicyConfig(), seed=42, registry=registry)
    assert result.event_occurred and result.valid


@pytest.mark.parametrize("template_id", ["cut_in", "front_brake", "lane_change"])
def test_legacy_builtin_bundle_retains_event_qualification(tmp_path, template_id):
    bundle = build_native(validate_spec(spec_data(template_id)), tmp_path / "legacy")
    scene = read_scenario_data(bundle.scene_path)
    del scene[SD.METADATA]["safety_event_track_id"]
    with bundle.scene_path.open("wb") as handle:
        pickle.dump(scene, handle, protocol=pickle.HIGHEST_PROTOCOL)
    manifest = json.loads(bundle.manifest_path.read_text())
    manifest["files"][bundle.scene_path.name] = hashlib.sha256(bundle.scene_path.read_bytes()).hexdigest()
    bundle.manifest_path.write_text(json.dumps(manifest))
    result = run_bundle(bundle.directory, PolicyConfig(), seed=42)
    assert result.event_occurred and result.valid


def test_nonvehicle_collision_and_actor_flags_are_recorded(runner_bundle):
    from types import SimpleNamespace
    from safety_platform.sim.metrics import SafetyMetrics, VehicleState
    from safety_platform.sim.runner import _vehicle_collision

    contact = SimpleNamespace(crash_vehicle=False, crash_object=True, crash_building=False,
                              crash_human=False, crash_sidewalk=False)
    assert _vehicle_collision(contact)
    metrics = SafetyMetrics()
    ego = VehicleState((0, 0), (0, 0), 0, 4.5, 1.8)
    metrics.observe(ego, [], collision=_vehicle_collision(contact))
    assert metrics.min_ttc == 0
    result = run_bundle(runner_bundle.directory, PolicyConfig(), seed=42)
    steps = json.loads(result.trajectory_path.read_text())["steps"]
    assert all(isinstance(actor["collision"], bool)
               for step in steps for actor in step["actors"].values())
