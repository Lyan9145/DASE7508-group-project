# Five-Speaker 12-Minute Presentation Plan

Based on official course guidelines (`12 min` presentation including demo + `3 min` Q&A; `8/20` grade weight). Required elements: background, motivation, contributions, threat model, insights, architecture, evaluation, limitations, future work, takeaways, member credits, and AI disclosure.

Body timing: `11 min = 660 s` (`132 s` per speaker across 5 speakers) + `4 x 10 s = 40 s` speaker transitions + `20 s` buffer = `12 min`. Speaker labels `A–E` denote presentation roles only, not authorship assignments. Ten main slides are used, with full condition tables and credits in backup slides. Actual pacing requires a timed five-person rehearsal.

| Slide | Speaker | Body Time | Core Message & Evidence |
|---|---|---|---|
| 1 | A | 66s | Research question, motivation, normal workflow |
| 2 | A | 66s | System and trust boundaries; protected position/velocity assumptions; architecture diagram |
| 3 | B | 66s | `bias`/`ramp`/random-sign controls; what was reused vs. newly added |
| 4 | B | 66s | Timing experiment and weak terminal effects; Figures `01`/`02` |
| 5 | C | 66s | Kinematic residual, calibration, and angle prediction; alarm != attribution |
| 6 | C | 66s | Original 21-alarm abort vs. Wait+1 22-alarm abort; dev tie-break `15/15 -> 1`; Figure `05` |
| 7 | D | 66s | Paired design, 90 states, success criteria, main reproduction (`2250/2248`) |
| 8 | D | 66s | Figures `03`/`04`; short `1080/1076/1080`; sustained `73/90` (`+20 ms`); clean `89/8910` & `54/90` |
| 9 | E | 75s | Selected historical boundary case 4-mode annotated replay (`seed 802009`, not average) |
| 10 | E | 57s | Limitations, future evaluation plan, takeaways, AI & member credits |

Transitions occur after Slides 2, 4, 6, and 8 (`10 s` each). Slide timing aligns with [SPEAKER_NOTES.md](SPEAKER_NOTES.md) (demo included in Speaker E's time), followed by `3 min` Q&A ([QA_PREP.md](QA_PREP.md)).

Rubric mapping: motivation/threat model (`1 pt` -> Slides 1–2); insights/contributions/design (`2 pts` -> Slides 3, 5–6); evaluation evidence (`2 pts` -> Slides 4, 7–9); clarity & pacing (`1 pt` -> readable figures & timing); Q&A/reflection (`1.5 pts` -> Slide 10 & Q&A); credits (`0.5 pts` -> Slides 3, 10 & Backup). Verify submission dates, speaking order, slide deadlines, and final report format on Moodle.

| Work Component | Confirmed Source | Member Authorship / Review Evidence |
|---|---|---|
| MuJoCo, Gymnasium, SAC/SB3 | Upstream libraries & papers | Not claimed as original algorithms |
| Baseline models, attacks, original monitor, `main_v1` | Baseline group repo & execution snapshots | Confirm with group; Proposal roles are not proof of actual authorship |
| Windows reproduction, timing study, Wait+1, audits | 2026-11-18 integration round (Codex-assisted) | Confirm manual review/integration members |
| Acceptance recomputation, annotated demo, slide drafts | 2026-11-18 acceptance round (Codex-assisted) | Record each member's review & rehearsal sign-off |

Preparation reading: all members read [FINAL_ACCEPTANCE.md](FINAL_ACCEPTANCE.md) and [QA_PREP.md](QA_PREP.md). Speaker A focuses on threat model; B on attack code & Figures `01`/`02`; C on `security.py` / `recovery_monitor.py` & Figure `05`; D on denominators, truncation, & cost tables; E on [DEMO_GUIDE.md](DEMO_GUIDE.md) and static fallbacks.

AI disclosure statement for slides: Codex assisted with code inspection, environment troubleshooting, experiment execution, trace auditing, figure generation, and draft preparation; team members independently verify and explain all findings without fabricating authors, successful attacks, or unverified claims.
