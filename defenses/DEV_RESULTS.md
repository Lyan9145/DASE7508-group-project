# Phase-2 defense development handoff (Track 2)

## Scope and protocol

This is a **development-set study**, not the held-out Phase-2 main study.
Unless stated otherwise every number uses the three frozen policies
(`models/sac_seed_{1,2,3}_sync`), 30 paired states per policy from
`DEV_BASE=1100000` (policy `i` uses `1100000 + 1000*i + episode`), 10 clean
calibration episodes per policy from `CAL_BASE=1000000` (the setting of the
Track-2 verification command), position noise `sigma=0.002 m`, no velocity
noise, and alternating attack signs. Parameters were chosen on this block and
then checked on a disjoint dev slice (`1110000`, the verification block) and
with 100-episode calibration. `TEST_BASE=1200000` was not used.

Detection metrics follow `evaluation/runner.py`: a clean false-alarm episode is
any alarm at step `>= 1`; an attack is detected when an alarm falls inside the
attack window; delay is measured from the window start. "Success" is the
runner's `task_success` (no abort, 100 steps, final-10 mean distance
`<= 0.03 m`). One clean episode of policy 2 (seed 1101020, final error 0.0345 m) fails without any attack, so 0.99
is the ceiling in most rows.

Attack cases (all registered plugins, no attack code changed):

| Case | Plugin and parameters |
| --- | --- |
| `bias_e0.3_s80` / `bias_e1.0_s80` / `bias_e1.0_s60d40` | `bias`, 0.3 or 1.0 rad, start 80 for 20 steps or start 60 for 40 |
| `ramp_e0.5_s80` / `ramp_e1.0_s60d40` | `ramp` |
| `ta_e0.1_s80` / `ta_e0.3_s60d40` | `threshold_aware`, margin 0.85 |
| `elbow_s60d30` / `elbow_s80d20` | `elbow_flip` |
| `jvc_e1.0_v0.5` / `jvc_e1.0_v2.0` | `joint_vel_coupled`, 1.0 rad + 0.5 or 2.0 rad/s, start 60 for 40 |
| `jvc_e0_v1.0` / `jvc_e0_v3.0` | `joint_vel_coupled` with `epsilon=0`: velocity-only spoofing, 1 or 3 rad/s |
| `freeze_s60d40`, `replay_s60d40`, `sin_e1.0_s80` | magnitude/timing plugins |

## Baseline limitations (before this branch)

* **Clean false alarms.** Every defense with the single-step p99 residual
  threshold (`original_fail_stop`, `grace1`, `continuous_velocity`,
  `ik_velocity_fusion`, `fallback_policy`) alarmed in **48.9%** of clean dev
  episodes (60% on the `1110000` slice, 4/6 in the verification command).
  Clean residuals are close to independent across steps (lag-1
  autocorrelation 0.02, 0.03 and -0.01 for policies 1-3), so a p99 threshold
  is expected to fire in about `1 - 0.99**99 = 63%` of episodes; the largest
  clean residual per episode reached 1.42x the threshold.
* **Stealthy attacks.** `sliding_window` never detected a threshold-aware ramp
  (hits required the full threshold, which the attack is designed to stay
  under); `cusum` detected 80% (0.1 rad) with a 14.6-step delay.
* **Velocity tampering.** `joint_vel_coupled` with 2.0 rad/s left
  `ik_velocity_fusion` at 16% success and every other defense at 0-2%;
  velocity-only spoofing at 3 rad/s left every defense at 4%, undetected.
* **Elbow flip.** Only `ik_velocity_fusion` handled it (99%); all others stayed
  at the no-defense level (30% / 46%).

## 1. Cumulative statistical detectors (`defenses/statistical.py`)

Because a detector's first alarm happens before it has changed any
observation, first-alarm statistics can be replayed exactly from no-defense
traces. A grid of 90 CUSUM settings (`k` 0.5-1.5, `h` 2-8, `spike_factor`
1.25-2.0) and 270 sliding-window settings (`window_size` 5-15, `min_hits` 2-8,
hit level 0.7-1.0 x threshold) was scored offline, and the chosen settings
were re-run closed-loop.

