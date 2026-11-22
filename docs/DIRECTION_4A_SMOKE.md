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

## Final Report Tables and Reporting Conventions

Completed held-out Phase-2 tables, per-defense totals, and figures are archived in [the held-out results bundle](../outputs/evidence/phase2-held-out-167d7d2/README.md) and documented alongside exact seed blocks and checkpoint hashes in [the evaluation run manifest](EVALUATION_RUN_MANIFEST.md).

When compiling final slides or paper tables from the CSV summaries (`matrix_summary.csv`, `summary.csv`, `ablation_summary.csv`):

Use the paired clean condition for the distance comparison and identify the
number of paired initial states. Mark unavailable metrics explicitly. Distinguish
a fail-stop abort from an episode that finishes outside the distance criterion.

The ablation curves show task success, distance, applied joint-angle error,
and calibrated threshold. For the final report, verify the aggregation in
`ablation_summary.csv` before interpreting velocity drift or position-noise
sensitivity.

## Sinusoidal comparison for the Phase 2 matrix

The `late_strong` and `full_matrix` presets include two sinusoidal cases:

| Case ID | Frequency | Phase |
|---|---:|---:|
| `sinusoidal_e1.0_s80_d20` | 5 Hz | 0 rad |
| `sinusoidal_e1.0_s80_d20_f0.25_phase_pi_over_2` | 0.25 Hz | π/2 rad |

Both cases use the same amplitude and window. Report them separately on paired
states. The tuned configuration came from development results in
[PR #4](https://github.com/Lyan9145/DASE7508-group-project/pull/4). Record the
integrated revision before the formal run, since the PR also changes the
behavior of other attack classes under their existing case IDs.

## Final-run checklist

Use the [evaluation run manifest](EVALUATION_RUN_MANIFEST.md) to record the
frozen configuration and output checks.

- Freeze the integrated commit, attack case IDs and parameters, defense
  settings, and checkpoint hashes. The matrix records most of this in
  `config.json`. Record the fallback checkpoint hash separately if one is used.
  Without that checkpoint, explicitly exclude `fallback_policy` from the final
  defense selectors or label any run of it as having no backup policy.
- From the integrated revision, rerun the framework and attack regression
  tests and a small trace-enabled matrix using development seeds. Confirm that
  both sinusoidal case IDs appear and that plotting and replay still work.
- Confirm the expected row counts before running the held-out block. With the
  frozen `167d7d2` configuration and all eight defense entries, `late_strong` has 21 cases
  and 15,120 evaluation rows, and `full_matrix` has 31 cases and 22,320 rows including `pulse_e1.0_s60_d40_on18_off2`.
  These counts include clean and use 3 policies × 30 paired states per case
  and defense. Keep the two matrix runs separate because they share overlapping
  cases and evaluation seeds (`1200000`).
- After each run, check the completion flag, verify the planned row count and
  unique (policy, seed, case, defense) keys, and confirm that each condition
  covers the same states within each policy. Keep traces for the selected replay.
- Use disjoint held-out ablation seed blocks (`1400000`/`1450000` for velocity; `1500000`/`1550000` for position, which are the defaults for `--preset full`) and include applied angle error and calibrated threshold in the ablation figures and tables.

## Periodic Pulse Case Note

Commit `12be6a8` added the periodic `pulse` attack to the registry, and it is
included as `pulse_e1.0_s60_d40_on18_off2` in `full_matrix` alongside the
matched sustained-bias reference `sustained_bias_e1.0_s60_d40`.

For the pulse comparison, report task success, aborts, and detection separately.
The episode-level detection metric counts alarms anywhere in the
scheduled `[start, start + duration)` window, including pulse-off observations. If a report requires
active-pulse detection, filter the pulse trace to nonzero `delta_rad` observations and label the
metric separately (`is_active` covers the scheduled pulse window).
