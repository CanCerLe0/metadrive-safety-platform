"""Deterministic, 0.1-second vehicle trajectories for registered builders."""

from __future__ import annotations

import copy

import numpy as np
from metadrive.scenario.scenario_description import ScenarioDescription as SD

from safety_platform.domain.spec import ActorSpec, ScenarioSpec


def set_ego_lane_change(scene: dict, spec: ScenarioSpec) -> dict:
    """Embed the planned ego route; the runtime controller will track this path."""
    geometry = scene["safety_geometry"]
    event = spec.event_spec
    steps = scene[SD.LENGTH]
    t = np.arange(steps, dtype=float) * 0.1
    progress = np.clip((t - event.start_s) / event.duration_s, 0.0, 1.0)
    smooth = progress * progress * (3.0 - 2.0 * progress)
    initial = geometry["lane_offsets"][spec.ego_spec.lane_index]
    target = geometry["lane_offsets"][event.target_lane_index]
    lateral_offset = initial + (target - initial) * smooth
    xy = (geometry["origin"][:2] + (spec.ego_spec.speed_mps * t)[:, None] * geometry["forward"]
          + lateral_offset[:, None] * geometry["lateral"])
    ego_id = str(scene[SD.METADATA][SD.SDC_ID])
    state = scene[SD.TRACKS][ego_id]["state"]
    state["position"] = np.column_stack((xy, np.full(steps, geometry["origin"][2])))
    state["velocity"] = np.gradient(xy, 0.1, axis=0)
    state["heading"] = np.arctan2(state["velocity"][:, 1], state["velocity"][:, 0])
    scene["safety_event_track_id"] = ego_id
    return state


def add_vehicle_track(scene: dict, actor: ActorSpec, spec: ScenarioSpec, *, mode: str) -> dict:
    geometry = scene["safety_geometry"]
    steps = scene[SD.LENGTH]
    t = np.arange(steps, dtype=float) * 0.1
    longitudinal = actor.longitudinal_gap_m + actor.speed_mps * t
    if mode == "front_brake":
        elapsed = np.clip(t - spec.event_spec.start_s, 0.0, None)
        deceleration = spec.event_spec.deceleration_mps2
        braking_time = np.minimum(elapsed, actor.speed_mps / deceleration)
        longitudinal -= 0.5 * deceleration * braking_time**2
        stopped = elapsed > actor.speed_mps / deceleration
        longitudinal[stopped] = (
            actor.longitudinal_gap_m + actor.speed_mps * spec.event_spec.start_s
            + actor.speed_mps**2 / (2 * deceleration)
        )
    lane_offset = np.full(steps, geometry["lane_offsets"][actor.lane_index])
    if mode == "cut_in":
        event = spec.event_spec
        progress = np.clip((t - event.start_s) / event.duration_s, 0.0, 1.0)
        smooth = progress * progress * (3.0 - 2.0 * progress)
        lane_offset += (geometry["lane_offsets"][event.target_lane_index] - lane_offset) * smooth
    elif mode not in {"steady", "front_brake"}:
        raise ValueError(f"unsupported vehicle trajectory mode: {mode}")
    xy = (geometry["origin"][:2] + longitudinal[:, None] * geometry["forward"]
          + lane_offset[:, None] * geometry["lateral"])
    velocity = np.gradient(xy, 0.1, axis=0)
    ego_id = str(scene[SD.METADATA][SD.SDC_ID])
    track = copy.deepcopy(scene[SD.TRACKS][ego_id])
    track["metadata"] = {"track_length": steps, "type": track["type"],
                         "object_id": actor.actor_id, "original_id": actor.actor_id}
    track["state"] = {
        "position": np.column_stack((xy, np.full(steps, geometry["origin"][2]))),
        "heading": np.arctan2(velocity[:, 1], velocity[:, 0]),
        "velocity": velocity,
        "valid": np.ones(steps),
        "length": np.full((steps, 1), 4.5),
        "width": np.full((steps, 1), 1.8),
        "height": np.full((steps, 1), 1.5),
    }
    scene[SD.TRACKS][actor.actor_id] = track
    return track["state"]
