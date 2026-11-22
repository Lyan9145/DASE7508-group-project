# Speaker Notes (5 Speakers, ~12 Minutes Total)

Corresponds to the 10 slides in [SLIDES_CONTENT.md](SLIDES_CONTENT.md) (`132 s` per speaker including pauses; Speaker E includes the ~75s demo). Speaker labels `A–E` represent speaking order, not authorship assignments. Pace should be verified in a timed rehearsal.

## A — Slides 1–2 / 132s

**Slide 1**

Our project asks a practical security question: if one joint-angle sensor lies, can a robot still complete its task, and does adding a monitor actually help? Our system is a simulated two-joint arm controlled by a trained reinforcement-learning policy. Its normal job is to move the fingertip close to a target. The security goal is to preserve task performance when one observation channel is corrupted. We examine both the attack's effect and the monitor's own costs. We do not assume that an attack must succeed, or that a defense must improve the outcome.

**Slide 2**

This diagram shows the trust boundary. We use MuJoCo and Reacher with a frozen SAC policy. The attacker can replace only joint zero's sine and cosine entries. It cannot change the physical state, target, policy weights, position measurements, or velocities. Independent position and velocity channels are trusted by assumption in this simulator. We have not demonstrated their independence on real hardware. The monitor receives reported observations and nominal geometry. Simulator truth goes to a separate evaluator and to the demonstration display. It never decides an alarm, correction, or abort. Each episode has one hundred control steps, with twenty milliseconds per step.

## B — Slides 3–4 / 132s

**Slide 3**

We study two simple observation attacks. Bias adds a constant signed angle offset. Ramp increases the offset gradually during a fixed window. Both consistently update the sine and cosine pair. The original study also includes random-sign controls with matched magnitudes and durations. The models, original attacks, and kinematic monitor were already present in the group project. Our later work reproduced the results on Windows, added a separate timing study, evaluated a bounded waiting rule, and checked the evidence. Individual authorship must follow our actual group records; these speaking roles are not author assignments.

**Slide 4**

The timing study keeps the policies frozen and changes only the attack start: step twenty, fifty, or seventy. We use two amplitudes and twenty-step bias or ramp attacks, with thirty new states per policy. For the point-one-radian bias, the final ten-state mean error rises from about five-point-five-eight to six-point-one-six millimetres when the attack starts later. However, all one thousand and eighty unprotected short-attack conditions still succeed. The success threshold is thirty millimetres. The transient window effect does not simply increase with later timing. Our first-state example has almost overlapping trajectories; we retain it rather than choose a more dramatic picture. This experiment compares timing, not the causal importance of one input channel.

## C — Slides 5–6 / 132s

**Slide 5**

The monitor compares two estimates of fingertip position: forward kinematics from the reported angles, and the protected position measurement. A large residual triggers an alarm. Each policy's threshold is the ninety-ninth percentile from one hundred separate clean calibration episodes. During an alarm, the monitor predicts joint zero from the previous accepted or predicted angle and previous trusted velocity. It replaces only that joint's sine and cosine entries. A normal reading resets the alarm chain. Noise can trigger the same alarm, and folded poses or gradual offsets can remain below the threshold. Therefore an alarm is an anomaly signal, not reliable attribution to an attacker.

**Slide 6**

Here is the original failure mechanism. A twenty-step attack produces twenty consecutive alarms. In this selected historical case, the first post-attack noisy observation produces alarm twenty-one. The original rule aborts, although the true target distance is only about three-point-eight-five millimetres. The new rule waits one extra step. A clear reading resets it; a continued alarm at twenty-two still aborts. This is mathematically a shifted abort boundary, not improved recognition of attack recovery. We compared one-step and three-step candidates on a separate development set. Both had fifteen aborts, so the predeclared tie-break chose the shorter wait. The independent test set was not used to tune it.

## D — Slides 7–8 / 132s

**Slide 7**

The main evaluation uses three frozen policies and thirty paired states per policy. Conditions share the initial state, sensor-noise stream, and attack schedule. Success requires all one hundred actions, no abort, and a final ten-state mean distance within thirty millimetres. The reproduced main counts are twenty-two-fifty successes without defense, and twenty-two-forty-eight with the original defense. The two failures repeat one initial state under bias and its random-sign control. Four thousand five hundred episodes are repeated conditions on ninety states, not independent samples. Calibration, development, and test states are separate. We audited source snapshots, model hashes, and full traces.

**Slide 8**

In the new short-attack tests, the unprotected baseline succeeds in all one thousand and eighty conditions. The original defense succeeds in one thousand and seventy-six, and the waiting rule in all one thousand and eighty. The four avoided aborts involve four different states from two policies. This removes a defense side effect; it does not beat the unprotected baseline. Under forty-step sustained attacks, both defenses abort seventy-three of ninety cases. Waiting adds exactly one step, or twenty milliseconds, in all seventy-three paired aborts. Clean observations produce eighty-nine alarms across eight thousand nine hundred and ten step opportunities, and fifty-four of ninety episodes contain an alarm. We compare matching normal windows before interpreting attack-window alarms. Aborted runs remain failures, and their shorter trajectories are not presented as lower-cost successes.

## E — Slides 9–10 / 132s

**Slide 9 (use the ~70–75s walkthrough in DEMO_GUIDE.md)**

This is a selected historical boundary case, not the average result. All four panels use policy three and initial-state seed eight-zero-two-zero-zero-nine. We hold the noise and attack schedule fixed. The labels show mode, simulation time, attack window, true distance, alarm streak, and abort status. Truth is display-only. At step forty, the original rule aborts on alarm twenty-one. The waiting rule continues and completes the task. The normal and unprotected attack runs also complete. The replay is slowed for explanation; an aborted panel freezes instead of pretending to continue. The overall performance comes from the statistics, not this selected example.

**Slide 10**

Our strongest finding is a trade-off. Within this bounded simulation, the attacks do not cause unprotected task failure, while the original monitor can introduce false stops. One extra waiting step reduces some boundary failures but delays sustained response. Three policies, ideal geometry, and protected channels limit generalisation. A future study should predeclare more policy seeds and pose-stratified tests, and jointly assess false stops, delay, and prediction drift. We credit the existing group implementation, upstream tools, and AI assistance; actual member contributions must be confirmed. Thank you.
