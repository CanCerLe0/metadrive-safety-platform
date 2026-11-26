import json
import pickle
from pathlib import Path

import pytest

from safety_platform.domain.registry import validate_spec
from safety_platform.sim.builder import build_native
from safety_platform.sim.bundle import BundleIntegrityError, verify_bundle
from tests.factories import spec_data


def test_invalid_bundle_rejected_before_pickle_load(tmp_path: Path, monkeypatch) -> None:
    bundle = build_native(validate_spec(spec_data()), tmp_path / "bundle")
    original = pickle.load

    def forbidden_load(*args, **kwargs):
        raise AssertionError("pickle was loaded before integrity verification")

    monkeypatch.setattr(pickle, "load", forbidden_load)
    bundle.mapping_path.unlink()
    with pytest.raises(BundleIntegrityError):
        verify_bundle(bundle.directory)
    monkeypatch.setattr(pickle, "load", original)

    bundle = build_native(validate_spec(spec_data()), tmp_path / "again")
    bundle.scene_path.write_bytes(b"tampered")
    monkeypatch.setattr(pickle, "load", forbidden_load)
    with pytest.raises(BundleIntegrityError):
        verify_bundle(bundle.directory)


def test_manifest_rejects_path_traversal_and_unlisted_files(tmp_path: Path) -> None:
    bundle = build_native(validate_spec(spec_data()), tmp_path / "bundle")
    manifest = json.loads(bundle.manifest_path.read_text())
    manifest["files"]["../escape.pkl"] = manifest["files"].pop(bundle.scene_path.name)
    bundle.manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(BundleIntegrityError):
        verify_bundle(bundle.directory)

    bundle = build_native(validate_spec(spec_data()), tmp_path / "again")
    (bundle.directory / "extra.pkl").write_bytes(b"unknown")
    with pytest.raises(BundleIntegrityError):
        verify_bundle(bundle.directory)


def test_manifest_records_rebuild_inputs_and_file_hashes(tmp_path: Path) -> None:
    spec = validate_spec(spec_data())
    bundle = build_native(spec, tmp_path / "bundle")
    manifest = verify_bundle(bundle.directory)
    assert manifest.scene_id == spec.fingerprint()
    assert manifest.template_version == spec.template_version
    assert manifest.seed == spec.seed
    assert len(manifest.metadrive_sha) == 40
    assert manifest.generator_version
    assert manifest.reactive_traffic is False
    assert json.loads(bundle.spec_path.read_text()) == spec.model_dump(mode="json")
    assert set(manifest.files) == {bundle.scene_path.name, "dataset_summary.pkl",
                                   "dataset_mapping.pkl", "scenario_spec.json"}


def test_manifest_identity_must_match_spec_and_installed_simulator(tmp_path: Path) -> None:
    bundle = build_native(validate_spec(spec_data()), tmp_path / "bundle")
    manifest = json.loads(bundle.manifest_path.read_text())
    manifest["scene_id"] = "forged"
    bundle.manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(BundleIntegrityError):
        verify_bundle(bundle.directory)

    manifest["scene_id"] = validate_spec(spec_data()).fingerprint()
    manifest["metadrive_sha"] = "0" * 40
    bundle.manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(BundleIntegrityError):
        verify_bundle(bundle.directory)
