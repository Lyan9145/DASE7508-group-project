# Evaluation development snapshot, November 21, 2026

The matrix and smoke runs use one policy, `sac_seed_1_sync`. The five-level
velocity development sweep uses all three baseline policies. The official
held-out matrix block beginning at 1200000 was unused.

| Run | Evaluation episodes | Calibration episodes | Seed base |
|---|---:|---:|---:|
| Sinusoidal preset smoke | 6 | 10 | 1100000 |
| Merged Defense verification | 150 | 10 | 1110000 |
| Velocity ablation smoke | 40 | 20 | 1300000 |
| Position ablation smoke | 40 | 20 | 1350000 |
| Five-level velocity development sweep | 2,250 | 1,500 | 1150000 |

For the original matrix and smoke runs, the checkout was at merged Defense commit
`5e18eca02978896dd56c37cc7e5e45c3ede8cfe5`, with the sinusoidal preset edit
later committed as `f19a019`. The other draft edits were documentation.
The matrix used a subset of cases in the full preset. The five-level velocity
sweep ran at `d04d645` with calibration seed base `1070000`. See the
[run manifest](../../../docs/EVALUATION_RUN_MANIFEST.md) for all baseline
checkpoint hashes. Git normalizes CSV line endings.
Configs use repository-relative model paths and snapshot-relative ablation
subdirectories in place of machine-specific absolute paths. Episode logs,
calibration data, traces, and replay remain local.

| Checkpoint | SHA-256 |
|---|---|
| `models/sac_seed_1_sync/model.zip` | `7f2b85e22601fd847793710991d245f8b6975ef935fa5a2e0592ca83f219bc24` |
| `models/sac_seed_1_robust/model.zip` (matrix fallback) | `1a2cc2dba8d1487c8e0b6ccaf1653968cd9b79c6053b290af681e46b90513c3b` |

See the [preliminary report](../../../docs/EVALUATION_PRELIMINARY.md) for interpretation
and the [run manifest](../../../docs/EVALUATION_RUN_MANIFEST.md) for the pending freeze
decisions. The snapshot contains summary evidence. The result checker requires
the original episode logs.

## Matrix figures

- [Matrix heatmap](matrix/figures/matrix_heatmap.png) shows task success and
  paired distance change for one policy and six development states per
  condition.
- [Comparison frame](matrix/figures/comparison_frame.png) illustrates one
  paired bias case, seed `1110005`. All three runs completed 100 steps. The
  undefended arm missed the success criterion. The original fail-stop and
  IK fusion runs both succeeded.

## Ablation figure

The [two-panel ablation figure](ablation/figures/ablation_curves.png) shows
measured joint-angle error at five velocity noise levels and the calibrated
threshold at two position noise levels. The [velocity development summary](ablation/velocity-development-sweep/ablation_summary.csv)
and [position smoke summary](ablation/position/ablation_summary.csv) contain
exact task-success and final-distance values. The original velocity smoke
summary remains available for traceability.
