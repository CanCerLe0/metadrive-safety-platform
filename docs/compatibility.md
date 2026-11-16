# MetaDrive 兼容性验证

状态：待执行 Task 1。当前 `MetaDrive-0.4.3` 仅是验证候选；其源码 SHA 为 `5bf8ea8909c4643a4099a250e6f5fb89c695d8b4`，但尚未记录可重载的原生数据集、连续俯视帧或性能数据。

依赖声明勘误：该 tag 的 `setup.py` 声明的发行包名为 `metadrive-simulator`，包版本元数据为 `0.4.2.3`。初次以 `metadrive` 声明时，`uv lock` 报 `Package metadata name metadrive-simulator does not match given name metadrive`；项目依赖名已按源码修正。Python 版本约束为 `<3.12`，本地环境为 3.11.17。tag 名和包版本号不同，因此以后以锁文件中的 commit SHA 标识兼容性候选。

安装检查：`uv sync --dev --locked` 已安装 77 个包；`import safety_platform, metadrive, fastapi, sqlalchemy, sklearn` 成功。导入时 macOS 报告 `pygame` 与 `cv2` 各自打包的 SDL2 Objective-C 类重复；这尚未证明仿真或渲染可用，Task 1 必须以真实重载和连续出帧验证。Matplotlib 缓存需设 `MPLCONFIGDIR=$PWD/.cache/matplotlib`，避免写入沙箱外的用户目录。

验证时记录：macOS/Python 版本、MetaDrive SHA、导出与重载命令、至少 100 步自车运动和周车变道结果、索引可读性、至少 100 帧连续非空且变化的俯视画面、平均渲染耗时与峰值内存。失败时保留最小复现和日志。
