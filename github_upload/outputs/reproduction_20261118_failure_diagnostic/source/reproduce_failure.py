"""Diagnostic replay of the known failure; never used for parameter selection."""
import functools
import gzip
import json
from pathlib import Path
import torch
from stable_baselines3 import SAC
from evaluate import trial, write_csv
from exploration import Sink
from reacher_env import make_env
from security import Attack, ArmGeometry, KinematicMonitor
from recovery_monitor import RecoveryMonitor


def main():
    out=Path('outputs/reproduction_20261118_failure_diagnostic')
    out.mkdir(exist_ok=False)
    torch.set_num_threads(1)
    selected=json.loads(Path('outputs/exploratory_20261118/frozen_selection.json').read_text())['selected_grace']
    threshold=json.loads(Path('outputs/main_v1/calibration.json').read_text())['sac_seed_3_sync']['threshold_m']
    model=SAC.load('outputs/sac_seed_3_sync/model.zip',device='cpu')
    env=make_env(); geometry=ArmGeometry.from_model(env.unwrapped.model)
    rows=[]
    with gzip.open(out/'traces.jsonl.gz','wt',encoding='utf-8') as file:
        for kind in ['bias','random_bias']:
            for variant in ['none','original',f'grace{selected}']:
                factory=KinematicMonitor if variant in ['none','original'] else functools.partial(RecoveryMonitor,grace=selected)
                sink=Sink(file,variant)
                row=trial(model,env,geometry,threshold,Attack(kind,.1,20,20,-1,802009+20000000),variant!='none',802009,sink,'sac_seed_3_sync',kind,monitor_factory=factory)
                row.pop('_distances'); row['variant']=variant
                rows.append(row)
    write_csv(out/'episodes.csv',rows)
    env.close()


if __name__=='__main__': main()
