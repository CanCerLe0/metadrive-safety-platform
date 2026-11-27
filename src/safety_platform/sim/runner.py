"""Verified native bundle replay with one fixed policy and durable run evidence."""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Callable
from uuid import uuid4

import numpy as np
from metadrive.envs.scenario_env import ScenarioEnv
from metadrive.scenario.scenario_description import ScenarioDescription as SD
from PIL import Image

from safety_platform.config import VAR_DIR
from safety_platform.domain.registry import DEFAULT_REGISTRY, ScenarioRegistry
from safety_platform.domain.spec import ScenarioSpec
from safety_platform.sim.bundle import verify_bundle
from safety_platform.sim.frames import FrameSink, pace_to_deadline
from safety_platform.sim.metrics import METRICS_VERSION, SafetyMetrics, VehicleState
from safety_platform.sim.policy import PolicyConfig, RulePolicy


@dataclass(frozen=True)
class RunOutcome:
    status: str
    trajectory_path: Path
    collision: bool
    out_of_road: bool
    completed: bool
    min_ttc: float
    valid: bool
    validity_reason: str | None
    event_occurred: bool
    termination_reason: str
    steps: int
    frame_count: int
    render_mean_ms: float
    seed: int
    policy_version: str
    metrics_version: str
    metadrive_version: str
    metadrive_sha: str


def _vehicle_state(vehicle) -> VehicleState:
    return VehicleState(
        tuple(float(value) for value in vehicle.position[:2]),
        tuple(float(value) for value in vehicle.velocity[:2]),
        float(vehicle.heading_theta), float(vehicle.LENGTH), float(vehicle.WIDTH), float(vehicle.HEIGHT),
    )


def _vehicle_collision(vehicle, info: dict | None = None) -> bool:
    return bool((info or {}).get("crash", False) or any(
        getattr(vehicle, flag, False) for flag in (
            "crash_vehicle", "crash_object", "crash_building", "crash_human", "crash_sidewalk"
        )
    ))


def _state_json(state: VehicleState, *, collision: bool) -> dict:
    return {
        "position": state.position, "velocity": state.velocity,
        "heading_rad": state.heading_rad,
        "length_m": state.length_m, "width_m": state.width_m, "height_m": state.height_m,
        "collision": collision,
    }


def _actors(env: ScenarioEnv) -> dict[str, tuple[VehicleState, bool]]:
    manager = env.engine.traffic_manager
    objects = env.engine.get_objects()
    result = {}
    for scenario_id, object_id in manager._scenario_id_to_obj_id.items():
        vehicle = objects.get(object_id)
        if vehicle is not None and vehicle.id != env.agent.id:
            result[str(scenario_id)] = (_vehicle_state(vehicle), _vehicle_collision(vehicle))
    return result


def _event_observed(scenario_type, spec: ScenarioSpec, scenario: dict, records: list[dict]) -> tuple[bool, str | None]:
    selected = scenario[SD.METADATA].get("safety_event_track_id")
    if selected is None:
        selector = getattr(scenario_type, "event_track_id", None)
        if selector is None:
            return False, "legacy_event_subject_unknown"
        selected = selector(spec, scenario)
    ego = str(scenario[SD.METADATA][SD.SDC_ID])
    trajectory = _track(records, str(selected), ego=str(selected) == ego)
    observed = len(trajectory["position"]) > 1 and scenario_type.check_event(trajectory)
    return observed, None if observed else "event_not_observed"


def _track(records: list[dict], track_id: str, *, ego: bool) -> dict:
    states = [record["ego"] if ego else record["actors"].get(track_id) for record in records]
    return {
        "position": np.asarray([(*state["position"], 0.0) if state else (0.0, 0.0, 0.0)
                                for state in states]),
        "velocity": np.asarray([state["velocity"] if state else (0.0, 0.0) for state in states]),
        "heading": np.asarray([state["heading_rad"] if state else 0.0 for state in states]),
        "valid": np.asarray([state is not None for state in states]),
        "length": np.asarray([[state["length_m"] if state else 0.0] for state in states]),
        "width": np.asarray([[state["width_m"] if state else 0.0] for state in states]),
        "height": np.asarray([[state["height_m"] if state else 0.0] for state in states]),
    }


