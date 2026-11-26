"""Versioned scenario type dispatch used by every generic entry point."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Protocol, runtime_checkable

from safety_platform.domain.spec import ScenarioSpec
from safety_platform.domain.templates import BUILTIN_TYPES


class UnknownScenarioTypeError(LookupError):
    pass


@runtime_checkable
class ScenarioType(Protocol):
    template_id: str
    template_version: str

    @property
    def json_schema(self) -> dict[str, Any]: ...

    @property
    def form_fields(self) -> list[dict[str, Any]]: ...

    def validate(self, raw: Mapping[str, Any]) -> ScenarioSpec: ...

    def sample(self, count: int, seed: int) -> list[ScenarioSpec]: ...

    def build_native(self, spec: ScenarioSpec, out_dir: Path) -> Any: ...

    def check_event(self, trajectory: Any) -> bool: ...


class ScenarioRegistry:
    def __init__(self) -> None:
        self._types: dict[tuple[str, str], ScenarioType] = {}

    def register(self, scenario_type: ScenarioType) -> None:
        if not isinstance(scenario_type, ScenarioType):
            raise TypeError("scenario type must implement the ScenarioType contract")
        key = (scenario_type.template_id, scenario_type.template_version)
        if not key[0] or not key[1]:
            raise ValueError("template ID and version must be nonempty")
        if key in self._types:
            raise ValueError(f"scenario type {key} already registered")
        self._types[key] = scenario_type

    def get(self, template_id: str, version: str | None = None) -> ScenarioType:
        if version is None:
            versions = [ver for key_id, ver in self._types if key_id == template_id]
            if not versions:
                raise UnknownScenarioTypeError(f"unknown scenario type: {template_id}")
            version = max(versions, key=_version_key)
        try:
            return self._types[(template_id, version)]
        except KeyError as exc:
            raise UnknownScenarioTypeError(f"unknown scenario type/version: {template_id}@{version}") from exc

    def list(self, *, include_history: bool = False) -> list[ScenarioType]:
        if include_history:
            return [self._types[key] for key in sorted(self._types, key=lambda k: (k[0], _version_key(k[1])))]
        return [self.get(template_id) for template_id in sorted({key[0] for key in self._types})]


def _version_key(version: str) -> tuple[tuple[int, int | str], ...]:
    return tuple((0, int(part)) if part.isdigit() else (1, part) for part in version.split("."))


DEFAULT_REGISTRY = ScenarioRegistry()
for _scenario_type in BUILTIN_TYPES:
    DEFAULT_REGISTRY.register(_scenario_type)


def validate_spec(raw: Mapping[str, Any], *, registry: ScenarioRegistry = DEFAULT_REGISTRY) -> ScenarioSpec:
    template_id = raw.get("template_id")
    version = raw.get("template_version")
    scenario_type = registry.get(str(template_id), str(version) if version is not None else None)
    if version is None:
        raw = {**raw, "template_version": scenario_type.template_version}
    return scenario_type.validate(raw)


def sample_specs(
    template_id: str, count: int, seed: int, *, registry: ScenarioRegistry = DEFAULT_REGISTRY
) -> list[ScenarioSpec]:
    if count < 0:
        raise ValueError("count must be nonnegative")
    scenario_type = registry.get(template_id)
    samples = scenario_type.sample(count, seed)
    if len(samples) != count:
        raise ValueError("scenario sampler returned the wrong count")
    return [scenario_type.validate(sample.model_dump()) for sample in samples]
