# Evidence index

Read the repository-root REPRODUCTION_REPORT.md, FINAL_RESULTS.md and
PRESENTATION_PLAN.md first. README.md gives Windows commands using the final
local CPU Torch environment based on mp1 Python.

- Historical main results remain in `../main_v1/`; independent read-only audit:
  `../reproduction_20261118_environment/historical_audit.json`.
- Final supported-environment main rerun:
  `../reproduction_20261118_compatible_main/` (configuration, source/model hashes,
  calibration, episodes, summaries, compressed traces, completion record).
- Final supported-environment exploratory development and tests:
  `../exploratory_20261118_compatible/` (preregistered plan and frozen selection;
  development/test subdirectories use disjoint seeds).
- Supported-environment independent audits:
  `../reproduction_20261118_environment/compatible_main_audit.json`,
  `../reproduction_20261118_compatible_audit/exploratory_audit.json`.
- Initial mp1 Torch run is preserved in `../reproduction_20261118_main/` and
  `../exploratory_20261118/`; its runtime package metadata disclosed a Torch
  dependency declaration conflict. Final full reruns fix it; they repeat the
  same states and must never be pooled as additional independent samples.
- `compatible_environment_comparison.csv` compares these complete reruns.
  Tables/figures here were computed from the first numerically verified runs,
  then checked against the supported-environment reruns.
- `reproduction_comparison.csv`, `reproduction_totals.csv`: main vs history.
- `per_policy_results.csv`, `aggregate_results.csv`: all exploratory conditions.
- `cohort_comparison.csv`: complete trajectories vs abort counts and costs.
- `paired_windows.csv`, `window_alarm_summary.csv`: matching normal and attack
  alarm probabilities, paired increment, no-alarm proportion, conditional delay.
- `new_clean_false_alarms.csv`: step and episode rates. No-defense detection
  rates are blank because monitoring is disabled, not because it is perfect.
- `alarm_prediction_per_episode.csv`, `alarm_prediction_summary.csv`,
  `prediction_cohort_summary.csv`: angle errors only on actual predicted steps;
  episode summaries precede aggregation. Aborted prefixes remain identified
  through episodes.csv and must not be compared as complete trajectories.
- `sustained_response_pairs.csv`: all 73 paired aborted sustained attacks,
  improved response delayed exactly one step (20ms).
- `exploratory_failures.csv`, `exploratory_failure_steps.csv`: all four short
  attack failures under the original defense. No cases were omitted.
- `paired_state_success.json`: all-12-short-condition pass rate per initial
  state, with stratified paired-state bootstrap (fixed three policies).
- Five main figures: `representative_trajectory.png`, `timing.png`,
  `alarm_background.png`, `defense_cost.png`, `abort_case.png`.
- `analysis_source/`, `analysis_manifest.json`: reporting source and documents;
  executed simulation snapshots stay inside each actual experiment run.

Representative trajectory: first policy, first new test seed930000, largest
predeclared bias at latest start70. Curves nearly overlap: this is retained
as a zero/weak-effect example. Abort case: unique historical failing initial
state802009, not a case selected to maximize apparent attack damage.
