"""Manifest and integrity gate for platform-generated native datasets."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from safety_platform.domain.spec import ScenarioSpec

GENERATOR_VERSION = "1.0"
SPEC_FILE = "scenario_spec.json"
MANIFEST_FILE = "manifest.json"
INDEX_FILES = {"dataset_summary.pkl", "dataset_mapping.pkl"}


class BundleIntegrityError(ValueError):
    """A bundle is incomplete, altered, or has an unsafe path."""


@dataclass(frozen=True)
class NativeBundle:
    directory: Path
    scene_id: str
    scene_path: Path
    summary_path: Path
    mapping_path: Path
    manifest_path: Path
    spec_path: Path


@dataclass(frozen=True)
class BundleManifest:
    scene_id: str
    scene_file: str
    template_id: str
    template_version: str
    generator_version: str
    metadrive_version: str
    metadrive_sha: str
    seed: int
    reactive_traffic: bool
    files: dict[str, str]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_manifest(directory: Path, spec: ScenarioSpec, scene_file: str) -> BundleManifest:
    from safety_platform.sim.probe import _metadrive_identity

    version, sha = _metadrive_identity()
    files = {name: _sha256(directory / name) for name in
             (scene_file, *sorted(INDEX_FILES), SPEC_FILE)}
    manifest = BundleManifest(
        scene_id=spec.fingerprint(), scene_file=scene_file,
        template_id=spec.template_id, template_version=spec.template_version,
        generator_version=GENERATOR_VERSION, metadrive_version=version,
        metadrive_sha=sha, seed=spec.seed, reactive_traffic=False, files=files,
    )
    (directory / MANIFEST_FILE).write_text(
        json.dumps(manifest.__dict__, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def verify_bundle(bundle_dir: Path) -> BundleManifest:
    """Check every path and hash without deserializing any pickle content."""
    directory = Path(bundle_dir)
    manifest_path = directory / MANIFEST_FILE
    if not directory.is_dir() or directory.is_symlink() or not manifest_path.is_file() or manifest_path.is_symlink():
        raise BundleIntegrityError("bundle directory or manifest is missing or unsafe")
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = BundleManifest(**raw)
    except (OSError, ValueError, TypeError) as exc:
        raise BundleIntegrityError("invalid bundle manifest") from exc
    if not isinstance(manifest.files, dict) or not isinstance(manifest.scene_file, str):
        raise BundleIntegrityError("invalid file manifest")
    expected = {manifest.scene_file, *INDEX_FILES, SPEC_FILE}
    if (not manifest.scene_file.startswith("sd_") or not manifest.scene_file.endswith(".pkl")
            or set(manifest.files) != expected or manifest.reactive_traffic is not False):
        raise BundleIntegrityError("bundle file list or playback mode is invalid")
    actual = {entry.name for entry in directory.iterdir()}
    if actual != expected | {MANIFEST_FILE}:
        raise BundleIntegrityError("bundle contains missing or unlisted files")
    for name, expected_hash in manifest.files.items():
        if Path(name).name != name or name in {".", ".."} or not isinstance(expected_hash, str):
            raise BundleIntegrityError("unsafe bundle path or hash")
        path = directory / name
        if not path.is_file() or path.is_symlink() or len(expected_hash) != 64 or _sha256(path) != expected_hash:
            raise BundleIntegrityError(f"bundle file missing or altered: {name}")
    try:
        spec = ScenarioSpec.model_validate_json((directory / SPEC_FILE).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise BundleIntegrityError("invalid bundled scenario spec") from exc
    if (manifest.scene_id != spec.fingerprint() or manifest.template_id != spec.template_id
            or manifest.template_version != spec.template_version or manifest.seed != spec.seed):
        raise BundleIntegrityError("manifest does not match bundled scenario spec")
    from safety_platform.sim.probe import _metadrive_identity

    version, sha = _metadrive_identity()
    if manifest.metadrive_version != version or manifest.metadrive_sha != sha:
        raise BundleIntegrityError("bundle simulator version does not match installed MetaDrive")
    return manifest
