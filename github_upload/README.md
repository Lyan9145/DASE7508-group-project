# DASE7508: Robotic Arm Sensor Spoofing and Mitigation

This directory contains the active Phase-2 plugin framework, SAC training and setup tools, interactive demos, and frozen Phase-1/historical artifacts.

- **Phase-2 extension architecture, interfaces, and teammate assignments**: [FRAMEWORK_GUIDE.md](FRAMEWORK_GUIDE.md)
- **Frozen Phase-1 experiment protocol and metric definitions**: [PROTOCOL.md](PROTOCOL.md)
- **Geometric and statistical interpretation notes**: [ANALYSIS_NOTES.md](ANALYSIS_NOTES.md)
- **Archived Phase-1 and 2026-11-18 reproduction/acceptance scripts**: [legacy/README.md](legacy/README.md)

---

## Active Entry Points (`github_upload/`)

| File / Directory | Purpose |
|---|---|
| `check_setup.py` | Verifies MuJoCo, Gymnasium `Reacher-v5`, forward kinematics, noise replay, and optional rendering |
| `train.py` | Trains a clean SAC policy with synchronized sampling and runs 30-episode validation |
| `demo.py` | Interactive MuJoCo viewer supporting all 12 registered attacks and 8 defenses |
| `run_matrix.py` | Runs paired Phase-2 `Attack x Defense` evaluations (`smoke`, `late_strong`, `full_matrix`) |
| `run_ablation.py` | Runs Direction 4A velocity-noise and position-noise ablations (`smoke`, `full`) |
| `plot_matrix.py` | Generates matrix heatmaps, detection tradeoff plots, ablation curves, and 3-panel replay GIFs |
| `test_framework.py` | Unified test suite covering kinematics, contracts, trust boundaries, legacy parity, and CLI smoke tests |
| `framework/` | Core environment/monitors (`framework/core/`), attacks, defenses, and evaluation modules |
| `legacy/` | Archived Phase-1 and 2026-11-18 reproduction/acceptance scripts |
| `outputs/` | Frozen trained models (`sac_seed_1/`, `sac_seed_{1,2,3}_sync/`) and historical archived runs |

---

## Setup

### Linux (Conda)

Run commands inside `github_upload/`:

```bash
conda create -n dase7508 python=3.11 pip
conda activate dase7508
python -m pip install 'torch==2.14.1' --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.lock.txt
python -m pip install -r requirements-dev.txt
python -m pytest -q test_framework.py
MUJOCO_GL=egl python check_setup.py --out outputs/setup_linux_check_001
```

If `dase7508` already exists, run `conda activate dase7508` directly. A full verified CPU package lock is saved in `environment-linux-cpu.lock.txt`. Desktop OpenGL works for interactive `demo.py`; headless training and numerical runs do not require a display server (`--no-render` disables rendering in `check_setup.py`).

### Windows (PowerShell)

Open PowerShell in `github_upload/` with 64-bit Python 3.11 or 3.12 installed:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q test_framework.py
.\.venv\Scripts\python.exe check_setup.py --out outputs/setup_windows_check_001
.\.venv\Scripts\python.exe demo.py
```

Alternatively, `setup.ps1` sets up `.venv` using `uv` (use `-Python <path_or_version>` if needed). For Windows Python 3.12 compatibility with `torch==2.14.1+cpu`, see `environment-windows-mp1.lock.txt`.

---

## Running Experiments

### 1. Interactive Demo

```bash
python demo.py
python demo.py --random
python demo.py --attack bias --epsilon 1.0 --start 80 --duration 20
python demo.py --attack bias --epsilon 1.0 --start 80 --duration 20 --defense ik_velocity_fusion
```

### 2. Phase-2 Matrix and Noise Ablations (Active Workflow)

Always provide a fresh `--out` path (existing directories are never overwritten):

```bash
python run_matrix.py --preset smoke --out outputs/phase2_matrix_smoke_001
python plot_matrix.py outputs/phase2_matrix_smoke_001

python run_ablation.py --mode both --preset smoke --out outputs/phase2_ablation_smoke_001
python plot_matrix.py outputs/phase2_ablation_smoke_001
```

See [FRAMEWORK_GUIDE.md](FRAMEWORK_GUIDE.md) for `late_strong`, `full_matrix`, full ablation presets, and plugin extension instructions.

### 3. Training Additional Policies

```bash
python train.py --steps 150000 --seed 4 --eval-episodes 30 --out outputs/sac_seed_4_sync
tensorboard --logdir outputs
```

Training defaults to single-thread CPU with an 1800-second wall-clock cap (`--max-seconds` to adjust) and refuses to overwrite existing output directories. Validation uses `10000 + 1000 * policy_seed + episode` (minimum 24/30 successes required by Proposal 2.0).

---

## Provided Models and Environment Conventions

- `outputs/sac_seed_1/model.zip`: original baseline 150,000-step SAC model (legacy sampling, kept intact for reference; 30/30 clean validation, 0.67 cm mean final-10 distance).
- `outputs/sac_seed_{1,2,3}_sync/model.zip`: three synchronized-sampling 150,000-step SAC models (all 30/30 clean validation). `demo.py` prefers `sac_seed_1_sync/model.zip` when present.
- `Reacher-v5` uses a 10D observation, 2D action, 100-step episodes, and `dt = 0.02 s`:
  - `0:2`: `[cos(q0), cos(q1)]`, `2:4`: `[sin(q0), sin(q1)]`
  - `4:6`: `target_xy`
  - `6:8`: `[q0_dot, q1_dot]`
  - `8:10`: `fingertip_xy - target_xy` (with `sigma = 0.002 m` Gaussian noise per coordinate)
- Synchronized position sampling computes `xipos` on an isolated `mujoco.MjData` via `mj_forward` so the physics integrator state is never altered (`--legacy-sampling` remains available for auditing the original model).
