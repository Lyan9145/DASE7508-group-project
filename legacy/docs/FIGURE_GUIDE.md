# Five Main Presentation Figures (2026-11-18)

Figure directory: `github_upload/outputs/final_acceptance_20261118/figures/`. All figures use final compatible-environment data, distances in mm, and `dt = 20 ms`.

*(Note: `final_acceptance.py` and `prepare_presentation.py` have been archived under `github_upload/legacy/`. Existing figure directories are immutable and scripts refuse to overwrite them; normal presentations do not need to regenerate these artifacts.)*

To inspect the archived generation commands:
- `github_upload/legacy/final_acceptance.py`
- `github_upload/legacy/prepare_presentation.py`

| Figure | Units & Data Source | Slide Takeaway | Required Limitations |
|---|---|---|---|
| `01_trajectory.png` | True distance (mm), step; compatible exploratory `test/traces` -> `selected_traces.json` | The predeclared example shows weak visible differences, which we retain. | `sac_seed_1_sync` / seed `930000` / `0.10 rad` bias / `start=70`; chosen by first policy, first seed, max predeclared amplitude, latest start (not cherry-picked); one case does not prove robustness. |
| `02_timing.png` | Paired window delta (mm), final-10 mean distance (mm), `start` step; compatible test CSV & clean traces -> `verified_episodes.csv` | Later bias slightly increases final error, but no unprotected short attack causes task failure. | 90 states per point (reusing states across points); unprotected curve only; timing comparison does not prove causal channel dependence. |
| `03_alarm_background.png` | Window proportion `/90`; compatible step alarms -> `paired_windows.csv`, `window_rates.csv` | Attack windows alarm more often than matched normal windows; an alarm is not attribution. | Clean `13/90` or `17/90`, attack `76/90–90/90`; short-attack detection observation windows are complete (aborted observation still checked before action skip). Sustained attacks have 73 truncated detection windows; delay averages only alarmed windows. |
| `04_defense_cost.png` | Abort count, corrections/episode, complete-trajectory angle MAE (rad); compatible CSV & traces -> `presentation_cohorts.csv` | Wait+1 avoids four short-condition aborts but delays sustained response by 20 ms. | Per variant: `90` normal, `1080` short, `90` sustained (conditions repeat states); complete-only metrics carry survivor selection and must be read alongside abort counts; unprotected baseline already succeeded 100%. |
| `05_abort_case.png` | Residual (mm), alarm count, step; compatible `main/traces` -> `selected_traces.json` | A post-attack noise alarm extends 20 attack alarms to 21 and triggers a rule-induced abort. | Known historical case `policy3` / seed `802009`; not average performance; true distance `~3.849 mm` is evaluation-only; `random_bias` repeats the same state rather than a second independent state. |

Complete condition tables are in `verified_episodes.csv` and window exposure counts in `paired_windows.csv`. Raw logs retain SI metre fields for auditing while presentation figures convert to mm. The architecture figure reuses `proposal_reference_exact_diagram.png`.
