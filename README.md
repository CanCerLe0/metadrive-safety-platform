# MetaDrive 安全场景平台

[中文](README.md) | [English](README_EN.md)

本项目是在本人[原本科毕业设计项目](https://gitee.com/liu-shengdong-714/Intelligent-driving-scenario)基础上开展的改进型项目。它延续原项目对智能驾驶场景生成与安全管理的研究目标，并围绕 MetaDrive 原生场景、仿真证据追溯和风险模型训练重新设计与实现。

项目目标是建立“安全需求 → 参数化场景 → MetaDrive 仿真 → 安全判定 → 证据追溯”的可复现流程，并用实际仿真数据训练风险模型。Task 1 已验证原生数据集重载和连续真实俯视出帧；模板、业务 API、网页及风险模型仍待后续任务。

## 依据与实施顺序

- [需求基线与设计草案](docs/需求基线与设计草案.md)（v0.13）
- [实施计划](docs/项目实施计划.md)（Task 1–12）
- [相似开源项目调研](docs/相似开源项目调研.md)

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

`pyproject.toml` 与 `uv.lock` 锁定官方 `MetaDrive-0.4.3` 对应源码 SHA `5bf8ea8909c4643a4099a250e6f5fb89c695d8b4`。首次运行还需下载官方 MetaDrive 资源包。运行 Task 1 集成探针：

```sh
uv run --locked pytest tests/integration/test_native_probe.py -q
```

结果与环境限制见[兼容性验证](docs/仿真器兼容性验证.md)。当前尚无可启动服务。

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
