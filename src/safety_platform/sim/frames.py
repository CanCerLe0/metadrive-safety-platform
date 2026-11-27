"""Ephemeral latest-frame transport for a single visual run."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol
from uuid import uuid4


class FrameSink(Protocol):
    def publish(self, jpeg: bytes, sim_time_s: float) -> None: ...


class LatestFrameSink:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.last_sim_time_s = 0.0
        self.frame_count = 0

    def publish(self, jpeg: bytes, sim_time_s: float) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_bytes(jpeg)
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
        self.last_sim_time_s = sim_time_s
        self.frame_count += 1
