"""Local paths used by the probe and, later, the platform services."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VAR_DIR = PROJECT_ROOT / "var"
