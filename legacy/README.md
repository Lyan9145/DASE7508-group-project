# Archived Phase-1 and 2026-11-18 Scripts and Documentation

This directory archives historical Phase-1 experiment scripts, archived 2026-11-18 reproduction/acceptance/presentation assets, and historical reports so the repository root remains focused on active Phase-2 code.

Active development and Phase-2 experiments use only the 6 root CLI scripts (`check_setup.py`, `train.py`, `demo.py`, `run_matrix.py`, `run_ablation.py`, `plot_matrix.py`), `tests/test_framework.py`, and the top-level packages (`core/`, `attacks/`, `defenses/`, `evaluation/`).

## Directory Contents

- **`legacy/scripts/`** (19 scripts):
  - **Phase-1 evaluation and analysis**: `evaluate.py`, `audit_results.py`, `plot_results.py`, `plot_training.py`, `make_replay.py`, `inspect_failures.py`, `test_security.py`
  - **2026-11-18 exploratory bounded-wait study**: `exploration.py`, `audit_exploration.py`, `test_exploration.py`
  - **2026-11-18 reproduction, acceptance, packaging, and presentation helpers**: `build_deliverables.py`, `final_acceptance.py`, `finalize_deliverables.py`, `package_team.py`, `prepare_presentation.py`, `presentation_demo.py`, `reproduce_failure.py`, `verify_compatible.py`, `write_acceptance_report.py`
- **`legacy/docs/`** (13 archived Markdown reports and guides):
  `DEMO_GUIDE.md`, `FIGURE_GUIDE.md`, `FINAL_ACCEPTANCE.md`, `FINAL_RESULTS.md`, `PRESENTATION_PLAN.md`, `QA_PREP.md`, `REPRODUCTION_REPORT.md`, `RESULTS.md`, `SLIDES_CONTENT.md`, `SPEAKER_NOTES.md`, `TEAM_HANDOFF.md`, `UPLOAD_NOTES.md`, `WORK_LOG.md`
- **`legacy/main_plan.json`**: Frozen Phase-1 main experiment plan snapshot.

## Notes on Running Archived Code and Accessing Historical Outputs

- Archived scripts in `legacy/scripts/` retain their original top-level import paths (such as `security`, `reacher_env`, `evaluate`, `recovery_monitor`) and historical output path conventions as read-only snapshots. When inspecting or running an archived script unchanged from the repository root, pass `PYTHONPATH=legacy/scripts:core`.
- Historical Phase-1 `outputs/` directories were removed from this branch to keep the workspace clean and avoid duplicating large artifacts; those Phase-1 artifacts remain preserved on `main` and in Git history.
