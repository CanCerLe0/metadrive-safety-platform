"""Editable, JSON-friendly scenario parameters and stable identity."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, model_validator


class StrictSpecModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class MapSpec(StrictSpecModel):
    lane_count: int = Field(ge=1, strict=True)
    lane_width_m: float = Field(gt=0, strict=True)
    duration_s: float = Field(gt=0, strict=True)


class EgoSpec(StrictSpecModel):
    lane_index: int = Field(ge=0, strict=True)
    speed_mps: float = Field(ge=0, strict=True)


class ActorSpec(StrictSpecModel):
    actor_id: str = Field(min_length=1)
    lane_index: int = Field(ge=0, strict=True)
    speed_mps: float = Field(ge=0, strict=True)
    longitudinal_gap_m: float = Field(strict=True)


class EventSpec(StrictSpecModel):
    start_s: float = Field(ge=0, strict=True)
    duration_s: float = Field(gt=0, strict=True)
    target_lane_index: int | None = Field(default=None, ge=0, strict=True)
    deceleration_mps2: float | None = Field(default=None, gt=0, strict=True)


class ScenarioSpec(StrictSpecModel):
    template_id: str = Field(min_length=1)
    template_version: str = Field(min_length=1)
    map_spec: MapSpec
    ego_spec: EgoSpec
    actor_specs: tuple[ActorSpec, ...] = Field(min_length=1)
    event_spec: EventSpec
    seed: int = Field(strict=True)

    @model_validator(mode="after")
    def check_geometry_and_template(self, info: ValidationInfo) -> "ScenarioSpec":
        if self.ego_spec.lane_index >= self.map_spec.lane_count:
            raise ValueError("ego lane_index is outside the map")
        if any(actor.lane_index >= self.map_spec.lane_count for actor in self.actor_specs):
            raise ValueError("actor lane_index is outside the map")
        if self.event_spec.target_lane_index is not None and self.event_spec.target_lane_index >= self.map_spec.lane_count:
            raise ValueError("event target_lane_index is outside the map")
        if self.event_spec.start_s + self.event_spec.duration_s > self.map_spec.duration_s:
            raise ValueError("event must finish before simulation ends")
        ids = [actor.actor_id for actor in self.actor_specs]
        if len(ids) != len(set(ids)):
            raise ValueError("actor IDs must be unique")
        validator = (info.context or {}).get("semantic_validator") if isinstance(info.context, dict) else None
        if validator is not None:
            validator(self)
        return self

    def fingerprint(self) -> str:
        """SHA-256 of normalized, sorted parameters, including the replay seed."""
        normalized: dict[str, Any] = self.model_dump(mode="json", exclude_none=True)
        encoded = json.dumps(normalized, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
