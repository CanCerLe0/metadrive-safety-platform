from pathlib import Path

import numpy as np
import pytest
from metadrive.envs.scenario_env import ScenarioEnv
from metadrive.scenario.scenario_description import ScenarioDescription as SD
from metadrive.scenario.utils import read_scenario_data

from safety_platform.domain.registry import ScenarioRegistry, validate_spec
from safety_platform.domain.templates import BuiltinScenarioType
from safety_platform.sim.builder import build_native
from safety_platform.sim.bundle import verify_bundle
from tests.factories import spec_data


@pytest.mark.parametrize("template_id", ["cut_in", "front_brake", "lane_change"])
def test_each_template_builds_valid_scenarionet_dataset(tmp_path: Path, template_id: str) -> None:
    spec = validate_spec(spec_data(template_id))
    bundle = build_native(spec, tmp_path / template_id)
    assert bundle.scene_path.is_file()
    assert bundle.summary_path.is_file()
    assert bundle.mapping_path.is_file()
    assert verify_bundle(bundle.directory).scene_id == bundle.scene_id

    scene = read_scenario_data(bundle.scene_path)
    SD.sanity_check(scene)
    actor = scene[SD.TRACKS]["lead"]["state"]
    assert len(actor["position"]) >= 100
    assert np.all(actor["valid"])
    ego = scene[SD.TRACKS][str(scene[SD.METADATA][SD.SDC_ID])]["state"]
    if template_id == "cut_in":
        assert abs(actor["position"][-1, 1] - actor["position"][0, 1]) > 2.5
    elif template_id == "front_brake":
        assert np.linalg.norm(actor["velocity"][-1]) < np.linalg.norm(actor["velocity"][0]) - 1
    else:
        assert abs(ego["position"][-1, 1] - ego["position"][0, 1]) > 2.5
    env = ScenarioEnv({
        "data_directory": str(bundle.directory), "num_scenarios": 1,
        "reactive_traffic": False, "filter_overlapping_car": False,
        "horizon": 125, "use_render": False, "log_level": 40,
    })
    try:
        env.reset(seed=0)
        for _ in range(30):
            env.step([0.0, 0.2])
        assert env.engine.traffic_manager.vehicles
    finally:
        env.close()


def test_parameter_change_changes_replayed_actor(tmp_path: Path) -> None:
    base = validate_spec(spec_data("cut_in"))
    farther = validate_spec(spec_data("cut_in", actor_specs__0__longitudinal_gap_m=35.0))
    later = validate_spec(spec_data("cut_in", event_spec__start_s=3.0))
    tracks = []
    replayed = []
    for index, spec in enumerate((base, farther, later)):
        bundle = build_native(spec, tmp_path / str(index))
        tracks.append(read_scenario_data(bundle.scene_path)[SD.TRACKS]["lead"]["state"]["position"])
        env = ScenarioEnv({"data_directory": str(bundle.directory), "num_scenarios": 1,
                           "reactive_traffic": False, "filter_overlapping_car": False,
                           "horizon": 125, "use_render": False, "log_level": 40})
        positions = []
        try:
            env.reset(seed=0)
            for _ in range(50):
                env.step([0.0, 0.2])
                actor = next(vehicle for vehicle in env.engine.traffic_manager.vehicles
                             if vehicle.id != env.agent.id)
                positions.append(np.asarray(actor.position).copy())
        finally:
            env.close()
        replayed.append(np.asarray(positions))
    assert not np.array_equal(tracks[0], tracks[1])
    assert not np.array_equal(tracks[0], tracks[2])
    assert not np.array_equal(replayed[0], replayed[1])
    assert not np.array_equal(replayed[0], replayed[2])


def test_registered_fourth_type_builds_and_replays(tmp_path: Path) -> None:
    class FourthType(BuiltinScenarioType):
        def validate(self, raw):
            from safety_platform.domain.spec import ScenarioSpec
            spec = ScenarioSpec.model_validate(raw)
            assert spec.template_id == self.template_id
            return spec

        def build_native(self, spec, out_dir):
            from safety_platform.sim.base_map import create_base_scene
            from safety_platform.sim.trajectories import add_vehicle_track
            scene = create_base_scene(spec)
            add_vehicle_track(scene, spec.actor_specs[0], spec, mode="steady")
            return scene

        def check_event(self, trajectory):
            return len(trajectory["position"]) >= 100

    registry = ScenarioRegistry()
    registry.register(FourthType("test_fourth"))
    spec = validate_spec(spec_data("test_fourth"), registry=registry)
    bundle = build_native(spec, tmp_path / "fourth", registry=registry)
    assert verify_bundle(bundle.directory).template_id == "test_fourth"
    env = ScenarioEnv({"data_directory": str(bundle.directory), "num_scenarios": 1,
                       "reactive_traffic": False, "filter_overlapping_car": False,
                       "use_render": False, "log_level": 40})
    try:
        env.reset(seed=0)
        env.step([0.0, 0.2])
        assert env.engine.traffic_manager.vehicles
    finally:
        env.close()


def test_registered_event_checker_can_reject_native_build(tmp_path: Path) -> None:
    class RejectingType(BuiltinScenarioType):
        def validate(self, raw):
            from safety_platform.domain.spec import ScenarioSpec
            return ScenarioSpec.model_validate(raw)

        def build_native(self, spec, out_dir):
            from safety_platform.sim.base_map import create_base_scene
            from safety_platform.sim.trajectories import add_vehicle_track
            scene = create_base_scene(spec)
            add_vehicle_track(scene, spec.actor_specs[0], spec, mode="steady")
            return scene

        def check_event(self, trajectory):
            return False

    registry = ScenarioRegistry()
    registry.register(RejectingType("test_rejected"))
    spec = validate_spec(spec_data("test_rejected"), registry=registry)
    with pytest.raises(ValueError, match="event check failed"):
        build_native(spec, tmp_path / "rejected", registry=registry)
