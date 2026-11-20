"""Build an explicit allowlist package; excludes environments, caches and full traces."""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
from final_acceptance import ROOT,OUT

def main():
    dest=ROOT.parent/'deliverables';dest.mkdir(exist_ok=True)
    bundle=dest/'DASE7508_team_handoff_20261118';bundle.mkdir(exist_ok=False)
    paths=[]
    paths+=list(ROOT.glob('*.py'))
    paths+=[ROOT/n for n in ['environment-windows-mp1.lock.txt','main_plan.json','PROTOCOL.md','ANALYSIS_NOTES.md']]
    paths+=[ROOT.parent/n for n in ['README.md','REPRODUCTION_REPORT.md','FINAL_RESULTS.md','FINAL_ACCEPTANCE.md','PRESENTATION_PLAN.md','SLIDES_CONTENT.md','SPEAKER_NOTES.md','QA_PREP.md','FIGURE_GUIDE.md','DEMO_GUIDE.md','TEAM_HANDOFF.md','DASE7508_Proposal_2.0.md','proposal_reference_exact_diagram.png','proposal_reference_exact_diagram.svg']]
    for name in ['sac_seed_1_sync','sac_seed_2_sync','sac_seed_3_sync']:
        paths += [ROOT/'outputs'/name/n for n in ['model.zip','validation.json']]
    for name in ['reproduction_20261118_compatible_main','exploratory_20261118_compatible/test','exploratory_20261118_compatible/development']:
        folder=ROOT/'outputs'/name
        paths += [folder/n for n in ['config.json','calibration.json','episodes.csv','run_status.json']]
        paths += list((folder/'source').glob('*'))
    paths += [ROOT/'outputs/exploratory_20261118_compatible'/n for n in ['preregistered_plan.json','frozen_selection.json']]
    paths += list(OUT.glob('*.csv'))+list(OUT.glob('*.json'))+list(OUT.glob('*.md'))+list(OUT.glob('*.txt'))+list((OUT/'figures').glob('*.png'))
    # Preserve immutable evidence index hashes, but never add full raw trace content.
    paths += [OUT/'demo_boundary_v2'/n for n in ['config.json','episodes.csv','run_status.json','comparison.gif','replay.html','boundary_step40.png','attack_step30.png']]
    manifest=[]
    for p in sorted(set(paths)):
        relative=p.relative_to(ROOT.parent)
        target=bundle/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
        manifest.append(dict(path=relative.as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    (bundle/'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    archive=dest/'DASE7508_team_handoff_20261118.zip'
    if archive.exists():raise FileExistsError(archive)
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for p in bundle.rglob('*'):
            if p.is_file():z.write(p,p.relative_to(bundle))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert not any(n.endswith('traces.jsonl.gz') or any(part in ['.venv','.uv-cache','.aws','.codex','.git'] for part in Path(n).parts) for n in z.namelist())
    print(json.dumps(dict(archive=str(archive),files=len(manifest),bytes=archive.stat().st_size),indent=2))

if __name__=='__main__':main()
