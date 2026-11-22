# DASE7508 Phase-2 Extension Framework Guide

This guide documents the unified plugin architecture at the repository root (`core/`, `attacks/`, `defenses/`, `evaluation/`), the Attack-Defense contract and trust boundaries, extension instructions, three-track technical responsibilities, and verified CLI commands.

---

## 1. Directory Layout and Baseline Isolation

The flat root layout places the 7 active CLI entry points alongside top-level packages, `models/`, `tests/`, `docs/`, `env/`, `legacy/`, and `outputs/`:

```text
.
├── README.md                             # Project overview, setup, and quick-start entry point
├── FRAMEWORK_GUIDE.md                    # This document
├── requirements.txt                      # Pinned base runtime lockfile
├── check_setup.py                        # Environment, kinematics, and rendering verification
├── train.py                              # SAC policy training and 30-episode clean validation
├── train_fallback.py                     # Masked-observation SAC fallback policy for fallback_policy
├── demo.py                               # Interactive visualization for any registered attack/defense
├── run_matrix.py                         # Phase-2 paired Attack x Defense matrix evaluation CLI
├── run_ablation.py                       # Direction 4A velocity/position noise ablation CLI
├── plot_matrix.py                        # Matrix heatmaps, tradeoff curves, ablation curves, and 3-panel replay
│
├── core/
│   ├── __init__.py                       # Re-exports ArmGeometry, Attack, KinematicMonitor, RecoveryMonitor, kinematics, and env helpers
│   ├── reacher_env.py                    # Synchronized Reacher-v5 sampling and PositionNoise wrapper
│   ├── security.py                       # Baseline ArmGeometry, Attack, KinematicMonitor, wrap, rotation
│   ├── recovery_monitor.py               # Bounded recovery wait monitor (grace 1 or 3)
│   ├── kinematics.py                     # solve_q0_ik, solve_2link_ik, elbow_flip_angles
│   └── env_wrapper.py                    # AblationNoiseWrapper, make_ablation_env
├── attacks/
│   ├── __init__.py                       # Auto-imports & exposes all 13 registered attacks
│   ├── base.py                           # AttackContext, AttackResult, BaseAttack, @register_attack
│   ├── legacy.py                         # CleanAttack, BiasAttack, RampAttack, RandomBiasAttack, RandomRampAttack
│   ├── magnitude_timing.py               # SinusoidalAttack, FreezeAttack, ReplayAttack, PulseAttack
│   ├── stealthy.py                       # ThresholdAwareRampAttack, ElbowFlipAttack, JointVelocityCoupledAttack
│   ├── adaptive.py                       # PolicyGradientAttack (white-box PGD on SAC actor)
│   ├── DEV_RESULTS.md                    # Track 1 development failure-boundary scan and tuning notes
│   └── EXPLORATORY_RESULTS.md            # Periodic pulse and exploratory attack comparison notes
├── defenses/
│   ├── __init__.py                       # Auto-imports & exposes all 8 registered defenses
│   ├── base.py                           # CalibrationStats, DefenseContext, DefenseResult, BaseDefense, @register_defense
│   ├── legacy.py                         # NoDefense, OriginalFailStopDefense, Grace1Defense
│   ├── statistical.py                    # CusumDefense, SlidingWindowDefense
│   ├── fusion_recovery.py                # ContinuousVelocityDefense, IKVelocityFusionDefense, VelocityConsistencyMonitor
│   ├── policy_level.py                   # FallbackPolicyDefense, MaskedObservationExtractor
│   └── DEV_RESULTS.md                    # Track 2 development-set tuning results
├── evaluation/
│   ├── __init__.py                       # Re-exports metrics, presets, runner, ablation, visualize
│   ├── metrics.py                        # recovery_time, summarize_matrix, aggregate_across_policies, collect_seed_set
│   ├── presets.py                        # Phase-2 seed block constants, validate_disjoint_seeds, smoke/late_strong/full_matrix
│   ├── runner.py                         # calibrate_policy, run_paired_trial, run_matrix
│   ├── ablation.py                       # run_velocity_noise_ablation, run_position_noise_ablation
│   ├── visualize.py                      # plot_matrix_heatmap, plot_detection_tradeoff, plot_ablation_curves, make_comparison_replay
│   └── check_results.py                  # Completeness, pairing, and outcome-total verifier
│
├── models/
│   ├── sac_seed_1_sync/model.zip         # Synchronized SAC baseline policy (seed 1)
│   ├── sac_seed_2_sync/model.zip         # Synchronized SAC baseline policy (seed 2)
│   ├── sac_seed_3_sync/model.zip         # Synchronized SAC baseline policy (seed 3)
│   └── sac_seed_1_robust/model.zip       # Fallback SAC policy with the joint-0 encoder masked
├── tests/
│   ├── test_framework.py                 # Unified verification suite (kinematics, contracts, parity, CLIs)
│   ├── test_attack_optimization.py       # Track 1 attack optimization and pulse regression checks
│   └── test_defense_extensions.py        # Track 2 defense regression checks
├── docs/
│   ├── DASE7508_Proposal_2.0.md          # Phase-1/2 proposal document
│   ├── PROTOCOL.md                       # Frozen Phase-1 protocol and metric definitions
│   ├── ANALYSIS_NOTES.md                 # Geometric and statistical interpretation notes
│   ├── EVALUATION_RUN_MANIFEST.md        # Frozen Phase-2 held-out run manifest and checkpoint hashes
│   ├── EVALUATION_PRELIMINARY.md         # Nov 21 development evaluation snapshot
│   ├── DIRECTION_4A_SMOKE.md             # Direction 4A smoke record and reporting conventions
│   └── EVALUATION_LAYOUT.md              # Full-size evaluation figure layout verification notes
├── env/
│   └── setup.ps1                         # Windows uv bootstrap script (+ lockfiles and requirements-dev.txt)
├── legacy/
│   └── README.md                         # Index of archived Phase-1 scripts (legacy/scripts/) and reports (legacy/docs/)
└── outputs/
    └── evidence/phase2-held-out-167d7d2/ # Committed Phase-2 held-out results and figures (+ development snapshot)
```

