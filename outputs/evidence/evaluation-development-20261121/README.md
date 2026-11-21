# Evaluation development snapshot, November 21, 2026

These are preliminary runs using one policy, `sac_seed_1_sync`. The official
held-out matrix block beginning at 1200000 was unused.

| Run | Evaluation episodes | Calibration episodes | Seed base |
|---|---:|---:|---:|
| Sinusoidal preset smoke | 6 | 10 | 1100000 |
| Merged Defense verification | 150 | 10 | 1110000 |
| Velocity ablation smoke | 40 | 20 | 1300000 |
| Position ablation smoke | 40 | 20 | 1350000 |

The checkout was at merged Defense commit
`5e18eca02978896dd56c37cc7e5e45c3ede8cfe5`, with the sinusoidal preset edit
later committed as `f19a019`. The other draft edits were documentation.
The matrix used a subset of cases in the full preset. The summaries,
completion records, and ablation PNG preserve the original results. Git
normalizes CSV line endings.
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
