# MetaDrive Safety Scenario Platform

[中文](README.md) | [English](README_EN.md)

This project is an improved follow-up to my [original graduation project](https://gitee.com/liu-shengdong-714/Intelligent-driving-scenario). It carries forward that project's research goals in driving scenario generation and safety management, while redesigning and implementing native MetaDrive scenarios, simulation evidence traceability, and risk model training.

The goal is to establish a reproducible workflow from **safety requirements → parameterized scenarios → MetaDrive simulation → safety assessment → evidence traceability**, and to train a risk model on actual simulation data. This repository is currently at the **project structure initialization** stage. Native scenario reloading, live top-down rendering, and the application features have not yet been validated or implemented.

## Design and implementation order

- [Requirements baseline and design draft](docs/design.md) (v0.13; Chinese)
- [Implementation plan](docs/implementation-plan.md) (Tasks 1–12; Chinese)
- [Related open-source projects research](docs/research.md) (Chinese)

Task 1 first verifies export of a native MetaDrive scenario, reloading it with `ScenarioEnv`, and continuous top-down frame rendering. Scenario templates, the runner, business API, web interface, and risk model follow. Natural-language template configuration begins only after independent acceptance of the first release.

## Local setup

The target environment is macOS arm64 with Python 3.11. Keep uv and Matplotlib caches inside the project:

```sh
export UV_CACHE_DIR="$PWD/.cache/uv"
export UV_PYTHON_INSTALL_DIR="$PWD/.cache/uv/python"
export MPLCONFIGDIR="$PWD/.cache/matplotlib"
uv python install 3.11
uv venv --python 3.11
uv sync --dev
```

`pyproject.toml` currently uses the official `MetaDrive-0.4.3` tag as a compatibility candidate. The lockfile records the tag's source SHA, but it becomes a compatibility baseline only after native scenario reloading and frame rendering pass validation. There is no runnable service yet.

## Directory layout

| Path | Planned responsibility |
| --- | --- |
| `src/safety_platform/domain/` | Scenario specifications, templates, and type registration |
| `src/safety_platform/sim/` | Native scenarios, execution, metrics, and frames |
| `src/safety_platform/storage/` | SQLite persistence and versioning |
| `src/safety_platform/api/`, `jobs/` | HTTP API and independent worker |
| `src/safety_platform/ml/`, `nl/` | Risk modeling and second-phase language parsing |
| `web/` | Vue 3 frontend (planned for a later task) |
| `tests/` | Unit tests and integration tests with MetaDrive |
| `docs/` | Design, plan, compatibility, and feasibility records |

Runtime data, virtual environments, caches, databases, native `.pkl` files, and model binaries are excluded from Git.
