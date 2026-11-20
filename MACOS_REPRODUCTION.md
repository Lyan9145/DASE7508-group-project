# Apple Silicon macOS reproduction

The reproduction uses the three committed SAC checkpoints and the frozen
experiment plan from merge commit `27884ec8ddb6975aef5072b9e7f20516b81fc0fa`.
The numerical runs use CPU inference. They reuse the reference seeds, so
they add cross-platform evidence for the same cases.

## Environment and tests

From the repository root on an Apple Silicon Mac, with [uv](https://docs.astral.sh/uv/getting-started/installation/)
installed:

```bash
uv venv --managed-python --python 3.12.14 .venv
uv pip install --python .venv/bin/python --only-binary :all: \
  -r github_upload/requirements.lock.txt -r github_upload/requirements-dev.txt
uv pip check --python .venv/bin/python
uv pip freeze --python .venv/bin/python

cd github_upload
py=../.venv/bin/python
run=$(mktemp -d "${TMPDIR:-/tmp}/dase7508-macos.XXXXXX")
printf 'Reproduction outputs: %s\n' "$run"
"$py" -m pytest -q test_security.py test_exploration.py
"$py" check_setup.py --no-render --out "$run/setup-numeric"
"$py" presentation_demo.py --scenario boundary --numeric-only --out "$run/boundary"
```

Run the separate offscreen rendering check from the macOS desktop session.
Clear any renderer setting inherited from a Linux setup.

```bash
env -u MUJOCO_GL "$py" check_setup.py --out "$run/setup-render"
```

## Full numerical runs and trace audits

From the same shell in `github_upload/`:

```bash
"$py" evaluate.py --phase main --plan main_plan.json --episodes 30 \
  --test-base 800000 --calibration-base 300000 \
  --models outputs/sac_seed_1_sync/model.zip outputs/sac_seed_2_sync/model.zip \
           outputs/sac_seed_3_sync/model.zip \
  --out "$run/main"
"$py" audit_results.py "$run/main" --output "$run/main-audit.json"

"$py" exploration.py --out "$run/exploration"
"$py" audit_exploration.py --run "$run/exploration/test" --out "$run/exploration-audit"
```

The full traces and run outputs stay in the temporary directory printed above.
The committed Windows reference tables are
[`reproduction_20261118_compatible_main/episodes.csv`](github_upload/outputs/reproduction_20261118_compatible_main/episodes.csv)
and [`exploratory_20261118_compatible/test/episodes.csv`](github_upload/outputs/exploratory_20261118_compatible/test/episodes.csv).

## Observed on November 20, 2026

| Component | Verified environment |
|---|---|
| macOS | 27.0.1 (26A434), arm64 |
| Python and installer | CPython 3.12.14, uv 0.13.9 |
| Simulation | MuJoCo 3.15.0, Gymnasium 1.4.0 |
| Inference | PyTorch 2.14.1 on CPU, Stable-Baselines3 2.9.0 |
| Numeric and test packages | NumPy 2.4.6, pytest 9.1.1 |

Dependency validation passed and all 16 tests passed. All three checkpoint
SHA-256 hashes matched their committed validation records. The numerical setup
check verified 100 steps at 20 ms per step. Maximum forward-kinematics error
was `6.94e-17 m`. The separate offscreen check produced a 480 × 480 RGB frame.
The rendering attempt in a restricted shell stalled at a macOS desktop service.
Running the same check with desktop access succeeded. The interactive viewer
was outside this check.

The four-mode boundary replay reproduced the reference outcomes. The clean,
unmonitored perturbation, and one-step-wait modes succeeded in 100 steps. The
original monitor aborted after 40 executed steps.

| Run and condition | Successful episodes | Aborts |
|---|---:|---:|
| Main, monitor off | 2,250 / 2,250 | 0 |
| Main, monitor on | 2,248 / 2,250 | 2 |
| Exploratory short cases, none | 1,080 / 1,080 | 0 |
| Exploratory short cases, original | 1,076 / 1,080 | 4 |
| Exploratory short cases, one-step wait | 1,080 / 1,080 | 0 |
| Exploratory sustained case, none | 90 / 90 | 0 |
| Exploratory sustained case, original | 17 / 90 | 73 |
| Exploratory sustained case, one-step wait | 17 / 90 | 73 |

The exploratory development run completed 1,008 episodes and selected the same
one-step wait as Windows. All three exploratory clean conditions were 90 / 90
successful. The held-out test completed 3,780 episodes, including the clean
conditions.

Both trace audits passed. The main audit checked 449,882 trace rows and the
held-out exploratory audit checked 369,446. The same 73 sustained cases aborted
under both monitored variants. The one-step wait delayed each abort by 20 ms.

I matched episodes to Windows by policy, seed, case, and monitor state or
defense variant. Across all 4,500 main and 3,780 held-out exploratory episodes,
task success, abort status, executed step count, alarm count, detection step
count, detection delay, missed-detection flag, and window coverage matched.
The exploratory alarm-step lists also matched. Floating-point results differed
slightly.

| Maximum absolute difference vs. Windows | Main | Exploratory test |
|---|---:|---:|
| Mean distance over the final ten steps | 1.43e-8 m | 1.31e-8 m |
| Terminal distance | 2.09e-8 m | 1.22e-8 m |
| Mean distance over the evaluation window | 8.75e-9 m | 7.13e-9 m |
| Control effort | 2.19e-7 | 1.62e-7 |
