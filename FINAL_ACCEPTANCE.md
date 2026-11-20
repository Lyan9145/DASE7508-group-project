# Final Acceptance (2026-11-18)

Acceptance verdict: **Experimental counts and key metric semantics pass; presentation slide drafts and local replay artifacts are ready for review. Manual verification items remain pending and cannot be claimed as final course approval.**

This acceptance pass performed no retraining, no new attacks, no hyperparameter search, and no edits to decision-making experiment code; only read-only verification/plotting scripts and presentation entry points were added. (These scripts are now archived under `github_upload/legacy/`.)

Primary verified datasets: `github_upload/outputs/exploratory_20261118_compatible/test` and `reproduction_20261118_compatible_main`. All metrics were recomputed directly from `episodes.csv` and full `traces.jsonl.gz` (`3,780` episodes / `369,446` rows and `4,500` episodes / `449,882` rows). Earlier unsupported-Torch runs were not pooled as additional samples.

Unless otherwise noted, evidence files reside in `github_upload/outputs/final_acceptance_20261118/`.

| Check | Status | Result & Limitations | Evidence |
|---|---|---|---|
| Short-attack totals | PASS | `none`: `1080/1080`; `original`: `1076/1080`; `grace1`: `1080/1080` | `short_totals.csv` |
| Four abort identities & independence | PASS | 4 failures across 4 distinct `(policy, seed)` pairs across 2 policies; not 4 independent training seeds | `four_failures.csv` |
| Sustained 40-step attacks | PASS | `original` & `grace1` both abort `73/90` on identical 73 pairs; `none`: `90/90` success | `sustained_pairs.csv`; `cohorts.csv` |
| Extra response delay | PASS | All 73 shared pairs delay by `+1` step (`dt = 0.02 s`, i.e., `20 ms`) | `sustained_pairs.csv`; `acceptance.json` |
| Alarm denominators | PASS WITH QUALIFICATION | Clean per-step `89/8910 = 0.998878%`; clean per-episode `54/90 = 60.00%`; per-condition windows `n=90` | `false_alarms.csv`; `window_rates.csv` |
| Truncated windows | CORRECTED METADATA | Short-attack detection observation windows are all complete (the aborting step was monitored). `original` has 3 incomplete attack-action windows and 4 incomplete attack+10 distance windows; sustained has 73 truncated alarm windows per defense | `paired_windows.csv`; `verified_episodes.csv` |
| Aborted trajectories | PASS | All aborts count as task failure; final distance stats cover complete 100-step trajectories only and are paired with abort counts (survivor selection acknowledged) | `verified_episodes.csv`; `presentation_cohorts.csv` |
| Seed separation | PASS | Dev (`18`), test (`90`), exploratory calibration (`300`), and validation/main/checked-pilot blocks are mutually disjoint | `acceptance.json`; `seed_inventory.json` |
| Paired states, noise & schedules | PASS | Stepwise recomputation confirmed identical initial truth per `(policy, seed)`, noise match `< 1e-13 m`, and exact step-by-step `delta` | `acceptance.json`; `legacy/final_acceptance.py` |
| Source, model & config hashes | PASS | Executed snapshots match SHA256 across both runs; 3 models match; frozen `main_plan.json` hash matches | `acceptance.json`; `protected_before.json` |
| Frozen selection order | SUPPORTED, NOT CERTIFIED | Dev aborts tied `15/15`; predeclared tie-break chose `1`; executed source writes selection before testing. Local files cannot serve as third-party timestamp certification | `frozen_selection.json`; `source/exploration.py` |
| Course requirements | FOUND | Extracted from official course presentation PDF (`12 min` incl. demo + `3 min` Q&A, `8`-point rubric); Moodle dates/deadlines/format require group verification | `course_sources.json` |
| Second-computer check | PENDING | No second teammate / second physical machine verification logged; multiple venvs on one machine do not count | `TEAM_HANDOFF.md` |
| Video & timed rehearsal | PENDING | Annotated 4-mode MuJoCo GIF/HTML replay generated; desktop MP4 recording and 5-person timed rehearsal remain pending | `DEMO_GUIDE.md` |

## Four Avoided Abort Records

| Policy | Seed | Case | Attack Kind | `epsilon` (rad) | Start | Duration | Steps |
|---|---|---|---|---|---|---|---|
| `sac_seed_1_sync` | 930016 | `bias_e0.1_s70` | `bias` | 0.1 | 70 | 20 | 89 |
| `sac_seed_2_sync` | 931009 | `bias_e0.1_s20` | `bias` | 0.1 | 20 | 20 | 39 |
| `sac_seed_2_sync` | 931011 | `bias_e0.1_s70` | `bias` | 0.1 | 70 | 20 | 90 |
| `sac_seed_2_sync` | 931023 | `bias_e0.1_s20` | `bias` | 0.1 | 20 | 20 | 39 |

These four records come from 4 distinct paired initial states across 2 policies (`3` total trained policies). Each state is evaluated under 12 short-attack conditions, so `1080` denotes `90 x 12` condition trials rather than `1080` independent initial states. Similarly, the two historical main-study aborts repeat the single `(policy3, 802009)` state under `bias` and `random_bias`.

In the new clean tests, both defenses trigger `89` alarms across `90 x 99 = 8910` detectable observations (step `0` excluded from alarm opportunities) and `54/90` episodes. Do not mix this with historical main-study clean rates (`91/8910 = 1.021324%` steps, `63/90` episodes).

Window rates use `n = 90` paired states per condition (reusing the clean trajectory). Matched normal 20-step windows alarm in `13/90` (`start=20`) or `17/90` (`start=50/70`) cases; attack windows show at least one observed alarm in `76/90–90/90` cases. First-alarm delay averages only alarmed windows; no-alarm counts are reported separately. Truncated detection windows in sustained attacks (`73` per defense) retain observed exposure without treating unobserved suffixes as clean.

Metadata correction summary: earlier figures relied on initial legacy-Torch troubleshooting outputs, and `complete_windows` measured completed action steps rather than observation exposure. All five presentation figures were regenerated from compatible runs with separate accounting for detection exposure, attack-action windows, and post-attack distance windows; primary counts and conclusions did not change.

In the 4 newly identified `original` failures, aborts at steps `39`/`89` occurred when a pre-window noise alarm connected to the attack streak, whereas step `90` extended one step past the attack window. Full step-level trace evidence is retained. One-step waiting merely shifts the abort threshold from 21 to 22 and does not enhance attack attribution or recovery recognition.

## Local Package Acceptance Summary

A 109-file allowlisted archive passed same-machine extraction verification: all `109` `PACKAGE_MANIFEST.json` SHA256 digests matched, `16` unit tests passed (`14.13 s`), and the 4-mode numeric demo produced `100/100/40/100` steps (`True/True/False/True`). All 141 protected baseline/run files matched pre/post hashes. This same-machine check does not substitute for second-computer verification. Remaining manual tasks: `.pptx` assembly, desktop MP4 capture (if desired), browser/projector verification, 5-person timed rehearsal, Moodle requirement check, and group confirmation of individual member contributions.