| Detector | Clean FA ep. | `ta_e0.1` det. / delay | `ta_e0.3` det. / delay | `ramp_e0.5` delay |
| --- | ---: | ---: | ---: | ---: |
| CUSUM, former `k=1.5, h=5` | 0.0% | 80% / 14.6 | 100% / 13.8 | 2.30 |
| **CUSUM, new `k=1.0, h=5`** | 1.1% | **92% / 10.2** | **100% / 8.7** | 2.16 |
| Sliding window, former 3 of 5 above threshold | 0.0% | 0% | 0% | 2.41 |
| **Sliding window, new 4 of 8 above 0.8 x threshold** | 0.0% | **94% / 8.9** | **100% / 7.0** | 2.34 |

Holdout check (offline, same metric): on the `1110000` slice the new CUSUM gave
0.0% clean false alarms with 10- and 100-episode calibration and detected
97.8% of `ta_e0.1` (former: 85.6%); the new sliding window gave 0.0% false alarms
with both calibrations and 97.8% detection. Task success is unchanged in every case:
these detectors only dead-reckon joint 0, so they cannot help against elbow
flip or tampered velocity. Use `ik_velocity_fusion` for those.

`SlidingWindowDefense` gained `hit_factor` (appended after `max_alarm_steps`
so existing positional calls keep working). `hit_factor=1.0` reproduces the
former detector.

Neither residual detector sees `freeze` or `replay` (1-8%): the arm is nearly
still near the target late in an episode, so frozen or replayed angles barely
move the fingertip residual. Neither attack changed task success.

## 2. Fusion recovery (`defenses/fusion_recovery.py`)

### False alarms: `threshold_factor`

Both `ContinuousVelocityDefense` and `IKVelocityFusionDefense` take
`threshold_factor` (default **1.5**) on the calibrated threshold.

| Multiplier | Clean FA ep. (1100000, cal 10 / 100) | Clean FA ep. (1110000, cal 10 / 100) | `ramp_e0.5` delay |
| --- | ---: | ---: | ---: |
| 1.0 (former) | 48.9% / 53.3% | 60.0% / 57.8% | 1.57 |
| 1.25 | 4.4% / 4.4% | 8.9% / 11.1% | 1.99 |
| 1.4 | 1.1% / 1.1% | 2.2% / 2.2% | 2.29 |
| **1.5** | **0% / 0%** | **0% / 0%** | 2.43 |

Bias of 0.3 rad still triggers on the first attacked step; the extra delay on
ramps is about one step.

### Velocity-consistency gate (`IKVelocityFusionDefense`)

In clean rollouts the encoder increment equals the trapezoidal integral of the
reported joint velocity to within 1e-4 rad per step (the simulator integrates
this way). `VelocityConsistencyMonitor` flags a joint when the median of the
last 5 mismatches exceeds `max(0.002 rad, 4 * sigma_ref)`, where `sigma_ref`
is a robust (MAD) noise scale of the *other* joint's mismatch over the last 20
steps, so a biased joint cannot widen its own tolerance. The median ignores the
one-step spike at the onset or end of a constant angle offset. The check is
off for the first 8 steps while the noise estimate fills.

Offline, before any correction, this check had:

| Velocity noise sigma (rad/s) | 0 | 0.05 | 0.2 | 0.5 | 1.0 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Clean FA episodes | 0% | 0% | 1.1% | 1.1% | 1.1% |

Without the 8-step warm-up, 10-20% of noisy clean episodes alarmed in steps
1-3. Detection with no velocity noise was 100% within 2-3 steps for
`jvc_e0_v1.0` and `jvc_e1.0_v0.5`. At sigma 0.5 detection fell to 72% for 1 rad/s
velocity-only spoofing and 12% for the 0.5 rad/s bias of `jvc_e1.0_v0.5`: a
bias that small is buried in the noise, which is a physical limit of the
signal (the residual channel still catches the 1 rad angle part of that
attack).

A mismatch means either the velocity or the encoder lies. The defense compares
the encoder increment and the integrated velocity over the window against the
increment of the joint angle recovered from the independent fingertip
position (IK), and blames whichever is farther from it:

