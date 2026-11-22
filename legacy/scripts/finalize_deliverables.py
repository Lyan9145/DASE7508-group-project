"""Final review additions with explicit sustained-response and incomplete cohorts."""
import gzip
import hashlib
import importlib.metadata as im
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from build_deliverables import ROOT, OUT, md


def main():
    t=pd.read_csv(ROOT/'outputs/exploratory_20261118/test/episodes.csv')
    t['cohort']=np.where(t.case=='clean','Normal',np.where(t.case=='sustained','Sustained 40','Short '+t.attack_kind))
    groups=[]
    for (cohort,variant),g in t.groupby(['cohort','variant']):
        full=g[g.final_complete]
        groups.append(dict(cohort=cohort,variant=variant,n=len(g),success=int(g.task_success.sum()),aborts=int(g.aborted.sum()),
                           complete_final_mm=full.final_10_mean_distance_m.mean()*1000 if len(full) else None,
                           complete_angle_mae_rad=full.angle_mae_rad.mean() if len(full) else None,
                           complete_action_cost=full.control_effort.mean() if len(full) else None,
                           correction_steps_mean=g.alarm_count.mean()))
    groups=pd.DataFrame(groups); groups.to_csv(OUT/'cohort_comparison.csv',index=False)
    variants=['none','original','grace1']; cohorts=['Normal','Short bias','Short ramp','Sustained 40']
    fig,axes=plt.subplots(1,4,figsize=(14,4))
    labels=['No defense','Original','Recovery +1']
    for i,v in enumerate(variants):
        g=groups[groups.variant==v].set_index('cohort').loc[cohorts]
        for ax,col in zip(axes,['aborts','correction_steps_mean','complete_angle_mae_rad','complete_action_cost']):
            ax.bar(np.arange(4)+(i-1)*.25,g[col],.25,label=labels[i])
    for ax,label in zip(axes,['Abort count (see n in table)','Corrections / episode','Angle MAE, complete only (rad)','Action squares, complete only']):
        ax.set_xticks(range(4),cohorts,rotation=30,ha='right'); ax.set_ylabel(label)
    axes[0].legend(fontsize=7); fig.suptitle('Cohorts: n=90 normal/sustained; n=540 short bias/ramp per variant\nComplete-only costs exclude aborts: compare success and abort counts alongside costs',fontsize=10)
    fig.tight_layout(); fig.savefig(OUT/'defense_cost.png',dpi=180); plt.close(fig)
    a=t[(t.case=='sustained') & t.aborted & (t.variant=='original')][['policy','seed','steps']]
    b=t[(t.case=='sustained') & t.aborted & (t.variant=='grace1')][['policy','seed','steps']]
    response=a.merge(b,on=['policy','seed'],suffixes=('_original','_improved'),validate='one_to_one')
    response['added_response_steps']=response.steps_improved-response.steps_original
    response['added_response_ms']=response.added_response_steps*20
    response.to_csv(OUT/'sustained_response_pairs.csv',index=False)
    failures=t[(t.duration==20)&t.aborted]
    failures.to_csv(OUT/'exploratory_failures.csv',index=False)
    # Window misses and predicted/corrected errors per policy already in primary CSV.
    snippets=[]
    identities=set(zip(failures.policy,failures.seed,failures.case))
    with gzip.open(ROOT/'outputs/exploratory_20261118/test/traces.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            r=json.loads(line)
            if r['variant']=='original' and (r['policy'],r['seed'],r['case']) in identities:
                if r['monitor']['alarm_streak']>=19 or r['observation_step'] in [19,20,39,40,69,70,89,90]:
                    snippets.append(r)
    pd.json_normalize(snippets).to_csv(OUT/'exploratory_failure_steps.csv',index=False)
    # Freeze all directly installed versions as well as the inherited mp1 Torch.
    names=[s.split('==')[0] for s in (ROOT/'outputs/reproduction_20261118_environment/local_install.txt').read_text().splitlines() if s.strip()]
    names+=['torch','pytest','iniconfig','pluggy','pygments']
    (ROOT/'environment-windows-mp1.lock.txt').write_text('--extra-index-url https://download.pytorch.org/whl/cu126\n'+'\n'.join(f'{n}=={im.version(n)}' for n in sorted(set(names)))+'\n',encoding='utf-8')
    windows=pd.read_csv(OUT/'window_alarm_summary.csv')
    short=windows[windows.case!='sustained']
    text=f'''\n\n## 经逐表核对的主要结论

20步攻击共1080个配对条件：无防御1080/1080，原防御1076/1080，改进1080/1080。原防御4次失败来自4个不同初始状态（sac_seed_1:1个，sac_seed_2:3个，sac_seed_3:0个），全部为0.10rad bias。不能把1080重复条件当1080独立状态。正常三种方法均90/90成功。

4次失败的触发不全是“攻击后噪声”：931009/931023在step39中止，930016在step89中止，报警链可由攻击前单步噪声延伸；931011在step90中止。详见exploratory_failure_steps.csv。等待1步覆盖这些边界案例，但并不识别攻击结束，持续异常仍中止。

40步持续攻击：原/改进均73/90中止、17/90成功，无防御90/90成功。73对共同中止样本，改进均延迟1步=20ms；原中止动作数39–57，改进40–58。未中止的17例说明连续报警规则并不保证发现/中止所有持续攻击；须看逐策略misses、报警中断和姿态敏感性。维持中止功能产生大量任务失败，说明它不是任务成功率优化器。

时机影响：未防御0.10rad bias最终十步均距从start20的5.581mm到start70的6.157mm，仍远低于30mm成功阈值；对应攻击及后10步配对额外距离从1.119mm降到1.016mm。更晚时机对最终误差有影响，但本次未产生未防御任务失败，不应描述为成功攻击。

正常匹配20步窗口报警率范围{short.normal_rate.min():.1%}–{short.normal_rate.max():.1%}；攻击窗口报警率范围{short.attack_rate.min():.1%}–{short.attack_rate.max():.1%}。不同幅值/形状分别看表，不能把噪声报警解释为准确识别。misses和条件延迟在window_alarm_summary.csv与per_policy_results.csv；每步20ms。

改进有效之处：本次独立测试消除了4次短攻击下的规则中止，也完成了两次历史诊断失败回放。未见改善之处：正常条件、ramp及40步持续攻击的成功/中止数没有变化，持续异常响应反而慢20ms。角度预测和干预成本没有系统性提升，仍存在预测漂移与渐增攻击漏检。保留原正式结果为主结果，改进仅为范围有限的探索证据。

按完整/中止队列分开后的防御效果和代价：

{md(groups.round(6))}

新图defense_cost.png按四个明确队列绘制。角度与动作代价仅完整轨迹，必须连同中止数阅读（存在幸存者选择）；全部轨迹原始指标另保留。sustained_response_pairs.csv逐对保存响应延迟。图表无防御、原防御、改进使用相同状态和噪声。
'''
    final=ROOT.parent/'FINAL_RESULTS.md'
    final.write_text(final.read_text(encoding='utf-8')+text,encoding='utf-8')
    report=ROOT.parent/'REPRODUCTION_REPORT.md'
    content=report.read_text(encoding='utf-8').replace('14 项测试通过（tests_verified.log）','16 项测试通过（tests_final.log）').replace('comparison.csv','reproduction_comparison.csv').replace('见 ../README.md','见 README.md')
    report.write_text(content,encoding='utf-8')
    # Analysis source and presentation/report content are distinct from executed simulation snapshots.
    source=OUT/'analysis_source'; source.mkdir(exist_ok=False)
    manifest={}
    for path in [*ROOT.glob('*.py'),ROOT.parent/'README.md',ROOT.parent/'REPRODUCTION_REPORT.md',ROOT.parent/'FINAL_RESULTS.md',ROOT.parent/'PRESENTATION_PLAN.md']:
        dest=source/path.name
        dest.write_bytes(path.read_bytes()); manifest[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    (OUT/'analysis_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Reviewed results and analysis snapshot complete')


if __name__=='__main__': main()
