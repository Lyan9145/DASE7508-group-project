# Q&A Preparation (~3 Minutes Live Q&A)

Lead each answer with a one-sentence conclusion, then cite the supporting evidence without reading full backup tables.

1. **Why did the unprotected arm always succeed?**
   Within the tested small, short attacks, perturbations change transient errors but not final success. Earlier attacks leave recovery time. Protected position input may also help, though we did not establish that causal explanation through ablation in Phase 1. *(Evidence: `02_timing.png`, `short_totals.csv`.)*

2. **What is the security value if attacks do not cause failure?**
   We quantify a threat boundary and a mitigation trade-off. The original defense introduces four short-condition aborts (`1076/1080`) that the unprotected baseline (`1080/1080`) does not have. A bounded wait avoids them (`1080/1080`) at the cost of a `20 ms` sustained-response delay. Reporting negative attack results prevents unsupported vulnerability claims. *(Evidence: `cohorts.csv`, `sustained_pairs.csv`.)*

3. **What can the attacker change?**
   In the Phase-1 model, only `joint0`'s cosine and sine (`observation[0]` and `observation[2]`), with a bounded `bias` or `ramp` in one declared window. It cannot alter target, `joint1`, velocities, position measurements, physics dynamics, reward, policy weights, or monitor code. *(Evidence: `framework/core/security.py`, step-level protected-channel audits.)*

4. **Why trust independent position and velocity?**
   It is an explicit simulator threat-model assumption. The wrapper generates separate channels before angle-only injection, and trace audits confirm they are unmodified. This does not establish physical hardware isolation or resistance to multi-channel compromise. *(Evidence: `framework/core/reacher_env.py`, [FINAL_ACCEPTANCE.md](FINAL_ACCEPTANCE.md).)*

5. **What are the detector's blind spots?**
   Small offsets and folded arm poses can yield residuals below the noise-calibrated threshold. Gradual attacks can be accepted prior to the first alarm and bias the predictor's initial state. Gaussian noise alone triggers alarms (`89/8910` clean steps), and long prediction chains drift. *(Evidence: `window_rates.csv`, `github_upload/ANALYSIS_NOTES.md`, prediction logs.)*

6. **Why is waiting not better detection?**
   The residual, threshold, and velocity-integration correction are unchanged. Wait+1 shifts the abort threshold from `21` to `22` consecutive alarms. The extra step provides no new evidence that an attack has ended. *(Evidence: `framework/core/recovery_monitor.py`, executed snapshots.)*

7. **What does the 20 ms delay cost?**
   Across all `73` shared sustained-attack aborts, termination occurs one control action (`dt = 0.02 s`) later, permitting one more step of anomalous operation before stopping. This experimental abort is not a certified physical safety stop. *(Evidence: `sustained_pairs.csv`.)*

8. **How did you prevent test-set tuning?**
   Calibration states (`900000` block) set thresholds; separate development states (`910000` block) compared predeclared `{1, 3}` waits. Both tied at `15` aborts, and the fixed tie-break selected `1`. Executed code saved `frozen_selection.json` prior to running the held-out test block (`930000`). Local logs support this ordering rather than third-party timestamp certification. *(Evidence: `seed_inventory.json`, `frozen_selection.json`, `source/exploration.py`.)*

9. **Are 1,080 trials independent? Why only three policies?**
   No: `1,080` equals `12` attack conditions repeated across `90` paired states from `3` trained policies. The `4` avoided aborts involve `4` distinct states across `2` policies. State-level paired analyses condition on these `3` policies and do not establish broad cross-policy generalization. *(Evidence: `four_failures.csv`.)*

10. **Could lower error or control cost be caused by early aborts?**
    Yes, if naively pooled. We count every abort as task failure, flag incomplete windows, and report complete 100-step final distances separately alongside abort counts. Complete-only means still carry survivor selection and do not prove efficiency gains; squared normalized actions are not mechanical energy. *(Evidence: `verified_episodes.csv`, `04_defense_cost.png`, [FINAL_ACCEPTANCE.md](FINAL_ACCEPTANCE.md).)*

11. **Does a high window alarm rate mean accurate attack recognition?**
    No. Matched normal 20-step windows alarm in `13/90` or `17/90` cases, while attack windows observe alarms in `76/90` to `90/90` cases. We report paired differences, conditional first-alarm delays, and no-alarm rates. Truncated windows preserve observed exposure without treating unobserved suffixes as clean. *(Evidence: `false_alarms.csv`, `window_rates.csv`, `paired_windows.csv`.)*

12. **What is reused, what is new, and what remains unfinished?**
    Upstream MuJoCo, Gymnasium, and SAC/SB3 plus baseline models, attacks, monitor, and `main_v1` are reused. Subsequent rounds added Windows reproduction, the timing and bounded-wait studies, acceptance audits, presentation drafts, and the Phase-2 unified attack/defense framework (`github_upload/framework/`). Actual member contributions require group confirmation; second-computer verification, timed rehearsal, and final submission remain pending. *(Evidence: [TEAM_HANDOFF.md](TEAM_HANDOFF.md), [PRESENTATION_PLAN.md](PRESENTATION_PLAN.md), [github_upload/FRAMEWORK_GUIDE.md](github_upload/FRAMEWORK_GUIDE.md).)*
