# Final Exploratory and Reproduction Results (2026-11-18)

All primary counts were re-verified in the project-local `Torch 2.14.1+cpu` compatible environment; initial legacy-Torch diagnostic runs are retained separately, and floating-point differences are tabulated below.

## Verified Key Findings

Across 1,080 paired 20-step attack conditions (`90` states x `12` conditions): unprotected `1080/1080`, original defense `1076/1080`, Wait+1 (`grace1`) `1080/1080`. All 4 failures under the original defense came from 4 distinct initial states (`sac_seed_1`: 1, `sac_seed_2`: 3, `sac_seed_3`: 0), all under `0.10 rad` bias. (`1,080` denotes repeated conditions, not `1,080` independent initial states.) Clean baseline achieved `90/90` under all three variants.

Not all 4 failures were caused by post-attack noise: `931009`/`931023` aborted at step `39` and `930016` at step `89` when a pre-window noise alarm connected to the attack streak; `931011` aborted at step `90` (see `exploratory_failure_steps.csv`). Waiting 1 extra step avoids these boundary aborts without identifying attack termination; sustained anomalies still abort.

Under 40-step sustained attacks (`0.10 rad` bias from step `20`): both `original` and `grace1` aborted `73/90` (same 73 pairs) and succeeded `17/90`, while unprotected succeeded `90/90`. Across the 73 shared aborted pairs, `grace1` delayed termination by exactly `+1` step (`20 ms`; `original` aborted at `39–57` steps, `grace1` at `40–58`). The 17 non-aborted cases confirm that consecutive-alarm rules do not abort every sustained anomaly (depending on misses, streak resets, and pose sensitivity).

Timing effect: under unprotected `0.10 rad` bias, final 10-step mean distance increased from `5.581 mm` (`start=20`) to `6.157 mm` (`start=70`), still well below the `30 mm` success threshold; paired attack+10-step delta moved from `1.119 mm` to `1.016 mm`. Later timing increases final error slightly, but caused no unprotected failures in this sweep.

Matched normal 20-step window alarm rates ranged from `14.4%` to `18.9%`; attack-window alarm rates ranged from `84.4%` to `100.0%`. Report per-amplitude/shape tables rather than conflating noise alarms with accurate attribution.

Summary by complete vs. aborted cohorts (`defense_cost.png`; complete-only means carry survivor selection and must be read with abort counts):

| Cohort | Variant | n | Success | Aborts | Complete Final (mm) | Complete Angle MAE (rad) | Complete Action Cost | Correction Steps Mean |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Normal | grace1 | 90 | 90 | 0 | 5.575288 | 1e-05 | 0.72918 | 0.988889 |
| Normal | none | 90 | 90 | 0 | 5.575245 | 0.0 | 0.72918 | 0.0 |
| Normal | original | 90 | 90 | 0 | 5.575288 | 1e-05 | 0.72918 | 0.988889 |
| Short bias | grace1 | 540 | 540 | 0 | 5.615182 | 0.006121 | 0.730209 | 16.081481 |
| Short bias | none | 540 | 540 | 0 | 5.681732 | 0.015 | 0.731314 | 0.0 |
| Short bias | original | 540 | 536 | 4 | 5.5914 | 0.006158 | 0.727881 | 16.077778 |
| Short ramp | grace1 | 540 | 540 | 0 | 5.588502 | 0.006389 | 0.729858 | 8.342593 |
| Short ramp | none | 540 | 540 | 0 | 5.628286 | 0.007875 | 0.730564 | 0.0 |
| Short ramp | original | 540 | 540 | 0 | 5.588502 | 0.006389 | 0.729858 | 8.342593 |
| Sustained 40 | grace1 | 90 | 17 | 73 | 6.464624 | 0.03455 | 0.871523 | 23.577778 |
| Sustained 40 | none | 90 | 90 | 0 | 5.583848 | 0.04 | 0.731374 | 0.0 |
| Sustained 40 | original | 90 | 17 | 73 | 6.464624 | 0.03455 | 0.871523 | 22.766667 |

## Full Experiment Tables and Definitions

Main-study reproduction counts (3 policies x 30 states x 50 paired conditions = 4,500 episodes):

| Dataset | Defense | Successes | Episodes | Aborts |
|---|---|---:|---:|---:|
| historical | False | 2250 | 2250 | 0 |
| historical | True | 2248 | 2250 | 2 |
| local | False | 2250 | 2250 | 0 |
| local | True | 2248 | 2250 | 2 |

