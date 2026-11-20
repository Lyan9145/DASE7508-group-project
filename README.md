# DASE7508-group-project

Group 9: joint-angle sensor spoofing and kinematic mitigation for a simulated reinforcement-learning robotic arm (`Reacher-v5` + SAC).

## Quick Navigation

- **Phase-2 Plugin Architecture, Contracts & Contributor Tasks**: [FRAMEWORK_GUIDE.md](FRAMEWORK_GUIDE.md)
- **Proposal & Frozen Phase-1 Protocol**: [docs/DASE7508_Proposal_2.0.md](docs/DASE7508_Proposal_2.0.md), [docs/PROTOCOL.md](docs/PROTOCOL.md), [docs/ANALYSIS_NOTES.md](docs/ANALYSIS_NOTES.md)
- **Archived Phase-1 / 2026-11-18 Scripts & Historical Reports**: [legacy/README.md](legacy/README.md) (`legacy/scripts/`, `legacy/docs/`, `legacy/main_plan.json`)

---

## Repository Layout

| Path | Purpose |
|---|---|
| `check_setup.py` | Verifies MuJoCo, Gymnasium `Reacher-v5`, forward kinematics, noise replay, and optional rendering |
| `train.py` | Trains a clean SAC policy with synchronized sampling and runs 30-episode clean validation |
| `demo.py` | Interactive MuJoCo viewer supporting all 12 registered attacks and 8 defenses |
| `run_matrix.py` | Runs paired Phase-2 `Attack x Defense` evaluations (`smoke`, `late_strong`, `full_matrix`) |
| `run_ablation.py` | Runs Direction 4A velocity-noise and position-noise ablations (`smoke`, `full`) |
| `plot_matrix.py` | Generates matrix heatmaps, detection tradeoff plots, ablation curves, and 3-panel replay GIFs |
| `core/` | Environment wrappers (`reacher_env.py`, `env_wrapper.py`), kinematics (`kinematics.py`), baseline monitors (`security.py`, `recovery_monitor.py`) |
| `attacks/` | Attack plugin interface (`base.py`) and registered attack implementations (`legacy.py`, `magnitude_timing.py`, `stealthy.py`, `adaptive.py`) |
| `defenses/` | Defense plugin interface (`base.py`) and registered defense implementations (`legacy.py`, `statistical.py`, `fusion_recovery.py`, `policy_level.py`) |
| `evaluation/` | Calibration, paired trial runner, matrix metrics, presets, Direction 4A ablations, and plotting (`metrics.py`, `presets.py`, `runner.py`, `ablation.py`, `visualize.py`) |
| `models/` | Frozen synchronized-sampling SAC policies (`sac_seed_1_sync/`, `sac_seed_2_sync/`, `sac_seed_3_sync/`) |
| `tests/` | Unified verification suite (`tests/test_framework.py`) covering kinematics, contracts, trust boundaries, legacy parity, and CLI smoke tests |
| `docs/` | Proposal 2.0, reference diagram, frozen Phase-1 protocol (`PROTOCOL.md`), and analysis notes (`ANALYSIS_NOTES.md`) |
| `env/` | Dependency inputs and environment lockfiles (`requirements.in`, `requirements-dev.txt`, `environment-linux-cpu.lock.txt`, `environment-windows-mp1.lock.txt`, `setup.ps1`) |
| `legacy/` | Archived Phase-1 and 2026-11-18 scripts (`legacy/scripts/`), reports (`legacy/docs/`), and `main_plan.json` |
| `outputs/` | Target directory for new local training, setup, matrix, and ablation runs |
| `requirements.txt` | Pinned base runtime lockfile for `pip install -r requirements.txt` |

---

## Setup

Run all setup and experiment commands directly from the repository root.

### Linux (Conda)

```bash
conda create -n dase7508 python=3.11 pip
conda activate dase7508
python -m pip install 'torch==2.14.1' --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.txt
python -m pip install -r env/requirements-dev.txt
python -m pytest -q tests/test_framework.py
MUJOCO_GL=egl python check_setup.py --out outputs/check_setup_001
```

If `dase7508` already exists, run `conda activate dase7508` directly. A full verified CPU package lock is saved in `env/environment-linux-cpu.lock.txt`. Desktop OpenGL works for interactive `demo.py`; headless training and numerical evaluations do not require a display server (`--no-render` disables rendering in `check_setup.py`).

### Windows (PowerShell)

Open PowerShell in the repository root with 64-bit Python 3.11 or 3.12 installed:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r env/requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q tests/test_framework.py
.\.venv\Scripts\python.exe check_setup.py --out outputs/check_setup_001
.\.venv\Scripts\python.exe demo.py
```

Alternatively, `.\env\setup.ps1` sets up `.venv` using `uv` (pass `-Python <path_or_version>` if needed). For Windows Python 3.12 compatibility with `torch==2.14.1+cpu`, see `env/environment-windows-mp1.lock.txt`.

---

## Quick Start

Always specify a fresh `--out` directory (existing directories are never overwritten):

```bash
# 1. Verify tests and local environment
python -m pytest -q tests/test_framework.py
python check_setup.py --no-render --out outputs/check_setup_001

# 2. Interactive demo (supports any registered attack and defense)
python demo.py
python demo.py --attack bias --epsilon 1.0 --start 80 --duration 20 --defense ik_velocity_fusion

# 3. Smoke Attack x Defense matrix evaluation and plotting
python run_matrix.py --preset smoke --out outputs/smoke_matrix_001
python plot_matrix.py outputs/smoke_matrix_001

# 4. Direction 4A smoke ablation (velocity + position noise) and curves
python run_ablation.py --mode both --preset smoke --out outputs/smoke_ablation_001
python plot_matrix.py outputs/smoke_ablation_001

# 5. Train an additional clean SAC policy with synchronized sampling
python train.py --steps 150000 --seed 4 --eval-episodes 30 --out outputs/sac_seed_4_sync
```

See [FRAMEWORK_GUIDE.md](FRAMEWORK_GUIDE.md) for `late_strong`, `full_matrix`, full ablation commands, the Attack-Defense contract, and plugin extension instructions.

---

## Frozen Models and Environment Conventions

- `models/sac_seed_1_sync/model.zip`, `models/sac_seed_2_sync/model.zip`, and `models/sac_seed_3_sync/model.zip`: three synchronized-sampling 150,000-step SAC models (all 30/30 clean validation). `demo.py` defaults to `models/sac_seed_1_sync/model.zip`.
- `Reacher-v5` uses a 10D observation, 2D action, 100-step episodes, and `dt = 0.02 s`:
  - `0:2`: `[cos(q0), cos(q1)]`, `2:4`: `[sin(q0), sin(q1)]`
  - `4:6`: `target_xy`
  - `6:8`: `[q0_dot, q1_dot]`
  - `8:10`: `fingertip_xy - target_xy` (with `sigma = 0.002 m` Gaussian noise per coordinate)
- Synchronized position sampling computes `xipos` on an isolated `mujoco.MjData` via `mj_forward` so the physics integrator state is never altered.
