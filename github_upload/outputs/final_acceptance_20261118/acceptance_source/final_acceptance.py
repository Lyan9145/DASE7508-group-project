"""Read-only independent acceptance of frozen experiments; outputs go elsewhere."""
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
from reacher_env import make_env
from security import ArmGeometry

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'outputs/final_acceptance_20261118'
TEST=ROOT/'outputs/exploratory_20261118_compatible/test'
MAIN=ROOT/'outputs/reproduction_20261118_compatible_main'

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def protected_manifest():
    roots=['main_v1','pilot_20261022','pilot_checked_20261022','reproduction_20261118_main',
           'reproduction_20261118_compatible_main','exploratory_20261118','exploratory_20261118_compatible',
           'sac_seed_1','sac_seed_1_sync','sac_seed_2_sync','sac_seed_3_sync']
    return {str(p.relative_to(ROOT)):digest(p) for name in roots for p in (ROOT/'outputs'/name).rglob('*') if p.is_file()}

def audit(run):
    frame=pd.read_csv(run/'episodes.csv')
    exploratory='variant' in frame
    keys=['policy','seed','case']+(['variant'] if exploratory else ['monitor_on'])
    metric=frame.set_index(keys,drop=False)
    assert metric.index.is_unique
    config=json.loads((run/'config.json').read_text())
    hashes=config.get('source_sha256',config.get('implementation_sha256'))
    for name,value in hashes.items():assert digest(run/'source'/name)==value
    for name,value in config['model_sha256'].items():
        modelname=Path(name).parent.name if name.endswith('.zip') else name
        assert digest(ROOT/'outputs'/modelname/'model.zip')==value
    if 'plan_sha256' in config:assert digest(run/'source/main_plan.json')==config['plan_sha256']
    cal=json.loads((run/'calibration.json').read_text())
    env=make_env(); geometry=ArmGeometry.from_model(env.unwrapped.model); dt=env.unwrapped.dt; env.close()
    noise={}; initial={}; derived=[]; chosen=[]; trace_count=0
    with gzip.open(run/'traces.jsonl.gz','rt',encoding='utf-8') as f:
        records=(json.loads(line) for line in f)
        key=lambda r:tuple(r[k] for k in keys)
        for identity,records in itertools.groupby(records,key):
            m=metric.loc[identity]; distances=[]; actions=[]; alarms=[]; streak=0
            prevangle=velocity=None; abort=False; window_seen=0; prediction=[]
            random_signs=np.random.default_rng(int(m.seed)+20000000).choice([-1,1],size=int(m.duration))
            for r in records:
                trace_count+=1; t=r['observation_step']
                raw=r['raw_sensor']; rep=r['reported_sensor']; applied=r['policy_sensor']
                assert all(raw[i]==rep[i]==applied[i] for i in [1,3,4,5,6,7,8,9])
                target=r['truth_before']['target']; tip=r['truth_before']['fingertip']
                n=(raw[8]-tip[0]+target[0],raw[9]-tip[1]+target[1]); nk=(r['policy'],r['seed'],t)
                if nk in noise:assert max(abs(a-b) for a,b in zip(n,noise[nk]))<1e-13
                else:noise[nk]=n
                if t==0:
                    ik=(r['policy'],r['seed'])
                    if ik in initial:assert initial[ik]==r['truth_before']
                    else:initial[ik]=r['truth_before']
                active=m.attack_kind!='clean' and int(m.attack_start)<=t<int(m.attack_start+m.duration)
                delta=0.
                if active:
                    offset=t-int(m.attack_start)
                    sign=int(random_signs[offset]) if str(m.attack_kind).startswith('random_') else int(m.sign)
                    delta=sign*float(m.epsilon_rad)*((offset+1)/m.duration if str(m.attack_kind).endswith('ramp') else 1)
                assert abs(r['delta_rad']-delta)<1e-14
                angle=math.atan2(raw[2],raw[0])+delta
                assert max(abs(rep[0]-math.cos(angle)),abs(rep[2]-math.sin(angle)))<1e-12
                if int(m.attack_start)<=t<int(m.attack_start+m.duration):window_seen+=1
                s=r['monitor']
                if s:
                    residual=geometry.residual(np.asarray(rep))
                    alarm=t>0 and residual>cal[r['policy']]['threshold_m']
                    assert alarm==s['alarm'] and abs(residual-s['residual_m'])<1e-12
                    streak=streak+1 if alarm else 0
                    assert s['alarm_streak']==streak
                    limit=21 if exploratory and r['variant']=='grace1' else 20
                    assert s['abort']==(streak>limit)
                    if alarm:
                        alarms.append(t); predicted=prevangle+velocity*dt
                        assert max(abs(applied[0]-math.cos(predicted)),abs(applied[2]-math.sin(predicted)))<1e-12
                        err=predicted-r['truth_before']['angles'][0]
                        prediction.append(abs(math.atan2(math.sin(err),math.cos(err))))
                    else:assert applied==rep
                else:assert applied==rep
                prevangle=math.atan2(applied[2],applied[0]); velocity=raw[6]
                if not distances:distances=[r['truth_before']['distance']]
                if r['action'] is None:
                    abort=True; assert s and s['abort']
                else:
                    actions.append(sum(x*x for x in r['action'])); distances.append(r['truth_after']['distance'])
                if (exploratory and r['policy']=='sac_seed_1_sync' and r['seed']==930000 and r['case'] in ['clean','bias_e0.1_s70'] and r['variant'] in ['none','original']) or (not exploratory and r['seed']==802009 and r['case']=='bias_e0.1_d20'):
                    chosen.append(r)
            assert len(actions)==m.steps and abort==m.aborted
            final=float(np.mean(distances[-10:])); success=not abort and len(actions)==100 and final<=.03
            assert success==m.task_success and abs(final-m.final_10_mean_distance_m)<1e-12
            assert abs(sum(actions)-m.control_effort)<1e-5
            window=distances[int(m.attack_start)+1:min(int(m.attack_start+m.duration)+11,len(distances))]
            assert len(window)==m.window_samples and (len(window)==int(m.duration)+10)==m.window_complete
            if window:assert abs(np.mean(window)-m.window_mean_distance_m)<1e-12
            assert len(alarms)==m.alarm_count
            if exploratory:assert alarms==json.loads(m.alarm_steps_json)
            row={k:m[k] for k in frame.columns if k not in ['alarm_steps_json']}
            row.update(alarms=alarms,distances=distances,observed_window_steps=window_seen,
                       complete_final_mm=final*1000 if len(actions)==100 and not abort else None,
                       prediction_mae_rad=float(np.mean(prediction)) if prediction else None)
            derived.append(row)
    assert len(derived)==len(frame)
    print(run.name, 'audited',len(derived),'episodes',trace_count,'trace rows',flush=True)
    return derived,chosen,dict(episodes=len(derived),trace_rows=trace_count,paired_states=len(initial),dt=dt)