Exploratory design: 3 frozen policies, 30 fresh test states per policy (`930000`/`931000`/`932000` blocks), independent calibration (`900000`/`901000`/`902000`, 100 episodes each), and development (`910000`/`911000`/`912000`, 6 states each). Conditions: clean, `bias`/`ramp` x `0.05`/`0.10 rad` x `start 20/50/70` x `20` steps, plus `40`-step sustained `0.10 rad` bias from step `20`. Defense states: `normal -> correcting -> recovery_pending (alarm 21) -> aborted (alarm 21 + grace)`. Development compared `grace=1` vs. `grace=3` (`development_aborts: {'1': 15, '3': 15}`), and the predeclared tie-break selected `grace=1` before test evaluation.

Condition summary (final distance covers complete 100-step trajectories; aborts count as task failure):

| Case | Variant | n | Successes | Aborts | Incomplete | Angle MAE (rad) | Action Cost | Alarm Steps | Complete Final (mm) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| bias_e0.05_s20 | grace1 | 90 | 90 | 0 | 0 | 0.00775 | 0.73003 | 13.35556 | 5.57524 |
| bias_e0.05_s20 | none | 90 | 90 | 0 | 0 | 0.01 | 0.72939 | 0.0 | 5.57822 |
| bias_e0.05_s20 | original | 90 | 90 | 0 | 0 | 0.00775 | 0.73003 | 13.35556 | 5.57524 |
| bias_e0.05_s50 | grace1 | 90 | 90 | 0 | 0 | 0.00817 | 0.73038 | 12.65556 | 5.56709 |
| bias_e0.05_s50 | none | 90 | 90 | 0 | 0 | 0.01 | 0.73026 | 0.0 | 5.57754 |
| bias_e0.05_s50 | original | 90 | 90 | 0 | 0 | 0.00817 | 0.73038 | 12.65556 | 5.56709 |
| bias_e0.05_s70 | grace1 | 90 | 90 | 0 | 0 | 0.00787 | 0.7303 | 12.63333 | 5.68036 |
| bias_e0.05_s70 | none | 90 | 90 | 0 | 0 | 0.01 | 0.7302 | 0.0 | 5.62505 |
| bias_e0.05_s70 | original | 90 | 90 | 0 | 0 | 0.00787 | 0.7303 | 12.63333 | 5.68036 |
| bias_e0.1_s20 | grace1 | 90 | 90 | 0 | 0 | 0.00496 | 0.73066 | 19.51111 | 5.57543 |
| bias_e0.1_s20 | none | 90 | 90 | 0 | 0 | 0.02 | 0.73139 | 0.0 | 5.5808 |
| bias_e0.1_s20 | original | 90 | 88 | 2 | 2 | 0.00504 | 0.73056 | 19.48889 | 5.52686 |
| bias_e0.1_s50 | grace1 | 90 | 90 | 0 | 0 | 0.00408 | 0.72999 | 19.1 | 5.56377 |
| bias_e0.1_s50 | none | 90 | 90 | 0 | 0 | 0.02 | 0.73341 | 0.0 | 5.57204 |
| bias_e0.1_s50 | original | 90 | 90 | 0 | 0 | 0.00408 | 0.72999 | 19.1 | 5.56377 |
| bias_e0.1_s70 | grace1 | 90 | 90 | 0 | 0 | 0.00389 | 0.72989 | 19.23333 | 5.7292 |
| bias_e0.1_s70 | none | 90 | 90 | 0 | 0 | 0.02 | 0.73322 | 0.0 | 6.15674 |
| bias_e0.1_s70 | original | 90 | 88 | 2 | 2 | 0.00389 | 0.72988 | 19.23333 | 5.6346 |
| clean | grace1 | 90 | 90 | 0 | 0 | 1e-05 | 0.72918 | 0.98889 | 5.57529 |
| clean | none | 90 | 90 | 0 | 0 | 0.0 | 0.72918 | 0.0 | 5.57524 |
| clean | original | 90 | 90 | 0 | 0 | 1e-05 | 0.72918 | 0.98889 | 5.57529 |
| ramp_e0.05_s20 | grace1 | 90 | 90 | 0 | 0 | 0.00504 | 0.72959 | 5.04444 | 5.57647 |
| ramp_e0.05_s20 | none | 90 | 90 | 0 | 0 | 0.00525 | 0.72963 | 0.0 | 5.57642 |
| ramp_e0.05_s20 | original | 90 | 90 | 0 | 0 | 0.00504 | 0.72959 | 5.04444 | 5.57647 |
| ramp_e0.05_s50 | grace1 | 90 | 90 | 0 | 0 | 0.00503 | 0.72974 | 5.28889 | 5.57579 |
| ramp_e0.05_s50 | none | 90 | 90 | 0 | 0 | 0.00525 | 0.72979 | 0.0 | 5.57623 |
| ramp_e0.05_s50 | original | 90 | 90 | 0 | 0 | 0.00503 | 0.72974 | 5.28889 | 5.57579 |
| ramp_e0.05_s70 | grace1 | 90 | 90 | 0 | 0 | 0.00505 | 0.72974 | 5.24444 | 5.56985 |
| ramp_e0.05_s70 | none | 90 | 90 | 0 | 0 | 0.00525 | 0.72976 | 0.0 | 5.57391 |
| ramp_e0.05_s70 | original | 90 | 90 | 0 | 0 | 0.00505 | 0.72974 | 5.24444 | 5.56985 |
| ramp_e0.1_s20 | grace1 | 90 | 90 | 0 | 0 | 0.00768 | 0.72981 | 11.55556 | 5.57713 |
| ramp_e0.1_s20 | none | 90 | 90 | 0 | 0 | 0.0105 | 0.73121 | 0.0 | 5.57802 |
| ramp_e0.1_s20 | original | 90 | 90 | 0 | 0 | 0.00768 | 0.72981 | 11.55556 | 5.57713 |
| ramp_e0.1_s50 | grace1 | 90 | 90 | 0 | 0 | 0.00784 | 0.73019 | 11.35556 | 5.57051 |
| ramp_e0.1_s50 | none | 90 | 90 | 0 | 0 | 0.0105 | 0.73156 | 0.0 | 5.57055 |
| ramp_e0.1_s50 | original | 90 | 90 | 0 | 0 | 0.00784 | 0.73019 | 11.35556 | 5.57051 |
| ramp_e0.1_s70 | grace1 | 90 | 90 | 0 | 0 | 0.00769 | 0.73009 | 11.56667 | 5.66127 |
| ramp_e0.1_s70 | none | 90 | 90 | 0 | 0 | 0.0105 | 0.73144 | 0.0 | 5.89458 |
| ramp_e0.1_s70 | original | 90 | 90 | 0 | 0 | 0.00769 | 0.73009 | 11.56667 | 5.66127 |
| sustained | grace1 | 90 | 17 | 73 | 73 | 0.01347 | 0.72768 | 23.57778 | 6.46462 |
| sustained | none | 90 | 90 | 0 | 0 | 0.04 | 0.73137 | 0.0 | 5.58385 |
| sustained | original | 90 | 17 | 73 | 73 | 0.01326 | 0.72762 | 22.76667 | 6.46462 |

