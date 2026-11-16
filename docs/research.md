# MetaDrive 新项目：相似开源仓库调研

核查日期：2026-11-15。依据各仓库 README、少量关键源码和 GitHub 仓库元数据；尚未在本机安装或运行这些项目。目标项目的约束是：MetaDrive 原生场景可由 `ScenarioEnv` 重载运行，管理安全需求与场景版本，使用本项目仿真数据训练风险预测模型并开展同预算比较。

## 优先参考

| 仓库 | 已核实的能力 | 对本项目的具体价值 | 边界与状态 |
|---|---|---|---|
| [metadriverse/metadrive](https://github.com/metadriverse/metadrive) | 官方模拟器；支持程序化道路、真实场景重建、`ScenarioEnv` | 确定运行接口、车辆状态、碰撞结果和原生格式验收；以其源码/文档作为版本兼容依据 | Apache-2.0；2026-10-16 有代码推送。它是模拟器，不提供我们的需求追溯与风险模型业务层 |
| [metadriverse/scenarionet](https://github.com/metadriverse/scenarionet) | 官方场景库与转换工具；支持公开交通数据和程序化数据转为 Scenario Description | 参考场景目录、索引、校验、数据集分组与公开数据转换；重点验证生成的 `.pkl` 能由 `ScenarioEnv` 运行 | Apache-2.0；2026-03-09 有代码推送。它不是安全需求管理平台，也不直接给出本项目策略的风险标签 |
| [metadriverse/metadrive-scenario](https://github.com/metadriverse/metadrive-scenario) | 提供约 3000 个合成场景和 1165 个 Waymo 场景及[运行示例](https://github.com/metadriverse/metadrive-scenario/blob/main/metadrive_scenario/examples/run_scenarios.py)；README 说明可选择轨迹回放或反应式交通 | 借鉴场景集合组织方式、批量运行入口、合成与真实场景分组；可用少量场景作初期加载试验 | Apache-2.0；最后代码推送为 2023-03-20，示例使用旧版 MetaDrive API，需在锁定的当前版本中验证。Waymo 原始数据许可与代码许可应分别处理 |
| [metadriverse/TrafficGen](https://github.com/metadriverse/TrafficGen) | 学习车辆放置和轨迹生成；README 给出 `generate.py --save_metadrive` 生成 `.pkl`，以及 [`run_metadrive.py`](https://github.com/metadriverse/TrafficGen/blob/main/trafficgen/run_metadrive.py) 重载场景 | 特别适合参考“生成原生场景文件 → 再加载运行”的数据路径；后续可研究用真实交通数据增强模板多样性 | Apache-2.0；最后代码推送为 2024-07-30；依赖较旧的 PyTorch/CUDA，生成模型不纳入首版 |

## 方法与系统架构参考

| 仓库 | 可借鉴之处 | 不直接采用的原因 |
|---|---|---|
| [CrimsonAzul/adversarial-av-testing](https://github.com/CrimsonAzul/adversarial-av-testing) | 与本项目最接近的 MetaDrive 危险场景搜索实验：参数化急刹/切入、固定被测驾驶器、随机与优化搜索的同预算比较、重复运行和有效失败判定；可读其[场景空间](https://github.com/CrimsonAzul/adversarial-av-testing/blob/main/avtest/scenario.py)与[实验设计](https://github.com/CrimsonAzul/adversarial-av-testing/blob/main/docs/DESIGN.md) | README 明确写出完整对抗搜索实验尚未运行；场景实现基于 `MetaDriveEnv`，不是我们要求的 `ScenarioEnv` 原生文件交付；仓库未声明许可证。只参考研究问题与实验口径，不复制代码 |
| [trust-ai/SafeBench](https://github.com/trust-ai/SafeBench) | 安全关键场景基准，包括被测驾驶策略、场景训练/评测模式、安全指标和对抗场景选择；可参考[运行配置与评价流程](https://github.com/trust-ai/SafeBench/blob/main/README.md) | 依赖 CARLA 0.9.13，不能直接复用仿真适配层；MIT，最后代码推送为 2024-02-23 |
| [VAIL-UCLA/MetaDrive-Arena](https://github.com/VAIL-UCLA/MetaDrive-Arena) | MetaDrive + FastAPI 的评测服务，含任务运行、结果存储和网页榜单；可参考服务进程与评测任务的组织 | 目标是多人竞速而非安全需求与场景生成；仓库未声明许可证，不能直接复制实现 |
| [valeoai/ScenarioMax](https://github.com/valeoai/ScenarioMax) | 公开数据的统一转换流水线与并行处理 | 主要扩展到 Waymax/GPUDrive 等格式，本项目只交付 MetaDrive 原生格式；Apache-2.0，不必作为首版依赖 |
| [Yuxin45/Adv-BMT](https://github.com/Yuxin45/Adv-BMT) | 更复杂的学习式危险场景生成、场景评价脚本及预训练模型；适合未来神经网络扩展研究 | 与首版树模型预测风险的任务不同，依赖较重的 GPU/Waymo 环境；仓库未声明许可证，不复制代码 |

## 对新项目的取舍

1. **运行与文件格式**：以 MetaDrive + ScenarioNet 为主参考，并用 TrafficGen 的原生 `.pkl` 生成/重载路径交叉核对。任何外部示例都必须在选定的 MetaDrive 版本上重跑，不能只因文件扩展名相同就认为兼容。
2. **场景与评测设计**：参考 MetaDrive-Scenario 的批量场景组织和 CrimsonAzul 项目的同预算实验、有效失败及重复性定义；保留我们既定的“自有仿真数据 → 树模型风险预测 → 选场景 → 再仿真”主线。
3. **业务平台**：需求版本、场景版本、双向追溯、变更影响、安全标记及证据链未见上述仓库提供完整对应实现，需要按任务书自行设计。
4. **代码复用**：先核对对应仓库的代码许可证及数据来源许可证。未声明许可证的仓库只作阅读参考；CARLA 代码和旧版 MetaDrive API 不直接迁入。

推荐阅读顺序：[ScenarioNet README](https://github.com/metadriverse/scenarionet/blob/main/README.md) → [MetaDrive-Scenario README](https://github.com/metadriverse/metadrive-scenario/blob/main/README.md) → [TrafficGen README](https://github.com/metadriverse/TrafficGen/blob/main/README.md) → [危险场景搜索实验 README](https://github.com/CrimsonAzul/adversarial-av-testing/blob/main/README.md)。