def main():
    before=protected_manifest()
    (OUT/'protected_before.json').write_text(json.dumps(before,indent=2),encoding='utf-8')
    t,chosen,ta=audit(TEST); mainrows,known,ma=audit(MAIN)
    with (OUT/'selected_traces.json').open('x',encoding='utf-8') as f:json.dump(chosen+known,f)
    t=pd.DataFrame(t); m=pd.DataFrame(mainrows)
    short=t[(t.attack_kind!='clean')&(t.duration==20)]
    totals=short.groupby('variant').agg(episodes=('seed','size'),successes=('task_success','sum'),aborts=('aborted','sum')).reset_index()
    totals.to_csv(OUT/'short_totals.csv',index=False)
    failed=short[(short.variant=='original')&short.aborted].copy()
    failed[['policy','seed','case','attack_kind','epsilon_rad','attack_start','duration','steps']].to_csv(OUT/'four_failures.csv',index=False)
    assert len(failed)==4 and len(failed[['policy','seed']].drop_duplicates())==4
    sustained=t[t.case=='sustained']
    response=sustained[sustained.variant=='original'][['policy','seed','steps','aborted']].merge(sustained[sustained.variant=='grace1'][['policy','seed','steps','aborted']],on=['policy','seed'],suffixes=('_original','_improved'),validate='one_to_one')
    assert (response.aborted_original==response.aborted_improved).all()
    response=response[response.aborted_original].copy(); response['added_steps']=response.steps_improved-response.steps_original; response['added_ms']=response.added_steps*ta['dt']*1000
    assert len(response)==73 and (response.added_steps==1).all()
    response.to_csv(OUT/'sustained_pairs.csv',index=False)
    clean=t[t.case=='clean'].set_index(['policy','seed','variant']); windows=[]
    for _,r in t[(t.case!='clean')&(t.variant!='none')].iterrows():
        c=clean.loc[(r.policy,r.seed,r.variant)]; start,end=int(r.attack_start),int(r.attack_start+r.duration)
        n=[a for a in c.alarms if start<=a<end]; a=[v for v in r.alarms if start<=v<end]
        windows.append(dict(policy=r.policy,seed=r.seed,case=r.case,variant=r.variant,normal_alarm=bool(n),attack_alarm=bool(a),difference=int(bool(a))-int(bool(n)),
                            delay_steps=a[0]-start if a else None,delay_ms=(a[0]-start)*20 if a else None,
                            no_observed_alarm=not a,observed_steps=r.observed_window_steps,planned_steps=r.duration,
                            censored=r.observed_window_steps<r.duration))
    w=pd.DataFrame(windows);w.to_csv(OUT/'paired_windows.csv',index=False)
    w.groupby(['case','variant']).agg(n=('seed','size'),normal_alarm_count=('normal_alarm','sum'),attack_alarm_count=('attack_alarm','sum'),normal_rate=('normal_alarm','mean'),attack_observed_rate=('attack_alarm','mean'),paired_difference=('difference','mean'),delay_steps=('delay_steps','mean'),delay_ms=('delay_ms','mean'),no_observed_alarm=('no_observed_alarm','sum'),censored=('censored','sum')).reset_index().to_csv(OUT/'window_rates.csv',index=False)
    c=t[(t.case=='clean')&(t.variant!='none')]
    fp=c.groupby(['policy','variant']).agg(episodes=('seed','size'),alarms=('alarm_count','sum'),opportunities=('detection_steps','sum'),episodes_with_alarm=('any_alarm','sum')).reset_index()
    fp['step_rate']=fp.alarms/fp.opportunities;fp['episode_rate']=fp.episodes_with_alarm/fp.episodes;fp.to_csv(OUT/'false_alarms.csv',index=False)
    complete=t.drop(columns=['alarms','distances']);complete.to_csv(OUT/'verified_episodes.csv',index=False)
    # Grouping excludes aborted prefixes for final distances; counts always retain failures.
    t['cohort']=np.where(t.case=='clean','normal',np.where(t.case=='sustained','sustained',t.attack_kind))
    t.groupby(['cohort','variant']).agg(n=('seed','size'),successes=('task_success','sum'),aborts=('aborted','sum'),complete_final_mm=('complete_final_mm','mean'),prediction_mae_rad=('prediction_mae_rad','mean'),alarm_steps=('alarm_count','mean')).to_csv(OUT/'cohorts.csv')
    seeds={}
    for label,run in [('development',TEST.parent/'development'),('test',TEST),('main',MAIN),('pilot',ROOT/'outputs/pilot_checked_20261022')]:
        f=pd.read_csv(run/'episodes.csv');seeds[label]=set(f.seed.astype(int))
    calibration=json.loads((TEST/'calibration.json').read_text()); seeds['calibration']={v for c in calibration.values() for v in c['seeds']}
    seeds['validation']={r['seed'] for i in [1,2,3] for r in json.loads((ROOT/f'outputs/sac_seed_{i}_sync/validation.json').read_text())['trials']}
    overlap={a+' / '+b:sorted(seeds[a]&seeds[b]) for a,b in itertools.combinations(seeds,2)}
    assert not any(overlap.values())
    development=pd.read_csv(TEST.parent/'development/episodes.csv'); scores={g:int(development[development.variant==f'grace{g}'].aborted.sum()) for g in [1,3]}
    selection=json.loads((TEST.parent/'frozen_selection.json').read_text()); assert selection['selected_grace']==min(scores,key=lambda g:(scores[g],g))
    result=dict(passed=True,exploration=ta,main=ma,unique_failed_states=4,development_scores=scores,seed_sets={k:dict(count=len(v),minimum=min(v),maximum=max(v)) for k,v in seeds.items()},overlaps=overlap,
                notes=['All numeric checks reconstructed from CSV and full traces','Configuration/source/model hashes verified','Freeze order supported by sequential executed source; cannot independently certify pre-test chronology from mutable local files','Calibration is deliberately reused by development and test, but calibration states do not overlap evaluation states','Censored windows report observed alarms and exposure; no unobserved suffix is assumed clean'])
    (OUT/'acceptance.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':main()