Window alarm comparison (bootstrap 2000 resamples within policies over 3 policies; truncated windows noted):

| Case | Variant | n | Normal Rate | Attack Rate | Paired Difference | No-Alarm Rate | Delay Steps | Delay (ms) | Complete Windows | CI Low | CI High |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| bias_e0.05_s20 | grace1 | 90 | 0.1444 | 0.9667 | 0.8222 | 0.0333 | 0.6207 | 12.4138 | 90 | 0.7333 | 0.9 |
| bias_e0.05_s20 | original | 90 | 0.1444 | 0.9667 | 0.8222 | 0.0333 | 0.6207 | 12.4138 | 90 | 0.7333 | 0.9 |
| bias_e0.05_s50 | grace1 | 90 | 0.1889 | 0.9889 | 0.8 | 0.0111 | 1.4045 | 28.0899 | 90 | 0.7111 | 0.8778 |
| bias_e0.05_s50 | original | 90 | 0.1889 | 0.9889 | 0.8 | 0.0111 | 1.4045 | 28.0899 | 90 | 0.7222 | 0.8778 |
| bias_e0.05_s70 | grace1 | 90 | 0.1889 | 0.9778 | 0.7889 | 0.0222 | 0.9886 | 19.7727 | 90 | 0.7 | 0.8778 |
| bias_e0.05_s70 | original | 90 | 0.1889 | 0.9778 | 0.7889 | 0.0222 | 0.9886 | 19.7727 | 90 | 0.7 | 0.8667 |
| bias_e0.1_s20 | grace1 | 90 | 0.1444 | 1.0 | 0.8556 | 0.0 | 0.0333 | 0.6667 | 90 | 0.7778 | 0.9222 |
| bias_e0.1_s20 | original | 90 | 0.1444 | 1.0 | 0.8556 | 0.0 | 0.0333 | 0.6667 | 88 | 0.7778 | 0.9222 |
| bias_e0.1_s50 | grace1 | 90 | 0.1889 | 0.9889 | 0.8 | 0.0111 | 0.1461 | 2.9213 | 90 | 0.7222 | 0.8778 |
| bias_e0.1_s50 | original | 90 | 0.1889 | 0.9889 | 0.8 | 0.0111 | 0.1461 | 2.9213 | 90 | 0.7111 | 0.8778 |
| bias_e0.1_s70 | grace1 | 90 | 0.1889 | 0.9889 | 0.8 | 0.0111 | 0.1236 | 2.4719 | 90 | 0.7222 | 0.8778 |
| bias_e0.1_s70 | original | 90 | 0.1889 | 0.9889 | 0.8 | 0.0111 | 0.1236 | 2.4719 | 89 | 0.7111 | 0.8778 |
| ramp_e0.05_s20 | grace1 | 90 | 0.1444 | 0.8444 | 0.7 | 0.1556 | 10.7632 | 215.2632 | 90 | 0.5889 | 0.8 |
| ramp_e0.05_s20 | original | 90 | 0.1444 | 0.8444 | 0.7 | 0.1556 | 10.7632 | 215.2632 | 90 | 0.6 | 0.8 |
| ramp_e0.05_s50 | grace1 | 90 | 0.1889 | 0.9333 | 0.7444 | 0.0667 | 10.2381 | 204.7619 | 90 | 0.6556 | 0.8333 |
| ramp_e0.05_s50 | original | 90 | 0.1889 | 0.9333 | 0.7444 | 0.0667 | 10.2381 | 204.7619 | 90 | 0.6556 | 0.8333 |
| ramp_e0.05_s70 | grace1 | 90 | 0.1889 | 0.9 | 0.7111 | 0.1 | 9.6667 | 193.3333 | 90 | 0.6111 | 0.8 |
| ramp_e0.05_s70 | original | 90 | 0.1889 | 0.9 | 0.7111 | 0.1 | 9.6667 | 193.3333 | 90 | 0.6111 | 0.8 |
| ramp_e0.1_s20 | grace1 | 90 | 0.1444 | 0.9778 | 0.8333 | 0.0222 | 6.0909 | 121.8182 | 90 | 0.7444 | 0.9111 |
| ramp_e0.1_s20 | original | 90 | 0.1444 | 0.9778 | 0.8333 | 0.0222 | 6.0909 | 121.8182 | 90 | 0.7553 | 0.9111 |
| ramp_e0.1_s50 | grace1 | 90 | 0.1889 | 0.9889 | 0.8 | 0.0111 | 6.6067 | 132.1348 | 90 | 0.7111 | 0.8778 |
| ramp_e0.1_s50 | original | 90 | 0.1889 | 0.9889 | 0.8 | 0.0111 | 6.6067 | 132.1348 | 90 | 0.7111 | 0.8778 |
| ramp_e0.1_s70 | grace1 | 90 | 0.1889 | 0.9778 | 0.7889 | 0.0222 | 6.1932 | 123.8636 | 90 | 0.7 | 0.8778 |
| ramp_e0.1_s70 | original | 90 | 0.1889 | 0.9778 | 0.7889 | 0.0222 | 6.1932 | 123.8636 | 89 | 0.7 | 0.8667 |
| sustained | grace1 | 90 | 0.2778 | 1.0 | 0.7222 | 0.0 | 0.0333 | 0.6667 | 17 | 0.6333 | 0.8111 |
| sustained | original | 90 | 0.2778 | 1.0 | 0.7222 | 0.0 | 0.0333 | 0.6667 | 17 | 0.6222 | 0.8111 |

