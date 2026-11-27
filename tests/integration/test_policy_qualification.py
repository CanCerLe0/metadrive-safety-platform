from safety_platform.domain.registry import validate_spec
from safety_platform.sim.builder import build_native
from safety_platform.sim.policy import PolicyConfig
from safety_platform.sim.runner import run_bundle
from tests.factories import spec_data


def test_policy_qualification_on_twenty_safe_two_lane_seeds(tmp_path):
    outcomes = []
    for seed in range(20):
        spec = validate_spec(spec_data(
            "cut_in", seed=seed, ego_spec__speed_mps=10.0 + seed * 0.1,
            actor_specs__0__speed_mps=11.0 + seed * 0.1,
            actor_specs__0__longitudinal_gap_m=70.0 + seed * 0.25,
        ))
        bundle = build_native(spec, tmp_path / str(seed))
        outcomes.append(run_bundle(bundle.directory, PolicyConfig(), seed=seed))
    assert sum(outcome.completed and not outcome.collision for outcome in outcomes) >= 19
    assert all(outcome.valid for outcome in outcomes)
