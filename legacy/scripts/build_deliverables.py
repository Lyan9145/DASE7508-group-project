"""Derive review tables, figures and reports from completed runs; no simulation."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from evaluate import write_json

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'outputs/reproduction_20261118_materials'


def read(run):
    return pd.read_csv(ROOT/'outputs'/run/'episodes.csv')


def md(frame):
    # Avoid an optional tabulate dependency.
    return '| '+' | '.join(frame.columns)+' |\n|'+ '|'.join(['---']*len(frame.columns))+'|\n'+ '\n'.join('| '+' | '.join(str(v) for v in row)+' |' for row in frame.itertuples(index=False,name=None))


def capture(run, predicate):
    records=[]
    with gzip.open(ROOT/'outputs'/run/'traces.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            r=json.loads(line)
            if predicate(r): records.append(r)
    return records


def main():
    OUT.mkdir(exist_ok=False)
    import importlib.metadata as im
    env=dict(python=sys.version,executable=sys.executable,base_prefix=sys.base_prefix,
             platform=platform.platform(),cpu=os.environ.get('PROCESSOR_IDENTIFIER'),logical_cpus=os.cpu_count(),
             packages={p:im.version(p) for p in ['torch','numpy','mujoco','gymnasium','stable-baselines3','pytest','matplotlib','pandas']})
    write_json(OUT/'environment.json',env)
    (ROOT/'environment-windows-mp1.lock.txt').write_text('\n'.join(f'{k}=={v}' for k,v in env['packages'].items())+'\n',encoding='utf-8')
    h=read('main_v1'); r=read('reproduction_20261118_main'); t=read('exploratory_20261118/test')
    keys=['policy','case','monitor_on','seed']
    joined=h.merge(r,on=keys,suffixes=('_history','_local'),validate='one_to_one')
    comparison=[]
    for col in ['task_success','aborted','steps','alarm_count','final_10_mean_distance_m','terminal_distance_m','window_mean_distance_m','control_effort']:
        a,b=joined[col+'_history'],joined[col+'_local']
        comparison.append(dict(metric=col,unequal=int((a!=b).sum()),max_abs_difference=float(np.max(np.abs(a.astype(float)-b.astype(float))))))
    comparison=pd.DataFrame(comparison); comparison.to_csv(OUT/'reproduction_comparison.csv',index=False)
    manifest=json.loads((ROOT/'outputs/main_v1/config.json').read_text())
    hashes={Path(p).parent.name:(hashlib.sha256((ROOT/'outputs'/Path(p).parent.name/'model.zip').read_bytes()).hexdigest()==v) for p,v in manifest['model_sha256'].items()}
    write_json(OUT/'model_hash_check.json',hashes)
    # Recompute success and false alarms from episodes, never trust written prose.
    totals=[]
    for label,frame in [('historical',h),('local',r)]:
        for defense,g in frame.groupby('monitor_on'):
            totals.append(dict(dataset=label,defense=defense,successes=int(g.task_success.sum()),episodes=len(g),aborts=int(g.aborted.sum())))
    totals=pd.DataFrame(totals); totals.to_csv(OUT/'reproduction_totals.csv',index=False)
    failures=r[r.aborted]; failures.to_csv(OUT/'local_failures.csv',index=False)
    c=h[(h.case=='clean') & h.monitor_on]
    fp=dict(step_rate=float(c.alarm_count.sum()/c.detection_steps.sum()),episode_alarms=int(c.any_alarm.sum()),episodes=len(c))
    write_json(OUT/'historical_false_alarms.json',fp)
    historical_clean=capture('main_v1',lambda a:a['case']=='clean' and a['monitor_on'])
    normal_alarms={}
    for a in historical_clean:
        if a['monitor']['alarm']:
            normal_alarms.setdefault((a['policy'],a['seed']),[]).append(a['observation_step'])
    hw=[]
    for _,a in h[(h.case!='clean') & h.monitor_on].iterrows():
        normal=any(a.attack_start<=s<a.attack_start+a.duration for s in normal_alarms.get((a.policy,a.seed),[]))
        attacked=bool(pd.notna(a.detection_delay_steps))
        hw.append(dict(policy=a.policy,seed=a.seed,case=a.case,normal_alarm=normal,attack_alarm=attacked,difference=int(attacked)-int(normal),delay_steps=a.detection_delay_steps))
    hw=pd.DataFrame(hw)
    hw.groupby('case').agg(normal_window_rate=('normal_alarm','mean'),attack_window_rate=('attack_alarm','mean'),paired_difference=('difference','mean'),delay_steps=('delay_steps','mean')).to_csv(OUT/'historical_window_background.csv')
    new_clean=t[t.case=='clean'].groupby(['policy','variant']).agg(episodes=('seed','size'),alarms=('alarm_count','sum'),opportunities=('detection_steps','sum'),episodes_with_alarm=('any_alarm','sum')).reset_index()
    new_clean['step_false_alarm_rate']=new_clean.alarms/new_clean.opportunities
    new_clean['episode_false_alarm_rate']=new_clean.episodes_with_alarm/new_clean.episodes
    new_clean.to_csv(OUT/'new_clean_false_alarms.csv',index=False)
    summary=[]; windows=[]
    # Keep each initial state as one unit in each condition. Pool policies only descriptively.
    for (policy,case,variant),g in t.groupby(['policy','case','variant']):
        complete=g[g.final_complete]
        summary.append(dict(policy=policy,case=case,variant=variant,n=len(g),successes=int(g.task_success.sum()),aborts=int(g.aborted.sum()),incomplete=int((~g.final_complete).sum()),
                            final_mean_mm=float(complete.final_10_mean_distance_m.mean()) if len(complete) else None,
                            window_delta_mm=float(g[g.window_complete].paired_window_delta_mm.mean()) if g.window_complete.any() else None,
                            action_cost_mean=float(g.control_effort.mean()),alarm_steps_mean=float(g.alarm_count.mean()),angle_mae_rad=float(g.angle_mae_rad.mean()),
                            delay_steps=float(g.detection_delay_steps.mean()) if g.detection_delay_steps.notna().any() else None,
                            delay_ms=float(g.detection_delay_steps.mean()*20) if g.detection_delay_steps.notna().any() else None,
                            misses=int(g.missed_detection.sum())))
    summary=pd.DataFrame(summary); summary.to_csv(OUT/'per_policy_results.csv',index=False)
    clean=t[t.case=='clean'].set_index(['policy','seed','variant'])
    for _,row in t[(t.case!='clean') & (t.variant!='none')].iterrows():
        baseline=clean.loc[(row.policy,row.seed,row.variant)]
        start,end=int(row.attack_start),int(row.attack_start+row.duration)
        normal=[x for x in json.loads(baseline.alarm_steps_json) if start<=x<end]
        attacked=[x for x in json.loads(row.alarm_steps_json) if start<=x<end]
        windows.append(dict(policy=row.policy,seed=row.seed,case=row.case,variant=row.variant,start=start,
                            normal_alarm=bool(normal),attack_alarm=bool(attacked),difference=int(bool(attacked))-int(bool(normal)),
                            delay_steps=attacked[0]-start if attacked else None,delay_ms=(attacked[0]-start)*20 if attacked else None,
                            no_window_alarm=not attacked,window_complete=row.steps>=end))
    w=pd.DataFrame(windows); w.to_csv(OUT/'paired_windows.csv',index=False)
    window_summary=w.groupby(['case','variant']).agg(n=('seed','size'),normal_rate=('normal_alarm','mean'),attack_rate=('attack_alarm','mean'),paired_difference=('difference','mean'),no_alarm_rate=('no_window_alarm','mean'),delay_steps=('delay_steps','mean'),delay_ms=('delay_ms','mean'),complete_windows=('window_complete','sum')).reset_index()
    # Stratified paired-state bootstrap within each policy; no time-step resampling.
    rng=np.random.default_rng(7508)
    for idx,row in window_summary.iterrows():
        g=w[(w.case==row['case'])&(w.variant==row['variant'])]
        arrays=[v.difference.to_numpy() for _,v in g.groupby('policy')]
        means=np.mean([rng.choice(a,(2000,len(a)),replace=True).mean(axis=1) for a in arrays],axis=0)
        window_summary.loc[idx,'difference_ci_low'],window_summary.loc[idx,'difference_ci_high']=np.quantile(means,[.025,.975])
    window_summary.to_csv(OUT/'window_alarm_summary.csv',index=False)
    agg=t.groupby(['case','variant']).agg(n=('seed','size'),successes=('task_success','sum'),aborts=('aborted','sum'),incomplete=('final_complete',lambda x:(~x).sum()),angle_mae_rad=('angle_mae_rad','mean'),action_cost=('control_effort','mean'),alarm_steps=('alarm_count','mean')).reset_index()
    finals=t[t.final_complete].groupby(['case','variant']).final_10_mean_distance_m.mean().mul(1000).rename('complete_final_mm').reset_index()
    agg=agg.merge(finals,on=['case','variant'],how='left'); agg.to_csv(OUT/'aggregate_results.csv',index=False)
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for (kind,eps),g in t[(t.variant=='none') & (t.case!='sustained') & (t.case!='clean')].groupby(['attack_kind','epsilon_rad']):
        m=g.groupby('attack_start').paired_window_delta_mm.mean()
        axes[0].plot(m.index,m.values,'o-',label=f'{kind} {eps} rad')
        m=g.groupby('attack_start').final_10_mean_distance_m.mean()*1000
        axes[1].plot(m.index,m.values,'o-',label=f'{kind} {eps} rad')
    axes[0].set_ylabel('Paired window distance increase (mm)'); axes[1].set_ylabel('Final 10-state mean distance (mm)')
    for ax in axes: ax.set_xlabel('Attack start (step)'); ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(OUT/'timing.png',dpi=180); plt.close(fig)
    g=window_summary[window_summary.variant=='original'].sort_values('case')
    fig,ax=plt.subplots(figsize=(10,4)); x=np.arange(len(g)); ax.bar(x-.18,g.normal_rate,.36,label='Matched normal window'); ax.bar(x+.18,g.attack_rate,.36,label='Attacked window'); ax.set_xticks(x,g.case,rotation=40,ha='right',fontsize=7); ax.set_ylabel('At least one window alarm'); ax.legend(); fig.tight_layout(); fig.savefig(OUT/'alarm_background.png',dpi=180); plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(11,4))
    for variant,g in agg.groupby('variant'):
        # sustained separately from 20-step attacks
        g=g[g.case!='sustained']; axes[0].plot(range(len(g)),g.aborts,'o-',label=variant); axes[1].plot(range(len(g)),g.angle_mae_rad,'o-',label=variant); axes[2].plot(range(len(g)),g.alarm_steps,'o-',label=variant)
    for ax,y in zip(axes,['Aborts / 90','Angle MAE (rad)','Corrected observations / episode']): ax.set_ylabel(y); ax.set_xlabel('Condition (CSV order)'); ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(OUT/'defense_cost.png',dpi=180); plt.close(fig)
    selected=capture('exploratory_20261118/test',lambda a:a['seed']==930000 and a['case'] in ['clean','bias_e0.1_s70'] and a['variant'] in ['none','original'])
    fig,ax=plt.subplots(figsize=(8,4))
    for case,variant,label in [('clean','none','Normal'),('bias_e0.1_s70','none','Attack'),('bias_e0.1_s70','original','Attack + original defense')]:
        group=[a for a in selected if a['case']==case and a['variant']==variant and a['truth_after']]
        ax.plot([a['observation_step']+1 for a in group],[a['truth_after']['distance']*1000 for a in group],label=label)
    ax.axvspan(70,90,alpha=.15,color='red'); ax.set(xlabel='Post-action state',ylabel='True target distance (mm)'); ax.legend(); fig.tight_layout(); fig.savefig(OUT/'representative_trajectory.png',dpi=180); plt.close(fig)
    abort=capture('reproduction_20261118_smoke',lambda a:a['seed']==802009 and a['case']=='bias_e0.1_d20' and a['monitor_on'])
    pd.json_normalize(abort).to_csv(OUT/'abort_step_log.csv',index=False)
    fig,axes=plt.subplots(2,1,figsize=(8,5),sharex=True)
    axes[0].plot([a['observation_step'] for a in abort],[a['monitor']['residual_m']*1000 for a in abort]); axes[0].axhline(6.071,color='red',ls='--'); axes[0].set_ylabel('Residual (mm)')
    axes[1].step([a['observation_step'] for a in abort],[a['monitor']['alarm_streak'] for a in abort],where='post'); axes[1].axhline(20,color='red',ls='--'); axes[1].set(xlabel='Observation step',ylabel='Consecutive alarms'); fig.tight_layout(); fig.savefig(OUT/'abort_case.png',dpi=180); plt.close(fig)
    last=abort[-1]
    status=json.loads((ROOT/'outputs/reproduction_20261118_main/run_status.json').read_text())
    oldstatus=json.loads((ROOT/'outputs/main_v1/run_status.json').read_text())
    selection=json.loads((ROOT/'outputs/exploratory_20261118/frozen_selection.json').read_text())
    report=f'''# 本机独立复现报告（2026-11-18）

Windows ZIP 项目无 .git，不能独立证明分支名；代码、模型、main_v1、pilot 与方案均存在。未发现适用 AGENTS.md。三个模型哈希与历史配置核对：{hashes}。

使用 mp1 Python 创建本地 .venv，复用 mp1 Torch；没有重新训练。环境：{json.dumps(env,ensure_ascii=False)}。

原锁联网 dry-run 成功。受限网络、uv 默认缓存与 ensurepip、pytest 临时目录曾失败，日志在 outputs/reproduction_20261118_environment。改用本地 uv 缓存安装原锁除 Torch 外的包；Torch 使用 mp1 2.7.1+cu126，所有评估 CPU。原锁未改写。本机核心版本见 environment-windows-mp1.lock.txt，完整依赖见环境目录 pip_freeze.txt。14 项测试通过（tests_verified.log），数值与 Windows GLFW 离屏渲染分别通过；未设置 EGL。

历史与本机回合核算：

{md(totals)}

逐项比较：

{md(comparison)}

历史正常逐步报警率 {fp['step_rate']:.6%}，整回合 {fp['episode_alarms']}/{fp['episodes']}。失败记录见 local_failures.csv；seed 802009 的 bias/random_bias 均在 40 步、连续第21次报警中止。bias 中止时残差 {last['monitor']['residual_m']*1000:.4f} mm，真距离 {last['truth_before']['distance']*1000:.4f} mm。完整日志见 abort_step_log.csv。

历史运行 {oldstatus['elapsed_seconds']:.2f} s，本机 {status['elapsed_seconds']:.2f} s（包含校准；本次与审计/探索并发，计时不可视为硬件基准）。历史审计另存 historical_audit.json，本机审计另存 local_audit.json。源码快照按历史 manifest 校验；当前 evaluate 仅新增可选 monitor_factory，正式默认规则保持不变，check_setup/audit 的输出防覆盖另作修改。

精确命令见 ../README.md 与 outputs/reproduction_20261118_environment/commands.ps1。渲染数值检查均成功；human 窗口交互未自动验证。本机并非历史 Python/Torch 二进制环境，因此有数值差异须以 comparison.csv 为准。
'''
    (ROOT.parent/'REPRODUCTION_REPORT.md').write_text(report,encoding='utf-8')
    conclusion=f'''# 最终结果（2026-11-18）

历史正式结果、本机重复测量和新探索数据分别保存，旧结果未改写。4500 回合是90个配对初始状态的重复条件，不是4500个独立样本。

{md(totals)}

新探索：三个冻结策略，每策略30个全新测试状态（930000/931000/932000起）；独立校准900000/901000/902000各100回合，开发910000/911000/912000各6状态。每状态正常三种防御条件只运行一次，攻击 bias/ramp × .05/.10 rad × start20/50/70 ×20步；另有40步持续攻击压力检查。所有窗含后10步均在100步边界内。逐步自动核对同一状态噪声流，攻击符号按状态交替，策略不重训。新 seed 与历史 validation/calibration/main/pilot 区间不重叠。

防御状态：normal → correcting（残差超阈值，原预测修正）→ recovery_pending（第21次报警）→ aborted（第21+grace次仍报警）；任一正常读数立即清零恢复。开发只比较grace1/3，按中止次数最少、平局等待最短选择：{selection}。选择在独立测试前保存。它没有额外观测或真值输入，但持续异常中止会推迟，这是代价。

汇总（最终距离仅完整100步轨迹；中止单独计失败）：

{md(agg.round(5))}

窗口报警对照：

{md(window_summary.round(4))}

完整按策略表 per_policy_results.csv。正常逐步、窗口、整回合报警含义不同；上述 attack_rate 包含噪声报警，配对差异及其区间才描述超出匹配背景的增量，也不等价于攻击归因准确率。延迟对窗口内曾报警者条件平均；无报警单列。窗口被中止截断须结合complete_windows阅读。bootstrap每个条件按策略内配对状态重采样2000次；仅三个训练策略，不能支持广泛跨策略推断。

效果与限制：依据表格比较各时机最终误差、瞬态误差和失败，不通过提高攻击幅度制造效果。等待恢复可能避免孤立第21次噪声触发的中止，但也延迟持续异常响应；若新测试没有中止差异，不能声称成功率稳定提升。主结果仍保留原规则。控制代价为归一化动作平方和，非机械能；中止的低代价/低角度误差来自较短轨迹，不能直接称更好。angle_mae_rad是真值仅用于评分的已施加策略角度误差（清洁接收/报警预测均包含），持续攻击与正常分别列出。

图：timing.png、alarm_background.png、defense_cost.png、representative_trajectory.png、abort_case.png。案例选择：新测试首个策略首个seed930000、最大预声明幅值bias、最晚时段；未按效果挑选。旧中止图按唯一失败初始状态802009选取。持续攻击仅检验响应，不混入20步时机结论。独立位置/速度受保护、理想运动学与仿真限定均保持；时机比较不能证明策略依赖某通道的因果关系。
'''
    (ROOT.parent/'FINAL_RESULTS.md').write_text(conclusion,encoding='utf-8')
    print('Materials complete:',OUT)


if __name__=='__main__': main()
