# Slide-Ready Content: 10 Main Slides + Backups

Figure directory prefix: `github_upload/outputs/final_acceptance_20261118/figures/`. Total body time: `660 s` + `40 s` transitions + `20 s` buffer. Confirm actual team names, IDs, and individual contributions before submission.

## 1 — When Can a Sensor Monitor Make Reaching Worse?
Speaker A · 66s

- Joint-angle spoofing in a SAC-controlled simulated arm.
- Question: does kinematic mitigation improve reaching under bounded corruption?
- Measure transient errors, task completion, false alarms, and false stops.
- Team names and IDs: confirm before submission.

Visual: cropped `01_trajectory.png`. Note: define assets as sensor integrity and task completion; do not pre-promise task failures from small attacks.

## 2 — System and Trust Boundaries
Speaker A · 66s

- MuJoCo / `Reacher-v5`; frozen SAC policies; 100-step episodes (`dt = 20 ms`).
- Attacker changes only `joint0` cosine/sine entries `0` and `2`.
- Target, `joint1`, position, and velocity remain protected by assumption.
- Simulator truth is evaluation/display only.

Visual: `proposal_reference_exact_diagram.png` (`sensors -> angle injection -> optional monitor -> policy -> simulator`; separate `truth -> evaluator` arrow). Note: initial compromise is out of scope, and independent position/velocity channels carry `2 mm` noise as a simulator assumption rather than proven hardware isolation.

## 3 — Attacks and What We Added
Speaker B · 66s

- `Bias`: fixed signed offset; `Ramp`: offset grows linearly within the window.
- Matched random-sign controls preserve the magnitude envelope.
- Reused baseline: trained policies, attacks, original monitor, and frozen main study.
- Added: Windows reproduction, held-out timing study, Wait+1 rule, and audits.

Visual: concise schedule formula from `framework/core/security.py` (`Attack.delta`).

## 4 — Timing Changes Errors, Not Observed Task Success
Speaker B · 66s

- `Bias`/`Ramp`; `epsilon = 0.05 / 0.10 rad`; duration `20`; `start = 20 / 50 / 70`.
- Three frozen policies; `30` new paired states per policy.
- At `0.10 rad` bias, final error rises `5.581 -> 6.157 mm` (`start 20 -> 70`).
- All `1,080 / 1,080` unprotected short-attack conditions succeed.

Visual: `02_timing.png` (with `01_trajectory.png` as representative example). Note: final error remains well below `30 mm`, and timing variation alone does not prove causal channel dependence.

## 5 — Kinematic Consistency Is an Anomaly Signal
Speaker C · 66s

- Residual = `||forward_kinematics(reported_angles) - measured_position||`.
- Threshold: 99th percentile from 100 clean calibration episodes per policy.
- Alarm correction: previous angle + previous trusted velocity x `20 ms`.
- Noise, folded geometry, and gradual offsets create blind spots.

Visual: residual formula and trust arrows (keep `03_alarm_background.png` for Speaker D). Clarify that an alarm signals inconsistency rather than attacker attribution, and sub-threshold gradual offsets can bias the predictor's initial angle.

## 6 — One Extra Step Changes the Abort Boundary
Speaker C · 66s

- Original: abort on `21` consecutive alarms.
- Wait+1: `recovery_pending` on `21`; clear reading resets; alarm `22` aborts.
- Same detector/predictor; no additional trusted channel.
- Development `{1, 3}`-step candidates tie at `15` aborts; fixed tie-break selects `1`.

Visual: `05_abort_case.png`. Clarify state transitions (`normal -> correcting -> recovery_pending -> aborted`) and note that Wait+1 shifts the time tolerance rather than detection accuracy.

## 7 — Paired Evidence, Not Thousands of Independent States
Speaker D · 66s

- `3` policies x `30` paired states = `90` state units.
- Main reproduction: `2250 / 2250` without defense; `2248 / 2250` with original defense.
- Success: `100` actions, no abort, final-10-state mean distance <= `30 mm`.
- Disjoint splits; matched initial states, sensor noise, and attack schedules.

Visual: compact 3-row summary table from `compatible_main/episodes.csv` and `acceptance.json`. Emphasize `4,500` trials are repeated conditions over `90` paired states.

## 8 — Fewer False Stops, With a Response Trade-off
Speaker D · 66s

- Short successes: `1080/1080`, `1076/1080`, `1080/1080` (`none` / `original` / `wait+1`).
- Four avoided aborts: `4` distinct state units across `2` policies.
- Sustained: both defenses abort `73 / 90`; Wait+1 responds `20 ms` later.
- Clean: `89 / 8910` step alarms; `54 / 90` episodes alarm.

Visual: `04_defense_cost.png` (main) and `03_alarm_background.png` (secondary). Clarify that avoiding aborts does not beat the `1080/1080` unprotected baseline, and complete-only means carry survivor selection.

## 9 — Selected Boundary Case: Four Paired Modes
Speaker E · 75s (includes demo)

- Identical `policy3`, seed `802009`, noise stream, and 20-step bias window.
- `Normal` / `Attack` / `Original` / `Wait+1` shown side by side.
- At step `40`, `Original` aborts on alarm `21`; `Wait+1` continues.
- Selected case, not average performance; truth is display-only.

Visual: `outputs/final_acceptance_20261118/demo_boundary_v2/replay.html` (or `comparison.gif`, static fallback `boundary_step40.png`).

## 10 — Takeaways, Limits, and Next Tests
Speaker E · 57s

- No observed task-failing unprotected attack in the tested Phase-1 scope.
- Consistency checks can reduce transient error yet introduce false stops.
- Wait+1 reduces boundary aborts, not attack-identification errors.
- Future: predeclare more policy seeds and pose-stratified tests; measure false stops, delay, and prediction drift (and evaluate stronger/late attacks under the Phase-2 extension framework).
- Credit reused tools/group code; confirm member contributions; disclose AI help.

## Backup B1 — Full Conditions and Per-Policy Results

Source files: `final_acceptance_20261118/verified_episodes.csv`, `exploratory_20261118_compatible/test/episodes.csv`, `four_failures.csv`. Retain all zero-effect and abort records.

## Backup B2 — Denominators and Censoring

Step FA = `clean_alarms / (90 x 99)`; episode FA = `episodes_with_alarm / 90`; window rate = `windows_with_observed_alarm / 90` (with truncated windows noted separately). Delay averages alarmed windows only; no-alarm counts are listed separately. Aborts always count as task failures; squared normalized actions are not mechanical energy.

## Backup B3 — Credits and References

Confirm actual member contributions before submission (do not use proposal tables or A–E speaking slots as authorship proof). Reused components: MuJoCo, Gymnasium `Reacher-v5`, SB3/SAC (references in `DASE7508_Proposal_2.0.md`). AI disclosure: Codex assisted with inspection, troubleshooting, reproduction, auditing, plotting, and draft preparation; team members verify and own final explanations.
