from hashlib import sha256
from pathlib import Path

import numpy as np

from metadrive.envs.scenario_env import ScenarioEnv
from metadrive.scenario.utils import read_scenario_data
from safety_platform.sim.probe import probe_native


def test_native_export_then_scenarioenv_replay(tmp_path: Path) -> None:
    """A saved native dataset must replay a traffic cut-in with live ego control."""
    result = probe_native(tmp_path)

    assert result.dataset_dir.is_dir()
    assert (result.dataset_dir / "dataset_summary.pkl").is_file()
    assert (result.dataset_dir / "dataset_mapping.pkl").is_file()
    assert result.scenario_id
    assert result.metadrive_version
    assert len(result.metadrive_sha) == 40
    assert result.steps >= 100
    assert result.actor_changed_lane
    assert result.ego_moved
    assert result.dataset_index_readable
    assert result.topdown_frames_valid
    assert result.mean_render_ms > 0
    assert result.peak_memory_mb > 0


def _replay_positions(dataset_dir: Path, throttle: float, steps: int) -> tuple[np.ndarray, np.ndarray]:
    """Observe the loaded vehicles, independently of the probe's reported flags."""
    env = ScenarioEnv({
        "data_directory": str(dataset_dir),
        "num_scenarios": 1,
        "reactive_traffic": False,
        "filter_overlapping_car": False,
        "horizon": 125,
        "use_render": False,
        "log_level": 40,
    })
    ego_positions = []
    actor_positions = []
    try:
        env.reset(seed=0)
        for _ in range(steps):
            _, _, terminated, truncated, _ = env.step([0.0, throttle])
            actors = [vehicle for vehicle in env.engine.traffic_manager.vehicles if vehicle.id != env.agent.id]
            assert len(actors) == 1
            ego_positions.append(np.asarray(env.agent.position).copy())
            actor_positions.append(np.asarray(actors[0].position).copy())
            assert not terminated and not truncated
    finally:
        env.close()
    return np.asarray(ego_positions), np.asarray(actor_positions)


def test_cut_in_parameter_changes_native_file_replay_and_result(tmp_path: Path) -> None:
    near = probe_native(tmp_path / "near", actor_initial_distance_m=25.0)
    near_repeat = probe_native(tmp_path / "near_repeat", actor_initial_distance_m=25.0)
    far = probe_native(tmp_path / "far", actor_initial_distance_m=35.0)

    near_file = next(near.dataset_dir.glob("sd_*.pkl"))
    near_repeat_file = next(near_repeat.dataset_dir.glob("sd_*.pkl"))
    far_file = next(far.dataset_dir.glob("sd_*.pkl"))
    near_saved_actor = read_scenario_data(near_file)["tracks"]["probe-cut-in"]["state"]["position"]
    near_repeat_saved_actor = read_scenario_data(near_repeat_file)["tracks"]["probe-cut-in"]["state"]["position"]
    far_saved_actor = read_scenario_data(far_file)["tracks"]["probe-cut-in"]["state"]["position"]

    # Whole-file hashes can also change because export assigns fresh object IDs.
    # The native actor track must stay stable for the same parameter and change
    # for the changed parameter.
    np.testing.assert_array_equal(near_saved_actor, near_repeat_saved_actor)
    assert not np.array_equal(near_saved_actor, far_saved_actor)
    assert sha256(near_file.read_bytes()).digest() != sha256(far_file.read_bytes()).digest()

    near_ego, near_actor = _replay_positions(near.dataset_dir, 0.25, 100)
    near_repeat_ego, near_repeat_actor = _replay_positions(near_repeat.dataset_dir, 0.25, 100)
    far_ego, far_actor = _replay_positions(far.dataset_dir, 0.25, 100)
    near_min_distance = np.linalg.norm(near_actor - near_ego, axis=1).min()
    near_repeat_min_distance = np.linalg.norm(near_repeat_actor - near_repeat_ego, axis=1).min()
    far_min_distance = np.linalg.norm(far_actor - far_ego, axis=1).min()

    np.testing.assert_allclose(near_actor, near_repeat_actor, atol=1e-6)
    assert abs(near_min_distance - near_repeat_min_distance) < 1e-6
    np.testing.assert_allclose(near_ego, far_ego, atol=1e-6)
    assert not np.allclose(near_actor, far_actor)
    assert far_min_distance > near_min_distance + 5.0


def test_external_ego_action_changes_ego_not_replayed_actor(tmp_path: Path) -> None:
    result = probe_native(tmp_path)

    coast_ego, coast_actor = _replay_positions(result.dataset_dir, 0.0, 60)
    accelerate_ego, accelerate_actor = _replay_positions(result.dataset_dir, 0.25, 60)

    assert np.linalg.norm(accelerate_ego[-1] - coast_ego[-1]) > 0.5
    np.testing.assert_allclose(accelerate_actor, coast_actor, atol=1e-6)