Core repository paths tracked in this layout:
- Root docs & setup: `README.md`, `FRAMEWORK_GUIDE.md`, `requirements.txt`, `docs/PROTOCOL.md`, `docs/ANALYSIS_NOTES.md`, `docs/EVALUATION_RUN_MANIFEST.md`, `docs/EVALUATION_PRELIMINARY.md`, `docs/DIRECTION_4A_SMOKE.md`, `docs/EVALUATION_LAYOUT.md`, `legacy/README.md`
- Tests: `tests/test_framework.py`, `tests/test_attack_optimization.py`, `tests/test_defense_extensions.py`
- Root CLIs: `check_setup.py`, `train.py`, `train_fallback.py`, `demo.py`, `run_matrix.py`, `run_ablation.py`, `plot_matrix.py`
- Core package: `core/__init__.py`, `core/kinematics.py`, `core/env_wrapper.py`, `core/reacher_env.py`, `core/security.py`, `core/recovery_monitor.py`
- Attacks package: `attacks/__init__.py`, `attacks/base.py`, `attacks/legacy.py`, `attacks/magnitude_timing.py`, `attacks/stealthy.py`, `attacks/adaptive.py`, `attacks/DEV_RESULTS.md`, `attacks/EXPLORATORY_RESULTS.md`
- Defenses package: `defenses/__init__.py`, `defenses/base.py`, `defenses/legacy.py`, `defenses/statistical.py`, `defenses/fusion_recovery.py`, `defenses/policy_level.py`, `defenses/DEV_RESULTS.md`
- Evaluation package: `evaluation/__init__.py`, `evaluation/metrics.py`, `evaluation/presets.py`, `evaluation/runner.py`, `evaluation/ablation.py`, `evaluation/visualize.py`, `evaluation/check_results.py`
- Synchronized & fallback policies: `models/sac_seed_1_sync/model.zip`, `models/sac_seed_2_sync/model.zip`, `models/sac_seed_3_sync/model.zip`, `models/sac_seed_1_robust/model.zip`
- Held-out evidence index: `outputs/evidence/phase2-held-out-167d7d2/README.md`

