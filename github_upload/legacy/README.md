# Archived Phase-1 and 2026-11-18 Scripts

This directory archives the historical Phase-1 experiment scripts and the 2026-11-18 reproduction, acceptance, packaging, and presentation generation scripts so the top-level `github_upload/` workspace remains clean.

Active development and Phase-2 experiments use only the 7 top-level scripts in `github_upload/` (`check_setup.py`, `train.py`, `demo.py`, `run_matrix.py`, `run_ablation.py`, `plot_matrix.py`, `test_framework.py`) and the `github_upload/framework/` package.

## Archived Files

- **Phase-1 evaluation & analysis**: `evaluate.py`, `audit_results.py`, `plot_results.py`, `plot_training.py`, `make_replay.py`, `inspect_failures.py`, `test_security.py`
- **2026-11-18 exploratory wait-rule study**: `exploration.py`, `audit_exploration.py`, `test_exploration.py`
- **2026-11-18 reproduction, acceptance & presentation helpers**: `build_deliverables.py`, `final_acceptance.py`, `finalize_deliverables.py`, `package_team.py`, `prepare_presentation.py`, `presentation_demo.py`, `reproduce_failure.py`, `verify_compatible.py`, `write_acceptance_report.py`

> Note: These archived scripts retain their original top-level import paths (such as `security`, `reacher_env`, `evaluate`, `recovery_monitor`) and hardcoded 2026-11-18 run paths as historical snapshots. To run an archived script unchanged, include `github_upload/legacy` and `github_upload/framework/core` on `PYTHONPATH` from `github_upload/`. Historical frozen outputs under `github_upload/outputs/` remain unmodified.
