# Local Independent Reproduction Report (2026-11-18)

Final compatible Windows environment: Python 3.12.14 base interpreter with project-local `.venv` running `Torch 2.14.1+cpu` (`pip check` clean, 16 tests passed, numerical and Windows offscreen rendering checks passed). Final compatible runs are stored in `github_upload/outputs/reproduction_20261118_compatible_main` and `exploratory_20261118_compatible`; full trace audits passed for both. Task outcomes matched historical results, with maximum final-10-step mean distance discrepancy ~`0.000027 mm`.

All three model hashes matched historical config: `{'sac_seed_1_sync': True, 'sac_seed_2_sync': True, 'sac_seed_3_sync': True}`.

Initial diagnostic environment details (before switching `.venv` Torch to `2.14.1+cpu`): Python `3.12.14` (MSC v.1942 64-bit AMD64, Windows 11), `torch 2.7.1+cu126`, `numpy 2.4.6`, `mujoco 3.15.0`, `gymnasium 1.4.0`, `stable-baselines3 2.9.0`, `pytest 9.1.1`, `matplotlib 3.11.2`, `pandas 3.0.6`, CPU Intel Core Ultra 7 155H (16 cores, 22 logical CPUs).

Historical vs. initial local run counts (`4,500` evaluation + `300` calibration episodes):

| Dataset | Defense | Successes | Episodes | Aborts |
|---|---|---:|---:|---:|
| historical | False | 2250 | 2250 | 0 |
| historical | True | 2248 | 2250 | 2 |
| local | False | 2250 | 2250 | 0 |
| local | True | 2248 | 2250 | 2 |

Elementwise comparison (initial local diagnostic run vs. historical `main_v1`):

| Metric | Unequal | Max Abs Difference |
|---|---:|---:|
| `task_success` | 0 | 0.0 |
| `aborted` | 0 | 0.0 |
| `steps` | 0 | 0.0 |
| `alarm_count` | 0 | 0.0 |
| `final_10_mean_distance_m` | 97 | 1.0061396160665481e-16 |
| `terminal_distance_m` | 140 | 1.0061396160665481e-16 |
| `window_mean_distance_m` | 72 | 1.0061396160665481e-16 |
| `control_effort` | 0 | 0.0 |

Historical clean step false-alarm rate: `1.021324%`, episode rate `63/90`. Seed `802009` aborted at step `40` on the 21st consecutive alarm under both `bias` and `random_bias` (`bias` abort residual `6.9769 mm`, true distance `3.8490 mm`).

Historical main run elapsed `126.90 s`; initial local run `290.16 s` (concurrent with audit/exploratory work); compatible-Torch main rerun elapsed `286.37 s`.

Compatibility fix: `pip check` under `Torch 2.7.1` flagged SB3 `2.9.0` requiring `Torch >= 2.8`. Installing `Torch 2.14.1+cpu` inside the project `.venv` resolved `pip check` (`No broken requirements found`). Full `4,500`-episode main and `1,008`-dev / `3,780`-test exploratory reruns were saved in `reproduction_20261118_compatible_main` and `exploratory_20261118_compatible`. Discrete outcomes matched 100%, while floating-point differences between binaries exceeded the initial `1e-10` strict check (`0.000026805 mm` final-10 mean, `0.000035683 mm` terminal, `~1.77e-7` control effort, `0.000009602 mm` exploratory paired delta; see `compatible_environment_comparison.csv`).

Final Windows CPU dependency lock is saved in `github_upload/environment-windows-mp1.lock.txt`. See [FINAL_ACCEPTANCE.md](FINAL_ACCEPTANCE.md) and [FINAL_RESULTS.md](FINAL_RESULTS.md) for the subsequent compatible-run evidence reconciliation and presentation figure updates.
