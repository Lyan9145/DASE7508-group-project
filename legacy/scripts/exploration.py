"""Frozen exploratory timing/defense study, independent development and test blocks."""
import argparse
import functools
import gzip
import hashlib
import json
from pathlib import Path
import time
import numpy as np
import torch
from stable_baselines3 import SAC
from evaluate import trial, calibrate, write_csv, write_json
from reacher_env import make_env
from security import Attack, ArmGeometry, KinematicMonitor, wrap
from recovery_monitor import RecoveryMonitor


def validate_window(start, duration):
    if start < 1 or duration < 1 or start + duration + 10 > 100:
        raise ValueError('Attack and 10 subsequent commands must fit in 100 actions')


class Sink:
    def __init__(self, file, variant):
        self.file, self.variant = file, variant
        self.alarms, self.errors, self.noise = [], [], []

    def write(self, line):
        r = json.loads(line)
        r['variant'] = self.variant
        s = r['monitor']
        if s and s['alarm']:
            self.alarms.append(r['observation_step'])
        self.errors.append(abs(wrap(np.arctan2(r['policy_sensor'][2], r['policy_sensor'][0]) - r['truth_before']['angles'][0])))
        self.noise.append(np.array(r['raw_sensor'][8:10]) - (np.array(r['truth_before']['fingertip']) - np.array(r['truth_before']['target'])))
        self.file.write(json.dumps(r) + '\n')


def run(out, phase, selected=None):
    out.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    torch.set_num_threads(1)
    dev = phase == 'development'
    base, count = (910000, 6) if dev else (930000, 30)
    variants = ['none', 'original', 'grace1', 'grace3'] if dev else ['none', 'original', f'grace{selected}']
    config = dict(phase='exploratory_' + phase, base=base, episodes_per_policy=count,
                  variants=variants, starts=[20, 50, 70], epsilons=[.05, .1], duration=20,
                  sustained='bias epsilon .1 start20 duration40; response stress check',
                  selection='minimize development abort count, then added sustained response delay; no test tuning',
                  calibration_base=900000, calibration_episodes=100)
    source = out / 'source'; source.mkdir()
    config['source_sha256'] = {}
    for name in ['exploration.py','recovery_monitor.py','security.py','reacher_env.py','evaluate.py']:
        content = Path(__file__).with_name(name).read_bytes()
        (source/name).write_bytes(content)
        config['source_sha256'][name] = hashlib.sha256(content).hexdigest()
    config['model_sha256'] = {}
    rows, calibrations = [], {}
    write_json(out/'config.json', config)
    with gzip.open(out/'traces.jsonl.gz','wt',encoding='utf-8') as trace:
        for p in range(3):
            name = f'sac_seed_{p+1}_sync'
            path = Path('outputs')/name/'model.zip'
            config['model_sha256'][name] = hashlib.sha256(path.read_bytes()).hexdigest()
            model = SAC.load(path, device='cpu')
            env = make_env(); g = ArmGeometry.from_model(env.unwrapped.model)
            cal = calibrate(model,g,100,900000+p*1000,.002)
            calibrations[name] = cal
            write_json(out/'calibration.json',calibrations)
            for i in range(count):
                seed = base+p*1000+i
                cases = [('clean',Attack())]
                for start in [20,50,70]:
                    for epsilon in [.05,.1]:
                        for kind in ['bias','ramp']:
                            validate_window(start,20)
                            cases.append((f'{kind}_e{epsilon}_s{start}',Attack(kind,epsilon,20,start,1 if i%2==0 else -1,seed+20000000)))
                cases.append(('sustained',Attack('bias',.1,40,20,1 if i%2==0 else -1)))
                references = {}
                paired_noise = None
                for case, attack in cases:
                    for variant in variants:
                        factory = KinematicMonitor if variant in ['none','original'] else functools.partial(RecoveryMonitor,grace=int(variant[-1]))
                        sink = Sink(trace, variant)
                        row = trial(model,env,g,cal['threshold_m'],attack,variant!='none',seed,sink,name,case,monitor_factory=factory)
                        distances = row.pop('_distances')
                        if paired_noise is None:
                            paired_noise = sink.noise
                        np.testing.assert_allclose(sink.noise,paired_noise[:len(sink.noise)],rtol=0,atol=1e-13)
                        row.update(variant=variant, angle_mae_rad=float(np.mean(sink.errors)),
                                   angle_max_rad=max(sink.errors), alarm_steps_json=json.dumps(sink.alarms))
                        row['final_complete'] = row['steps']==100
                        if case=='clean':
                            references[variant] = distances
                        if case!='clean':
                            ref = references['none'][attack.start+1:attack.start+1+row['window_samples']]
                            row['paired_window_delta_mm'] = 1000*(row['window_mean_distance_m']-np.mean(ref)) if ref else None
                        else:
                            row['paired_window_delta_mm'] = None
                        rows.append(row)
                print(f'{phase} {name}: {i+1}/{count}',flush=True)
                write_csv(out/'episodes.csv',rows)
            env.close()
    write_json(out/'config.json',config)
    write_json(out/'run_status.json',dict(complete=True,episodes=len(rows),elapsed_seconds=time.perf_counter()-started))
    return rows


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    plan=dict(frozen_before_development=True, candidates=[1,3],calibration_seeds='900000+p*1000+[0,99]',
              development_seeds='910000+p*1000+[0,5]',test_seeds='930000+p*1000+[0,29]',
              rule='21st alarm enters recovery_pending; clear resets; sustained alarm aborts at 21+grace',
              selection='fewest development aborts; ties choose smallest grace',
              trust='identical protected position and velocity channels; truth for evaluation only')
    write_json(args.out/'preregistered_plan.json',plan)
    rows=run(args.out/'development','development')
    scores={g:sum(r['aborted'] for r in rows if r['variant']==f'grace{g}') for g in [1,3]}
    selected=min(scores,key=lambda g:(scores[g],g))
    write_json(args.out/'frozen_selection.json',dict(selected_grace=selected,development_aborts=scores,selected_before_test=True))
    run(args.out/'test','test',selected)


if __name__=='__main__':
    main()
