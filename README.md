# DASE7508-group-project

Group 9: joint-angle sensor spoofing and kinematic mitigation for a simulated reinforcement-learning robotic arm (`Reacher-v5` + SAC).

## Quick Navigation

- **Phase-2 Unified Extension Framework (Active)**: [github_upload/FRAMEWORK_GUIDE.md](github_upload/FRAMEWORK_GUIDE.md) — plugin interface contract for attacks, defenses, matrix evaluation, Direction 4A noise ablations, and teammate tasks.
- **Installation, Training & CLI Usage**: [github_upload/README.md](github_upload/README.md)
- **Proposal & Frozen Phase-1 Protocol**: [DASE7508_Proposal_2.0.md](DASE7508_Proposal_2.0.md), [github_upload/PROTOCOL.md](github_upload/PROTOCOL.md), [github_upload/ANALYSIS_NOTES.md](github_upload/ANALYSIS_NOTES.md)
- **Archived Phase-1 & 2026-11-18 Reports**:
  - [RESULTS.md](RESULTS.md) — Phase-1 3-policy 4,500-trial summary (`outputs/main_v1/`)
  - [WORK_LOG.md](WORK_LOG.md) — integration and audit work log
  - [REPRODUCTION_REPORT.md](REPRODUCTION_REPORT.md), [FINAL_RESULTS.md](FINAL_RESULTS.md), [FINAL_ACCEPTANCE.md](FINAL_ACCEPTANCE.md) — 2026-11-18 Windows reproduction and bounded-wait (`grace1`) study
  - [PRESENTATION_PLAN.md](PRESENTATION_PLAN.md), [SLIDES_CONTENT.md](SLIDES_CONTENT.md), [SPEAKER_NOTES.md](SPEAKER_NOTES.md), [QA_PREP.md](QA_PREP.md), [FIGURE_GUIDE.md](FIGURE_GUIDE.md), [DEMO_GUIDE.md](DEMO_GUIDE.md), [TEAM_HANDOFF.md](TEAM_HANDOFF.md), [UPLOAD_NOTES.md](UPLOAD_NOTES.md)

## Quick Start (Active Phase-2 Workspace)

All executable code resides in `github_upload/` (archived Phase-1 and 2026-11-18 one-off scripts are kept under `github_upload/legacy/`, and frozen experiment artifacts under `github_upload/outputs/` remain untouched):

```bash
cd github_upload
python -m pytest -q test_framework.py
python check_setup.py --no-render --out outputs/setup_check_001
python run_matrix.py --preset smoke --out outputs/phase2_matrix_smoke_001
python plot_matrix.py outputs/phase2_matrix_smoke_001
python run_ablation.py --mode both --preset smoke --out outputs/phase2_ablation_smoke_001
python plot_matrix.py outputs/phase2_ablation_smoke_001
```
