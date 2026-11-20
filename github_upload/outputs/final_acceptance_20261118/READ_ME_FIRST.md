# Final acceptance and presentation evidence

This is the latest presentation evidence directory. Read repository-root
FINAL_ACCEPTANCE.md first, then PRESENTATION_PLAN.md, SLIDES_CONTENT.md,
SPEAKER_NOTES.md, QA_PREP.md, FIGURE_GUIDE.md, DEMO_GUIDE.md and TEAM_HANDOFF.md.

- acceptance.json: independent raw-log checks,3780 exploratory and4500 main episodes.
- acceptance_retry.log: successful full acceptance execution; acceptance.log retains the first verifier implementation error (index columns were dropped), not an experiment failure.
- protected_before.json / protected_after.json: before/after hashes of original models, frozen sources and historical/new raw experiment directories. No raw data overwritten.
- verified_episodes.csv: compatible test rows rechecked against every trace, complete-only final distance and alarm-only prediction error added.
- four_failures.csv: all four original short-attack aborts, four distinct paired states, two policies. Each state still repeats across12 conditions.
- short_totals.csv:1080/1076/1080 successes for none/original/wait+1.
- sustained_pairs.csv:73 paired sustained aborts, exactly+1 step/+20ms.
- false_alarms.csv: new clean rates89/8910 step and54/90 episode; no duplication across settings.
- paired_windows.csv / window_rates.csv: one window per state/condition, matched clean baseline, observed alarms, conditional delay and censored exposure. Unobserved suffixes are not clean samples.
- seed_inventory.json: disjoint evaluation blocks; calibration is intentionally shared by development/test as a fixed threshold source.
- figures/: five newly generated figures, all from compatible-run data. Details in FIGURE_GUIDE.md.
- selected_traces.json: predeclared first-state example plus known historical abort for plotting.
- demo_boundary_v2/: four-mode paired numerical runs plus MuJoCo GIF/HTML replay and static screenshots. It is a selected case, not average performance. Truth is evaluation/display only.
- demo_representative_numeric/: four numeric modes for the predeclared first-state case.
- course_sources.json and extracted course .txt: read actual requirements; dates/submission details still require Moodle.
- documents_before/: pre-acceptance versions of edited reports/plan, retained for provenance.
- same_machine_package_check.json: package integrity and numerical smoke check on this computer only. No second-computer claim.

Full original logs remain outside the lightweight team package:
github_upload/outputs/reproduction_20261118_compatible_main/traces.jsonl.gz and
github_upload/outputs/exploratory_20261118_compatible/test/traces.jsonl.gz.
Historical main_v1 and first environment-investigation runs remain intact.

Pending: group-confirmed actual contributions, human browser/projector check,
timed five-person rehearsal, optional70s desktop recording, second-member/second
computer verification, and Moodle date/format checks. No MP4 generated.
