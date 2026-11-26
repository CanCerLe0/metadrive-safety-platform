"""One-time native MetaDrive roundtrip and rendering capability probe.

This is intentionally a small recorded-scenario prototype, not the template
builder used by later tasks. It creates one replayed traffic cut-in on top of
an official procedural scenario export and tests the saved dataset in a new
ScenarioEnv instance.
"""

from __future__ import annotations

import copy
import importlib.metadata
import json
import resource
import sys
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import numpy as np

from metadrive.envs.metadrive_env import MetaDriveEnv
from metadrive.envs.scenario_env import ScenarioEnv
from metadrive.scenario.scenario_description import ScenarioDescription as SD
from metadrive.scenario.utils import read_dataset_summary, save_dataset


@dataclass(frozen=True)
class ProbeResult:
    dataset_dir: Path
    scenario_id: str
    metadrive_version: str
    metadrive_sha: str
    steps: int
    actor_changed_lane: bool
    ego_moved: bool
    dataset_index_readable: bool
    topdown_frames_valid: bool
    mean_render_ms: float
    peak_memory_mb: float


def _metadrive_identity() -> tuple[str, str]:
    dist = importlib.metadata.distribution("metadrive-simulator")
    direct_url = json.loads(dist.read_text("direct_url.json") or "{}")
    sha = direct_url.get("vcs_info", {}).get("commit_id")
    if not sha or len(sha) != 40:
        raise RuntimeError("MetaDrive installation has no verifiable source commit")
    return dist.version, sha


def _make_cut_in(scenario: dict, actor_initial_distance_m: float) -> tuple[dict, str]:
    """Add a deterministic traffic track to an officially exported road/ego."""
    scenario = copy.deepcopy(scenario)
    ego_id = str(scenario[SD.METADATA][SD.SDC_ID])
    ego = scenario[SD.TRACKS][ego_id]
    steps = scenario[SD.LENGTH]
    start = np.asarray(ego["state"]["position"][0], dtype=float)
    heading = float(ego["state"]["heading"][0])
    forward = np.array([np.cos(heading), np.sin(heading)])
    lateral = np.array([-np.sin(heading), np.cos(heading)])

    # The probe map is a two-lane straight road. Infer the neighbor's side
    # from its actual lane centerline rather than assuming world-axis signs.
    lane_offsets = []
    for feature in scenario[SD.MAP_FEATURES].values():
        if "polyline" not in feature or "lane" not in str(feature.get("type", "")).lower():
            continue
        polyline = np.asarray(feature["polyline"])
        nearest = polyline[np.argmin(np.linalg.norm(polyline[:, :2] - start[:2], axis=1)), :2]
        offset = float(np.dot(nearest - start[:2], lateral))
        lane_offsets.append(offset)
    adjacent = [offset for offset in lane_offsets if 2.0 < abs(offset) < 5.0]
    if not adjacent:
        raise RuntimeError(f"Two-lane map did not expose adjacent lane: {lane_offsets[:10]}")
    side = 1 if adjacent[0] > 0 else -1

    actor_id = "probe-cut-in"
    actor = copy.deepcopy(ego)
    actor["metadata"] = {
        "track_length": steps,
        "type": actor["type"],
        "object_id": actor_id,
        "original_id": actor_id,
    }
    t = np.arange(steps, dtype=float) * 0.1
    progress = np.clip((t - 2.0) / 3.0, 0.0, 1.0)
    smooth = progress * progress * (3.0 - 2.0 * progress)
    lateral_offset = side * 3.5 * (1.0 - smooth)
    positions = (
        start[:2]
        + (actor_initial_distance_m + 8.0 * t)[:, None] * forward
        + lateral_offset[:, None] * lateral
    )
    actor["state"] = {
        "position": np.column_stack((positions, np.full(steps, start[2]))),
        "heading": np.full(steps, heading),
        "velocity": np.gradient(positions, 0.1, axis=0),
        "valid": np.ones(steps),
        "length": np.full((steps, 1), 4.5),
        "width": np.full((steps, 1), 1.8),
        "height": np.full((steps, 1), 1.5),
    }
    scenario[SD.TRACKS][actor_id] = actor
    SD.sanity_check(scenario, check_self_type=True)
    return scenario, actor_id


