# Phase 2 held-out evaluation

The runs used the frozen revision `167d7d2` and three baseline policies.
The two matrices reuse paired states and overlapping cases. Their totals
are reported separately. All shared episode keys agree on task success,
abort status, and in-window detection.

## Completed runs

| Run | Evaluation episodes | Calibration episodes |
|---|---:|---:|
| `late_strong` | 15,120 | 300 |
| `full_matrix` | 22,320 | 300 |
| `ablation/velocity` | 2,250 | 1,500 |
| `ablation/position` | 1,350 | 900 |

## Full matrix outcomes

Each defense has 90 clean episodes and 2,700 episodes across the 30
non-clean conditions. These counts aggregate repeated conditions
on paired states. A fail-stop abort counts as task failure.

| Defense | Task successes | Aborts | In-window detections | Clean episodes with alarms |
|---|---:|---:|---:|---:|
| `no_defense` | 1,376/2,700 | 0 | 0/2,700 | 0/90 |
| `original_fail_stop` | 1,652/2,700 | 930 | 2,335/2,700 | 59/90 |
| `grace1` | 1,684/2,700 | 898 | 2,335/2,700 | 59/90 |
| `cusum` | 2,542/2,700 | 0 | 2,351/2,700 | 1/90 |
| `sliding_window` | 2,542/2,700 | 0 | 2,357/2,700 | 5/90 |
| `continuous_velocity` | 2,541/2,700 | 0 | 2,171/2,700 | 1/90 |
| `ik_velocity_fusion` | 2,699/2,700 | 0 | 2,536/2,700 | 1/90 |
| `fallback_policy` | 2,690/2,700 | 0 | 2,536/2,700 | 1/90 |

### Pulse and sustained-bias comparison

Detection covers the scheduled pulse window, including its off steps.

| Case | Defense | Task successes | Aborts | In-window detections |
|---|---|---:|---:|---:|
| Pulse | `no_defense` | 3/90 | 0 | 0/90 |
| Pulse | `original_fail_stop` | 90/90 | 0 | 90/90 |
| Pulse | `ik_velocity_fusion` | 90/90 | 0 | 90/90 |
| Pulse | `fallback_policy` | 90/90 | 0 | 90/90 |
| Sustained bias | `no_defense` | 1/90 | 0 | 0/90 |
| Sustained bias | `original_fail_stop` | 0/90 | 90 | 90/90 |
| Sustained bias | `ik_velocity_fusion` | 90/90 | 0 | 90/90 |
| Sustained bias | `fallback_policy` | 89/90 | 0 | 90/90 |

The fallback policy overrode 44,850 actions across
2,414 episodes in the full matrix. The per-policy tables give
the clean step-level false-alarm rates as well as the episode rates.

## Noise ablations

Velocity results show mean applied joint-angle error. Position results show
the mean calibrated threshold across policies and task outcomes for IK fusion.
Each method and noise level uses 90 paired episodes. Full per-defense
task success, final distance, and angle error are in the ablation CSVs.

| Velocity noise σ (rad/s) | Integration error (mrad) | IK fusion error (mrad) | Integration successes | IK fusion successes |
|---:|---:|---:|---:|---:|
| 0 | 0.81 | 5.46 | 89/90 | 89/90 |
| 0.05 | 2.78 | 5.49 | 89/90 | 89/90 |
| 0.2 | 10.12 | 5.69 | 89/90 | 89/90 |
| 0.5 | 25.15 | 6.44 | 89/90 | 89/90 |
| 1 | 50.21 | 8.48 | 85/90 | 90/90 |

| Position noise σ (mm) | Calibrated threshold (mm) | IK fusion task successes | IK fusion aborts | IK fusion mean final distance (cm) |
|---:|---:|---:|---:|---:|
| 2 | 6.05 | 88/90 | 0 | 0.65 |
| 5 | 15.14 | 88/90 | 0 | 0.65 |
| 10 | 30.27 | 88/90 | 0 | 0.67 |

## Figures and evidence

- [Late-strong heatmap](late_strong/figures/matrix_heatmap.png) and [detection trade-off](late_strong/figures/detection_tradeoff.png).
- [Full matrix heatmap](full_matrix/figures/matrix_heatmap.png), [detection trade-off](full_matrix/figures/detection_tradeoff.png), and [per-policy summary](full_matrix/summary.csv).
- [Two-panel ablation figure](ablation/figures/ablation_summary.png), [all ablation curves](ablation/figures/ablation_curves.png), [velocity summary](ablation/velocity/ablation_summary.csv), and [position summary](ablation/position/ablation_summary.csv).
- [Paired comparison frame](full_matrix/figures/comparison_frame.png) and [replay](full_matrix/figures/comparison_replay.gif).

The replay illustrates `sustained_bias_e1.0_s60_d40` for `sac_seed_1_sync` at seed `1200007`.
All three panels share the same case, policy, and initial state.
Panel outcomes and fallback override counts are in [trace checks](trace_checks.json).

The [frozen configuration](freeze.json) records the revision, checkpoint
hashes, effective defense parameters, and seed blocks. Config paths were
made portable for this bundle. Full episode logs and traces remain local.
