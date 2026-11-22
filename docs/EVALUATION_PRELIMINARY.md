# Preliminary Evaluation Results (Nov 21 Development Snapshot)

**Status:** Historical pre-freeze development snapshot (`2026-11-21`). The final Phase-2 case list, defense parameters, and held-out evaluation runs (`15,120` + `22,320` matrix episodes and `3,600` noise ablation episodes) have since been frozen and completed in [the held-out results bundle](../outputs/evidence/phase2-held-out-167d7d2/README.md); see [EVALUATION_RUN_MANIFEST.md](EVALUATION_RUN_MANIFEST.md) for the authoritative freeze record.

See the [development evidence bundle](../outputs/evidence/evaluation-development-20261121/README.md)
for the development summary tables, run configs, and figures recorded prior to the held-out runs.

## What Was Validated Here

- The smoke report, ablation plots, result checker, and full-size layout check
  were merged through [PR #5](https://github.com/Lyan9145/DASE7508-group-project/pull/5).
  The framework smoke covered 96 matrix episodes and 80 ablation episodes.
- The paired sinusoidal comparison and exploratory `pulse` attack candidate
  (`12be6a8`) were integrated and subsequently frozen in [EVALUATION_RUN_MANIFEST.md](EVALUATION_RUN_MANIFEST.md).

## Defense verification

The before and after runs used policy `sac_seed_1_sync`, the same six paired
development states starting at 1110000, and ten clean calibration episodes
per run. Each matrix contained 150 evaluation episodes. The comparison is
between the earlier shared framework and the merged Defense code at `5e18eca`.
The rerun reproduced the results from [Defense PR #6](https://github.com/Lyan9145/DASE7508-group-project/pull/6).
The checkpoint changed along with the defense implementation, so the result
measures the combined change.

| Metric | Before | Merged Defense |
|---|---:|---:|
| Clean episodes with any alarm, IK fusion | 4/6 | 0/6 |
| Clean episodes with any alarm, fallback | 4/6 | 0/6 |
| In-window detections, threshold-aware case, CUSUM | 5/6 | 6/6 |
| In-window detections, threshold-aware case, IK fusion | 2/6 | 6/6 |
| In-window detections, threshold-aware case, fallback | 2/6 | 6/6 |
| Task successes, elbow-flip case, fallback | 2/6 | 6/6 |
| Task successes, coupled-velocity case, fallback | 5/6 | 6/6 |

The merged run passed the result checker and recorded 391 backup-policy
action overrides across 21 episodes. The [fallback fix](https://github.com/Lyan9145/DASE7508-group-project/commit/7ba82c61010ca147f2d8cdd9ea9c0d715c2502a3)
now rejects a missing checkpoint before writing an output directory. A separate
two-state check with the checkpoint recorded 62 action overrides.

## Noise ablation preview

Both smoke sweeps were rerun on the merged Defense code. Each used one policy,
four paired states per noise level, and 40 evaluation episodes in total.
The result checker accepted both sweeps and the combined run.

A separate five-level velocity sweep used three policies and 30 paired states
per policy at each level. The checker accepted all 2,250 evaluation
episodes. The velocity sweep used development seeds starting at 1150000
and calibration seeds starting at 1070000.

| Velocity noise SD (rad/s) | Mean applied angle error, continuous velocity (mrad) | Mean applied angle error, IK fusion (mrad) |
|---:|---:|---:|
| 0.00 | 0.77 | 5.40 |
| 0.05 | 2.39 | 5.41 |
| 0.20 | 9.20 | 5.58 |
| 0.50 | 23.02 | 6.41 |
| 1.00 | 46.05 | 8.62 |

The position threshold values below come from the smoke run.

| Position noise SD (m) | Mean calibrated threshold (mm) |
|---:|---:|
| 0.002 | 6.14 |
| 0.008 | 24.54 |

The smoke artifacts include a matrix heatmap, detection trade-off plot,
ablation figure, and a paired three-panel replay. The full-size synthetic
heatmap in the [layout check](EVALUATION_LAYOUT.md) is a formatting preview.
For a progress slide, use the Defense verification table and label it
**Development verification · 1 policy · 6 paired states**.

## Progression to Held-Out Runs

Following these development checks, the frozen Phase-2 configuration (`167d7d2`), disjoint ablation seed blocks (`1400000`–`1550000`), and completed held-out results were recorded in [EVALUATION_RUN_MANIFEST.md](EVALUATION_RUN_MANIFEST.md) and [the held-out results bundle](../outputs/evidence/phase2-held-out-167d7d2/README.md).