def _peak_memory_mb() -> float:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / (1024 * 1024 if sys.platform == "darwin" else 1024)


def probe_native(out_dir: Path, *, actor_initial_distance_m: float = 25.0) -> ProbeResult:
    """Export, save, reload, drive and render one native cut-in scenario."""
    version, sha = _metadrive_identity()
    dataset_dir = Path(out_dir) / "native_probe"
    source = MetaDriveEnv({
        "map_config": {"type": "block_sequence", "config": "S", "lane_num": 2, "lane_width": 3.5},
        "traffic_density": 0.0,
        "horizon": 125,
        "out_of_road_done": False,
        "on_continuous_line_done": False,
        "crash_vehicle_done": False,
        "use_render": False,
        "log_level": 40,
    })
    try:
        exported, _ = source.export_scenarios(
            lambda _obs: [0.0, 0.25], scenario_index=0, max_episode_length=119
        )
        scenario, actor_id = _make_cut_in(exported[0], actor_initial_distance_m)
        save_dataset([scenario], "safety-probe", "1", dataset_dir)
    finally:
        source.close()

    summary, files, mapping = read_dataset_summary(dataset_dir)
    index_readable = len(files) == 1 and files[0] in summary and files[0] in mapping
    replay = ScenarioEnv({
        "data_directory": str(dataset_dir),
        "num_scenarios": 1,
        "reactive_traffic": False,
        "filter_overlapping_car": False,
        "horizon": 125,
        "use_render": False,
        "log_level": 40,
    })
    try:
        replay.reset(seed=0)
        ego_initial = np.asarray(replay.agent.position).copy()
        actor_positions = []
        frame_checksums = []
        render_times = []
        steps = 0
        for _ in range(100):
            _, _, terminated, truncated, _ = replay.step([0.0, 0.25])
            steps += 1
            actor_name = replay.engine.traffic_manager._scenario_id_to_obj_id.get(actor_id)
            if actor_name is not None:
                actor_positions.append(np.asarray(replay.engine.get_objects()[actor_name].position).copy())
            started = perf_counter()
            frame = replay.render(mode="topdown", window=False, screen_size=(640, 360))
            render_times.append((perf_counter() - started) * 1000)
            pixels = np.asarray(frame)
            if pixels.shape != (360, 640, 3) or pixels.dtype != np.uint8 or not pixels.any():
                raise RuntimeError(f"Invalid MetaDrive topdown frame: {pixels.shape}, {pixels.dtype}")
            frame_checksums.append(hash(pixels.tobytes()))
            if terminated or truncated:
                break
        ego_moved = bool(np.linalg.norm(np.asarray(replay.agent.position) - ego_initial) > 2.0)
        if len(actor_positions) >= 70:
            actor_array = np.asarray(actor_positions)
            heading = float(scenario[SD.TRACKS][actor_id]["state"]["heading"][0])
            lateral = np.array([-np.sin(heading), np.cos(heading)])
            actor_changed_lane = abs(float(np.dot(actor_array[-1] - actor_array[0], lateral))) > 2.5
        else:
            actor_changed_lane = False
        return ProbeResult(
            dataset_dir=dataset_dir,
            scenario_id=scenario[SD.ID],
            metadrive_version=version,
            metadrive_sha=sha,
            steps=steps,
            actor_changed_lane=actor_changed_lane,
            ego_moved=ego_moved,
            dataset_index_readable=index_readable,
            topdown_frames_valid=len(frame_checksums) == 100 and len(set(frame_checksums)) > 1,
            mean_render_ms=float(np.mean(render_times)),
            peak_memory_mb=_peak_memory_mb(),
        )
    finally:
        replay.close()