Isolation rules:
1. Do not modify frozen Phase-1 synchronized models (`models/sac_seed_1_sync/model.zip`, `models/sac_seed_2_sync/model.zip`, `models/sac_seed_3_sync/model.zip`) or archived scripts/reports documented in `legacy/README.md`.
2. `run_matrix.py`, `run_ablation.py`, `train.py`, `train_fallback.py`, and `check_setup.py` refuse to overwrite an existing `--out` directory.
3. Phase-2 experiments use disjoint seed blocks verified by `validate_disjoint_seeds` before execution:
   - Matrix defaults: `CAL_BASE=1000000`, `DEV_BASE=1100000`, `TEST_BASE=1200000`, `ABLATION_BASE=1300000`.
   - Smoke ablation defaults (`--preset smoke`): velocity cal `1050000` / test `1300000`; position cal `1060000` / test `1350000`.
   - Full ablation defaults (`--preset full`): velocity cal `1400000` / test `1450000`; position cal `1500000` / test `1550000`.
   - Protected historical blocks: `10000..13999`, `200000..202999`, `300000..302999`, `500000..502999`, `800000..802999`, `900000..932999`.

---

## 2. Attack-Defense Interface Contract and Trust Boundaries

### 2.1 Reacher-v5 Observation Vector (`float64`, shape `(10,)`)

| Indices | Physical Meaning | Trust Boundary |
|---|---|---|
| `0, 1` | `cos(q0), cos(q1)` | Encoder channel (subject to attack injection) |
| `2, 3` | `sin(q0), sin(q1)` | Encoder channel (subject to attack injection) |
| `4, 5` | `target_x, target_y` | Target coordinates (protected) |
| `6, 7` | `q0_dot, q1_dot` (rad/s) | Joint velocity (protected by default; `joint_vel_coupled` explicitly targets index `6`) |
| `8, 9` | `fingertip - target` (m) | Independent position channel with Gaussian noise (`pos_sigma=0.002` default) |

### 2.2 Attack Contract (`attacks/base.py`)

- `AttackContext(geometry: ArmGeometry, dt: float, calibrated_threshold_m: float | None = None, policy: Any | None = None)`
- `AttackResult(reported_obs: np.ndarray, is_active: bool, attacked_channels: tuple[int, ...] = (0, 2), delta_rad: float = 0.0, metadata: dict[str, Any] = ...)`
- `BaseAttack` methods: `reset(seed, sign=1, context=None)`, `apply(raw_obs, step, context) -> AttackResult`, `window_bounds() -> tuple[int, int] | None`, `config_dict() -> dict[str, Any]`.

Invariants enforced on every step by `evaluation/runner.py` (`run_paired_trial`):
1. `apply` must never mutate `raw_obs`; it must return a fresh `float64` copy in `reported_obs`.
2. Every index not in `attacked_channels` must remain bit-for-bit equal to `raw_obs`.
3. Modified `(cos, sin)` pairs at `(0, 2)` or `(1, 3)` must satisfy `cos^2 + sin^2 == 1`.

### 2.3 Defense Contract (`defenses/base.py`)

- `CalibrationStats`: `threshold_m`, `residual_mean_m`, `residual_std_m`, `residual_p95_m`, `residual_p99_m`, `q0_jump_p99_rad`, `q0_jump_p999_rad`, `q1_jump_p99_rad`, `q1_jump_p999_rad`, `control_dt_seconds`, `episodes`, `seed_base`.
- `DefenseContext(geometry: ArmGeometry, dt: float, calibration: CalibrationStats, fallback_policy: Any | None = None)`
- `DefenseResult(policy_obs: np.ndarray, alarm: bool, abort: bool, state: str, residual_m: float, alarm_streak: int = 0, action_override: np.ndarray | None = None, metadata: dict[str, Any] = ...)`
- `VALID_DEFENSE_STATES = ("normal", "correcting", "recovery_pending", "fallback", "aborted")`

Trust-boundary rules:
1. `Defense.process(reported_obs, step, context)` sees only `reported_obs`, `step`, and static `DefenseContext`. Never pass `raw_obs`, `info['truth']`, or `AttackResult` to a defense.
2. `process` must never mutate `reported_obs`; it must return a fresh `float64` copy `policy_obs` with unit-circle angle pairs and a valid `state`.
3. Step `0` initializes estimators (unattacked post-reset reading) and is excluded from alarm counts and false-alarm step denominators (`detection_steps` counts `step >= 1`).
4. When `action_override is not None`, the runner executes `action_override`; otherwise it calls `model.predict(defense_res.policy_obs, deterministic=True)`.

### 2.4 Built-In Registered Plugins

- **Attacks (13 total via `attacks.list_attacks()`)**:
  - Legacy baseline: `clean`, `bias`, `ramp`, `random_bias`, `random_ramp`
  - Magnitude/timing: `sinusoidal`, `freeze`, `replay`, `pulse` (periodic on/off spoofing)
  - Stealthy/multi-channel: `threshold_aware`, `elbow_flip` (modifies `(0, 1, 2, 3)` with zero FK residual), `joint_vel_coupled` (modifies `(0, 2, 6)`)
  - White-box adaptive: `policy_gradient` (PGD against frozen SAC actor)
