"""Generate inspection figures from completed, immutable evaluation outputs."""
import argparse
import csv
import gzip
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    summary = json.loads((args.run / 'summary.json').read_text())
    config = json.loads((args.run / 'config.json').read_text())
    policies = sorted({r['policy'] for r in summary})
    cases = sorted({r['case'] for r in summary if r['case'] != 'clean'})
    figures = args.run / 'figures'; figures.mkdir(exist_ok=True)
    aggregated = []
    for case in ['clean'] + cases:
        for defense in (False, True):
            rows = [r for r in summary if r['case'] == case and r['monitor_on'] == defense]
            result = {'case': case, 'monitor_on': defense, 'policies': len(rows)}
            for metric in ('task_success_rate', 'attack_success_rate', 'mean_final_error_m',
                           'paired_window_mean_delta_m', 'paired_window_max_delta_m', 'abort_rate'):
                values = [r[metric] for r in rows if r[metric] is not None]
                for label, function in [('mean', np.mean), ('min', np.min), ('max', np.max)]:
                    result[f'{metric}_{label}'] = float(function(values)) if values else None
            aggregated.append(result)
    with (args.run / 'aggregate.csv').open('w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(aggregated[0]))
        writer.writeheader(); writer.writerows(aggregated)
    fig, axes = plt.subplots(len(policies), 2, figsize=(13, max(5, 4*len(policies))), squeeze=False,
                             constrained_layout=True)
    for index, policy in enumerate(policies):
        for column, (metric, title, scale) in enumerate([
                ('attack_success_rate', 'Clean-successful trials made to fail (%)', 100),
                ('paired_window_mean_delta_m', 'Extra mean target distance in attack + 10 steps (cm)', 100)]):
            matrix = np.array([[next(r[metric] for r in summary if r['policy'] == policy and
                                     r['case'] == case and r['monitor_on'] == defense)
                                for case in cases] for defense in (False, True)], dtype=float)*scale
            ax = axes[index, column]
            limit = max(float(np.nanmax(np.abs(matrix))), 0.1)
            heat = ax.imshow(matrix, aspect='auto', cmap='YlOrRd' if column==0 else 'coolwarm',
                             vmin=0 if column==0 else -limit, vmax=100 if column==0 else limit)
            ax.set_yticks([0,1], ['Monitor off','Monitor on'])
            ax.set_xticks(range(len(cases)), cases, rotation=90, fontsize=7)
            ax.set_title(f'{policy}: {title}', fontsize=10)
            fig.colorbar(heat, ax=ax, shrink=0.7)
    fig.suptitle(f'{config["phase"].upper()} — {config["episodes"]} paired initial states per policy')
    fig.savefig(figures / 'paired_results.png', dpi=170)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(11,4), constrained_layout=True)
    for ax, kind in zip(axes, ('bias', 'ramp')):
        for policy_index, policy in enumerate(policies):
            for duration in config['durations']:
                probabilities = []
                for epsilon in config['epsilons']:
                    row = next(r for r in summary if r['policy']==policy and r['monitor_on'] and
                               r['case']==f'{kind}_e{epsilon:g}_d{duration}')
                    probabilities.append(100*(1-row['missed_detections']/row['episodes']))
                ax.plot(config['epsilons'],probabilities,marker='o',color=f'C{policy_index}',
                        ls='--' if duration==5 else '-',label=f'{policy}, {duration} steps')
        ax.set_title(kind); ax.set_xlabel('Maximum angle offset (rad)')
        ax.set_ylabel('At least one in-window alarm (%)'); ax.set_ylim(-3,103)
        ax.set_xticks(config['epsilons']); ax.grid(alpha=0.2); ax.legend(fontsize=7)
    fig.suptitle('Detection probability; includes noise-triggered alarms inside the attack window')
    fig.savefig(figures / 'detection_rates.png',dpi=170); plt.close(fig)
    traces = args.run / 'traces.jsonl.gz'
    if traces.exists():
        selected = policies[0]
        seed = config['test_base']
        by_case = {}
        with gzip.open(traces, 'rt') as file:
            for line in file:
                row = json.loads(line)
                if row['policy'] == selected and row['seed'] == seed and (
                    (row['case']=='clean' and not row['monitor_on']) or
                    row['case']=='bias_e0.1_d20'):
                    by_case.setdefault((row['case'], row['monitor_on']), []).append(row)
        if len(by_case) >= 3:
            fig, axes = plt.subplots(3, 1, figsize=(10,8), sharex=True, constrained_layout=True)
            for (case, defense), rows in sorted(by_case.items()):
                label = 'Clean' if case == 'clean' else 'Bias + monitor' if defense else 'Bias only'
                steps = [r['observation_step'] for r in rows if r['truth_after']]
                distances = [r['truth_after']['distance']*100 for r in rows if r['truth_after']]
                axes[0].plot(steps, distances, label=label)
                if case != 'clean':
                    axes[1].plot([r['observation_step'] for r in rows],
                                 [float(np.angle(complex(r['policy_sensor'][0],r['policy_sensor'][2]) /
                                                 complex(r['raw_sensor'][0],r['raw_sensor'][2]))) for r in rows],label=label)
                if defense:
                    axes[2].plot([r['observation_step'] for r in rows],
                                 [r['monitor']['residual_m']*1000 for r in rows],label='Raw residual')
                    cal = json.loads((args.run / 'calibration.json').read_text())[selected]
                    axes[2].axhline(cal['threshold_m']*1000,color='black',ls='--',label='Frozen threshold')
                    alarms = [r for r in rows if r['monitor']['alarm']]
                    axes[2].scatter([r['observation_step'] for r in alarms],
                                    [r['monitor']['residual_m']*1000 for r in alarms],s=12,c='red',label='Alarm')
            axes[0].axhline(3,color='grey',ls=':',label='3 cm task criterion')
            for ax in axes:
                ax.axvspan(config['start'],config['start']+20,color='orange',alpha=0.12)
                ax.legend(fontsize=8); ax.grid(alpha=0.2)
            axes[0].set_ylabel('True target distance (cm)')
            axes[1].set_ylabel('Applied joint0 error (rad)')
            axes[2].set_ylabel('Kinematic residual (mm)'); axes[2].set_xlabel('Control step (zero indexed)')
            fig.suptitle(f'{selected}, seed {seed}: bias 0.1 rad for 20 steps')
            fig.savefig(figures / 'example_trajectory.png',dpi=170)
            plt.close(fig)
    print(f'Figures and per-policy aggregate: {args.run}')


if __name__ == '__main__':
    main()
