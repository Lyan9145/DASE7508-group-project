# DASE7508：机械臂传感器欺骗实验

当前版本提供 MuJoCo + Gymnasium Reacher-v5、SAC 训练、joint0 bias/ramp 欺骗、匹配随机符号扰动、运动学检测与修正，以及配对评估。实验定义见 [PROTOCOL.md](PROTOCOL.md)。已有 seed 1 上传模型保留为旧基线，新训练使用同步采样和不重复的训练噪声。

2026-10-22 已完成三策略训练验证和 4,500 回合正式实验；结果与限制见 [RESULTS.md](../RESULTS.md)。默认 demo 优先加载同步采样的 seed 1 新模型。

## Linux / Conda

先进入本文件所在目录（仓库中的 `github_upload/`），然后执行：

```bash
conda create -n dase7508 python=3.11 pip
conda activate dase7508
python -m pip install 'torch==2.14.1' --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.lock.txt
python -m pip install -r requirements-dev.txt
python -m pytest -q
MUJOCO_GL=egl python check_setup.py
```

已有 `dase7508` 环境直接激活，不要重复创建。CPU 足够完成本实验；图形桌面可运行 `python demo.py`。离屏渲染若不支持 EGL，可使用桌面 OpenGL；物理训练与数值评估不依赖窗口。

本次实际验证的 Linux CPU 完整版本另存为 `environment-linux-cpu.lock.txt`，可用 `python -m pip install -r environment-linux-cpu.lock.txt` 重建；文件只包含公开索引与版本号，不引用安装时的临时文件。

```bash
# 三个独立训练种子，示例逐个执行；输出目录已存在时会拒绝覆盖
python train.py --steps 150000 --seed 1 --out outputs/sac_seed_1_sync
python train.py --steps 150000 --seed 2 --out outputs/sac_seed_2_sync
python train.py --steps 150000 --seed 3 --out outputs/sac_seed_3_sync

# 小规模完整试验：100 回合校准 + 6 个初始状态 × 50 个条件 = 300 回合评估
python evaluate.py --models outputs/sac_seed_1/model.zip --out outputs/pilot_example
python plot_results.py outputs/pilot_example

# 正式实验：只接受 3 个已通过同步采样验证、不同训练种子的模型
# 测试 seed 与 pilot 分开；该命令开始后保持配置和阈值不变
python evaluate.py --phase main --plan main_plan.json --episodes 30 --test-base 800000 \
  --calibration-base 300000 \
  --models outputs/sac_seed_1_sync/model.zip outputs/sac_seed_2_sync/model.zip outputs/sac_seed_3_sync/model.zip \
  --out outputs/main_v1
python plot_results.py outputs/main_v1
python audit_results.py outputs/main_v1
python make_replay.py outputs/main_v1
python plot_training.py outputs/sac_seed_1_sync outputs/sac_seed_2_sync outputs/sac_seed_3_sync --out outputs/main_v1/figures/training.png
```

每次评估保存 `config.json`、实现快照、`calibration.json`、`episodes.csv`、`summary.csv/json` 和压缩逐步日志。`plot_results.py` 另生成跨策略均值/范围表和图。只有存在 `run_status.json` 且 `complete=true` 才算整轮完成。试验结果中 `phase=pilot` 不代表正式测试结论。

演示攻击可用 `python demo.py --attack bias --epsilon 0.1 --duration 20`。
启用防御需添加 `--monitor-threshold <该策略 calibration.json 中的 threshold_m>`，不可根据测试表现临时调阈值。

## 安装与运行（Windows）

