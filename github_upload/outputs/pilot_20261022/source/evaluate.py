"""Paired sensor-spoofing experiments. Truth is consumed only by the evaluator."""
import argparse
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import time

import numpy as np
import torch
from stable_baselines3 import SAC

from reacher_env import make_env
from security import ArmGeometry, Attack, KinematicMonitor


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')


def write_csv(path, rows):
    if not rows:
        return
    with path.open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def calibrate(model, geometry, episodes, seed_base, noise_sigma):
    residuals = []
    env = make_env(noise_sigma=noise_sigma)
    try:
        for index in range(episodes):
            seed = seed_base + index
            obs, _ = env.reset(seed=seed, options={'noise_seed': seed + 10000000})
            for step in range(100):
                residuals.append(geometry.residual(obs))
                action, _ = model.predict(obs, deterministic=True)
                obs, _, terminated, truncated, _ = env.step(action)
                if terminated or truncated:
                    break
    finally:
        env.close()
    return {'threshold_m': float(np.quantile(residuals, 0.99, method='linear')),
            'quantile': 0.99, 'quantile_method': 'linear',
            'episodes': episodes, 'step_residuals': len(residuals),
            'seed_base': seed_base, 'seeds': list(range(seed_base, seed_base + episodes)),
            'residual_mean_m': float(np.mean(residuals)),
            'residual_max_m': float(np.max(residuals)),
            'initial_observation': 'included in calibration; used only for initialization during detection'}


def recovery_time(distances, attack):
    # distances[k] is true distance at observation k; return first entry into a
    # five-observation successful interval, measured from the window end.
    end = attack.start + attack.duration
    for step in range(end, len(distances) - 4):
        if max(distances[step:step + 5]) <= 0.03:
            return step - end
    return None


def trial(model, env, geometry, threshold, attack, monitor_on, seed, trace_file,
          policy_name, case_name, noise_seed=None):
    noise_seed = seed + 10000000 if noise_seed is None else noise_seed
    obs, info = env.reset(seed=seed, options={'noise_seed': noise_seed})
    monitor = KinematicMonitor(geometry, threshold, env.unwrapped.dt)
    distances = [info['truth']['distance']]
    action_norms, residuals, alarm_steps, timings = [], [], [], []
    aborted = False
    for step in range(100):
        reported = attack.apply(obs, step)
        started = time.perf_counter_ns()
        corrected, status = monitor.process(reported)
        duration_ns = time.perf_counter_ns() - started
        policy_obs = corrected if monitor_on else reported
        if step:
            residuals.append(status['residual_m'])
            if monitor_on:
                timings.append(duration_ns)
                if status['alarm']:
                    alarm_steps.append(step)
        aborted = bool(monitor_on and status['abort'])
        record = {'policy': policy_name, 'case': case_name, 'monitor_on': monitor_on,
                  'seed': seed, 'noise_seed': noise_seed, 'observation_step': step,
                  'delta_rad': attack.delta(step), 'raw_sensor': obs.tolist(),
                  'reported_sensor': reported.tolist(), 'policy_sensor': policy_obs.tolist(),
                  'truth_before': info['truth'],
                  'monitor': status if monitor_on else None,
                  'monitor_ns': duration_ns if monitor_on else None,
                  'action': None, 'truth_after': None}
        if not aborted:
            action, _ = model.predict(policy_obs, deterministic=True)
            action_norms.append(float(np.sum(np.square(action))))
            obs, _, terminated, truncated, info = env.step(action)
            distances.append(info['truth']['distance'])
            record['action'] = action.tolist()
            record['truth_after'] = info['truth']
        if trace_file is not None:
            trace_file.write(json.dumps(record, allow_nan=False) + '\n')
        if aborted or terminated or truncated:
            break
    end = attack.start + attack.duration
    # Post-action distances for commands in the attack window and next 10 steps.
    window = distances[attack.start + 1:min(end + 11, len(distances))]
    relevant_alarms = [t for t in alarm_steps if attack.start <= t < end]
    final_mean = float(np.mean(distances[-10:]))
    return {'policy': policy_name, 'case': case_name, 'monitor_on': monitor_on,
            '_distances': distances,
            'seed': seed, 'noise_seed': noise_seed, 'attack_kind': attack.kind,
            'epsilon_rad': attack.epsilon, 'duration': attack.duration,
            'sign': attack.sign, 'attack_start': attack.start,
            'steps': len(action_norms), 'aborted': aborted,
            'task_success': bool(not aborted and len(action_norms) == 100 and final_mean <= 0.03),
            'final_10_mean_distance_m': final_mean, 'terminal_distance_m': distances[-1],
            'window_mean_distance_m': float(np.mean(window)) if window else None,
            'window_max_distance_m': max(window) if window else None,
            'window_samples': len(window),
            'window_complete': len(window) == attack.duration + 10,
            'control_effort': sum(action_norms),
            'alarm_count': len(alarm_steps), 'detection_steps': len(residuals),
            'any_alarm': bool(alarm_steps),
            'detection_delay_steps': relevant_alarms[0] - attack.start if relevant_alarms else None,
            'missed_detection': bool(monitor_on and attack.kind != 'clean' and not relevant_alarms),
            'recovery_steps': None if aborted or attack.kind == 'clean' else recovery_time(distances, attack),
            'monitor_total_ns': sum(timings), 'monitor_calls': len(timings),
            'monitor_median_us': float(np.median(timings) / 1000) if timings else None,
            'monitor_p95_us': float(np.quantile(timings, 0.95) / 1000) if timings else None}


