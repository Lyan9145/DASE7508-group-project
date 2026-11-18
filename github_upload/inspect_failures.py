"""Extract and plot aborted/failed main-study trials without changing the study."""
import argparse
import csv
import gzip
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('run',type=Path)
    args=parser.parse_args()
    with (args.run/'episodes.csv').open() as file:
        failures=[r for r in csv.DictReader(file) if r['task_success']=='False']
    keys={(r['policy'],r['case'],r['monitor_on']=='True',int(r['seed'])) for r in failures}
    traces={key:[] for key in keys}
    with gzip.open(args.run/'traces.jsonl.gz','rt') as file:
        for line in file:
            row=json.loads(line)
            key=(row['policy'],row['case'],row['monitor_on'],row['seed'])
            if key in keys: traces[key].append(row)
    cal=json.loads((args.run/'calibration.json').read_text())
    findings=[]
    for index,(identity,rows) in enumerate(traces.items()):
        last=rows[-1]
        attack_start=next(r['observation_step'] for r in rows if r['delta_rad']!=0)
        attacked=[r['observation_step'] for r in rows if r['delta_rad']!=0]
        streak_start=last['observation_step']-last['monitor']['alarm_streak']+1
        finding={'policy':identity[0],'case':identity[1],'monitor_on':identity[2],'seed':identity[3],
                 'abort':last['monitor']['abort'],'abort_step':last['observation_step'],
                 'alarm_streak':last['monitor']['alarm_streak'],
                 'streak_start':streak_start,
                 'injected_delta_at_abort_rad':last['delta_rad'],
                 'true_distance_at_abort_m':last['truth_before']['distance'],
                 'alarm_steps_without_injection_in_streak':[r['observation_step'] for r in rows if
                     r['observation_step']>=streak_start and r['delta_rad']==0 and r['monitor']['alarm']]}
        findings.append(finding)
        fig,axes=plt.subplots(3,1,figsize=(9,7),sharex=True,constrained_layout=True)
        t=[r['observation_step'] for r in rows]
        axes[0].plot(t,[r['truth_before']['distance']*100 for r in rows])
        axes[0].axhline(3,color='grey',ls='--',label='Task distance threshold')
        axes[0].set_ylabel('True distance (cm)'); axes[0].legend(fontsize=8)
        axes[1].plot(t,[r['monitor']['residual_m']*1000 for r in rows],label='Reported residual')
        axes[1].axhline(cal[identity[0]]['threshold_m']*1000,color='black',ls='--',label='Frozen threshold')
        alarms=[r for r in rows if r['monitor']['alarm']]
        axes[1].scatter([r['observation_step'] for r in alarms],
                        [r['monitor']['residual_m']*1000 for r in alarms],c='red',s=15)
        axes[1].set_ylabel('Residual (mm)'); axes[1].legend(fontsize=8)
        axes[2].step(t,[r['delta_rad'] for r in rows],where='post')
        axes[2].set_ylabel('Injected offset (rad)'); axes[2].set_xlabel('Observation step')
        for ax in axes:
            ax.axvspan(attack_start,max(attacked)+1,color='orange',alpha=.12)
            ax.axvline(last['observation_step'],color='red',ls=':',label='Abort')
            ax.grid(alpha=.2)
        fig.suptitle(f'{identity[0]}, seed {identity[3]}: {identity[1]} — {last["monitor"]["alarm_streak"]} alarms')
        fig.savefig(args.run/'figures'/f'abort_case_{index+1}.png',dpi=170)
        plt.close(fig)
    (args.run/'failure_analysis.json').write_text(json.dumps(findings,indent=2))
    print(json.dumps(findings,indent=2))


if __name__=='__main__':
    main()
