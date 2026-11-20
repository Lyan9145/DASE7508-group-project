# DASE7508-group-project
Group 9: joint-angle sensor spoofing and kinematic mitigation for a simulated
reinforcement-learning robotic arm.

- [2026-10-22 results and group progress](RESULTS.md): three validated policies,
  4,500 paired main-study trials, plots, replay, failure analysis and full audit.
- [Integration work log](WORK_LOG.md)
- [Proposal](DASE7508_Proposal_2.0.md)
- [Installation, training and experiment commands](github_upload/README.md)
- [Experiment protocol and metric definitions](github_upload/PROTOCOL.md)

Executable code and outputs are in `github_upload/`. Run commands there.

2026-11-18 Windows/mp1 independent reproduction and exploratory extensions:
[reproduction report](REPRODUCTION_REPORT.md), [final measured results](FINAL_RESULTS.md),
[five-person presentation](PRESENTATION_PLAN.md). Tables and figures are in
`github_upload/outputs/reproduction_20261118_materials/`; historical `main_v1` stays intact.

Windows PowerShell, from repository root (this machine already has mp1):

```powershell
# This project uses mp1's Python with project-local CPU Torch and dependencies.
# For a fresh machine install 64-bit Python 3.12, then replace the first command
# by: py -3.12 -m venv .venv
& C:/anaconda/envs/mp1/python.exe -m venv --system-site-packages .venv
& ./.venv/Scripts/python.exe -m pip install -r github_upload/environment-windows-mp1.lock.txt
Set-Location github_upload
& ../.venv/Scripts/python.exe -m pytest test_security.py test_exploration.py -q
$run = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
& ../.venv/Scripts/python.exe check_setup.py --no-render --out "outputs/reproduction_numeric_$run"
& ../.venv/Scripts/python.exe check_setup.py --out "outputs/reproduction_render_$run"
```

No CUDA or EGL is needed. On this machine ensurepip failed during venv creation;
the local `.venv/pyvenv.cfg` was set to `include-system-site-packages = true`,
and `uv pip install --python .venv/Scripts/python.exe` installed packages with
`$env:UV_CACHE_DIR = "$PWD/.uv-cache"`. Existing mp1 packages were not changed.
The original lock resolved successfully. The initial mp1 Torch 2.7.1 was below
SB3's declared minimum; the final local lock uses Torch 2.14.1+cpu installed only
inside `.venv`. `pip check` passes. Initial permission/network errors and verified
test output are preserved in `github_upload/outputs/reproduction_20261118_environment/`.
For a fresh Python environment, use pip normally; if using uv instead, install
uv first. Do not copy Linux `MUJOCO_GL=egl` commands to Windows.

From `github_upload`, demonstrate the same policy and initial seeds:

```powershell
& ../.venv/Scripts/python.exe demo.py --attack clean --episodes 1
& ../.venv/Scripts/python.exe demo.py --attack bias --epsilon 0.1 --duration 20 --episodes 1
$cal = Get-Content outputs/reproduction_20261118_compatible_main/calibration.json -Raw | ConvertFrom-Json
& ../.venv/Scripts/python.exe demo.py --attack bias --epsilon 0.1 --duration 20 --monitor-threshold $cal.sac_seed_1_sync.threshold_m --episodes 1
# Also show the intervention cost under normal observations.
& ../.venv/Scripts/python.exe demo.py --attack clean --monitor-threshold $cal.sac_seed_1_sync.threshold_m --episodes 1
# Frozen exploratory improvement, with the same detector threshold:
& ../.venv/Scripts/python.exe demo.py --attack bias --epsilon 0.1 --duration 20 --monitor-threshold $cal.sac_seed_1_sync.threshold_m --recovery-grace 1 --episodes 1
```

Human-window rendering should be checked before presenting. Use Windows screen
recording for all three conditions, keep the same model/episode seeds, and retain
the static trajectory/abort figures as backup. Historical replay GIF is available
under `outputs/main_v1/figures/`; do not label it a new Windows recording.

Quick numerical run, frozen main reproduction, and new exploratory study
(fresh timestamped directories, existing outputs are refused):

```powershell
$run = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
& ../.venv/Scripts/python.exe evaluate.py --models outputs/sac_seed_3_sync/model.zip --episodes 2 --epsilons 0.1 --durations 20 --test-base 802008 --calibration-base 302000 --out "outputs/reproduction_smoke_$run"
& ../.venv/Scripts/python.exe evaluate.py --phase main --plan main_plan.json --episodes 30 --test-base 800000 --calibration-base 300000 --models outputs/sac_seed_1_sync/model.zip outputs/sac_seed_2_sync/model.zip outputs/sac_seed_3_sync/model.zip --out "outputs/reproduction_main_$run"
& ../.venv/Scripts/python.exe audit_results.py "outputs/reproduction_main_$run" --output "outputs/reproduction_main_audit_$run.json"
# Read-only historical audit, save elsewhere:
& ../.venv/Scripts/python.exe audit_results.py outputs/main_v1 --output "outputs/reproduction_history_audit_$run.json"
& ../.venv/Scripts/python.exe exploration.py --out "outputs/exploratory_$run"
```

`exploration.py` freezes its plan, runs development, freezes one recovery rule,
then runs independent tests. Clean trajectories are reused for matched windows;
it also checks a predeclared sustained attack. Never retune on those test states.
The session-specific `build_deliverables.py` reads the dated runs listed in its
source and refuses an existing materials directory; it regenerates this session's
reports, tables and plots. Exact executed commands are recorded in
`github_upload/outputs/reproduction_20261118_environment/commands.ps1`.