* **velocity blamed** (`metadata["vel_gated"]`): the estimated bias is removed
  from the velocity used for prediction *and* from `policy_obs[6:8]`;
* **encoder blamed** (ramps, threshold-aware ramps, sinusoids): the joint
  angle is corrected exactly like a joint jump, and the honest velocity is left
  untouched.

Gating is skipped while a joint-1 jump (mirror pose) is active, because the IK
branch is then unreliable.

### Closed-loop results (dev block, 3 policies x 30 states)

| Case | `ik_velocity_fusion` former: success / det. | **new: success / det.** | `continuous_velocity` former -> new success |
| --- | ---: | ---: | ---: |
| clean (false-alarm episodes) | 48.9% FA | **0% FA** | 48.9% -> 0% FA |
| `jvc_e1.0_v2.0` | 16% / 100% | **99% / 100%** | 2% -> 2% |
| `jvc_e0_v3.0` (velocity only) | 4% / 26%* | **99% / 100%** (delay 2.0) | 4% -> 4% |
| `jvc_e0_v1.0` (velocity only) | 94% / 26%* | **99% / 100%** | 94% -> 94% |
| `jvc_e1.0_v0.5` | 99% / 100% | 99% / 100% | 47% -> 47% |
| `ta_e0.1_s80` | 99% / 13%* | 99% / **100%** (delay 2.2) | 99% |
| `ta_e0.3_s60d40` | 100% / 29%* | 99% / **100%** (delay 2.5) | 100% |
| `elbow_s60d30` / `elbow_s80d20` | 99% / 100% | 99% / 100% | 30% / 46% |
| bias, ramp, sinusoid, freeze, replay | 99-100% | 99-100% | 99-100% |

\* Former "detections" of these cases were almost entirely the 49% background
false-alarm rate.

Under velocity noise (20 states per policy, calibration at the same noise):
clean false-alarm episodes were **1.7%** at sigma 0.2, 0.5 and 1.0 (former
46.7%); success matched or beat the former defense on clean, sustained bias,
elbow flip and `jvc_e1.0_v0.5` (95-100%), and mean joint-0 error stayed at
0.003-0.006 rad versus 0.006-0.028 rad for `continuous_velocity`.

### Tuned parameters kept at their defaults

`alpha` (0.25 / 0.5 / 0.75) and `min_jump_rad` (0.08 / 0.15) changed success by
at most one episode on any dev case. `alpha=0.25` lowered joint-0 error under
heavy velocity noise on `jvc_e1.0_v0.5` (0.004 vs 0.006 rad at sigma 1.0) but
raised it with no noise, so `alpha=0.5`, `jump_factor=2.5`, `min_jump_rad=0.15`
are unchanged. Joint-jump false alarms were 0% for every setting tested
(sigma 0 to 1.0) and elbow flips were always detected.

### Divergence abort (`ContinuousVelocityDefense`)

`divergence_abort_m` now compares the residual of the **corrected**
(dead-reckoned) observation with the bound. The former code used the
reported residual, which measures attack size, not estimator drift, so any
bound below ~0.1 m aborted at the onset of every large spoof.

| `divergence_abort_m` | Aborts outside `joint_vel_coupled` | `jvc_e1.0_v0.5` abort / success | `jvc_e1.0_v2.0` abort / success |
| --- | ---: | ---: | ---: |
| None (default) | 0% | 0% / 47% | 0% / 2% |
| 0.06 m | 0% | 48% / 44% | 98% / 2% |
| 0.03 m | 0% | 92% / 8% | 100% / 0% |

With honest velocity, dead reckoning tracks the fingertip through 40-step
attacks, so the bound never fires; it only fires when a tampered velocity
drags the estimate away (mean joint-0 error 0.08-0.32 rad). Because the
runner scores every abort as a task failure, the default stays `None`;
`0.06 m` is the recommended setting when a safe stop is preferred to acting on
a drifted estimate.

## 3. Policy-level fallback (`defenses/policy_level.py`, `train_fallback.py`)

### Fallback model: masked-observation SAC (`models/sac_seed_1_robust`)

