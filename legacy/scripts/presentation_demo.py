"""Fixed paired numerical runs and annotated MuJoCo replay; truth is display-only."""
import argparse
import functools
import gzip
import hashlib
import io
import json
from pathlib import Path
import time
import numpy as np
import torch
import mujoco
from PIL import Image, ImageDraw, ImageFont
from stable_baselines3 import SAC
from evaluate import trial, write_json, write_csv
from reacher_env import make_env
from security import Attack, ArmGeometry, KinematicMonitor
from recovery_monitor import RecoveryMonitor

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--scenario',choices=['boundary','representative'],default='boundary')
    parser.add_argument('--mode',choices=['all','normal','attack','original','improved'],default='all')
    parser.add_argument('--numeric-only',action='store_true')
    parser.add_argument('--open',action='store_true',help='Open generated local replay in default browser')
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    boundary=args.scenario=='boundary'; policy='sac_seed_3_sync' if boundary else 'sac_seed_1_sync'
    seed=802009 if boundary else 930000; start=20 if boundary else 70; sign=-1 if boundary else 1
    run=ROOT/'outputs'/('reproduction_20261118_compatible_main' if boundary else 'exploratory_20261118_compatible/test')
    threshold=json.loads((run/'calibration.json').read_text())[policy]['threshold_m']
    path=ROOT/'outputs'/policy/'model.zip';torch.set_num_threads(1)
    model=SAC.load(path,device='cpu');env=make_env();geometry=ArmGeometry.from_model(env.unwrapped.model)
    config=dict(scenario=args.scenario,policy=policy,seed=seed,noise_seed=seed+10000000,start=start,duration=20,
                epsilon_rad=.1,sign=sign,threshold_m=threshold,dt_seconds=env.unwrapped.dt,
                model_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),calibration_source=str(run/'calibration.json'),
                selected_case='Known historical boundary failure; not representative of average effect' if boundary else 'First policy and first new test state, largest declared bias, latest start',
                truth_usage='Evaluator/display only; never supplied to model.predict or monitor.process',
                rendering='Separate render environment after numeric trajectories are fixed; GIF is a slowed simulator replay, not desktop video')
    write_json(args.out/'config.json',config)
    source=args.out/'source';source.mkdir()
    for name in ['presentation_demo.py','evaluate.py','security.py','recovery_monitor.py','reacher_env.py']:(source/name).write_bytes((ROOT/name).read_bytes())
    modes=['normal','attack','original','improved'] if args.mode=='all' else [args.mode]
    groups={};metrics=[]
    with gzip.open(args.out/'traces.jsonl.gz','wt',encoding='utf-8') as file:
        for mode in modes:
            attack=Attack('clean') if mode=='normal' else Attack('bias',.1,20,start,sign,seed+20000000)
            sink=io.StringIO();factory=functools.partial(RecoveryMonitor,grace=1) if mode=='improved' else KinematicMonitor
            row=trial(model,env,geometry,threshold,attack,mode in ['original','improved'],seed,sink,policy,mode,monitor_factory=factory)
            row.pop('_distances');row['mode']=mode;metrics.append(row)
            groups[mode]=[json.loads(line) for line in sink.getvalue().splitlines()]
            for r in groups[mode]:file.write(json.dumps(r)+'\n')
    env.close();write_csv(args.out/'episodes.csv',metrics)
    if not args.numeric_only:
        render=make_env(render_mode='rgb_array');render.reset(seed=seed)
        base=render.unwrapped;frames=[]
        try:
            font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
        except OSError:
            try:font=ImageFont.truetype('DejaVuSans.ttf',18)
            except OSError:font=ImageFont.load_default(size=18)
        # GIF samples every 2 observations; all numeric observations remain in logs.
        for t in range(0,101,2):
            canvas=Image.new('RGB',(480*len(modes),680),'white');draw=ImageDraw.Draw(canvas)
            draw.text((10,8),'SELECTED BOUNDARY CASE - not average effect' if boundary else 'PREDECLARED FIRST-STATE EXAMPLE - weak effects retained',fill='black',font=font)
            for j,mode in enumerate(modes):
                records=groups[mode];r=records[min(t,len(records)-1)];truth=r['truth_before'];s=r['monitor']
                base.data.qpos[:2]=truth['angles'];base.data.qpos[2:4]=truth['target'];base.data.qvel[:]=0
                mujoco.mj_forward(base.model,base.data)
                frame=Image.fromarray(render.render()).resize((480,480));canvas.paste(frame,(j*480,190))
                aborted=bool(s and s['abort']);held=t>=len(records) and aborted
                lines=[mode.upper(),f't={r["observation_step"]*.02:.2f}s  step={r["observation_step"]}',
                       f'Attack window [{start},{start+20})  injected={r["delta_rad"]:+.3f} rad',
                       f'True distance={truth["distance"]*1000:.3f} mm (display only)',
                       f'Alarm={s["alarm"] if s else "OFF"}  streak={s["alarm_streak"] if s else "N/A"}',
                       f'Abort={aborted}'+(' / frozen' if held else '')]
                for k,line in enumerate(lines):draw.text((j*480+8,40+k*23),line,fill='red' if aborted and k==5 else 'black',font=font)
            frames.append(canvas)
        render.close()
        frames[0].save(args.out/'comparison.gif',save_all=True,append_images=frames[1:],duration=160,loop=0)
        frames[20].save(args.out/'boundary_step40.png');frames[15].save(args.out/'attack_step30.png')
        html='''<!doctype html><meta charset="utf-8"><title>Paired sensor spoofing demo</title><style>body{font:18px sans-serif;margin:24px}img{width:100%}button{font-size:18px}</style><h1>Fixed paired simulator replay</h1><p>Truth is shown for evaluation only. GIF uses slowed playback; displayed time is simulation time. Aborted trajectories freeze. This selected example does not establish average benefit.</p><button onclick="document.querySelector('img').src='comparison.gif?'+Date.now()">Restart replay</button><img src="comparison.gif"><p>Numeric records: episodes.csv, config.json, traces.jsonl.gz. This is a generated simulator replay, not a screen recording.</p>'''
        (args.out/'replay.html').write_text(html,encoding='utf-8')
        if args.open:
            import webbrowser
            webbrowser.open((args.out/'replay.html').resolve().as_uri())
    write_json(args.out/'run_status.json',dict(complete=True,rendered=not args.numeric_only,desktop_video_generated=False))
    print(json.dumps(metrics,indent=2))

if __name__=='__main__':main()
