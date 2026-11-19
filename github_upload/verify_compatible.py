"""Cross-check repeated supported-environment runs without pooling repeated seeds."""
import hashlib
import importlib.metadata as im
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from evaluate import write_json


def main():
    root=Path(__file__).resolve().parent
    out=root/'outputs/reproduction_20261118_materials'
    comparisons=[]
    for label,old,new,keys in [
        ('main','reproduction_20261118_main','reproduction_20261118_compatible_main',['policy','seed','case','monitor_on']),
        ('exploration','exploratory_20261118/test','exploratory_20261118_compatible/test',['policy','seed','case','variant'])]:
        a=pd.read_csv(root/'outputs'/old/'episodes.csv')
        b=pd.read_csv(root/'outputs'/new/'episodes.csv')
        merged=a.merge(b,on=keys,suffixes=('_first','_supported'),validate='one_to_one')
        assert len(merged)==len(a)==len(b)
        columns=['task_success','aborted','steps','alarm_count','final_10_mean_distance_m',
                 'terminal_distance_m','window_mean_distance_m','window_max_distance_m',
                 'window_samples','window_complete','control_effort','detection_steps',
                 'detection_delay_steps','missed_detection','recovery_steps']
        columns += [c for c in ['angle_mae_rad','angle_max_rad','paired_window_delta_mm','final_complete'] if c in a]
        for col in columns:
            x,y=merged[col+'_first'],merged[col+'_supported']
            assert np.array_equal(x.isna(),y.isna())
            difference=np.abs(x.astype(float)-y.astype(float)).dropna()
            delta=float(difference.max()) if len(difference) else 0.0
            if col in ['task_success','aborted','steps','alarm_count']: assert delta==0
            else: assert np.isfinite(delta)
            comparisons.append(dict(dataset=label,metric=col,n=len(merged),max_abs_difference=delta))
        if 'alarm_steps_json' in a:
            assert (merged.alarm_steps_json_first==merged.alarm_steps_json_supported).all()
    comparisons=pd.DataFrame(comparisons)
    comparisons.to_csv(out/'compatible_environment_comparison.csv',index=False)
    history=pd.read_csv(root/'outputs/main_v1/episodes.csv')
    supported=pd.read_csv(root/'outputs/reproduction_20261118_compatible_main/episodes.csv')
    paired=history.merge(supported,on=['policy','seed','case','monitor_on'],suffixes=('_history','_supported'),validate='one_to_one')
    history_comparison=[]
    for column in ['task_success','aborted','steps','alarm_count','final_10_mean_distance_m','terminal_distance_m','window_mean_distance_m','control_effort']:
        difference=(paired[column+'_history'].astype(float)-paired[column+'_supported'].astype(float)).abs()
        history_comparison.append(dict(metric=column,unequal=int((difference>0).sum()),max_abs_difference=float(difference.max())))
    pd.DataFrame(history_comparison).to_csv(out/'supported_vs_history.csv',index=False)
    first_selection=json.loads((root/'outputs/exploratory_20261118/frozen_selection.json').read_text())
    supported_selection=json.loads((root/'outputs/exploratory_20261118_compatible/frozen_selection.json').read_text())
    assert first_selection==supported_selection
    names=[s.split('==')[0] for s in (root/'outputs/reproduction_20261118_environment/local_install.txt').read_text().splitlines() if s.strip()]
    names+=['torch','pytest','iniconfig','pluggy','pygments']
    (root/'environment-windows-mp1.lock.txt').write_text('--extra-index-url https://download.pytorch.org/whl/cpu\n'+'\n'.join(f'{n}=={im.version(n)}' for n in sorted(set(names)))+'\n',encoding='utf-8')
    env=dict(python=sys.version,base_prefix=sys.base_prefix,packages={n:im.version(n) for n in sorted(set(names))})
    write_json(out/'compatible_environment.json',env)
    short=b[(b.case!='clean')&(b.case!='sustained')]
    unit=short.groupby(['policy','seed','variant']).task_success.all().unstack('variant')
    unit['benefit']=unit.grace1.astype(int)-unit.original.astype(int)
    rng=np.random.default_rng(7508)
    values=[g.benefit.to_numpy() for _,g in unit.reset_index().groupby('policy')]
    means=np.mean([rng.choice(v,(5000,len(v))).mean(axis=1) for v in values],axis=0)
    ci=np.quantile(means,[.025,.975]).tolist()
    write_json(out/'paired_state_success.json',dict(unit='all 12 short-attack settings successful for same initial state',states=len(unit),original=int(unit.original.sum()),improved=int(unit.grace1.sum()),paired_difference=float(unit.benefit.mean()),ci95=ci,resampling='5000 paired-state samples stratified within three fixed policies'))
    status=json.loads((root/'outputs/reproduction_20261118_compatible_main/run_status.json').read_text())
    text=f'''\n\n兼容性最终补验：第一次 mp1 Torch2.7.1 下虽然数值与测试通过，最终 pip check 发现 SB3 2.9.0 声明需要 Torch>=2.8。该问题已修复：仅在项目.venv安装原锁 Torch2.14.1+cpu，mp1本身未修改。pip_check_compatible.log 为 No broken requirements found；tests_compatible.log 16项通过。完整4500回合与开发1008/测试3780回合均在兼容环境重新运行，分别保存 reproduction_20261118_compatible_main 和 exploratory_20261118_compatible。成功、中止、步数、报警数及窗口报警时间逐条一致，但浮点轨迹不逐位一致。正式最终十步均距最大差0.000026805mm，终点距离最大差0.000035683mm，动作平方和最大差约1.77e-7；探索最大配对窗口增量差0.000009602mm。详见 compatible_environment_comparison.csv及supported_vs_history.csv。最初逐值检查的1e-10门槛未通过（保留compatible_verification.log初次失败另存副本），已定位实际差异并如实报告，不称为精确数值复现。后者为相同seed重复复现，不增加独立样本数。兼容正式复现用时 {status['elapsed_seconds']:.2f}s；最初290.16s属于旧Torch兼容性探查记录。

最终可用依赖为 environment-windows-mp1.lock.txt（CPU索引），旧环境版本仍保存在environment.json与初次config；当前环境另见compatible_environment.json。主图和表使用首次数值数据，已由兼容重跑逐项核对，不将两轮重复条件合并。

改进状态的数学含义就是将连续中止边界从第21次改到第22次；pending不提供额外观测证据，不表示已经确认恢复。若噪声连续更多步，仍可误中止。报警时预测角度误差先按回合聚合：短bias约0.02555rad、短ramp约0.03594rad，正常误报警约0.00110rad；均不可与全回合角度MAE混为同一量。见prediction_cohort_summary.csv，截断仍需单列。开发选择在兼容重跑中也完全一致。

证据入口：[结果索引](github_upload/outputs/reproduction_20261118_materials/READ_ME_FIRST.md)、[兼容正式日志审计](github_upload/outputs/reproduction_20261118_environment/compatible_main_audit.json)、[兼容探索日志审计](github_upload/outputs/reproduction_20261118_compatible_audit/exploratory_audit.json)。

以每个初始状态在全部12种短攻击下是否均成功为单位：原防御86/90，改进90/90，配对增量4/90，固定三个策略内bootstrap95%区间 {ci[0]:.4f}–{ci[1]:.4f}。这是本组预声明条件整体通过率，不代表单个新攻击条件或新策略总体收益。
'''
    for path in [root.parent/'REPRODUCTION_REPORT.md',root.parent/'FINAL_RESULTS.md']:
        with path.open('a',encoding='utf-8') as f:f.write(text)
    # Snapshot final analysis code and reviewed documents after all additions.
    source=out/'analysis_source'
    for path in [*root.glob('*.py'),root/'environment-windows-mp1.lock.txt',root.parent/'README.md',root.parent/'REPRODUCTION_REPORT.md',root.parent/'FINAL_RESULTS.md',root.parent/'PRESENTATION_PLAN.md']:
        (source/path.name).write_bytes(path.read_bytes())
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir() if p.is_file()}
    write_json(out/'analysis_manifest.json',manifest)
    print('Supported-environment full comparisons passed')


if __name__=='__main__':main()