安装 64 位 Python 3.11，在本文件所在的 `github_upload/` 目录打开 PowerShell。无需激活虚拟环境。

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe check_setup.py
.\.venv\Scripts\python.exe demo.py
```

如果没有 `py` 命令，使用已安装的 Python 3.11 完整路径替代 `py -3.11`。已有 uv 的组员也可使用 `setup.ps1`，默认选择 Python 3.11；`-Python` 可以指定自己的解释器路径。项目不依赖原作者的 Conda 安装路径。

VS Code 中执行 **Python: Select Interpreter**，选择 `.venv/Scripts/python.exe`；Linux/Conda 选择 `dase7508/bin/python`。

## 已提供的模型

`outputs/sac_seed_1/model.zip` 是原始 seed 1 的 150,000 步 SAC 模型。模型使用 CPU 训练，Windows / Python 3.11.14，训练耗时约 31 分钟。它保留供复核；若存在 `outputs/sac_seed_1_sync/model.zip`，默认 demo 优先加载这个新模型，否则回退到原模型。

30 个干净验证回合全部成功：最后 10 步真实距离均值的总体平均为 0.67 cm，最差回合为 2.15 cm。成功判据为每回合最后 10 步平均距离不超过 3 cm。详细记录在 `outputs/sac_seed_1/validation.json`。这是一个训练种子的验证结果，尚非独立正式测试结果。

```powershell
# 默认展示已训练模型
.\.venv\Scripts\python.exe demo.py
# 展示随机动作
.\.venv\Scripts\python.exe demo.py --random
# 指定其他模型
.\.venv\Scripts\python.exe demo.py --model outputs\sac_seed_2\model.zip
```

## 训练与曲线

```powershell
.\.venv\Scripts\python.exe train.py --steps 150000 --seed 2 --eval-episodes 30
.\.venv\Scripts\tensorboard.exe --logdir outputs
```

训练从头开始，结束后保存模型并验证。默认 CPU 单线程，无自动续训，默认每次训练时间上限 1800 秒，可用 `--max-seconds` 调整。触及时限会保存并验证部分训练模型，JSON 记录实际步数。默认输出到脚本目录下 `outputs/sac_seed_<seed>_sync/`，已有目录会拒绝覆盖，也可用 `--out` 指定新目录。

TensorBoard 启动后，打开终端显示的网址。奖励越高通常表示表现越好，但最终以验证成功率判断；proposal 的筛选标准为 30 次至少成功 24 次。此上传包不含原训练 TensorBoard 日志，新训练会生成日志。

## 文件说明

| 文件 | 作用 |
|---|---|
| `demo.py` | 展示训练策略或随机动作 |
| `reacher_env.py` | 创建环境，设置 100 步上限和 2 mm 位置噪声 |
| `train.py` | SAC 训练、模型保存和干净验证 |
| `check_setup.py` | 观测、运动学、回合长度、噪声复现与离屏渲染检查 |
| `requirements.in` | 直接依赖与版本范围 |
| `requirements.lock.txt` | 实际安装版本，用于复现 |
| `setup.ps1` | uv 安装与检查入口 |
| `security.py` | 无仿真器访问的攻击、正向运动学和监测修正 |
| `evaluate.py` | 独立校准、配对评估、逐步日志与指标 |
| `plot_results.py` | 对比图、轨迹图和跨策略统计 |
| `test_security.py` | 通道边界、噪声、物理不变性和指标测试 |
| `audit_results.py` | 从完整日志独立审计配对、攻击范围、角度修正和任务评分 |
| `make_replay.py` | 根据日志生成物理机械臂/策略观测的动画与对比截图 |
| `main_plan.json` | 正式测试前冻结的配置与模型要求 |
| `outputs/sac_seed_1/` | 成功模型及其验证结果 |

## 环境约定与后续工作

- Reacher-v5 观测 10 维、动作 2 维、每回合 100 步，当前控制间隔 0.02 秒。
- 观测 0/1 是两关节 cos，2/3 是 sin；joint0 欺骗需要同时修改索引 **0 和 2**。
- 4:6 为目标位置，6:8 为关节速度，8:10 为 fingertip 减 target。
- 位置观测每坐标加入标准差 0.002 m 的高斯噪声；环境初始状态和传感器噪声可以分别设 seed。
- MuJoCo 缓存 body 位置与当前 qpos 存在时间差；现在独立 MjData 上执行 mj_forward 生成同步位置读数和评估真值，不修改真实仿真状态。旧采样通过 `--legacy-sampling` 保留供审计。
- 验证 seed 从 `10000 + 1000 * policy_seed` 开始。后续 calibration/test 应使用不重叠的 seed 集。
- 攻击、随机符号对照、监测修正和配对评估现已有实现；是否已完成多策略正式测试应以各输出目录的验证、配置和完成标记为准。
- 当前依赖在 Windows CPU 环境验证；GPU 可选，只有项目 Torch 支持 CUDA 时才使用 `--device cuda`。

## 上传

当前仓库以 `github_upload/` 保存可执行内容。根目录 `.gitignore` 排除环境、Python 缓存、训练 TensorBoard 和大型回合日志；模型、配置和实验结果可按需要提交。提案 Markdown 位于仓库根目录。

开源依赖通过安装获取，未复制其源代码；版本见锁文件，其许可证以各上游项目为准。
