# Direction 4A Matrix Evaluation, Ablation & Visualization

## macOS smoke validation

Verified on Apple Silicon macOS 27.0.1 with CPython 3.12.14 using framework
commit `abe050e`. The environment reused the Phase 1 macOS Python environment
with MuJoCo 3.15.0, Gymnasium 1.4.0, PyTorch 2.14.1 on CPU, and SB3 2.9.0.

## Reproduce the smoke checks

Run from the Phase 2 repository root with the dependencies from
`requirements.txt` and `env/requirements-dev.txt` installed.

```bash
run=$(mktemp -d "${TMPDIR:-/tmp}/dase7508-task3.XXXXXX")
export MPLBACKEND=Agg
export MPLCONFIGDIR="$run/matplotlib"
python -m pytest -q tests/test_framework.py
python check_setup.py --no-render --out "$run/setup"
python run_matrix.py --preset smoke --out "$run/matrix"
python plot_matrix.py "$run/matrix"
python run_ablation.py --mode both --preset smoke --out "$run/ablation"
python plot_matrix.py "$run/ablation"
printf 'Smoke outputs: %s\n' "$run"
```

| Check | Observed result |
|---|---|
| Framework tests | 49 passed |
| Numerical setup | 100 steps at 20 ms per step, maximum forward-kinematics error 6.94e-17 m |
| Matrix | 96 evaluation episodes, 10 calibration episodes, compressed traces retained |
| Velocity noise sweep | 40 evaluation episodes and 20 calibration episodes |
| Position noise sweep | 40 evaluation episodes and 20 calibration episodes |
| Plotting | Heatmap, detection trade-off, comparison frame, 51-frame replay GIF, and ablation curves generated |

The matrix used the development block beginning at 1100000 and left the held-out
matrix block at 1200000 unused. The ablation smoke preset uses the same velocity
and position seed bases as the full ablation, 1300000 and 1350000 respectively.
The initial smoke states therefore overlap the full ablation defaults. Keep
these results for pipeline validation. If the full ablation must use independent
states, agree on fresh seed blocks before running it.

## Final report table

Fill one row per case and defense from the formal runs. Keep the per-policy
breakdown and record the revision, preset, and model hashes with the results.

| Case | Defense | Task success (n/N) | Aborts (n/N) | In-window detection (%) | Clean false alarms per episode (%) | Clean false alarms per step (%) | Paired window distance change (cm) |
|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | — |

Use the paired clean condition for the distance comparison and identify the
number of paired initial states. Mark unavailable metrics explicitly. Distinguish
a fail-stop abort from an episode that finishes outside the distance criterion.

The stock ablation curves show task success and distance. For the final report,
also extract applied joint-angle error and the calibrated threshold from
`ablation_summary.csv` and verify how each is aggregated before interpreting
velocity drift or position-noise sensitivity.
