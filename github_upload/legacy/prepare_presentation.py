"""Presentation figures from acceptance-derived compatible-run evidence only."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from final_acceptance import ROOT,OUT

def main():
    figures=OUT/'figures';figures.mkdir(exist_ok=False)
    t=pd.read_csv(OUT/'verified_episodes.csv');w=pd.read_csv(OUT/'window_rates.csv')
    records=json.loads((OUT/'selected_traces.json').read_text())
    chosen=[r for r in records if r['seed']==930000]
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for case,v,label in [('clean','none','Normal'),('bias_e0.1_s70','none','Attack, no defense'),('bias_e0.1_s70','original','Attack, original defense')]:
        g=[r for r in chosen if r['case']==case and r['variant']==v and r['truth_after']]
        x=[r['observation_step']+1 for r in g];y=[r['truth_after']['distance']*1000 for r in g]
        for ax in axes:ax.plot(x,y,label=label)
    axes[1].set_xlim(65,100);axes[1].set_ylim(8,13)
    for ax in axes:ax.axvspan(70,90,color='red',alpha=.1);ax.set(xlabel='Post-action state',ylabel='True target distance (mm)');ax.legend(fontsize=7)
    fig.suptitle('1. Predeclared first-state example: weak effects retained (policy 1, seed 930000)');fig.tight_layout();fig.savefig(figures/'01_trajectory.png',dpi=190);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for (kind,e),g in t[(t.variant=='none')&(t.duration==20)&(t.case!='clean')].groupby(['attack_kind','epsilon_rad']):
        z=g.groupby('attack_start');a=z.paired_window_delta_mm.mean();b=z.final_10_mean_distance_m.mean()*1000
        axes[0].plot(a.index,a.values,'o-',label=f'{kind}, {e:.2f} rad');axes[1].plot(b.index,b.values,'o-',label=f'{kind}, {e:.2f} rad')
    axes[0].set_ylabel('Paired window distance increase (mm)');axes[1].set_ylabel('Final ten-state mean distance (mm)')
    for ax in axes:ax.set_xlabel('Attack start (step)');ax.legend(fontsize=7)
    fig.suptitle('2. Timing changes errors; all 1,080 unprotected short-attack conditions succeed');fig.tight_layout();fig.savefig(figures/'02_timing.png',dpi=190);plt.close(fig)
    g=w[(w.variant=='original')&(w.case!='sustained')].copy();g['label']=g.case.str.replace('_e',' ').str.replace('_s',' / start ')
    fig,ax=plt.subplots(figsize=(11,4));x=np.arange(len(g));ax.bar(x-.18,g.normal_rate,.36,label='Matched normal window');ax.bar(x+.18,g.attack_observed_rate,.36,label='Attack window: observed alarm')
    ax.set_xticks(x,g.label,rotation=35,ha='right',fontsize=8);ax.set_ylabel('Windows with at least one alarm / 90');ax.legend(fontsize=8,loc='lower right');ax.set_title('3. Alarm rate exceeds matched background; alarms do not identify their cause')
    fig.tight_layout();fig.savefig(figures/'03_alarm_background.png',dpi=190);plt.close(fig)
    t['cohort']=np.where(t.case=='clean','Normal',np.where(t.case=='sustained','Sustained 40','Short attacks'))
    groups=[]
    for (c,v),g in t.groupby(['cohort','variant']):
        full=g[g.final_complete]
        groups.append(dict(cohort=c,variant=v,n=len(g),successes=int(g.task_success.sum()),aborts=int(g.aborted.sum()),corrections=g.alarm_count.mean(),complete_cost=full.control_effort.mean(),complete_angle=full.angle_mae_rad.mean()))
    groups=pd.DataFrame(groups);groups.to_csv(OUT/'presentation_cohorts.csv',index=False)
    fig,axes=plt.subplots(1,3,figsize=(12,4));cohorts=['Normal','Short attacks','Sustained 40']
    for i,(v,label) in enumerate([('none','No defense'),('original','Original'),('grace1','Wait +1')]):
        g=groups[groups.variant==v].set_index('cohort').loc[cohorts]
        for ax,col in zip(axes,['aborts','corrections','complete_angle']):ax.bar(np.arange(3)+(i-1)*.25,g[col],.25,label=label)
    for ax,y in zip(axes,['Abort count','Corrected observations / episode','Angle MAE, complete runs only (rad)']):ax.set_xticks(range(3),cohorts);ax.set_ylabel(y)
    axes[0].legend(fontsize=8);fig.suptitle('4. Normal n=90; short conditions n=1,080; sustained n=90 per method\nWait +1 avoids four short-case aborts; sustained response remains 73/90 aborts, 20 ms later',fontsize=10)
    fig.tight_layout();fig.savefig(figures/'04_defense_cost.png',dpi=190);plt.close(fig)
    abort=[r for r in records if r['seed']==802009 and r['monitor_on']]
    fig,axes=plt.subplots(2,1,figsize=(8,5),sharex=True)
    x=[r['observation_step'] for r in abort];axes[0].plot(x,[r['monitor']['residual_m']*1000 for r in abort],label='Reported residual')
    threshold=json.loads((ROOT/'outputs/reproduction_20261118_compatible_main/calibration.json').read_text())['sac_seed_3_sync']['threshold_m']
    axes[0].axhline(threshold*1000,color='red',ls='--',label='Frozen threshold');axes[0].set_ylabel('Residual (mm)');axes[0].legend(fontsize=8)
    axes[1].step(x,[r['monitor']['alarm_streak'] for r in abort],where='post');axes[1].axhline(20,color='red',ls='--');axes[1].set(xlabel='Observation step (20 ms/step)',ylabel='Consecutive alarms')
    for ax in axes:ax.axvspan(20,39.9,alpha=.1,color='orange');ax.axvline(40,color='black',ls=':')
    fig.suptitle('5. Selected historical boundary case: noise extends 20 attack alarms to 21\nPolicy 3, seed 802009; target distance at abort about 3.849 mm',fontsize=10)
    fig.tight_layout();fig.savefig(figures/'05_abort_case.png',dpi=190);plt.close(fig)
    print('Five presentation figures generated from newly audited compatible-run data')

if __name__=='__main__':main()
