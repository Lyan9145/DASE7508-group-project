# Team Handoff and Verification Package Notes

Archived local handoff archive reference: `deliverables/DASE7508_team_handoff_20261118.zip` (generated locally only, not pushed to Git; `PACKAGE_MANIFEST.json` records file sizes and SHA256 digests using an explicit allowlist excluding `.venv`, caches, credentials, and multi-hundred-MB `traces.jsonl.gz` files).

Full exploratory/compatible traces remain in `reproduction_20261118_compatible_main` and `exploratory_20261118_compatible` on the originating machine; pre-acceptance hashes are saved in `final_acceptance_20261118/protected_before.json`.

## Environment Setup from Scratch (Windows PowerShell)

Extract to a writable directory containing `TEAM_HANDOFF.md` and `github_upload/` (do not execute directly inside a ZIP virtual folder). Requires 64-bit Python 3.11 or 3.12:

```powershell
py -0p
py -3.12 -m venv .venv
$py = (Resolve-Path .\.venv\Scripts\python.exe).Path
& $py -m pip install -r github_upload/environment-windows-mp1.lock.txt
& $py -m pip check
```

Notes:
- This environment locks `Torch 2.14.1+cpu`; CPU is sufficient, and `MUJOCO_GL=egl` is not needed on Windows.
- Initial installation requires network access (not an offline wheel bundle).

## Quick Verification Commands

Active Phase-2 tests and setup check:

```powershell
Set-Location github_upload
& ..\.venv\Scripts\python.exe -m pytest test_framework.py -q -p no:cacheprovider
$run = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
& ..\.venv\Scripts\python.exe check_setup.py --out "outputs/team_render_$run"
```

Archived 2026-11-18 4-mode numeric demo (requires `github_upload\legacy` and `github_upload\framework\core` on `PYTHONPATH` from repo root):

```powershell
$env:PYTHONPATH = "github_upload;github_upload\legacy;github_upload\framework\core"
$run = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
& $py github_upload/legacy/presentation_demo.py --scenario boundary --numeric-only --out "github_upload/outputs/team_numeric_$run"
```

Expected output for the 4-mode boundary numeric check: `normal` / `attack` / `improved` complete `100` steps (`success=True`), while `original` aborts at `40` steps (`success=False`).

## Viewing Results and Replays

```powershell
Invoke-Item github_upload/outputs/final_acceptance_20261118/demo_boundary_v2/replay.html
Invoke-Item FINAL_ACCEPTANCE.md
Invoke-Item SLIDES_CONTENT.md
Invoke-Item github_upload/outputs/final_acceptance_20261118/figures
```

See [DEMO_GUIDE.md](DEMO_GUIDE.md), [FIGURE_GUIDE.md](FIGURE_GUIDE.md), [SPEAKER_NOTES.md](SPEAKER_NOTES.md), and [QA_PREP.md](QA_PREP.md) for presentation details.

## Troubleshooting

- `ModuleNotFoundError`: ensure `$py` points to `.venv\Scripts\python.exe` (or activated `dase7508` Conda env on Linux).
- Torch/SB3 dependency conflicts: install via `github_upload/environment-windows-mp1.lock.txt` (or `requirements.lock.txt` + `torch==2.14.1` CPU) and verify `pip check`.
- `Output directory exists`: supply a fresh timestamped `--out` path; never overwrite existing outputs.
- OpenGL/GLFW failures: pass `--no-render` to `check_setup.py` and fall back to static PNGs/GIFs.

## Pending Second-Machine Verification Checklist

- [ ] Record tester name, date, machine model, OS, and Python version on a genuinely separate machine.
- [ ] Verify `PACKAGE_MANIFEST.json` SHA256 hashes, dependency install, and `pip check`.
- [ ] Confirm test suite and 4-mode numeric outputs match, saving fresh `run_status.json`, CSVs, and logs.
- [ ] Verify replay rendering legibility (mode, time, attack window, distance, alarms, and abort label).
- [ ] Confirm all five figures, denominators, truncated window notes, and four failure identities are understood.
- [ ] Confirm true individual member contributions, conduct a 12-minute timed rehearsal, and verify Moodle submission requirements.
