# DASE7508 integration session — 2026-10-22

## Scope and acceptance

Session started at approximately 16:03 Asia/Shanghai, targeting a reviewable
result around 17:03. The group-level objective is a working sensor-security
experiment, not individual work allocation.

Required for this session:

1. Fix repeating training noise, synchronize sensor/evaluation positions, and
   protect existing outputs from overwrite.
2. Provide observation-only bias/ramp attacks and amplitude-matched random-sign
   controls, plus kinematic detection, velocity-based correction and abort logic.
3. Run meaningful behavior tests and at least one end-to-end paired pilot with
   frozen calibration thresholds, raw traces, metric tables and inspection plots.
4. Record exact settings, limitations and reproducible commands.

Stretch: train three policies with synchronized sensing and run the full study
if all three qualify and the wall-clock budget allows. A run is never called
main-study evidence merely because its pilot succeeds.

## Decisions recorded before the pilot

- Use the proposal's Reacher-v5 and SAC, CPU PyTorch 2.14.1, MuJoCo 3.15.0,
  Gymnasium 1.4.0 and SB3 2.9.0.
- Keep the original uploaded model and validation intact. Corrected training
  gets new output directories.
- Use independent MuJoCo data for synchronized position sampling, avoiding
  mutation of the running physics state.
- Define ramp and random-control schedules, reset initialization, residual
  calibration and metric timing explicitly in `github_upload/PROTOCOL.md`.
- Main claims require three independently trained, validated policies. Weak or
  ineffective attacks and harmful corrections will be reported, not hidden.

## Results

- Completed the CPU dependency environment (approximately 1.5 GiB), numerical
  setup checks and EGL offscreen rendering. Download staging files were removed.
- Eleven behavior/CLI tests pass. They cover protected channels, attack windows,
  ramp/random amplitude matching, previous-velocity prediction, >20 alarm abort,
  physics invariance, replayable/non-repeating noise, score denominators, metric
  timing, output preservation and the frozen-plan gate.
- Reproduced the uploaded model's 30 clean validation successes. The maximum
  discrepancy against its recorded legacy metric was about 5.94e-9 m. The
  synchronized version also achieved 30/30 on those validation states.
- Completed and audited a six-initial-state pilot: 100 calibration episodes and
  300 paired evaluation episodes. All 300 completed the task; this is evidence
  of weak terminal attack impact on this one policy, not proof of universal
  robustness. Windowed deviations and detector misses remain measurable.
- The first pilot contained a display-only metric issue (clean false alarms
  listed under detection delay). It is retained as exploratory history in
  `pilot_20261022`; use `pilot_checked_20261022` for corrected pilot metrics.
- The main plan was frozen before main testing in `github_upload/main_plan.json`.
  Original amplitudes, durations, success criteria and seed counts were retained.
- Three fresh independent synchronized SAC policies completed 150,000 steps
  each in new directories, approximately 19 minutes per run concurrently. All
  three achieved 30/30 clean validation successes and qualified for main testing.

## Final outcome

- Completed the frozen main study: 300 separate calibration episodes and 4,500
  paired evaluation episodes, in approximately 127 seconds for calibration and
  evaluation. Seeds and all proposal attack settings were retained.
- All 2,250 unprotected episodes succeeded. Protected conditions succeeded in
  2,248/2,250. Both aborts occurred for the same policy/initial-state seed 802009,
  once under bias and once under its matched random-sign control. The first
  post-attack noisy sample extended 20 alarms to 21, triggering the specified
  abort although the true distance was only 3.85 mm. Both were independently
  reproduced; records were not removed and the rule was not retuned.
- Full audit passed for 4,500 episodes / 449,882 trace rows / 90 paired initial
  states. Source/model/plan hashes, sensor boundaries, noise and attack pairing,
  correction, scoring and abort semantics were checked.
- Produced per-policy and aggregate tables, detection and distance plots,
  training/validation figures, physical/observed-arm replay GIF, abort diagnoses,
  a portable CPU dependency lock and installation/experiment commands.
- The missing proposal diagram now exists in PNG and editable SVG form.

Read `RESULTS.md` for the group-level findings and file index. Main work remaining
is final course-report/presentation editing and installation reproduction on a
second machine. Late attacks or alternative alarm/abort rules would be separate
exploratory studies with fresh frozen settings and test seeds; the main results
must stay intact.
