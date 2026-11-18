# Interpretation notes recorded before the main test

These explain possible outcomes of the specified experiment. They are not a
replacement for measured results or evidence that a real robot is safe.

## Small offsets can fall below the residual threshold

For this planar arm, changing only joint0 rotates the full arm about its base.
If r is the current base-to-fingertip radius, the noiseless position discrepancy
caused by offset delta is `2 * r * abs(sin(delta / 2))`.

The nominal links are 0.10 m and 0.11 m, so r <= 0.21 m. Even at full extension,
a 0.02 rad offset creates at most about 4.20 mm discrepancy. With independent
2 mm standard-deviation Gaussian noise on x/y, the ideal clean residual's 99th
percentile is `sigma * sqrt(-2 * log(0.01))`, about 6.07 mm. Actual thresholds
are calibrated empirically, not set using this formula.

Thus small attacks may cause less geometric discrepancy than the clean
threshold. Noise can still push them over it, so this is not a claim that they
are impossible to detect. Folded poses with smaller r further reduce sensitivity.

## A 1% step false alarm target is not a 1% episode target

With independent 1% per-step alarms and 99 detection opportunities, the chance
of at least one alarm is `1 - 0.99**99`, approximately 63%. Report step-level and
episode-level false alarms separately. A high episode-level alarm fraction alone
does not imply the 99th-percentile calibration was implemented incorrectly.

## Early attacks may leave terminal success unchanged

Each control interval is 0.02 seconds. A 20-step attack beginning at observation
20 acts around 0.4–0.8 seconds of a 2-second episode. The task criterion averages
the last ten post-action distances, leaving substantial recovery time after the
attack. The policy also directly observes trusted fingertip-to-target position.
Therefore transient trajectory errors can coexist with zero measured task
failures. Windowed distance changes and control effort are essential secondary
outcomes. Do not change amplitude or timing after seeing the main results and
present the revised setup as the original study.

## Alarm-driven prediction has limits

The estimate integrates the previous velocity with a first-order update. Motion
acceleration and prolonged alarms can cause drift. A gradual attack below the
threshold can also be accepted before its first alarm; the predictor then starts
from that last accepted, possibly already biased angle. Noise-triggered alarms
can cause interventions on clean trajectories. Measure these costs rather than
assuming correction is always beneficial.

## Scope

The geometry is known and ideal, the independent position/velocity channels are
assumed protected, and all data come from the same simulator family. Three seeds
and 30 initial states per policy give limited evidence about generalization.
Neither successful mitigation nor zero observed failures establishes physical
safety or robustness to other attack channels, larger offsets or different arms.