`train_fallback.py` trains SAC with `MaskedObservationExtractor`, which
multiplies the listed observation channels by zero inside the network. The
saved `model.zip` therefore accepts the standard 10-dimensional observation
and drops into `--fallback-model`, while anything written into the masked
channels cannot change its actions (validation checks this by scrambling them:
maximum action change 0.0 for every model below). Hyperparameters match
`train.py` (SB3 defaults, buffer 100k, 1000 learning starts, synchronized
noise, 150k steps).

| Mask | Channels hidden | Validation, 30 clean episodes |
| --- | --- | --- |
| `0 2 6` | joint-0 encoder and joint-0 velocity | 4/30 for each of 3 seeds (rejected) |
| `0 2` (default) | joint-0 encoder `(cos q0, sin q0)` | **30/30 for seeds 1, 2 and 3** |

Hiding joint-0 velocity leaves the policy unable to damp joint 0, so it
overshoots and settles in only 4/30 episodes (these runs stopped at a 1-hour
cap, 90k-127k steps). With only the encoder hidden, joint 0 is still implied
by the fingertip-target vector, the target and joint 1. An earlier capped
`0 2` round (91k-126k steps) reached 24/30, 28/30 and 30/30; the full 150k-step
runs took 77-101 minutes each on one CPU thread (Python 3.11.18, Torch
2.14.1+cpu).

**Chosen model:** seed 1 (`models/sac_seed_1_robust`, sha256 `1a2cc2db...`),
the best fallback in the sweep below for both base defenses. As the main
policy without any defense it reaches 0.97 clean success, and joint-0 bias
and ramp attacks leave it at exactly that (0.97); velocity tampering and elbow
flips still break it (0-13% and 53%).

### Fallback inside `FallbackPolicyDefense` (dev block)

Sweep: `switch_streak` in {1, 3, 5, 10} x base defense in
{`continuous_velocity` (`cv`), `ik_velocity_fusion` (`ik`)} x `latch` in
{off, on}, all 17 cases, 3 frozen main policies x 30 states. Mean success over
the 16 attack cases (clean success is 0.99 and clean fallback use 0% for every
configuration):

| Fallback model | `ik` base, streak 10 | `cv` base, streak 10 | worst of 16 configs |
| --- | ---: | ---: | ---: |
| `sac_seed_1_sync` (unmasked reference) | 0.972 | 0.756 | 0.749 |
| **masked seed 1 (`sac_seed_1_robust`)** | **0.974** | **0.789** | 0.783 |
| masked seed 2 | 0.901 | 0.757 | 0.711 |
| masked seed 3 | 0.972 | 0.785 | 0.776 |
| masked, capped seeds 1 / 2 / 3 | 0.919 / 0.911 / 0.931 | 0.752 / 0.760 / 0.768 | 0.726 / 0.726 / 0.738 |

For comparison, `ik_velocity_fusion` alone (no fallback) reaches 0.99 on every
attack case.

Per-case success with `switch_streak=10`:

| Case | reference, `ik` | **robust, `ik`** | reference, `cv` | **robust, `cv`** |
| --- | ---: | ---: | ---: | ---: |
| `jvc_e1.0_v0.5` | 0.97 | 0.94 | 0.51 | **0.92** |
| `jvc_e1.0_v2.0` | 0.96 | 0.93 | 0.02 | 0.12 |
| `jvc_e0_v3.0` (velocity only) | 0.94 | 0.93 | 0.04 | 0.04 |
| `elbow_s60d30` / `elbow_s80d20` | 0.97 / 0.98 | 1.00 / 1.00 | 0.30 / 0.46 | 0.30 / 0.46 |
| `bias_e1.0_s60d40` / `ramp_e1.0_s60d40` | 0.94 / 0.96 | 0.93 / 0.93 | 0.96 / 0.96 | 0.93 / 0.94 |
| 20-step bias/ramp, freeze, replay, sinusoid, threshold-aware | 0.97-1.00 | 0.99-1.00 | 0.98-1.00 | 0.99-1.00 |

Findings:

