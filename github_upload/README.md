# DASE7508：机械臂传感器欺骗实验

当前版本提供 MuJoCo + Gymnasium Reacher-v5 仿真环境、Stable-Baselines3 SAC 干净基线训练与演示。攻击、运动学监测器、校准和配对实验尚未实现。

## 安装与运行（Windows）

安装 64 位 Python 3.11，在仓库根目录打开 PowerShell。无需激活虚拟环境。

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe check_setup.py
.\.venv\Scripts\python.exe demo.py
```

如果没有 `py` 命令，使用已安装的 Python 3.11 完整路径替代 `py -3.11`。已有 uv 的组员也可使用 `setup.ps1`，默认选择 Python 3.11；`-Python` 可以指定自己的解释器路径。项目不依赖原作者的 Conda 安装路径。

VS Code 中执行 **Python: Select Interpreter**，选择 `.venv/Scripts/python.exe`。F5 配置 `Reacher demo (.venv)` 也明确使用此解释器。

## 已提供的模型

`outputs/sac_seed_1/model.zip` 是 seed 1 的 150,000 步 SAC 模型，默认 demo 自动加载它。模型使用 CPU 训练，Windows / Python 3.11.14，训练耗时约 31 分钟。

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

训练从头开始，结束后保存模型并验证。默认 CPU 单线程，无早停、无自动续训。训练输出到 `outputs/sac_seed_<seed>/`；再次使用相同 seed 会覆盖其模型、验证结果和回合日志，因此不要使用 seed 1 覆盖已提供的模型，除非已备份。

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
| `.vscode/` | 工作区解释器与调试配置 |
| `outputs/sac_seed_1/` | 成功模型及其验证结果 |

## 环境约定与后续工作

- Reacher-v5 观测 10 维、动作 2 维、每回合 100 步，当前控制间隔 0.02 秒。
- 观测 0/1 是两关节 cos，2/3 是 sin；joint0 欺骗需要同时修改索引 **0 和 2**。
- 4:6 为目标位置，6:8 为关节速度，8:10 为 fingertip 减 target。
- 位置观测每坐标加入标准差 0.002 m 的高斯噪声；环境初始状态和传感器噪声可以分别设 seed。
- 检查发现 MuJoCo 步进后缓存 body 位置与当前 qpos 存在微小时间差；检查在独立 MjData 上执行 mj_forward 验证几何并记录缓存差异。后续监测器需明确采样时刻并进行干净残差校准。
- 验证 seed 从 `10000 + 1000 * policy_seed` 开始。后续 calibration/test 应使用不重叠的 seed 集。
- 还需两个独立训练策略、bias/ramp 攻击、随机符号对照、监测与修正、阈值校准及配对评估。
- 当前依赖在 Windows CPU 环境验证；GPU 可选，只有项目 Torch 支持 CUDA 时才使用 `--device cuda`。

## 上传

将本文件夹中的内容放在 GitHub 仓库根目录。`.gitignore` 排除环境、缓存和一般输出，但允许提交 seed 1 的模型和验证 JSON。本包不包含完整 proposal PDF，可按团队需要另行加入。

开源依赖通过安装获取，未复制其源代码；版本见锁文件，其许可证以各上游项目为准。
