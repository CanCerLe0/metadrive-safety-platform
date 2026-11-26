"""Procedural straight-road export used as the native Scenario Description base."""

from __future__ import annotations

import numpy as np
from metadrive.envs.metadrive_env import MetaDriveEnv
from metadrive.scenario.scenario_description import ScenarioDescription as SD

from safety_platform.domain.spec import ScenarioSpec


def _lane_centers(scene: dict, origin: np.ndarray, lateral: np.ndarray) -> list[float]:
    offsets = []
    for feature in scene[SD.MAP_FEATURES].values():
        if "lane" not in str(feature.get("type", "")).lower() or "polyline" not in feature:
            continue
        points = np.asarray(feature["polyline"], dtype=float)
        nearest = points[np.argmin(np.linalg.norm(points[:, :2] - origin[:2], axis=1)), :2]
        offset = float(np.dot(nearest - origin[:2], lateral))
        if abs(offset) < 0.5 or abs(abs(offset) - 3.5) < 0.5:
            offsets.append(offset)
    if not any(abs(x) < 0.5 for x in offsets):
        raise RuntimeError("exported map has no ego lane")
    adjacent = [x for x in offsets if 2.5 < abs(x) < 4.5]
    if not adjacent:
        raise RuntimeError("exported map has no adjacent lane")
    return [0.0, min(adjacent, key=abs)]


def create_base_scene(spec: ScenarioSpec) -> dict:
    """Export genuine MetaDrive geometry, then place the planned ego track on it."""
    steps = round(spec.map_spec.duration_s / 0.1) + 1
    env = MetaDriveEnv({
        "map_config": {"type": "block_sequence", "config": "SSSSSSSS",
                       "lane_num": spec.map_spec.lane_count,
                       "lane_width": spec.map_spec.lane_width_m},
        "traffic_density": 0.0, "horizon": steps + 25,
        "out_of_road_done": False, "on_continuous_line_done": False,
        "crash_vehicle_done": False, "use_render": False, "log_level": 40,
    })
    try:
        exported, _ = env.export_scenarios(
            lambda _obs: [0.0, 0.25], scenario_index=0, max_episode_length=steps - 2
        )
        scene = exported[0]
    finally:
        env.close()
    if scene[SD.LENGTH] != steps:
        raise RuntimeError(f"unexpected exported length: {scene[SD.LENGTH]} != {steps}")
    ego_id = str(scene[SD.METADATA][SD.SDC_ID])
    ego = scene[SD.TRACKS][ego_id]
    origin = np.asarray(ego["state"]["position"][0], dtype=float)
    heading = float(ego["state"]["heading"][0])
    forward = np.array([np.cos(heading), np.sin(heading)])
    lateral = np.array([-np.sin(heading), np.cos(heading)])
    lane_offsets = _lane_centers(scene, origin, lateral)
    scene["safety_geometry"] = {"origin": origin, "forward": forward,
                                "lateral": lateral, "lane_offsets": lane_offsets}
    t = np.arange(steps, dtype=float) * 0.1
    ego_y = np.full(steps, lane_offsets[spec.ego_spec.lane_index])
    positions = origin[:2] + (spec.ego_spec.speed_mps * t)[:, None] * forward + ego_y[:, None] * lateral
    state = ego["state"]
    state["position"] = np.column_stack((positions, np.full(steps, origin[2])))
    state["velocity"] = np.gradient(positions, 0.1, axis=0)
    state["heading"] = np.arctan2(state["velocity"][:, 1], state["velocity"][:, 0])
    state["valid"] = np.ones(steps)
    scene[SD.ID] = spec.fingerprint()
    scene[SD.METADATA]["scenario_id"] = scene[SD.ID]
    return scene