* **The base defense matters most.** The `cv` base never alarms on elbow
  flips or velocity-only spoofing, so the fallback never engages there.
  Switching to the `ik` base raises mean attack success from 0.76-0.79 to
  0.97, so it is now the default.
* **`switch_streak`.** Streak 10 was best or within 0.3 points of the best
  for every fallback model (masked seed 1: 0.974 vs 0.977 at streak 5).
  Weaker fallbacks lose more with short streaks because hand-over starts
  earlier and lasts longer: threshold-aware episodes switch in 99-100% of
  cases at streak 1-5 versus 82% at 10. For example, masked seed 2 scored
  0.829 at streak 1 versus 0.901 at 10. With the `ik` base the corrected
  observation is already good, so a long streak keeps the main policy in
  control. The default is now 10.
* **`latch`** never helped (+0.2 to -2.6 points across all models) and stays
  off.
* **Success after a fallback transition.** Over all attacked episodes that
  switched, success was 0.925 with `sac_seed_1_robust`, 0.898 with the
  unmasked reference, and 0.79 / 0.92 for masked seeds 2 / 3. Under the
  robust fallback, 40-step attacks that hand over at about step 70 finish at
  0.93-0.94 whatever the attack (bias, ramp, `jvc`, velocity-only), slightly
  below the model's 0.97 standalone clean success. Taking over mid-reach from
  a state the main policy produced costs a few points; the masked channels
  themselves do not.
* **Where the masked fallback adds value.** Behind the weak `cv` base it
  recovers `jvc_e1.0_v0.5` (0.51 -> 0.92). There, dead reckoning drifts with
  the spoofed encoder, and the unmasked reference fallback is fed that same
  corrupted angle. It does not help against strong velocity tampering behind
  `cv` (`jvc_e1.0_v2.0` 0.02 -> 0.12), since joint-0 velocity is still an
  input. Behind the `ik` base it matches the reference (0.974 vs 0.972) and
  is better on elbow flips. Keeping the main policy on the IK-corrected
  observation (0.99) is still best, so the fallback is defense in depth for
  when that correction is unavailable or untrusted, not a replacement for it.

## Reproduction

Dev sweeps used the registry and `evaluation.runner.calibrate_policy` /
`run_paired_trial` directly so that defense parameters could be varied; the
scripts are local (`outputs/dev_tools/`, gitignored). The CLI verification
command for this track is:

```bash
python run_matrix.py --preset full_matrix --models models/sac_seed_1_sync/model.zip \
  --attacks clean bias threshold_aware elbow_flip joint_vel_coupled \
  --defenses no_defense original_fail_stop cusum ik_velocity_fusion fallback_policy \
  --fallback-model models/sac_seed_1_robust/model.zip \
  --episodes 6 --calibration-episodes 10 --test-base 1110000 --no-traces \
  --out outputs/dev_defenses_001
```

Result (6 paired states, `sac_seed_1_sync`), compared with the same command
before this branch (former defaults, `--fallback-model
models/sac_seed_1_sync/model.zip`):

| Metric | Before | After |
| --- | ---: | ---: |
| Clean false-alarm episodes, `ik_velocity_fusion` / `fallback_policy` | 4/6 / 4/6 | **0/6 / 0/6** |
| Clean false-alarm episodes, `original_fail_stop` / `cusum` | 4/6 / 0/6 | 4/6 / 0/6 |
| Threshold-aware detection, `cusum` / `ik_velocity_fusion` / `fallback_policy` | 5/6 / 2/6 / 2/6 | **6/6 / 6/6 / 6/6** |
| `fallback_policy` success, `elbow_flip` / `joint_vel_coupled` | 2/6 / 5/6 | **6/6 / 6/6** |
| `ik_velocity_fusion` success, all cases | 6/6 | 6/6 |

Clean success was 6/6 for every defense in both runs. `original_fail_stop`
is legacy and unchanged.

Environment: Python 3.11.18 and the pinned `requirements.txt` stack (Torch
2.14.1+cpu, NumPy 2.4.6, Gymnasium 1.4.0, MuJoCo 3.15.0, SB3 2.9.0) for the
fallback training, tests and verification run; the earlier dev sweeps ran on
Python 3.12.3 with the same pinned package versions.
