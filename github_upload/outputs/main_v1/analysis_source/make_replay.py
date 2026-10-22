"""Replay logged physical states and policy-observed geometry; no new trials."""
import argparse
import gzip
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
import numpy as np

from security import ArmGeometry, rotation


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path)
    args=parser.parse_args()
    config=json.loads((args.run/'config.json').read_text())
    policy=Path(config['models'][0]).parent.name
    calibration=json.loads((args.run/'calibration.json').read_text())[policy]
    geometry=ArmGeometry(*(np.array(calibration['geometry'][k]) for k in ('origin','link','tip')))
    seed=config['test_base']
    keys=[('clean',False),('bias_e0.1_d20',False),('bias_e0.1_d20',True)]
    groups={key:[] for key in keys}
    with gzip.open(args.run/'traces.jsonl.gz','rt') as file:
        for line in file:
            row=json.loads(line); key=(row['case'],row['monitor_on'])
            if row['policy']==policy and row['seed']==seed and key in groups:
                groups[key].append(row)
    if any(not groups[key] for key in keys):
        raise ValueError('Replay requires clean and bias_e0.1_d20 off/on traces')
    fig,axes=plt.subplots(1,3,figsize=(11,4),constrained_layout=True)
    artists=[]
    for ax,title,key in zip(axes,['Clean','Bias 0.1 rad','Bias + mitigation'],keys):
        ax.set_aspect('equal'); ax.set_xlim(-.24,.24); ax.set_ylim(-.24,.24)
        ax.set_xlabel('x (m)'); ax.set_ylabel('y (m)'); ax.grid(alpha=.2)
        ax.set_title(title)
        physical,=ax.plot([],[],'o-',lw=3,color='#1565c0',label='Physical arm')
        perceived,=ax.plot([],[],'--',lw=2,color='#ef6c00',label='Policy-observed angles')
        target=groups[key][0]['truth_before']['target']
        ax.scatter(*target,marker='x',c='red',s=70,label='Target')
        note=ax.text(.03,.97,'',transform=ax.transAxes,va='top',fontsize=8)
        artists.append((physical,perceived,note))
    axes[0].legend(fontsize=7,loc='lower left')
    title=fig.suptitle('')
    def points(q):
        return np.array([geometry.origin, geometry.origin+rotation(q[0])@geometry.link,
                         geometry.forward(*q)])
    def frame(t):
        title.set_text(f'Logged trace replay — {policy}, seed {seed}, observation {t}')
        for key,(physical,perceived,note) in zip(keys,artists):
            row=groups[key][min(t,len(groups[key])-1)]
            actual=points(row['truth_before']['angles'])
            obs=np.array(row['policy_sensor'])
            inferred=points(np.arctan2(obs[2:4],obs[:2]))
            physical.set_data(actual[:,0],actual[:,1])
            perceived.set_data(inferred[:,0],inferred[:,1])
            alarm=row['monitor']['alarm'] if row['monitor'] else False
            aborted = bool(row['monitor'] and row['monitor']['abort'])
            note.set_text(f'Injected offset: {row["delta_rad"]:+.3f} rad\nAlarm: {alarm}' +
                          (f'\nABORTED at step {row["observation_step"]}' if aborted else ''))
        return [title]+[artist for group in artists for artist in group]
    out=args.run/'figures'; out.mkdir(exist_ok=True)
    frame(30); fig.savefig(out/'arm_comparison.png',dpi=170)
    animation=FuncAnimation(fig,frame,frames=range(0,100,2),interval=80,blit=False)
    animation.save(out/'arm_replay.gif',writer=PillowWriter(fps=12))
    plt.close(fig)
    print(f'Trace replay written to {out}')


if __name__=='__main__':
    main()
