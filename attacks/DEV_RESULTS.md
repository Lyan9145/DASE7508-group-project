# Phase-2 attack development handoff (2026-11-21)

## Scope and environment

This is a **development-set scan**, not the held-out Phase-2 main study. It uses
`DEV_BASE=1100000`, 30 paired states per frozen policy, 100 independent clean
calibration episodes per policy from `CAL_BASE=1000000`, position noise
`sigma=0.002 m`, and alternating attack signs. All results below use the
`no_defense` condition unless explicitly stated otherwise. The recorded runs are
`outputs/dev_attack_sweep_030/` and `outputs/dev_attack_plugins_030/` (local,
gitignored). The command for the first run was:

```bash
python run_matrix.py --preset late_strong --defenses no_defense \
  --episodes 30 --calibration-episodes 100 \
  --test-base 1100000 --cal-base 1000000 --no-traces \
  --out outputs/dev_attack_sweep_030
```

The available local verification environment differed from `requirements.txt`:
Python 3.12.13, Torch 2.11.0, NumPy 2.2.6, Gymnasium 1.3.0, MuJoCo 4.0.0,
SB3 2.9.0. Re-run selected cases with the pinned environment before using
numerical values in the final report. No frozen models were modified.

## No-defense failure boundary

Entries are **task successes / 30** for policy seeds 1, 2, and 3, in that order.
The clean baseline was `30/30`, `29/30`, `30/30`; use paired clean-success
denominators from `summary.csv` when reporting attack success rates.

| Attack case | Seed 1 | Seed 2 | Seed 3 |
| --- | ---: | ---: | ---: |
| Bias, start 80, 20 steps, 0.3 rad | 25 | 27 | 29 |
| Bias, start 80, 20 steps, 0.5 rad | 9 | 10 | 10 |
| Bias, start 80, 20 steps, 1.0 rad | 2 | 4 | 0 |
| Bias, start 60, 40 steps, 0.5 rad | 9 | 9 | 8 |
| Bias, start 60, 40 steps, 1.0 rad | 2 | 1 | 0 |
| Ramp, start 80, 20 steps, 0.5 rad | 27 | 29 | 29 |
| Ramp, start 80, 20 steps, 1.0 rad | 9 | 10 | 12 |
| Ramp, start 60, 40 steps, 1.0 rad | 4 | 6 | 1 |
| Elbow flip, start 80, 20 steps | 16 | 6 | 19 |
| Joint-angle/velocity coupled, start 60, 40 steps, 1.0 rad | 2 | 1 | 0 |
| Policy-gradient, start 60, 40 steps, 1.0 rad | 2 | 1 | 0 |
| Threshold-aware ramp, start 60, 40 steps, 0.3 rad | 30 | 30 | 30 |

In this tested grid, bias begins reducing success at 0.3 rad and causes a large
drop at 0.5 rad. A 1.0 rad sustained bias nearly eliminates success across all
three policies, but **does not reach zero on every policy**. The threshold-aware
ramp evades most alarms yet did not cause final task failures in this scan.
Elbow flip is a stronger low-residual case for defense evaluation; its measured
FK position is preserved by construction, though clean sensor noise can still
produce alarms.

## Attack implementation changes

- `ThresholdAwareRampAttack` now checks the actual noisy fingertip measurement
  and bisects to the largest angle in the requested sign direction that remains
  within `margin * calibrated_threshold_m`. When clean noise already exceeds the
  budget, it emits zero perturbation. In 1,146 eligible observations from ten
  clean trajectories per policy, the former ideal-geometry cap exceeded the
  requested residual budget 625 times; the revised cap exceeded it zero times.
- `PolicyGradientAttack` now searches from three starts by default and keeps the
  best intermediate candidate. It optionally subtracts an FK-residual penalty
  (`residual_weight > 0`) from its instantaneous action-divergence objective.
  On ten clean step-80 observations per policy, mean squared action divergence
  for one versus three starts was `0.0621 -> 0.0626`, `0.0564 -> 0.0672`, and
  `0.0657 -> 0.0805`. This is an action-level measure, **not** a measured
  improvement in episode attack-success rate.
- `SinusoidalAttack` defaults to `freq_hz=0.25`, `phase=pi/2`. A direct paired
  30-state scan of the existing `epsilon=1.0, start=80, duration=20` setup gave
  task successes `3/30`, `5/30`, `0/30`. The existing 5 Hz, zero-phase setting
  gave `30/30`, `29/30`, `30/30`. Frequencies 0.5 Hz and 1 Hz at phase `pi/2`
  were also checked; 0.25 Hz was strongest among these tested settings.

## Integration note

`evaluation/presets.py` and `evaluation/runner.py` explicitly pass 5 Hz and
zero phase for the named sinusoidal matrix case, so the new class default does
**not** change that preset. The evaluation track should add a separately named
`0.25 Hz, pi/2` case after reviewing the development result. Keep main-study
seed block `TEST_BASE=1200000` untouched until attacks and defenses are frozen.