- **Defenses (8 total via `defenses.list_defenses()`)**:
  - Legacy baseline: `no_defense`, `original_fail_stop`, `grace1`
  - Statistical: `cusum`, `sliding_window`
  - Fusion/recovery: `continuous_velocity`, `ik_velocity_fusion` (position residual + joint jump check + encoder/velocity consistency gate + single/dual-link IK-velocity fusion)
  - Policy-level: `fallback_policy` (pair with `--fallback-model models/sac_seed_1_robust/model.zip`)
- **Matrix Presets (`evaluation.list_presets()`)**: `smoke`, `late_strong`, `full_matrix`. `late_strong` and `full_matrix` include `fallback_policy`, so `run_matrix.py` requires `--fallback-model` for them unless `fallback_policy` is dropped via `--defenses`.

---

## 3. Adding New Plugins and Ablations

### 3.1 Adding an Attack Plugin
1. Add a subclass of `BaseAttack` in `attacks/` (for example, `attacks/stealthy.py` or a new module `attacks/<my_attack>.py`) decorated with `@register_attack("my_attack")`.
2. Store all JSON-serializable hyperparameters via `super().__init__(...)` so `config_dict()` records them automatically.
3. Implement `reset` and `apply` returning a fresh `AttackResult` with exact `attacked_channels` (importing geometry helpers from `core.security` or `core.kinematics`).
4. Import the class in `attacks/__init__.py` and add it to `__all__`.
5. Verify with `python run_matrix.py --preset smoke --attacks clean my_attack --out outputs/smoke_my_attack`.

### 3.2 Adding a Defense Plugin
1. Add a subclass of `BaseDefense` in `defenses/` (for example, `defenses/fusion_recovery.py` or a new module `defenses/<my_defense>.py`) decorated with `@register_defense("my_defense")`.
2. Store hyperparameters via `super().__init__(...)` and implement `reset(context)` and `process(reported_obs, step, context) -> DefenseResult`.
3. Handle `step == 0` warmup with `alarm=False, abort=False, state="normal"`, avoid mutating `reported_obs`, and use only observation/context inputs (importing helpers from `core.security` or `core.kinematics`).
4. Import the class in `defenses/__init__.py` and add it to `__all__`.
5. Verify with `python run_matrix.py --preset smoke --defenses no_defense my_defense --out outputs/smoke_my_defense`.

### 3.3 Adding an Ablation Sweep
1. Implement the sweep in `evaluation/ablation.py` reusing `make_ablation_env` (from `core.env_wrapper`) and `calibrate_policy` (from `evaluation.runner`) per noise distribution.
2. Validate disjoint seeds via `collect_seed_set` and `validate_disjoint_seeds` (from `evaluation.metrics` and `evaluation.presets`).
3. Wire the CLI option into `run_ablation.py` and plotting support into `evaluation/visualize.py`.

---

## 4. Three-Track Technical Responsibilities

1. **Track 1 — Attack Extensions** (`attacks/magnitude_timing.py`, `attacks/stealthy.py`, `attacks/adaptive.py`):
   - Tune or expand timing, amplitude, multi-channel (`elbow_flip`, `joint_vel_coupled`, `threshold_aware`), and adaptive (`policy_gradient`) attacks.
   - Sweep parameters under `no_defense` on `DEV_BASE=1100000` and document exact failure conditions across `models/sac_seed_1_sync/model.zip`, `models/sac_seed_2_sync/model.zip`, and `models/sac_seed_3_sync/model.zip`.
   - Status: tuned noisy-tip bisection in `ThresholdAwareRampAttack`, multi-start PGD + optional residual penalty in `PolicyGradientAttack`, 0.25 Hz / pi/2 `SinusoidalAttack` defaults, and `PulseAttack` are implemented and documented in `attacks/DEV_RESULTS.md` and `attacks/EXPLORATORY_RESULTS.md`.
