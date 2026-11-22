# Group Experiment Progress and Results | 2026-10-22

The approximately one-hour integration session is complete: foundational bugs were fixed, attacks and mitigation were implemented, tests passed, the pilot completed, and the frozen three-policy main experiment specified in Proposal 2.0 was executed and audited.

## Executive Summary

Under the Proposal 2.0 threat model, amplitudes, early attack window, and task success criterion, all unprotected episodes reached the target successfully, and no attack converted a clean success into a task failure. The monitor reduced some transient trajectory deviation, but introduced two rule-induced aborts; therefore, it cannot be claimed to improve terminal task success rate.

Both aborts occurred on the **same initial state** (policy seed 3, test seed 802009), repeated under `bias` and its matched `random_bias` control, rather than two independent failing states. A post-attack sensor-noise false alarm extended the 20-step attack alarm streak to 21, triggering the pre-specified abort rule while true fingertip-to-target distance was approximately 3.85 mm.

## Completed Fixes and Implementations

- Training sensor noise advances continuously across episodes by default; explicit `noise_seed` enables paired-noise replay.
- Position readings and evaluation truth are recomputed via `mj_forward` on an isolated `MjData` without modifying simulator state. Noiseless kinematic error is at floating-point precision, and physics trajectory invariance tests pass.
- Training and evaluation outputs refuse to overwrite existing directories; the original uploaded model and validation artifact remain intact.
- `joint0` `bias`/`ramp` spoofing and matched random-sign controls modify only indices `0` and `2` (`cos`/`sin`).
- Kinematic residual monitor, per-policy 99th-percentile clean calibration, previous-velocity integration correction, and abort when consecutive alarms strictly exceed 20.
- Disjoint validation/calibration/test seeds, frozen main plan, model hashes, executed code snapshots, full traces, and derived analysis snapshots.
- All 11 Phase-1 tests passed; dependencies, physics semantics, and EGL offscreen rendering checks passed.

## Three New Policies: Training and Independent Validation

Each policy was trained with synchronized sampling, non-repeating training noise, and identical hyperparameters for 150,000 steps without hitting the wall-clock cap. Three runs executed in parallel (~19 minutes each). Each policy was validated on 30 independent episodes (qualification threshold: at least 24/30).

| Training Seed | Steps | Validation Successes | Mean Final-10-Step Distance | Worst Episode |
|---|---:|---:|---:|---:|
| 1 | 150,000 | 30/30 | 0.535 cm | 1.536 cm |
| 2 | 150,000 | 30/30 | 0.602 cm | 1.536 cm |
| 3 | 150,000 | 30/30 | 0.602 cm | 2.012 cm |

The original uploaded model was also re-validated in both legacy and synchronized modes (30/30 in both; maximum discrepancy vs. recorded legacy metric ~`5.94e-9 m`). That check reused original validation seeds and is not treated as new held-out test evidence.

## Main Experiment Configuration and Integrity

- Configuration frozen before main testing in `github_upload/main_plan.json`; attacks and thresholds were not adjusted after observing results.
- 3 policies x 30 initial states per policy x 50 conditions = **4,500 episodes**, plus **300 independent clean calibration episodes**. The 4,500 episodes represent paired condition repetitions across 90 policy/initial-state pairs, not 4,500 independent initial states.
- Amplitudes `epsilon` = `0.02 / 0.05 / 0.10 rad`, durations `5 / 20` steps, `bias`/`ramp`, amplitude-matched random-sign controls, monitor off/on, and reused clean baselines.
- Default attack window starts at observation step `20`; 100 control steps per episode, `dt = 0.02 s`, position noise `sigma = 2 mm` per coordinate.
- Calibration seed blocks `300000/301000/302000` and test seed blocks `800000/801000/802000` are disjoint from validation and pilot blocks.
- Executed control actions: `449,880`; trace records: `449,882` (difference corresponds to the two aborted observation records).
- Calibration + main evaluation took ~`126.9 s` (CPU: Intel Core i5-14600KF, Python 3.11.17, Torch 2.14.1+cpu, MuJoCo 3.15.0, Gymnasium 1.4.0, SB3 2.9.0).
- Independent full-trace audit passed: paired states and noise, attack windows/amplitudes/signs, protected channels, angle correction, abort boundary, task scoring, control effort, and code/plan hashes.

## Main Results

All unprotected conditions (clean and perturbed) achieved **2250/2250** successes; protected conditions achieved **2248/2250** successes. Attack success rate was `0/90` for every unprotected `bias`/`ramp` setting. Under defense, `bias` `epsilon=0.10`, 20 steps succeeded `89/90` (and its matched random-sign control `89/90`); all other conditions succeeded `90/90`.

Aggregated across the 3 policies (30 paired states each; distance delta is mean target distance in the attack window plus 10 following steps minus the paired clean trajectory, in mm; missed detections count zero alarms inside the attack window, noting noise alarms inside the window also count per protocol):

