from safety_platform.domain.registry import sample_specs, validate_spec


def test_sampling_repeatable():
    assert sample_specs("cut_in", 10, 42) == sample_specs("cut_in", 10, 42)
    assert sample_specs("cut_in", 10, 42) != sample_specs("cut_in", 10, 43)
    for template_id in ("cut_in", "front_brake", "lane_change"):
        samples = sample_specs(template_id, 10, 42)
        assert len(samples) == 10
        assert len({spec.fingerprint() for spec in samples}) == 10
        assert all(validate_spec(spec.model_dump()) == spec for spec in samples)


def test_invalid_sampling_count():
    try:
        sample_specs("cut_in", -1, 42)
    except ValueError as exc:
        assert "count" in str(exc)
    else:
        raise AssertionError("negative count was accepted")
