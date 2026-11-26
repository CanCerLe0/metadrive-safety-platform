import pytest
from pydantic import ValidationError

from safety_platform.domain.registry import validate_spec
from safety_platform.domain.spec import ScenarioSpec
from tests.factories import spec_data


@pytest.mark.parametrize(
    "changes",
    [
        {"actor_specs__0__longitudinal_gap_m": 0.0},
        {"event_spec__start_s": -1.0},
        {"ego_spec__speed_mps": 23.0},
        {"event_spec__start_s": 9.0, "event_spec__duration_s": 3.0},
    ],
)
def test_cut_in_constraints(changes):
    with pytest.raises(ValidationError):
        validate_spec(spec_data(**changes))


def test_three_template_semantics():
    for template_id in ("cut_in", "front_brake", "lane_change"):
        spec = validate_spec(spec_data(template_id))
        assert spec.template_id == template_id
        assert spec.map_spec.lane_width_m == 3.5

    with pytest.raises(ValidationError):
        validate_spec(spec_data("cut_in", actor_specs__0__lane_index=0))
    with pytest.raises(ValidationError):
        validate_spec(spec_data("front_brake", event_spec__deceleration_mps2=0))
    with pytest.raises(ValidationError):
        validate_spec(spec_data("lane_change", event_spec__target_lane_index=0))


def test_fingerprint_uses_normalized_parameters():
    raw = spec_data()
    spec = validate_spec(raw)
    reordered = dict(reversed(list(raw.items())))
    assert spec.fingerprint() == validate_spec(reordered).fingerprint()
    assert spec.fingerprint() != validate_spec(spec_data(ego_spec__speed_mps=13)).fingerprint()


def test_nonfinite_numbers_are_rejected():
    raw = spec_data()
    raw["actor_specs"].append({"actor_id": "second", "lane_index": 1,
                               "speed_mps": 10, "longitudinal_gap_m": float("inf")})
    with pytest.raises(ValidationError):
        ScenarioSpec.model_validate(raw)


def test_boolean_is_not_accepted_as_numeric_parameter():
    with pytest.raises(ValidationError):
        validate_spec(spec_data(seed=True))
    with pytest.raises(ValidationError):
        validate_spec(spec_data(event_spec__target_lane_index=False))


@pytest.mark.parametrize("template_id", ["cut_in", "front_brake"])
def test_front_actor_has_nonoverlapping_nominal_headway_at_event_start(template_id):
    raw = spec_data(
        template_id,
        ego_spec__speed_mps=22.0,
        actor_specs__0__speed_mps=6.0,
        actor_specs__0__longitudinal_gap_m=15.0,
        event_spec__start_s=5.0,
    )
    with pytest.raises(ValidationError, match="event-start headway"):
        validate_spec(raw)
