# Sensor-spoofing experiment protocol

This implements Proposal 2.0. Pilot runs are exploratory and are never labelled
as held-out main-study results. All policies are frozen during calibration and
testing. Policies and the monitor receive observations only; `info['truth']` is
used exclusively by the evaluation/logger code.

## Sampling and reproducibility

- Observations 0 through 99 select actions 0 through 99. The post-action states
  have observation indices 1 through 100. The success criterion uses distances
  at states 91 through 100, not cached pre-integration body positions.
- Position measurements and evaluation truth are recomputed in separate MuJoCo
  data at current qpos. This does not modify the actual integrator state.
- Training noise advances continuously across episodes. Explicit reset
  `options={'noise_seed': ...}` replays a sensor-noise stream for paired trials.
- Legacy observation timing remains available for auditing the uploaded model,
  but new training and all security evaluations use synchronized sampling.
- Training validation seeds are `10000 + 1000 * training_seed + episode`.
  Calibration and evaluation use different blocks, listed in each run's config
  and calibration artifact. Pilot and main test seed blocks must also differ.

## Attack and estimator conventions fixed before experiments

- Only joint0's cosine (0) and sine (2) entries change. Everything else, including
  velocities, target, position measurement, physics and reward, is untouched.
- Default window is observations [20, 20 + duration). Bias has constant signed
  epsilon. Ramp is sign * epsilon * (window_index + 1) / duration, reaching
  epsilon on its last observation.
- Random controls draw independent +/- signs at every attacked observation,
  retaining the bias/ramp magnitude envelope. The schedule is identical with
  the monitor off/on. Deterministic attack signs alternate across test seeds.
- Reset observation 0 is known to be outside the attack window and initializes
  the angle predictor. It is included in clean calibration, but is not an alarm
  opportunity during evaluation. False-alarm denominators reflect this.
- Raw reported observations determine residuals; corrected observations never
  suppress an alarm. Only joint0's sin/cos pair is corrected. An alarm uses the
  previous accepted/predicted angle and previous trusted velocity, with actual
  environment dt. A clean residual immediately accepts the reported angle.
- Strictly more than 20 consecutive alarms abort the trial and count as failure.
  An ideal 20-step attack alone therefore need not trigger an abort.
- Each policy has its own threshold: empirical 99th percentile (NumPy linear
  quantile) from 100 clean episodes, 100 residuals each. It is fixed before tests.

## Metrics

- Success: all 100 actions complete, no abort, and mean true distance over final
  ten post-action states <= 0.03 m.
- Attack success: fraction of **unprotected clean-successful** paired trials
  turned into failures. The same clean-success set is used with/without defense.
  Unconditional success and paired differences across all trials are also saved.
- Attack-window metrics use post-action distances for attacked commands and the
  following ten commands. Aborted windows are marked incomplete. Paired clean
  differences compare the same observed window prefix in incomplete trials.
- Detection delay: first alarm inside the attack window minus its first step.
  Earlier false alarms do not count as detections; no alarm in-window is a miss.
- Recovery: first state index >= window end that begins five consecutive states
  within 3 cm, minus window end. Aborted/unrecovered trials are counted separately.
- Control effort is sum of squared normalized action commands, not mechanical
  energy or physical torque-squared. Processing latency is CPU wall time around
  the monitor only, excluding physics, policy inference, logging and warmup.
- At 1% per-step false alarm rate, the chance of an episode with at least one
  alarm can be substantial. Per-episode alarms are not expected to be only 1%.

## Artifacts and study boundaries

Each evaluation saves its command configuration, package versions, model hashes,
implementation snapshot, calibration, per-episode metrics, summaries and optional
compressed full traces. A completed run has `run_status.json` with complete=true.
Existing result directories cannot be overwritten. Training also refuses reuse
of an output directory. The original uploaded seed-1 model stays unchanged.

The main configuration is three qualified synchronized policies, 30 paired
initial states per policy, 100 clean calibration episodes per policy, epsilons
0.02/0.05/0.10 rad, durations 5/20 and bias/ramp plus matched random controls.
There are 4,500 main evaluation episodes plus 300 calibration episodes.
Changing thresholds or main settings after observing main results creates a
separate exploratory study and must not replace the original main artifacts.
