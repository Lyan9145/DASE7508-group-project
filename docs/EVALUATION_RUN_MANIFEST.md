# Evaluation run manifest

Copy this template into the final run record and fill in all decisions before
using the held-out seeds. Attach the actual commands and output configs after
execution.

## Freeze record

| Item | Value |
|---|---|
| Integrated Git commit and package lock | Preparation branch tested locally. Record the final shared commit and package lock before execution. |
| Attack cases and effective settings | Preparation includes both sinusoidal IDs and the existing pulse configuration from Attack commit `12be6a8` in `full_matrix`. The earlier elbow-flip candidate remains outside the proposed case list. |
| Defense settings | Pending. Record effective parameters, including any values supplied by class defaults. |
| Three baseline checkpoint paths and SHA-256 hashes | Pending |
| Backup checkpoint path and SHA-256 hash | Candidate verified on the merged Defense code. See the hash below. |
| Environment and package versions | Pending |
| Frozen by and date | Pending |

## Verified candidate checkpoints

Confirm these paths and hashes again at the frozen revision.

| Checkpoint | SHA-256 |
|---|---|
| `models/sac_seed_1_sync/model.zip` | `7f2b85e22601fd847793710991d245f8b6975ef935fa5a2e0592ca83f219bc24` |
| `models/sac_seed_2_sync/model.zip` | `dc3d8fb11d9f874b5bdee1384af18d3c4a947900a2105201d3382363fc7141b9` |
| `models/sac_seed_3_sync/model.zip` | `2ba35bea85ccbbfdb50d16cfa8257b2362329202c67fe6c716d58dc8b577616f` |
| `models/sac_seed_1_robust/model.zip` | `1a2cc2dba8d1487c8e0b6ccaf1653968cd9b79c6053b290af681e46b90513c3b` |

If the frozen configuration includes `fallback_policy`, pass the verified
checkpoint explicitly with `--fallback-model models/sac_seed_1_robust/model.zip`
and confirm a development trace records
`defense_status.action_overridden=true` in a case that exercises the switch.
Record override steps and episodes separately from steps labeled
`state="fallback"`.

## Planned runs

| Run | Calibration seed base / episodes per policy | Evaluation seed base / states per policy | Expected rows | Output directory |
|---|---|---|---|---|
| Integrated smoke | Development calibration / pending | Development block / pending | Pending | Pending |
| `late_strong` | `1000000` / 100 | `1200000` / 30 | 15,120 | Pending |
| `full_matrix` | `1000000` / 100 | `1200000` / 30 | 22,320 | Pending |
| Velocity ablation | `1400000` / 100 per noise level | `1450000` / 30 per noise level | 2,250 | `velocity/` within the combined ablation run |
| Position ablation | `1500000` / 100 per noise level | `1550000` / 30 per noise level | 1,350 | `position/` within the combined ablation run |

Matrix rows equal policies × states × cases × defenses, including the clean
case. With the current draft and all eight defenses, the counts are 15,120
for `late_strong` and 22,320 for `full_matrix` with its 31 cases, including
`pulse_e1.0_s60_d40_on18_off2`. Recalculate if the case or defense lists change.
Keep the two matrix runs separate because they share conditions and seeds.
The four proposed ablation blocks are disjoint across all three policies
(with a stride of 1,000), the known smoke runs, the five-level development
sweep, and the official matrix block. Each sweep reuses its paired states
across noise levels. Decide which runs retain traces and preserve at least the
matrix traces needed for the replay and fallback-override counts.

## Ablation command after the freeze

```bash
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
