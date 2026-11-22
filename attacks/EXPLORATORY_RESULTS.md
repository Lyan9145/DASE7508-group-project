# Additional attack methods: development results

These are exploratory results on the Phase-2 **development** seeds, not the
held-out test set. All three frozen policies were evaluated on 30 paired states
each (`DEV_BASE=1100000`) with 100 clean calibration episodes per policy
(`CAL_BASE=1000000`). The local environment has Python 3.12.13, Torch 2.11.0,
Gymnasium 1.3.0 and MuJoCo 4.0.0, which differ from the repository lockfile.

## Periodic pulse injection

`PulseAttack` changes only joint-0 angle channels `(0, 2)`, with a 1.0 rad
offset for 18 steps followed by 2 clean steps, repeated from observation 60
through 99. The off interval interrupts the legacy monitor's consecutive
alarm streak. The paired run is in local `outputs/dev_pulse_030/`:

```bash
python run_matrix.py --preset full_matrix \
  --attacks clean pulse sustained_bias_e1.0_s60_d40 elbow_flip_s80_d20 \
  --defenses no_defense original_fail_stop \
  --episodes 30 --calibration-episodes 100 \
  --test-base 1100000 --cal-base 1000000 --no-traces \
  --out outputs/dev_pulse_030
```

Task successes for policies 1 / 2 / 3:

| Attack | No defense | Original fail-stop |
| --- | --- | --- |
| Clean | 30 / 29 / 30 | 30 / 29 / 30 |
| Sustained 1.0 rad bias | 2 / 1 / 0 | 0 / 0 / 0; all aborted |
| 18-on, 2-off pulse | 2 / 1 / 0 | 30 / 29 / 30; none aborted |

The pulse is as damaging as sustained bias without a defense and avoids the
**abort rule**, but the old defense still detects and corrects it. It therefore
does **not** bypass the defense's task protection. Retaining this distinct case
helps evaluate whether a new defense relies excessively on consecutive alarms.

## Elbow-flip timing scan

An earlier start with injection through observation 99 was stronger against
`original_fail_stop` than the existing start-80, duration-20 case:

| Start / duration | Policy 1 | Policy 2 | Policy 3 |
| --- | ---: | ---: | ---: |
| 40 / 60 | 5/30 | 1/30 | 9/30 |
| 60 / 40 | 5/30 | 2/30 | 8/30 |
| 70 / 30 | 8/30 | 4/30 | 10/30 |
| 80 / 20 | 16/30 | 6/30 | 19/30 |

The original fail-stop monitor did not abort any of these elbow-flip trials.
The start-40 case is a useful candidate for the evaluation track, subject to
rechecking in the pinned environment and freezing before held-out testing.

## Discarded method

We also tried a two-joint grid search for maximal instantaneous policy action
divergence while constraining the observed FK residual. On a six-state pilot,
its task-success counts and detection behavior were identical to the existing
elbow-flip attack across all three policies. The implementation was removed to
avoid adding code without a demonstrated benefit.
