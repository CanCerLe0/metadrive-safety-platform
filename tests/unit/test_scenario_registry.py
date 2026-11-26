import pytest

from safety_platform.domain.registry import (
    DEFAULT_REGISTRY,
    ScenarioRegistry,
    UnknownScenarioTypeError,
    sample_specs,
    validate_spec,
)
from safety_platform.domain.spec import ScenarioSpec
from tests.factories import spec_data


class FourthType:
    template_id = "test_fourth"

    def __init__(self, version: str):
        self.template_version = version

    @property
    def json_schema(self):
        return ScenarioSpec.model_json_schema()

    @property
    def form_fields(self):
        return DEFAULT_REGISTRY.get("cut_in").form_fields

    def validate(self, raw):
        spec = ScenarioSpec.model_validate(raw)
        if spec.template_id != self.template_id or spec.template_version != self.template_version:
            raise ValueError("wrong test type or version")
        return spec

    def sample(self, count, seed):
        return [self.validate(spec_data(self.template_id,
                                        template_version=self.template_version,
                                        seed=seed + i)) for i in range(count)]

    def build_native(self, spec, out_dir):
        raise NotImplementedError

    def check_event(self, trajectory):
        return True


def test_fourth_type_catalog_validation_sampling_and_versions():
    registry = ScenarioRegistry()
    v1 = FourthType("1.0")
    v2 = FourthType("2.0")
    registry.register(v1)
    registry.register(v2)
    assert registry.get("test_fourth") is v2
    assert registry.get("test_fourth", "1.0") is v1
    assert registry.list() == [v2]
    assert registry.list(include_history=True) == [v1, v2]
    assert any(field["unit"] == "m/s" for field in registry.get("test_fourth").form_fields)
    assert validate_spec(spec_data("test_fourth"), registry=registry).template_version == "1.0"
    assert len(sample_specs("test_fourth", 3, 9, registry=registry)) == 3
    assert all(s.template_version == "2.0" for s in sample_specs("test_fourth", 3, 9, registry=registry))


def test_unknown_type_and_version_are_explicit():
    registry = ScenarioRegistry()
    with pytest.raises(UnknownScenarioTypeError, match="missing"):
        registry.get("missing")
    registry.register(FourthType("1.0"))
    with pytest.raises(UnknownScenarioTypeError, match="9.0"):
        registry.get("test_fourth", "9.0")
    with pytest.raises(ValueError, match="already registered"):
        registry.register(FourthType("1.0"))


def test_release_version_supersedes_prerelease():
    registry = ScenarioRegistry()
    prerelease = FourthType("1.0-rc1")
    release = FourthType("1.0")
    registry.register(prerelease)
    registry.register(release)
    assert registry.get("test_fourth") is release
    assert registry.list(include_history=True) == [prerelease, release]


def test_numeric_version_order_and_unsupported_format():
    registry = ScenarioRegistry()
    registry.register(FourthType("1.9"))
    registry.register(FourthType("1.10"))
    assert registry.get("test_fourth").template_version == "1.10"
    with pytest.raises(ValueError, match="version"):
        registry.register(FourthType("next"))


def test_dotted_prerelease_sorts_before_release():
    registry = ScenarioRegistry()
    prerelease = FourthType("1.0-rc.1")
    release = FourthType("1.0")
    registry.register(prerelease)
    registry.register(release)
    assert registry.list(include_history=True) == [prerelease, release]
    assert registry.get("test_fourth") is release


def test_equivalent_release_aliases_cannot_make_latest_order_dependent():
    registry = ScenarioRegistry()
    registry.register(FourthType("1.0"))
    with pytest.raises(ValueError, match="equivalent version"):
        registry.register(FourthType("1.0.0"))


def test_builtin_catalog_exposes_unit_defaults_and_json_bounds():
    assert {item.template_id for item in DEFAULT_REGISTRY.list()} == {"cut_in", "front_brake", "lane_change"}
    for item in DEFAULT_REGISTRY.list():
        fields = {field["path"]: field for field in item.form_fields}
        assert fields["ego_spec.speed_mps"]["unit"] == "m/s"
        assert fields["actor_specs.0.longitudinal_gap_m"]["default"] == 25
        schema = item.json_schema
        assert schema["$defs"]["EgoSpec"]["properties"]["speed_mps"]["minimum"] == 8
        assert schema["$defs"]["EgoSpec"]["properties"]["speed_mps"]["maximum"] == 22
        assert schema["$defs"]["ActorSpec"]["properties"]["longitudinal_gap_m"]["minimum"] == 15
        assert schema["$defs"]["ActorSpec"]["properties"]["actor_id"]["default"] == "lead"
        assert schema["$defs"]["MapSpec"]["properties"]["lane_width_m"]["const"] == 3.5
    brake = DEFAULT_REGISTRY.get("front_brake")
    assert {field["unit"] for field in brake.form_fields if field["path"] == "event_spec.deceleration_mps2"} == {"m/s²"}


def _default_raw_from_catalog(scenario_type):
    raw = {"template_id": scenario_type.template_id, "template_version": scenario_type.template_version,
           "map_spec": {}, "ego_spec": {}, "actor_specs": [{}], "event_spec": {}}
    for field in scenario_type.form_fields:
        target = raw
        path = field["path"].split(".")
        for part in path[:-1]:
            target = target[int(part)] if isinstance(target, list) else target[part]
        target[path[-1]] = field["default"]
    return raw


def test_catalog_defaults_make_a_valid_scene_for_builtin_and_fourth_type():
    registry = ScenarioRegistry()
    registry.register(FourthType("1.0"))
    for scenario_type in [*DEFAULT_REGISTRY.list(), registry.get("test_fourth")]:
        raw = _default_raw_from_catalog(scenario_type)
        assert validate_spec(raw, registry=DEFAULT_REGISTRY if scenario_type.template_id != "test_fourth" else registry)


def test_catalog_metadata_is_independent_between_calls():
    scene_type = DEFAULT_REGISTRY.get("cut_in")
    schema = scene_type.json_schema
    schema["x-form-fields"][0]["default"] = 999
    assert scene_type.json_schema["x-form-fields"][0]["default"] != 999
    assert DEFAULT_REGISTRY.get("front_brake").json_schema["x-form-fields"][0]["default"] != 999


def test_catalog_cross_field_rules_reference_real_field_paths():
    schema = DEFAULT_REGISTRY.get("cut_in").json_schema
    rule = schema["x-cross-field-rules"][0]
    for field_path in ("event_spec.start_s", "event_spec.duration_s", "map_spec.duration_s"):
        assert field_path in rule
    lane_rule = schema["x-cross-field-rules"][2]
    for field_path in ("ego_spec.lane_index", "actor_specs.0.lane_index", "event_spec.target_lane_index"):
        assert field_path in lane_rule


def test_front_actor_catalog_reports_headway_constraint():
    for template_id in ("cut_in", "front_brake"):
        rules = " ".join(DEFAULT_REGISTRY.get(template_id).json_schema["x-cross-field-rules"])
        assert "actor_specs.0.longitudinal_gap_m" in rules
        assert "ego_spec.speed_mps" in rules
        assert "4.5" in rules
    lane_change_rules = " ".join(DEFAULT_REGISTRY.get("lane_change").json_schema["x-cross-field-rules"])
    assert "4.5" not in lane_change_rules