def run_bundle(
    bundle_dir: Path,
    policy: PolicyConfig,
    seed: int,
    stop_requested: Callable[[], bool] | None = None,
    frame_sink: FrameSink | None = None,
    playback_rate: float | None = None,
    *,
    registry: ScenarioRegistry = DEFAULT_REGISTRY,
) -> RunOutcome:
    """Replay one checked bundle using its scene-generation seed."""
    manifest = verify_bundle(bundle_dir)
    if type(seed) is not int or seed != manifest.seed:
        raise ValueError(f"run seed must match bundle seed {manifest.seed}")
    scenario_type = registry.get(manifest.template_id, manifest.template_version)
    if playback_rate is not None and playback_rate <= 0:
        raise ValueError("playback_rate must be positive")
    rate = 1.0 if playback_rate is None else playback_rate
    spec = ScenarioSpec.model_validate_json((Path(bundle_dir) / "scenario_spec.json").read_text(encoding="utf-8"))
    env = ScenarioEnv({
        "data_directory": str(bundle_dir), "num_scenarios": 1,
        "reactive_traffic": False, "filter_overlapping_car": False,
        "horizon": round(spec.map_spec.duration_s / 0.1) + 1,
        "use_render": False, "log_level": 40,
        "crash_vehicle_done": False,
    })
    records: list[dict] = []
    metrics = SafetyMetrics()
    out_of_road = completed = False
    status, reason = "completed", "horizon"
    render_times: list[float] = []
    frame_count = 0
    steps = 0
    started = perf_counter()
    try:
        # ScenarioEnv's reset seed selects a dataset index, so a one-scene bundle uses 0.
        env.reset(seed=0)
        scenario = env.engine.data_manager.current_scenario
        ego_id = str(scenario[SD.METADATA][SD.SDC_ID])
        route = np.asarray(scenario[SD.TRACKS][ego_id]["state"]["position"])[:, :2]
        driver = RulePolicy(policy, route, spec.ego_spec.speed_mps)

        def capture(time_s: float, info: dict) -> None:
            nonlocal out_of_road, completed
            ego = _vehicle_state(env.agent)
            actors = _actors(env)
            collision = _vehicle_collision(env.agent, info)
            out_of_road |= bool(info.get("out_of_road", False))
            completed |= bool(info.get("arrive_dest", False))
            metrics.observe(ego, [state for state, _ in actors.values()], collision=collision)
            records.append({
                "sim_time_s": round(time_s, 6), "ego": _state_json(ego, collision=collision),
                "actors": {name: _state_json(state, collision=actor_collision)
                           for name, (state, actor_collision) in sorted(actors.items())},
                "collision": collision, "out_of_road": out_of_road, "completed": completed,
            })

        capture(0.0, {})
        max_steps = round(spec.map_spec.duration_s / 0.1)
        for _ in range(max_steps):
            if stop_requested is not None and stop_requested():
                status, reason = "stopped", "stop_requested"
                break
            ego = _vehicle_state(env.agent)
            actors = _actors(env)
            action = driver.action(ego, [state for state, _ in actors.values()])
            _, _, terminated, truncated, info = env.step(action)
            steps += 1
            capture(steps * 0.1, info)
            if frame_sink is not None:
                render_start = perf_counter()
                pixels = np.asarray(env.render(mode="topdown", window=False, screen_size=(640, 360)))
                if pixels.shape != (360, 640, 3) or pixels.dtype != np.uint8 or not pixels.any():
                    raise RuntimeError("MetaDrive returned an invalid topdown frame")
                buffer = io.BytesIO()
                Image.fromarray(pixels).save(buffer, format="JPEG", quality=80)
                frame_sink.publish(buffer.getvalue(), steps * 0.1)
                render_times.append((perf_counter() - render_start) * 1000)
                frame_count += 1
                deadline = started + steps * 0.1 / rate
                pace_to_deadline(deadline)
            if terminated or truncated:
                reason = next((key for key in ("arrive_dest", "out_of_road", "crash_vehicle", "max_step")
                               if info.get(key)), "terminated")
                break
        event_occurred, validity_reason = _event_observed(scenario_type, spec, scenario, records)
    finally:
        env.close()
    output_dir = VAR_DIR / "runs" / uuid4().hex
    output_dir.mkdir(parents=True, exist_ok=False)
    trajectory_path = output_dir / "trajectory.json"
    trajectory_path.write_text(json.dumps({
        "scene_id": manifest.scene_id, "seed": seed, "policy_version": policy.version,
        "metrics_version": METRICS_VERSION, "reactive_traffic": manifest.reactive_traffic,
        "status": status, "termination_reason": reason,
        "steps": records,
    }, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return RunOutcome(
        status=status, trajectory_path=trajectory_path, collision=metrics.collision,
        out_of_road=out_of_road, completed=completed, min_ttc=metrics.min_ttc,
        valid=status == "completed" and event_occurred,
        validity_reason="stopped" if status == "stopped" else validity_reason,
        event_occurred=event_occurred,
        termination_reason=reason, steps=steps, frame_count=frame_count,
        render_mean_ms=float(np.mean(render_times)) if render_times else 0.0,
        seed=seed, policy_version=policy.version, metrics_version=METRICS_VERSION,
        metadrive_version=manifest.metadrive_version, metadrive_sha=manifest.metadrive_sha,
    )
