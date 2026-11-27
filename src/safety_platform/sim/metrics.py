"""Version 1 safety metrics: constant-velocity swept oriented rectangles."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, inf, sin

import numpy as np

METRICS_VERSION = "1.0"
TTC_HORIZON_S = 10.0


@dataclass(frozen=True)
class VehicleState:
    position: tuple[float, float]
    velocity: tuple[float, float]
    heading_rad: float
    length_m: float
    width_m: float


def compute_ttc(ego_state: VehicleState, other_state: VehicleState, horizon_s: float = TTC_HORIZON_S) -> float:
    """First box intersection under fixed heading and relative velocity, capped at horizon."""
    if horizon_s <= 0:
        raise ValueError("horizon_s must be positive")
    relative_position = np.subtract(other_state.position, ego_state.position)
    relative_velocity = np.subtract(other_state.velocity, ego_state.velocity)
    axes = []
    for vehicle in (ego_state, other_state):
        forward = np.array((cos(vehicle.heading_rad), sin(vehicle.heading_rad)))
        lateral = np.array((-forward[1], forward[0]))
        axes.append((forward, lateral))
    enter, leave = -inf, inf
    for axis in (*axes[0], *axes[1]):
        radius = sum(
            abs(float(np.dot(axis, basis[0]))) * vehicle.length_m / 2
            + abs(float(np.dot(axis, basis[1]))) * vehicle.width_m / 2
            for vehicle, basis in zip((ego_state, other_state), axes)
        )
        distance = float(np.dot(relative_position, axis))
        speed = float(np.dot(relative_velocity, axis))
        if abs(speed) < 1e-12:
            if abs(distance) > radius:
                return horizon_s
            continue
        near, far = sorted(((-radius - distance) / speed, (radius - distance) / speed))
        enter, leave = max(enter, near), min(leave, far)
        if enter > leave:
            return horizon_s
    return max(0.0, enter) if leave >= 0 and enter < horizon_s else horizon_s


@dataclass
class SafetyMetrics:
    min_ttc: float = TTC_HORIZON_S
    collision: bool = False

    def observe(self, ego: VehicleState, others: list[VehicleState], *, collision: bool) -> None:
        self.collision |= collision
        if collision:
            self.min_ttc = 0.0
        elif not self.collision:
            self.min_ttc = min(self.min_ttc, *(compute_ttc(ego, other) for other in others))
