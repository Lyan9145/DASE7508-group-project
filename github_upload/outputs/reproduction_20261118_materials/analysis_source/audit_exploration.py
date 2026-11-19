"""Independent exploratory trace scoring and alarm-only prediction error audit."""
import gzip
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import numpy as np
import pandas as pd


def main():
    root=Path(__file__).resolve().parent
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',type=Path,default=root/'outputs/exploratory_20261118/test')
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    run=args.run
    out=args.out or root/'outputs/reproduction_20261118_materials'
    if args.out is not None:
        out.mkdir(parents=True,exist_ok=False)
    config=json.loads((run/'config.json').read_text())
    for name,value in config['source_sha256'].items():
        assert hashlib.sha256((run/'source'/name).read_bytes()).hexdigest()==value
    metrics=pd.read_csv(run/'episodes.csv').set_index(['policy','seed','case','variant'])
    errors=[]; count=episodes=0; noise={}
    with gzip.open(run/'traces.jsonl.gz','rt',encoding='utf-8') as file:
        records=(json.loads(line) for line in file)
        identity=lambda r:(r['policy'],r['seed'],r['case'],r['variant'])
        for key,group in itertools.groupby(records,key=identity):
            distances=[]; steps=0; aborted=False; previous_angle=velocity=None
            row=metrics.loc[key]
            for r in group:
                count+=1
                raw=np.array(r['raw_sensor']); reported=np.array(r['reported_sensor']); applied=np.array(r['policy_sensor'])
                safe=[1,3,4,5,6,7,8,9]
                assert np.array_equal(raw[safe],reported[safe])
                assert np.array_equal(reported[safe],applied[safe])
                n=raw[8:10]-(np.array(r['truth_before']['fingertip'])-np.array(r['truth_before']['target']))
                nk=(r['policy'],r['seed'],r['observation_step'])
                if nk in noise: assert np.max(np.abs(noise[nk]-n))<1e-13
                else: noise[nk]=n
                s=r['monitor']
                if s:
                    grace=1 if r['variant']=='grace1' else 0
                    assert s['abort']==(s['alarm_streak']>20+grace)
                    if s['alarm']:
                        prediction=previous_angle+velocity*.02
                        assert np.max(np.abs(applied[[0,2]]-np.array([np.cos(prediction),np.sin(prediction)])))<1e-12
                        actual=r['truth_before']['angles'][0]
                        err=abs(float(np.arctan2(np.sin(prediction-actual),np.cos(prediction-actual))))
                        errors.append(dict(policy=r['policy'],seed=r['seed'],case=r['case'],variant=r['variant'],error_rad=err))
                previous_angle=float(np.arctan2(applied[2],applied[0])); velocity=raw[6]
                if r['action'] is not None:
                    steps+=1; distances.append(r['truth_after']['distance'])
                else:
                    aborted=True; assert s['abort']
            assert steps==row.steps and aborted==row.aborted
            success=not aborted and steps==100 and np.mean(distances[-10:])<=.03
            assert success==row.task_success
            episodes+=1
    error=pd.DataFrame(errors)
    # First summarize each paired episode; never treat predictions as independent samples.
    per_episode=error.groupby(['policy','seed','case','variant']).agg(prediction_mae_rad=('error_rad','mean'),prediction_max_rad=('error_rad','max'),predicted_steps=('error_rad','size')).reset_index()
    per_episode.to_csv(out/'alarm_prediction_per_episode.csv',index=False)
    per_episode.groupby(['policy','case','variant']).agg(episodes_with_predictions=('seed','size'),mean_episode_prediction_mae_rad=('prediction_mae_rad','mean'),worst_prediction_rad=('prediction_max_rad','max')).to_csv(out/'alarm_prediction_summary.csv')
    result=dict(passed=True,episodes=episodes,trace_rows=count,paired_initial_states=90,
                checks=['source hashes','protected channels','paired noise','previous velocity prediction','original/improved abort boundary','independent task scoring'],
                prediction='errors measured only during actual corrections; per-episode mean precedes aggregation')
    with (out/'exploratory_audit.json').open('x',encoding='utf-8') as f: json.dump(result,f,indent=2)
    # Cross-check historical summary against the episode table.
    h=pd.read_csv(root/'outputs/main_v1/episodes.csv'); s=pd.read_csv(root/'outputs/main_v1/summary.csv')
    for _,v in s.iterrows():
        g=h[(h.policy==v.policy)&(h.case==v.case)&(h.monitor_on==v.monitor_on)]
        assert len(g)==v.episodes and g.task_success.sum()==v.successes
        assert abs(g.final_10_mean_distance_m.mean()-v.mean_final_error_m)<1e-13
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