| Attack | `epsilon` (rad) | Steps | Unprotected Delta (mm) | Protected Delta (mm) | Missed / 90 | Defense Aborts / 90 |
|---|---:|---:|---:|---:|---:|---:|
| bias | 0.02 | 5 | 0.034 | 0.033 | 58 | 0 |
| bias | 0.05 | 5 | 0.139 | 0.104 | 4 | 0 |
| bias | 0.10 | 5 | 0.426 | 0.003 | 0 | 0 |
| bias | 0.02 | 20 | 0.075 | 0.074 | 27 | 0 |
| bias | 0.05 | 20 | 0.460 | 0.382 | 0 | 0 |
| bias | 0.10 | 20 | 1.624 | 0.176 | 0 | 1 |
| ramp | 0.02 | 5 | 0.016 | 0.015 | 75 | 0 |
| ramp | 0.05 | 5 | 0.060 | 0.048 | 21 | 0 |
| ramp | 0.10 | 5 | 0.186 | 0.064 | 1 | 0 |
| ramp | 0.02 | 20 | 0.019 | 0.019 | 47 | 0 |
| ramp | 0.05 | 20 | 0.139 | 0.129 | 14 | 0 |
| ramp | 0.10 | 20 | 0.582 | 0.252 | 2 | 0 |

For `bias` `epsilon=0.10`, 20 steps, mean extra distance dropped from ~`1.62 mm` to `0.18 mm`, but one protected trial aborted (incomplete window, compared against equal-length clean prefix). Aborts count as task failures; secondary distance metrics do not override task success conclusions. Per-policy raw metrics, ranges, terminal errors, control effort, detection delays, and recovery times are stored in CSV/JSON.

## False Alarms and Failure Cases

| Policy | Calibrated Threshold (mm) | Clean Per-Step FA Rate | Clean Episodes with >= 1 Alarm |
|---|---:|---:|---:|
| `sac_seed_1_sync` | 6.158 | 0.94% | 70.0% |
| `sac_seed_2_sync` | 6.020 | 1.14% | 76.7% |
| `sac_seed_3_sync` | 6.071 | 0.98% | 63.3% |

Overall clean step false-alarm rate was ~**1.02%**, while **63/90 (70%)** of clean episodes had at least one alarm. The 99th percentile calibrates a per-step threshold rather than a 1% per-episode rate; at 1% independent per-step probability over 99 opportunities, at least one alarm occurs with probability `1 - 0.99**99 ≈ 63%`. No clean episode aborted or failed.

Both failures occurred on seed `802009` under defense at step `40`: after 20 attack alarms during steps `20–39`, the attack ended, but Gaussian sensor noise at step `40` pushed the residual over threshold for a 21st consecutive alarm while true distance was only ~`0.385 cm`. Independent single-case re-runs reproduced both outcomes exactly; records were retained and the protocol was not retuned retroactively.

Monitor overhead averaged ~**13.7 us/step** (excluding model inference, physics, logging, and initialization; specific to this machine and implementation).

## Interpretation and Next Steps

Conclusion within Proposal 2.0 bounds: small, short single-joint spoofing did not cause terminal reaching failures; kinematic detection reduced some transient deviations, yet small/ramping attacks still produced missed detections and consecutive-alarm aborts introduced task failures.

Likely reasons include direct policy access to trusted relative fingertip position and early attack termination leaving long recovery horizons. With total link length `0.21 m`, a `0.02 rad` offset yields at most ~`4.2 mm` noiseless geometric discrepancy, below the ~`6 mm` noise-calibrated threshold (see [github_upload/ANALYSIS_NOTES.md](github_upload/ANALYSIS_NOTES.md)).

Subsequent exploratory studies (such as late-window or multi-channel attacks and alternative defenses) must be run in separate output directories with fresh disjoint seeds and frozen configurations without altering `outputs/main_v1/`. (For the Phase-2 unified extension framework, see [github_upload/FRAMEWORK_GUIDE.md](github_upload/FRAMEWORK_GUIDE.md).)

These simulation results depend on idealized geometry and protected position/velocity assumptions and do not generalize directly to physical hardware safety.

## Artifact Index

- Protocol and metrics: [github_upload/PROTOCOL.md](github_upload/PROTOCOL.md), `github_upload/main_plan.json`
- Main results: `github_upload/outputs/main_v1/summary.csv`, `aggregate.csv`, `episodes.csv`
- Completion & audit: `run_status.json`, `audit.json`; failure diagnostics: `failure_analysis.json`, `failure_cases.csv`
- Full logs & snapshots: `traces.jsonl.gz`, `source/`, `analysis_source/`
- Figures & replay: `figures/paired_results.png`, `detection_rates.png`, `example_trajectory.png`, `abort_case_1.png`, `abort_case_2.png`, `figures/arm_replay.gif`, `outputs/session_20261022/training_curves.png`
- Setup & locks: [github_upload/README.md](github_upload/README.md), `github_upload/environment-linux-cpu.lock.txt`

The corrected pilot is in `pilot_checked_20261022`; `pilot_20261022` is retained solely as history (with a previously fixed display-metric bug) and is not used for formal conclusions.
