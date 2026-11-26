"""Small valid scene inputs shared by domain tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def spec_data(template_id: str = "cut_in", **changes: Any) -> dict[str, Any]:
    actor_lane = 1 if template_id in {"cut_in", "lane_change"} else 0
    event = {"start_s": 2.0, "duration_s": 3.0}
    if template_id == "front_brake":
        event["deceleration_mps2"] = 3.0
    else:
        event["target_lane_index"] = 0 if template_id == "cut_in" else 1
    data = {
        "template_id": template_id,
        "template_version": "1.0",
        "map_spec": {"lane_count": 2, "lane_width_m": 3.5, "duration_s": 10.0},
        "ego_spec": {"lane_index": 0, "speed_mps": 12.0},
        "actor_specs": [
            {"actor_id": "lead", "lane_index": actor_lane, "speed_mps": 10.0, "longitudinal_gap_m": 25.0}
        ],
        "event_spec": event,
        "seed": 42,
    }
    for path, value in changes.items():
        target = data
        parts = path.split("__")
        for part in parts[:-1]:
            target = target[int(part)] if isinstance(target, list) else target[part]
        target[parts[-1]] = value
    return deepcopy(data)