2. **Track 2 — Defense Extensions** (`defenses/statistical.py`, `defenses/fusion_recovery.py`, `defenses/policy_level.py`):
   - Tune `CusumDefense` and `SlidingWindowDefense` on `DEV_BASE=1100000` to reduce missed detections on small/ramping attacks while controlling clean false alarms.
   - Extend `IKVelocityFusionDefense` (e.g., velocity-channel gating under `joint_vel_coupled`) and train a robust/angle-masked backup SAC policy for `FallbackPolicyDefense` via `--fallback-model`.
   - Status: tuned defaults, the velocity-consistency gate, the corrected-estimate divergence abort, and the masked fallback policy (`train_fallback.py` -> `models/sac_seed_1_robust/model.zip`) are documented with development-set evidence in `defenses/DEV_RESULTS.md`.
3. **Track 3 — Direction 4A Matrix Evaluation, Ablation & Visualization** (`run_matrix.py`, `run_ablation.py`, `plot_matrix.py`, `evaluation/ablation.py`, `evaluation/visualize.py`, `evaluation/check_results.py`):
   - Run full 3-policy `late_strong` and `full_matrix` evaluations on `TEST_BASE=1200000` (`30` paired states/policy, `100` calibration episodes/policy).
   - Run full velocity (`[0.0, 0.05, 0.2, 0.5, 1.0]`) and position (`[0.002, 0.005, 0.010]`) noise ablations and generate heatmaps, detection tradeoff plots, ablation curves, and 3-panel comparison replays.
   - Status: completed `late_strong` (15,120 episodes), `full_matrix` (22,320 episodes), and Direction 4A velocity/position ablations (3,600 episodes) are recorded in `docs/EVALUATION_RUN_MANIFEST.md` and `outputs/evidence/phase2-held-out-167d7d2/README.md`.

---

## 5. Verified CLI Commands

Run all commands directly from the repository root using your activated Python environment, always specifying a fresh `--out` directory:

```bash
# 1. Verify environment and unified test suite (all tests must pass)
python -m pytest -q tests
python check_setup.py --no-render --out outputs/check_setup_001

# 2. Smoke matrix (1 policy x 4 attacks x 6 defenses x 4 episodes), integrity check, and plots
python run_matrix.py --preset smoke --out outputs/phase2_matrix_smoke_001
python evaluation/check_results.py outputs/phase2_matrix_smoke_001
python plot_matrix.py outputs/phase2_matrix_smoke_001

# 3. Direction 4A smoke ablation (velocity + position noise), integrity check, and curves
python run_ablation.py --mode both --preset smoke --out outputs/phase2_ablation_smoke_001
python evaluation/check_results.py outputs/phase2_ablation_smoke_001
python plot_matrix.py outputs/phase2_ablation_smoke_001

# 4. Interactive demo with any registered attack and defense
python demo.py --attack bias --epsilon 1.0 --start 80 --duration 20 --defense ik_velocity_fusion --episodes 2

# 5. Targeted plugin subset check (example with fallback model)
python run_matrix.py \
  --preset full_matrix \
  --models models/sac_seed_1_sync/model.zip \
  --attacks clean threshold_aware elbow_flip joint_vel_coupled policy_gradient \
  --defenses no_defense original_fail_stop cusum ik_velocity_fusion fallback_policy \
  --fallback-model models/sac_seed_1_robust/model.zip \
  --episodes 4 --calibration-episodes 10 \
  --test-base 1120000 --cal-base 1020000 \
  --no-traces \
  --out outputs/phase2_targeted_check_001

# 6. Train a masked-observation fallback policy (joint-0 encoder hidden inside the network)
python train_fallback.py --seed 1 --steps 150000 --out outputs/fallback_seed_1_001

# 7. Full 3-policy matrices and Direction 4A full ablations (with result verification)
python run_matrix.py --preset late_strong \
  --fallback-model models/sac_seed_1_robust/model.zip \
  --out outputs/phase2_late_strong_001
python evaluation/check_results.py outputs/phase2_late_strong_001
python plot_matrix.py outputs/phase2_late_strong_001

python run_matrix.py --preset full_matrix \
  --fallback-model models/sac_seed_1_robust/model.zip \
  --out outputs/phase2_full_matrix_001
python evaluation/check_results.py outputs/phase2_full_matrix_001
python plot_matrix.py outputs/phase2_full_matrix_001

python run_ablation.py --mode both --preset full \
  --velocity-cal-base 1400000 --velocity-seed-base 1450000 \
  --position-cal-base 1500000 --position-seed-base 1550000 \
  --out outputs/phase2_ablation_full_001
python evaluation/check_results.py outputs/phase2_ablation_full_001
python plot_matrix.py outputs/phase2_ablation_full_001
```
