from pathlib import Path

from safety_platform.sim.probe import probe_native


def test_native_export_then_scenarioenv_replay(tmp_path: Path) -> None:
    """A saved native dataset must replay a traffic cut-in with live ego control."""
    result = probe_native(tmp_path)

    assert result.dataset_dir.is_dir()
    assert (result.dataset_dir / "dataset_summary.pkl").is_file()
    assert (result.dataset_dir / "dataset_mapping.pkl").is_file()
    assert result.scenario_id
    assert result.metadrive_version
    assert len(result.metadrive_sha) == 40
    assert result.steps >= 100
    assert result.actor_changed_lane
    assert result.ego_moved
    assert result.dataset_index_readable
    assert result.topdown_frames_valid
    assert result.mean_render_ms > 0
    assert result.peak_memory_mb > 0
