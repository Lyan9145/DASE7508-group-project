# Preliminary Evaluation results

**Status:** Development evidence and pipeline validation. The final case set,
defense settings, and held-out results are pending. The official matrix seed
block beginning at 1200000 remains unused.

See the [development evidence bundle](../outputs/evidence/evaluation-development-20261121/README.md)
for the summary tables, run configs, and figures.

## What is ready

- The smoke report, ablation plots, result checker, and full-size layout check
  are merged into the shared Phase 2 branch through [PR #5](https://github.com/Lyan9145/DASE7508-group-project/pull/5).
  The framework smoke covered 96 matrix episodes and 80 ablation episodes.
- The paired sinusoidal comparison is wired locally and verified on two
  development states. The exploratory pulse and earlier elbow-flip cases
  are candidates for the final manifest.
- The [run manifest](EVALUATION_RUN_MANIFEST.md) will record the integrated revision, cases, defenses,
  checkpoint hashes, seeds, and expected row counts.

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
The result checker accepted both sweeps and the combined run. The two defenses
shown in the velocity table succeeded in all four states at both noise levels.
Their mean applied angle error differs even when success counts are equal.

| Velocity noise SD (rad/s) | Mean applied angle error, continuous velocity (rad) | Mean applied angle error, IK fusion (rad) |
|---:|---:|---:|
| 0.00 | 0.00113 | 0.00458 |
| 0.50 | 0.02238 | 0.00519 |

| Position noise SD (m) | Mean calibrated threshold (mm) |
|---:|---:|
| 0.002 | 6.14 |
| 0.008 | 24.54 |

The smoke artifacts include a matrix heatmap, detection trade-off plot,
ablation figure, and a paired three-panel replay. The full-size synthetic
heatmap in the [layout check](EVALUATION_LAYOUT.md) is a formatting preview.
For a progress slide, use the Defense verification table and label it
**Development verification · 1 policy · 6 paired states**.

## Before producing final figures

Freeze the case list, effective defense settings, and final ablation seed
blocks. Run the development smoke again if the integrated revision changes.
Complete the run manifest before starting the official runs.
