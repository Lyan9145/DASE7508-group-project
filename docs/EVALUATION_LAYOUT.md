# Evaluation figure layout check

The full-size preview used 30 case labels and eight defense labels from the
current draft. All 240 cells per panel rendered. Case labels, including the
long sinusoidal comparison ID, fit at native resolution. Use the full heatmap
in the report or appendix. For slides, show the rows relevant to the point
being discussed and keep the full matrix available alongside them.

The detection trade-off panels and eight-entry legend fit. Defenses with
identical detection and false-alarm rates share coordinates, so use the
summary table to identify exact ties. The min–max bars describe variation
across cases.

The three-panel replay was checked separately with real development smoke
traces. Its default selector prefers a bias case with more undefended failures,
then a paired example with undefended failure and fusion success. Label that
replay as an illustrative example. For a specified case, pass
`--attack-case CASE_ID`. Confirm the policy and seed match across panels.

## Reproduce the layout check

From the repository root, using the evaluation environment:

```bash
run=$(mktemp -d "${TMPDIR:-/tmp}/evaluation-layout.XXXXXX")
export MPLBACKEND=Agg
export MPLCONFIGDIR="$run/matplotlib"
python - "$run" <<'PY'
import json
import sys
from pathlib import Path

from evaluation.presets import get_preset

out = Path(sys.argv[1])
preset = get_preset("full_matrix")
rows = [
    {
        "attack_case": attack.case_id,
        "attack_name": attack.attack_name,
        "defense": defense.defense_id,
        "task_success_rate": ((i * 17 + j * 11) % 101) / 100,
        "paired_window_mean_delta_m": None if i == 0 else ((i + j) % 11 - 5) / 100,
        "clean_false_alarm_episode_rate": 0.5 if j else 0.0,
        "clean_false_alarm_step_rate": 0.01 if j else 0.0,
        "in_window_detection_rate": ((i * 7) % 101) / 100 if j else 0.0,
    }
    for i, attack in enumerate(preset.attacks)
    for j, defense in enumerate(preset.defenses)
]
(out / "matrix_summary.json").write_text(json.dumps({"across_policies": rows}))
(out / "config.json").write_text(json.dumps({
    "preset": "synthetic layout preview",
    "episodes": preset.episodes,
    "attacks": [{"case_id": attack.case_id} for attack in preset.attacks],
    "defenses": [{"defense_id": defense.defense_id} for defense in preset.defenses],
}))
PY
python plot_matrix.py "$run" --no-replay
printf 'Layout preview: %s\n' "$run/figures"
```

The fixture is for layout only and runs no simulations. For actual results,
run `python evaluation/check_results.py RUN_DIR` before plotting.
