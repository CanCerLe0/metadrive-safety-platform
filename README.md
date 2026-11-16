# MetaDrive 安全场景平台

[中文](README.md) | [English](README_EN.md)

本项目是在本人[原本科毕业设计项目](https://gitee.com/liu-shengdong-714/Intelligent-driving-scenario)基础上开展的改进型项目。它延续原项目对智能驾驶场景生成与安全管理的研究目标，并围绕 MetaDrive 原生场景、仿真证据追溯和风险模型训练重新设计与实现。

项目目标是建立“安全需求 → 参数化场景 → MetaDrive 仿真 → 安全判定 → 证据追溯”的可复现流程，并用实际仿真数据训练风险模型。当前仓库处于**项目结构初始化**阶段，尚未完成原生场景重载、实时俯视画面或业务功能验证。

## 依据与实施顺序

- [需求基线与设计草案](docs/design.md)（v0.13）
- [实施计划](docs/implementation-plan.md)（Task 1–12）
- [相似开源项目调研](docs/research.md)

先完成 Task 1 的 MetaDrive 原生场景导出、`ScenarioEnv` 重载和连续俯视出帧验证，再实现模板、运行器、业务 API、网页和风险模型。第一版通过独立验收后才接入自然语言配置。

## 本地准备

目标环境为 macOS arm64 和 Python 3.11。所有 uv 命令使用项目内缓存：

```sh
export UV_CACHE_DIR="$PWD/.cache/uv"
export UV_PYTHON_INSTALL_DIR="$PWD/.cache/uv/python"
export MPLCONFIGDIR="$PWD/.cache/matplotlib"
uv python install 3.11
uv venv --python 3.11
uv sync --dev
```

`pyproject.toml` 暂以官方 `MetaDrive-0.4.3` tag 为能力验证候选。锁文件已记录该 tag 对应的源码 SHA，但只有通过原生重载和出帧验证后，才能将其作为兼容性基线。当前尚无可启动服务。

## 目录

| 路径 | 计划职责 |
| --- | --- |
| `src/safety_platform/domain/` | 场景规格、模板与类型注册 |
| `src/safety_platform/sim/` | 原生场景、运行、指标与画面 |
| `src/safety_platform/storage/` | SQLite 持久化与版本 |
| `src/safety_platform/api/`、`jobs/` | HTTP 接口与独立 worker |
| `src/safety_platform/ml/`、`nl/` | 风险模型与第二阶段语言解析 |
| `web/` | Vue 3 前端（后续任务实现） |
| `tests/` | 单元与真实 MetaDrive 集成测试 |
| `docs/` | 设计、计划、兼容性与可行性记录 |

运行数据、虚拟环境、缓存、数据库、原生 `.pkl` 和模型二进制不进入 Git。