def summarize(rows):
    clean = {(r['policy'], r['seed']): r for r in rows
             if r['case'] == 'clean' and not r['monitor_on']}
    summary = []
    groups = sorted({(r['policy'], r['case'], r['monitor_on']) for r in rows})
    for policy, case, monitor_on in groups:
        group = [r for r in rows if (r['policy'], r['case'], r['monitor_on']) ==
                 (policy, case, monitor_on)]
        eligible = [r for r in group if clean[(policy, r['seed'])]['task_success']]
        delays = [r['detection_delay_steps'] for r in group if r['detection_delay_steps'] is not None]
        recoveries = [r['recovery_steps'] for r in group if r['recovery_steps'] is not None]
        corrupt = group[0]['attack_kind'] != 'clean'
        def mean(key):
            values = [r[key] for r in group if r[key] is not None]
            return float(np.mean(values)) if values else None
        clean_success = np.mean([clean[(policy, r['seed'])]['task_success'] for r in group])
        mean_window_delta, max_window_delta = [], []
        for row in group:
            baseline = clean[(policy, row['seed'])]
            # Filled by main after matching the identical clean trajectory window.
            if row.get('paired_window_mean_delta_m') is not None:
                mean_window_delta.append(row['paired_window_mean_delta_m'])
                max_window_delta.append(row['paired_window_max_delta_m'])
        summary.append({'policy': policy, 'case': case, 'monitor_on': monitor_on,
                        'episodes': len(group), 'successes': sum(r['task_success'] for r in group),
                        'task_success_rate': float(np.mean([r['task_success'] for r in group])),
                        'paired_success_difference_vs_clean': float(np.mean([r['task_success'] for r in group]) - clean_success),
                        'clean_success_denominator': len(eligible),
                        'attack_success_rate': (sum(not r['task_success'] for r in eligible) / len(eligible)) if eligible and corrupt else None,
                        'mean_final_error_m': mean('final_10_mean_distance_m'),
                        'mean_window_distance_m': mean('window_mean_distance_m'),
                        'mean_window_max_distance_m': mean('window_max_distance_m'),
                        'paired_window_mean_delta_m': float(np.mean(mean_window_delta)) if mean_window_delta else None,
                        'paired_window_max_delta_m': float(np.mean(max_window_delta)) if max_window_delta else None,
                        'mean_control_effort': mean('control_effort'),
                        'abort_rate': float(np.mean([r['aborted'] for r in group])),
                        'clean_false_alarm_step_rate': sum(r['alarm_count'] for r in group) / max(1, sum(r['detection_steps'] for r in group)) if case == 'clean' and monitor_on else None,
                        'clean_false_alarm_episode_rate': mean('any_alarm') if case == 'clean' and monitor_on else None,
                        'missed_detections': sum(r['missed_detection'] for r in group) if corrupt and monitor_on else None,
                        'mean_detection_delay_steps': float(np.mean(delays)) if delays else None,
                        'recovered_episodes': len(recoveries) if corrupt else None,
                        'unrecovered_or_aborted_episodes': len(group) - len(recoveries) if corrupt else None,
                        'mean_recovery_steps': float(np.mean(recoveries)) if recoveries else None,
                        'mean_monitor_us': sum(r['monitor_total_ns'] for r in group) / max(1, sum(r['monitor_calls'] for r in group)) / 1000 if monitor_on else None})
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models', nargs='+', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--episodes', type=int, default=6)
    parser.add_argument('--calibration-episodes', type=int, default=100)
    parser.add_argument('--epsilons', type=float, nargs='+', default=[0.02, 0.05, 0.10])
    parser.add_argument('--durations', type=int, nargs='+', default=[5, 20])
    parser.add_argument('--start', type=int, default=20)
    parser.add_argument('--noise-sigma', type=float, default=0.002)
    parser.add_argument('--calibration-base', type=int, default=200000)
    parser.add_argument('--test-base', type=int, default=500000)
    parser.add_argument('--phase', choices=['pilot', 'main'], default='pilot')
    parser.add_argument('--no-traces', action='store_true')
    args = parser.parse_args()
    if args.episodes < 2 or args.episodes % 2 or args.calibration_episodes < 1:
        parser.error('Use a positive even number of test episodes and positive calibration episodes')
    if args.start < 1 or any(d < 1 or args.start + d + 10 > 100 for d in args.durations):
        parser.error('Attack and following 10 steps must fit inside the 100-step episode')
    if any(e <= 0 or not np.isfinite(e) for e in args.epsilons):
        parser.error('epsilons must be positive finite values')
    if len({p.resolve() for p in args.models}) != len(args.models):
        parser.error('Duplicate model paths')
    if len({p.parent.name for p in args.models}) != len(args.models):
        parser.error('Models must have unique parent directory names')
    if args.episodes > 1000 or args.calibration_episodes > 1000:
        parser.error('At most 1000 episodes per seed block')
    for index in range(len(args.models)):
        validation = set(range(10000 + (index + 1) * 1000, 10000 + (index + 1) * 1000 + 30))
        calibration = set(range(args.calibration_base + index * 1000, args.calibration_base + index * 1000 + args.calibration_episodes))
        tests = set(range(args.test_base + index * 1000, args.test_base + index * 1000 + args.episodes))
        if calibration & tests or validation & calibration or validation & tests:
            parser.error('Validation, calibration and test seeds must be disjoint')
    if args.phase == 'main':
        if len(args.models) != 3 or args.episodes != 30 or args.calibration_episodes != 100:
            parser.error('Main study requires 3 models, 30 tests and 100 calibration episodes each')
        if args.epsilons != [0.02, 0.05, 0.10] or args.durations != [5, 20] or args.start != 20:
            parser.error('Main study must use the proposal sweep')
        training_seeds = []
        for path in args.models:
            validation = json.loads((path.parent / 'validation.json').read_text())
            if validation['validation_episodes'] < 30 or validation['validation_successes'] < 24 or not validation.get('synchronized'):
                parser.error(f'Model not qualified under synchronized sampling: {path}')
            if validation.get('model_sha256') != hashlib.sha256(path.read_bytes()).hexdigest():
                parser.error(f'Model does not match its validation artifact: {path}')
            training_seeds.append(validation['seed'])
        if len(set(training_seeds)) != 3:
            parser.error('Main study needs three distinct training seeds')
    if args.out.exists():
        parser.error('Output directory exists; use a new directory')
    args.out.mkdir(parents=True)
    torch.set_num_threads(1)
    config = {k: [str(x.resolve()) for x in v] if k == 'models' else str(v.resolve()) if isinstance(v, Path) else v
              for k, v in vars(args).items()}
    config.update({'started_utc': datetime.now(timezone.utc).isoformat(),
                   'python': platform.python_version(), 'platform': platform.platform(),
                   'packages': {p: importlib.metadata.version(p) for p in
                                ('torch', 'numpy', 'gymnasium', 'mujoco', 'stable-baselines3')},
                   'random_control': 'independent +/- sign each observation, same amplitude envelope',
                   'ramp': 'epsilon*(window_index+1)/duration',
                   'sign_balance': 'alternating +/- across paired initial states',
                   'initialization': 'observation 0 known clean, estimator initialization only',
                   'success': '100 actions, no abort, last 10 post-action true distances mean <= 0.03m',
                   'synchronized': True,
                   'model_sha256': {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in args.models}})
    config['implementation_sha256'] = {
        name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        for name in ('evaluate.py', 'security.py', 'reacher_env.py', 'train.py')}
    git = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True)
    config['git_head'] = git.stdout.strip()
    write_json(args.out / 'config.json', config)
    # Snapshot exact implementation, because a dirty Git HEAD alone is insufficient.
    source = args.out / 'source'; source.mkdir()
    for name in ('evaluate.py', 'security.py', 'reacher_env.py', 'train.py'):
        (source / name).write_bytes(Path(__file__).with_name(name).read_bytes())
    records, calibration_records = [], {}
    trace_file = None if args.no_traces else gzip.open(args.out / 'traces.jsonl.gz', 'wt', encoding='utf-8')
    started = time.perf_counter()
    try:
        for index, path in enumerate(args.models):
            name = path.parent.name
            model = SAC.load(path, device='cpu')
            env = make_env(noise_sigma=args.noise_sigma)
            geometry = ArmGeometry.from_model(env.unwrapped.model)
            cal = calibrate(model, geometry, args.calibration_episodes,
                            args.calibration_base + index * 1000, args.noise_sigma)
            cal['geometry'] = geometry.to_dict()
            calibration_records[name] = cal
            write_json(args.out / 'calibration.json', calibration_records)
            print(f'{name}: threshold {cal["threshold_m"]:.6f} m', flush=True)
            try:
                for episode in range(args.episodes):
                    seed = args.test_base + index * 1000 + episode
                    sign = 1 if episode % 2 == 0 else -1
                    cases = [('clean', Attack())]
                    for epsilon in args.epsilons:
                        for duration in args.durations:
                            for kind in ('bias', 'ramp', 'random_bias', 'random_ramp'):
                                attack = Attack(kind, epsilon, duration, args.start, sign, seed + 20000000)
                                cases.append((f'{kind}_e{epsilon:g}_d{duration}', attack))
                    # Identical seed/noise/attack schedule for each paired condition.
                    clean_distances = None
                    for case, attack in cases:
                        for monitor_on in (False, True):
                            row = trial(model, env, geometry, cal['threshold_m'], attack,
                                        monitor_on, seed, trace_file, name, case)
                            distances = row.pop('_distances')
                            if case == 'clean' and not monitor_on:
                                clean_distances = distances[1:]
                            reference = clean_distances[row['attack_start']:
                                                        row['attack_start'] + row['window_samples']]
                            row['paired_window_mean_delta_m'] = (row['window_mean_distance_m'] - float(np.mean(reference))) if reference else None
                            row['paired_window_max_delta_m'] = (row['window_max_distance_m'] - max(reference)) if reference else None
                            records.append(row)
                    print(f'{name}: paired initial state {episode + 1}/{args.episodes}', flush=True)
            finally:
                env.close()
    finally:
        if trace_file is not None:
            trace_file.close()
        write_csv(args.out / 'episodes.csv', records)
    summary = summarize(records)
    write_csv(args.out / 'summary.csv', summary)
    write_json(args.out / 'summary.json', summary)
    write_json(args.out / 'run_status.json', {'complete': True, 'phase': args.phase,
                'evaluation_episodes': len(records),
                'calibration_episodes': args.calibration_episodes * len(args.models),
                'elapsed_seconds': time.perf_counter() - started})
    print(f'Complete: {len(records)} paired evaluation episodes in {time.perf_counter()-started:.1f}s', flush=True)


if __name__ == '__main__':
    main()
