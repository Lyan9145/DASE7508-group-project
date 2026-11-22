# Evaluation run manifest

This records the configuration used for the held-out evaluation. The
[results bundle](../outputs/evidence/phase2-held-out-167d7d2/README.md) contains
the frozen settings, resolved run configs, and completed results.

## Freeze record

| Item | Value |
|---|---|
| Integrated Git commit and package lock | `167d7d26817399752f157dc1b603c74949538691` and the pinned `requirements.txt` at that revision |
| Attack cases and effective settings | Both sinusoidal IDs are included. `full_matrix` includes the pulse from Attack commit `12be6a8`. The earlier elbow-flip candidate was outside this case list. |
| Defense settings | All eight defense entries, with effective settings in the frozen configuration |
| Three baseline checkpoint paths and SHA-256 hashes | Verified against the checkout before running |
| Backup checkpoint path and SHA-256 hash | Used the verified `sac_seed_1_robust` checkpoint below |
| Environment and package versions | Apple Silicon macOS, CPython 3.12.14, CPU inference. Installed runtime versions matched the lock. |

## Verified checkpoints

| Checkpoint | SHA-256 |
|---|---|
| `models/sac_seed_1_sync/model.zip` | `7f2b85e22601fd847793710991d245f8b6975ef935fa5a2e0592ca83f219bc24` |
| `models/sac_seed_2_sync/model.zip` | `dc3d8fb11d9f874b5bdee1384af18d3c4a947900a2105201d3382363fc7141b9` |
| `models/sac_seed_3_sync/model.zip` | `2ba35bea85ccbbfdb50d16cfa8257b2362329202c67fe6c716d58dc8b577616f` |
| `models/sac_seed_1_robust/model.zip` | `1a2cc2dba8d1487c8e0b6ccaf1653968cd9b79c6053b290af681e46b90513c3b` |

The matrices used `--fallback-model models/sac_seed_1_robust/model.zip`.
The full matrix retained traces for replay and fallback action-override
counts.

## Executed runs

| Run | Calibration seed base / episodes per policy | Evaluation seed base / states per policy | Evaluation rows | Output directory |
|---|---|---|---|---|
| `late_strong` | `1000000` / 100 | `1200000` / 30 | 15,120 | `late_strong/` |
| `full_matrix` | `1000000` / 100 | `1200000` / 30 | 22,320 | `full_matrix/` |
| Velocity ablation | `1400000` / 100 per noise level | `1450000` / 30 per noise level | 2,250 | `velocity/` within the combined ablation run |
| Position ablation | `1500000` / 100 per noise level | `1550000` / 30 per noise level | 1,350 | `position/` within the combined ablation run |

Matrix rows equal policies × states × cases × defenses, including the clean
case. With the frozen case list and all eight defenses, the counts are 15,120
for `late_strong` and 22,320 for `full_matrix` with its 31 cases, including
`pulse_e1.0_s60_d40_on18_off2`. Recalculate if the case or defense lists change.
Keep the two matrix runs separate because they share conditions and seeds.
The four ablation blocks are disjoint across all three policies
(with a stride of 1,000), the known smoke runs, the five-level development
sweep, and the official matrix block. Each sweep reuses its paired states
across noise levels.

## Reproduction commands

Run from the frozen revision with the locked dependencies installed. The
commands below create fresh directories. The evidence bundle uses shorter
subdirectory names for the archived summaries and figures.

```bash
python run_matrix.py --preset late_strong \
  --fallback-model models/sac_seed_1_robust/model.zip \
  --no-traces --out outputs/phase2_late_strong_final_001
python run_matrix.py --preset full_matrix \
  --fallback-model models/sac_seed_1_robust/model.zip \
  --out outputs/phase2_full_matrix_final_001
python run_ablation.py --mode both --preset full \
  --velocity-cal-base 1400000 --velocity-seed-base 1450000 \
  --position-cal-base 1500000 --position-seed-base 1550000 \
  --out outputs/phase2_ablation_final_001
```

## Acceptance checks

- Run the framework and attack/defense regression tests at the integrated
  revision. Check the case IDs and paired states in a development smoke run.
- Run `python evaluation/check_results.py RUN_DIR` on each completed matrix
  and the combined ablation directory. Retain the resolved configs,
  calibration records, episode tables, summaries, and completion statuses.
- Report success, aborts, in-window detection, and clean false alarms per
  episode and per step separately. Report ablation joint-angle error and
  calibrated threshold with their units, along with task outcomes.
- Record the replay's policy, case, seed, and defense panels. Label it as an
  illustrative example and keep its source trace.
