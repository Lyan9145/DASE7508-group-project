# sensor-spoofing-new upload scope (2026-11-19)

This branch starts from codex/sensor-spoofing-pilot and adds the current local
reproduction, exploratory comparison, final acceptance and presentation work.
Existing models and historical experiment files are retained unchanged.

Included: current source/tests, compatible dependency lock, reports/slide text,
key episode CSVs, configurations, calibration, executed source snapshots,
hash/audit records, five presentation figures and four-mode GIF/HTML replay.

Not uploaded: .venv, caches, credentials, pytest scratch directories, extracted
package copies, intermediate document copy, course PDF/extracted requirements,
the generated distribution ZIP, or new full traces.jsonl.gz files (hundreds of MB).
Those full traces remain in the original local project. Existing historical
main_v1/pilot traces that were already tracked by the source branch remain tracked.

CSV/figure inspection and the fixed paired numerical demo work from this branch.
Full-trace re-audits of new experiments require the retained local original logs,
or rerunning the frozen evaluation into a NEW directory. Do not claim that this
branch alone contains every new raw trace. No independent new initial states are
created by rerunning the same seeds. See FINAL_ACCEPTANCE.md and TEAM_HANDOFF.md.

The older TEAM_HANDOFF wording 'local only / no upload' describes the earlier
packaging session. The user subsequently explicitly authorized this new branch
upload. The release ZIP itself remains local and can be rebuilt from source.
