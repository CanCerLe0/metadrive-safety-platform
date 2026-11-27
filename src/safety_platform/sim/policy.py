"""Fixed, deterministic route following and obstacle braking controller."""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, pi

import numpy as np

from safety_platform.sim.metrics import VehicleState

POLICY_VERSION = "route-rule-1.0"


@dataclass(frozen=True)
class PolicyConfig:
    version: str = POLICY_VERSION
    lookahead_m: float = 8.0
    heading_gain: float = 1.6
    lateral_gain: float = 0.08
    speed_gain: float = 0.25
    max_speed_mps: float = 22.0
    following_time_s: float = 1.2
    minimum_gap_m: float = 6.0

    def __post_init__(self) -> None:
        if self.version != POLICY_VERSION:
            raise ValueError(f"unsupported policy version: {self.version}")
        if (self.lookahead_m, self.heading_gain, self.lateral_gain, self.speed_gain,
            self.max_speed_mps, self.following_time_s, self.minimum_gap_m) != (
            8.0, 1.6, 0.08, 0.25, 22.0, 1.2, 6.0
        ):
            raise ValueError("changed controller parameters require a new policy version")


class RulePolicy:
    def __init__(self, config: PolicyConfig, route_xy: np.ndarray, target_speed_mps: float) -> None:
        self.config = config
        self.route = np.asarray(route_xy, dtype=float)
        if self.route.ndim != 2 or self.route.shape[1] != 2 or len(self.route) < 2:
            raise ValueError("route must have at least two xy points")
        self.target_speed_mps = min(target_speed_mps, config.max_speed_mps)

    def action(self, ego: VehicleState, actors: list[VehicleState]) -> list[float]:
        position = np.asarray(ego.position)
        nearest = int(np.argmin(np.linalg.norm(self.route - position, axis=1)))
        lookahead = max(1, round(self.config.lookahead_m / max(
            np.linalg.norm(self.route[min(nearest + 1, len(self.route) - 1)] - self.route[nearest]), 0.1)))
        target = self.route[min(nearest + lookahead, len(self.route) - 1)]
        desired = atan2(target[1] - position[1], target[0] - position[0])
        heading_error = (desired - ego.heading_rad + pi) % (2 * pi) - pi
        forward = np.array((np.cos(ego.heading_rad), np.sin(ego.heading_rad)))
        lateral = np.array((-forward[1], forward[0]))
        lateral_error = float(np.dot(target - position, lateral))
        steer = float(np.clip(self.config.heading_gain * heading_error
                              + self.config.lateral_gain * lateral_error, -1, 1))
        speed = float(np.dot(ego.velocity, forward))
        desired_speed = self.target_speed_mps
        for actor in actors:
            gap = float(np.dot(np.subtract(actor.position, ego.position), forward))
            across = abs(float(np.dot(np.subtract(actor.position, ego.position), lateral)))
            if gap <= 0 or across > (ego.width_m + actor.width_m) / 2 + 0.4:
                continue
            clear_gap = gap - (ego.length_m + actor.length_m) / 2
            safe_gap = self.config.minimum_gap_m + max(speed, 0) * self.config.following_time_s
            if clear_gap < safe_gap:
                desired_speed = min(desired_speed, max(0.0, float(np.linalg.norm(actor.velocity))
                                                       + (clear_gap - safe_gap) / self.config.following_time_s))
        throttle = float(np.clip(self.config.speed_gain * (desired_speed - speed), -1, 1))
        return [steer, throttle]
