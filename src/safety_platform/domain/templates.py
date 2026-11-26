"""Built-in deterministic parameter templates. Native building arrives in Task 3."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from random import Random
from typing import Any, Mapping

from safety_platform.domain.spec import ScenarioSpec


@dataclass(frozen=True)
class FormField:
    path: str
    label: str
    unit: str | None
    default: str | int | float
    minimum: int | float | None
    maximum: int | float | None
    editable: bool = True


_COMMON_FIELDS = (
    FormField("map_spec.lane_count", "车道数", None, 2, 2, 2, False),
    FormField("map_spec.lane_width_m", "车道宽度", "m", 3.5, 3.5, 3.5, False),
    FormField("map_spec.duration_s", "仿真时长", "s", 10, 10, 10, False),
    FormField("ego_spec.lane_index", "自车起始车道", None, 0, 0, 0, False),
    FormField("ego_spec.speed_mps", "自车速度", "m/s", 12, 8, 22),
    FormField("actor_specs.0.lane_index", "目标车起始车道", None, 1, 0, 1, False),
    FormField("actor_specs.0.actor_id", "目标车 ID", None, "lead", None, None, False),
    FormField("actor_specs.0.speed_mps", "目标车速度", "m/s", 10, 6, 22),
    FormField("actor_specs.0.longitudinal_gap_m", "初始纵向距离", "m", 25, 15, 80),
    FormField("event_spec.start_s", "事件开始", "s", 2, 1, 5),
    FormField("event_spec.duration_s", "事件持续", "s", 3, 2, 4),
    FormField("seed", "随机种子", None, 42, 0, 2**32 - 1),
)


@dataclass(frozen=True)
class BuiltinScenarioType:
    template_id: str
    template_version: str = "1.0"

    @property
    def form_fields(self) -> list[dict[str, Any]]:
        fields = list(_COMMON_FIELDS)
        actor_lane = 0 if self.template_id == "front_brake" else 1
        fields = [FormField("actor_specs.0.lane_index", "目标车起始车道", None,
                            actor_lane, actor_lane, actor_lane, False)
                  if field.path == "actor_specs.0.lane_index" else field for field in fields]
        if self.template_id == "front_brake":
            fields.append(FormField("event_spec.deceleration_mps2", "减速度", "m/s²", 3, 1, 6))
        else:
            target = 0 if self.template_id == "cut_in" else 1
            fields.append(FormField("event_spec.target_lane_index", "目标车道", None,
                                    target, target, target, False))
        return [asdict(field) for field in fields]

    @property
    def json_schema(self) -> dict[str, Any]:
        schema = ScenarioSpec.model_json_schema()
        schema["properties"]["template_id"] = {"const": self.template_id}
        schema["properties"]["template_version"] = {"const": self.template_version}
        definitions = schema["$defs"]
        map_props = definitions["MapSpec"]["properties"]
        map_props["lane_count"] = {"type": "integer", "const": 2}
        map_props["lane_width_m"] = {"type": "number", "const": 3.5}
        map_props["duration_s"] = {"type": "number", "const": 10}
        ego_props = definitions["EgoSpec"]["properties"]
        ego_props["lane_index"] = {"type": "integer", "const": 0}
        ego_props["speed_mps"] = {"type": "number", "minimum": 8, "maximum": 22}
        actor_props = definitions["ActorSpec"]["properties"]
        actor_props["actor_id"]["default"] = "lead"
        actor_props["lane_index"] = {"type": "integer", "const": 0 if self.template_id == "front_brake" else 1}
        actor_props["speed_mps"] = {"type": "number", "minimum": 6, "maximum": 22}
        actor_props["longitudinal_gap_m"] = {"type": "number", "minimum": 15, "maximum": 80}
        schema["properties"]["actor_specs"]["maxItems"] = 1
        event_props = definitions["EventSpec"]["properties"]
        event_props["start_s"] = {"type": "number", "minimum": 1, "maximum": 5}
        event_props["duration_s"] = {"type": "number", "minimum": 2, "maximum": 4}
        if self.template_id == "front_brake":
            event_props["target_lane_index"] = {"const": None}
            event_props["deceleration_mps2"] = {"type": "number", "minimum": 1, "maximum": 6}
            definitions["EventSpec"]["required"].append("deceleration_mps2")
        else:
            event_props["target_lane_index"] = {"type": "integer", "const": 0 if self.template_id == "cut_in" else 1}
            event_props["deceleration_mps2"] = {"const": None}
            definitions["EventSpec"]["required"].append("target_lane_index")
        schema["properties"]["seed"] = {"type": "integer", "minimum": 0, "maximum": 2**32 - 1}
        schema["x-form-fields"] = self.form_fields
        schema["x-cross-field-rules"] = [
            "event.start_s + event.duration_s <= map.duration_s",
            "actor starts 15–80 m ahead without overlap",
            "lane and event target must match template semantics",
        ]
        return schema

    def _validate_semantics(self, spec: ScenarioSpec) -> None:
        if spec.template_id != self.template_id or spec.template_version != self.template_version:
            raise ValueError("template ID/version does not match registered type")
        road = spec.map_spec
        if road.lane_count != 2 or road.lane_width_m != 3.5 or road.duration_s != 10:
            raise ValueError("built-in version 1.0 requires a 2-lane, 3.5 m, 10 s straight map")
        if len(spec.actor_specs) != 1:
            raise ValueError("built-in version 1.0 requires exactly one traffic actor")
        ego, actor, event = spec.ego_spec, spec.actor_specs[0], spec.event_spec
        if ego.lane_index != 0:
            raise ValueError("built-in ego must start in lane 0")
        if not 8 <= ego.speed_mps <= 22 or not 6 <= actor.speed_mps <= 22:
            raise ValueError("vehicle speed is outside template range")
        if not 15 <= actor.longitudinal_gap_m <= 80:
            raise ValueError("actor must begin 15–80 m ahead without overlap")
        if not 1 <= event.start_s <= 5 or not 2 <= event.duration_s <= 4:
            raise ValueError("event time or duration is outside template range")
        if not 0 <= spec.seed < 2**32:
            raise ValueError("seed must be a uint32")
        if self.template_id == "cut_in":
            if actor.lane_index != 1 or event.target_lane_index != 0 or event.deceleration_mps2 is not None:
                raise ValueError("cut-in actor must move from neighboring lane 1 to ego lane 0")
        elif self.template_id == "front_brake":
            if actor.lane_index != 0 or event.target_lane_index is not None:
                raise ValueError("front-brake actor must start ahead in ego lane 0")
            if event.deceleration_mps2 is None or not 1 <= event.deceleration_mps2 <= 6:
                raise ValueError("front-brake deceleration must be 1–6 m/s²")
        elif self.template_id == "lane_change":
            if actor.lane_index != 1 or event.target_lane_index != 1 or event.deceleration_mps2 is not None:
                raise ValueError("ego must change to neighboring lane 1 with a traffic actor there")
        else:
            raise ValueError(f"unsupported built-in template: {self.template_id}")

    def validate(self, raw: Mapping[str, Any]) -> ScenarioSpec:
        return ScenarioSpec.model_validate(raw, context={"semantic_validator": self._validate_semantics})

    def sample(self, count: int, seed: int) -> list[ScenarioSpec]:
        rng = Random(seed)
        samples = []
        for _ in range(count):
            event: dict[str, Any] = {
                "start_s": round(rng.uniform(1, 5), 3),
                "duration_s": round(rng.uniform(2, 4), 3),
            }
            if self.template_id == "front_brake":
                event["deceleration_mps2"] = round(rng.uniform(1, 6), 3)
            else:
                event["target_lane_index"] = 0 if self.template_id == "cut_in" else 1
            raw = {
                "template_id": self.template_id,
                "template_version": self.template_version,
                "map_spec": {"lane_count": 2, "lane_width_m": 3.5, "duration_s": 10},
                "ego_spec": {"lane_index": 0, "speed_mps": round(rng.uniform(8, 22), 3)},
                "actor_specs": [{
                    "actor_id": "lead", "lane_index": 0 if self.template_id == "front_brake" else 1,
                    "speed_mps": round(rng.uniform(6, 22), 3),
                    "longitudinal_gap_m": round(rng.uniform(15, 80), 3),
                }],
                "event_spec": event,
                "seed": rng.randrange(0, 2**32),
            }
            samples.append(self.validate(raw))
        return samples

    def build_native(self, spec: ScenarioSpec, out_dir: Path) -> Any:
        raise NotImplementedError("native builder is implemented in Task 3")

    def check_event(self, trajectory: Any) -> bool:
        raise NotImplementedError("event checking is implemented in Task 3")


BUILTIN_TYPES = (
    BuiltinScenarioType("cut_in"),
    BuiltinScenarioType("front_brake"),
    BuiltinScenarioType("lane_change"),
)
