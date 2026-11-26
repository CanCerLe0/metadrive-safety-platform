# MetaDrive Safety Scenario Platform

[中文](README.md) | [English](README_EN.md)

This project builds on my [original graduation project](https://gitee.com/liu-shengdong-714/Intelligent-driving-scenario). It continues the research goal of driving scenario generation and safety management, using native MetaDrive scenarios as the foundation for reproducible scenario generation, simulation evaluation, and evidence management.

## Project goal

The platform is designed around a complete workflow: **safety requirements → parameterized scenarios → MetaDrive simulation → safety assessment → evidence traceability**. Researchers and testers can link requirements to scenario versions and run results, inspect metrics such as collisions and minimum time to collision, and trace the basis for each assessment. A risk model trained on real simulation results helps select useful scenarios within a limited run budget.

## Scope

- Use MetaDrive as the sole simulation engine. Each scenario version stores both an editable parameter specification and a native dataset reloadable by `ScenarioEnv`.
- Provide parameterized cut-in, front-braking, and lane-change scenarios, with a versioned registry for adding other scenario types.
- Manage safety requirements, scenarios, run evidence, and safety labels, including bidirectional traceability and retest prompts after changes.
- Show live MetaDrive top-down frames for individual runs; run batch experiments without rendering.
- Train a risk model on actual simulation outcomes and compare model-guided selection with random selection under the same budget. Natural-language input maps descriptions only to parameters of supported templates.

## Architecture

The backend uses Python 3.11, FastAPI, and SQLite, with an independent worker for MetaDrive simulation jobs. The frontend uses Vue 3 and TypeScript. Scenario specifications, native datasets, trajectories, metrics, and model versions form a reproducible evidence chain. The target runtime environment is macOS arm64.

## Design documents

- [Requirements baseline and design draft](docs/需求基线与设计草案.md) (Chinese)
- [Implementation plan](docs/项目实施计划.md) (Chinese)
- [Simulator compatibility validation](docs/仿真器兼容性验证.md) (Chinese)
- [Feature feasibility assessment](docs/功能可行性评估.md) (Chinese)
- [Related open-source projects research](docs/相似开源项目调研.md) (Chinese)
