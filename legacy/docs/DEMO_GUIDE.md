# Fixed Paired Demo and Recording Guide

Completed artifacts: numerical runs for the four-mode boundary case, MuJoCo RGB rendering, GIF generation, HTML replay generation, and step-40 static frame checks. Numerical verification for the second predeclared first-state scenario is also complete. **No desktop screen-recording MP4 has been produced, and live browser/projector playback has not yet been verified manually.** The generated GIF is a slowed simulator replay rather than a desktop recording; the course instructions permit annotated traces as representative runs.

Open the pre-generated replay from the repository root (no rerun needed):

```powershell
Invoke-Item .\github_upload\outputs\final_acceptance_20261118\demo_boundary_v2\replay.html
# Static fallback
Invoke-Item .\github_upload\outputs\final_acceptance_20261118\demo_boundary_v2\boundary_step40.png
```

Fixed configuration: `policy3` (`sac_seed_3_sync`), seed `802009`, `noise_seed=10802009`, `bias=-0.10 rad`, attack window `[20, 40)`, `dt=20 ms`, calibrated `policy3` threshold from `compatible_main`, and `wait=1`. All four modes share the same initial state, sensor-noise stream, and attack schedule (normal mode disables injection). The original monitor aborts at observation `40` after 40 actions; the other three modes complete all 100 actions. This example is a known historical failure case, **not average performance** (see Figure `04_defense_cost.png` for aggregate counts).

True distance is used strictly for display and task scoring. Numerical trajectories are recorded first and replayed in a separate render environment; the policy receives only `policy_obs` and the monitor receives only `reported`. Overlays display mode, simulation time/step, attack window/injection, true distance (mm), alarm/streak, and abort state. Aborted frames freeze with an abort label rather than fabricating subsequent actions. The GIF samples every second step with simulation-time labels.

*(Note: `presentation_demo.py` referenced below has been archived to `github_upload/legacy/presentation_demo.py`; active Phase-2 multi-attack/multi-defense demos use `github_upload/demo.py` and `github_upload/plot_matrix.py`.)*

Regenerating the four-mode annotated demo from the archived script requires `github_upload/legacy` and `github_upload/framework/core` on `PYTHONPATH` (with a fresh output directory):

```powershell
$env:PYTHONPATH = "github_upload;github_upload\legacy;github_upload\framework\core"
$run = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
python github_upload/legacy/presentation_demo.py --scenario boundary --mode all --out "github_upload/outputs/demo_boundary_$run" --open
```

Individual modes, representative example, and numeric-only smoke check:

```powershell
python github_upload/legacy/presentation_demo.py --scenario boundary --mode normal --out "github_upload/outputs/demo_normal_$run"
python github_upload/legacy/presentation_demo.py --scenario boundary --mode attack --out "github_upload/outputs/demo_attack_$run"
python github_upload/legacy/presentation_demo.py --scenario boundary --mode original --out "github_upload/outputs/demo_original_$run"
python github_upload/legacy/presentation_demo.py --scenario boundary --mode improved --out "github_upload/outputs/demo_improved_$run"
python github_upload/legacy/presentation_demo.py --scenario representative --out "github_upload/outputs/demo_representative_$run"
python github_upload/legacy/presentation_demo.py --scenario boundary --numeric-only --out "github_upload/outputs/demo_numeric_$run"
```

Active `github_upload/demo.py` provides an interactive human window across all registered attacks and defenses, e.g., `cd github_upload && python demo.py --attack clean --episodes 1`. Neither retraining nor CUDA/EGL is required.

## ~70-Second Walkthrough Script (Within Speaker E's 75s Slot)

| Time | Visual / Action | Spoken Focus & Scope |
|---|---|---|
| 0–10s | Show 4-panel header & config | "This is a selected historical boundary case, not the average result." State fixed model/seed/noise. |
| 10–25s | Play GIF, highlight 4 modes & window | "Only the angle observation is corrupted. The physical state is not directly changed." Note physical paths look similar. |
| 25–45s | Switch to `boundary_step40.png` (zoomable) | "At step 40, the original rule aborts at alarm 21; wait+1 continues. True distance is display-only." Clarify this shifts the abort boundary rather than detection accuracy. |
| 45–60s | Return to GIF showing frozen panel & completed CSV | "Normal and unprotected attack also finish. The original aborted panel is frozen." Show side effect rather than claiming superiority over no defense. |
| 60–70s | Switch to Figure 04 / summary statistics | "Across held-out states, four short-case aborts are avoided, with a 20 ms sustained-response cost." Distinguish single case from aggregate stats. |

Manual screen recording checklist: open local `replay.html`, verify GIF loop, font legibility, and 4-panel visibility; record ~70s keeping "selected case" and "display only" visible; verify audio, file size, and total duration. Label saved files accurately as `screen recording` or `simulator replay` (do not label the generated GIF an MP4 screen recording).

Fallbacks: if HTML fails to launch, open `replay.html` directly in a browser; if GIF fails to play, use `boundary_step40.png` + `episodes.csv`; if live rendering fails, use archived replays while numeric checks remain runnable. Never change thresholds, amplitudes, or seeds during a demo.
