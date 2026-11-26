# MetaDrive Safety Scenario Platform

[中文](README.md) | [English](README_EN.md)

This project is an improved follow-up to my [original graduation project](https://gitee.com/liu-shengdong-714/Intelligent-driving-scenario). It carries forward that project's research goals in driving scenario generation and safety management, while redesigning and implementing native MetaDrive scenarios, simulation evidence traceability, and risk model training.

The goal is to establish a reproducible workflow from **safety requirements → parameterized scenarios → MetaDrive simulation → safety assessment → evidence traceability**, and to train a risk model on actual simulation data. Task 1 has validated native scenario reloading and continuous real top-down frames. Templates, the application features, and the risk model remain for later tasks.

## Design and implementation order

- [Requirements baseline and design draft](docs/需求基线与设计草案.md) (v0.13; Chinese)
- [Implementation plan](docs/项目实施计划.md) (Tasks 1–12; Chinese)
- [Related open-source projects research](docs/相似开源项目调研.md) (Chinese)

Task 1 first verifies export of a native MetaDrive scenario, reloading it with `ScenarioEnv`, and continuous top-down frame rendering. Scenario templates, the runner, business API, web interface, and risk model follow. Natural-language template configuration begins only after independent acceptance of the first release.

## Local setup

The target environment is macOS arm64 with Python 3.11. Keep uv and Matplotlib caches inside the project:

```sh
export UV_CACHE_DIR="$PWD/.cache/uv"
export UV_PYTHON_INSTALL_DIR="$PWD/.cache/uv/python"
export MPLCONFIGDIR="$PWD/.cache/matplotlib"
uv python install 3.11
uv venv --python 3.11
uv sync --dev --locked
```

`pyproject.toml` and `uv.lock` pin the official `MetaDrive-0.4.3` source commit `5bf8ea8909c4643a4099a250e6f5fb89c695d8b4`. The first simulation run also downloads MetaDrive's official assets. Run the Task 1 integration probe with `uv run --locked pytest tests/integration/test_native_probe.py -q`. See the [compatibility record](docs/仿真器兼容性验证.md) for results and limits. There is no runnable service yet.

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
