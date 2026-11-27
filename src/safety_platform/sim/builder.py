"""Dispatch registered native builders, validate events and export datasets."""

from __future__ import annotations

import json
from pathlib import Path

from metadrive.scenario.scenario_description import ScenarioDescription as SD
from metadrive.scenario.utils import save_dataset

from safety_platform.domain.registry import DEFAULT_REGISTRY, ScenarioRegistry
from safety_platform.domain.spec import ScenarioSpec
from safety_platform.sim.bundle import (
    MANIFEST_FILE, SPEC_FILE, NativeBundle, verify_bundle, write_manifest,
)


def build_native(
    spec: ScenarioSpec, out_dir: Path, *, registry: ScenarioRegistry = DEFAULT_REGISTRY
) -> NativeBundle:
    """Build a registered scenario into an independently loadable native bundle."""
    scenario_type = registry.get(spec.template_id, spec.template_version)
    spec = scenario_type.validate(spec.model_dump())
    directory = Path(out_dir)
    if directory.exists() and any(directory.iterdir()):
        raise FileExistsError(f"bundle directory must be empty: {directory}")
    directory.mkdir(parents=True, exist_ok=True)
    scene = scenario_type.build_native(spec, directory)
    scene.pop("safety_geometry", None)
    event_track_id = scene.pop("safety_event_track_id", spec.actor_specs[0].actor_id)
    scene[SD.METADATA]["safety_event_track_id"] = str(event_track_id)
    if not scenario_type.check_event(scene[SD.TRACKS][event_track_id]["state"]):
        raise ValueError(f"registered event check failed: {spec.template_id}")
    SD.sanity_check(scene, check_self_type=True)
    save_dataset([scene], "safety-platform", "1", directory)
    scene_files = list(directory.glob("sd_*.pkl"))
    if len(scene_files) != 1:
        raise RuntimeError("MetaDrive did not export exactly one scenario")
    (directory / SPEC_FILE).write_text(
        json.dumps(spec.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    write_manifest(directory, spec, scene_files[0].name)
    verify_bundle(directory)
    return NativeBundle(directory, spec.fingerprint(), scene_files[0],
                        directory / "dataset_summary.pkl", directory / "dataset_mapping.pkl",
                        directory / MANIFEST_FILE, directory / SPEC_FILE)