Independent full-trace exploratory audit passed (`3,780` episodes, `369,446` rows; `exploratory_audit.json`). Episode-aggregated prediction error during alarms (`prediction_cohort_summary.csv`): short `bias` ~`0.02555 rad`, short `ramp` ~`0.03594 rad`, clean false alarms ~`0.00110 rad`.

Compatibility verification (`Torch 2.14.1+cpu` vs. initial `Torch 2.7.1+cu126`): `pip check` reported `No broken requirements found` and all `16` tests passed (`tests_compatible.log`). Both main (`4,500`) and exploratory (`1,008` dev + `3,780` test) runs matched on success, aborts, step counts, alarm counts, and window alarm timings, with floating-point trajectory differences up to `0.000026805 mm` (final-10 mean), `0.000035683 mm` (terminal), `~1.77e-7` (action sum-of-squares), and `0.000009602 mm` (exploratory window delta; `compatible_environment_comparison.csv`).

Per-state pass rate across all 12 short-attack conditions (`90` states): `original` `86/90`, `grace1` `90/90`, paired gain `+4/90` (within-policy bootstrap 95% CI `0.0111–0.0889`).

Evidence entry points: [github_upload/outputs/reproduction_20261118_materials/READ_ME_FIRST.md](github_upload/outputs/reproduction_20261118_materials/READ_ME_FIRST.md), [compatible_main_audit.json](github_upload/outputs/reproduction_20261118_environment/compatible_main_audit.json), [exploratory_audit.json](github_upload/outputs/reproduction_20261118_compatible_audit/exploratory_audit.json), and [FINAL_ACCEPTANCE.md](FINAL_ACCEPTANCE.md).
