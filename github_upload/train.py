"""Train a clean SAC baseline. A short run checks plumbing, not task success."""
import argparse
import json
import time
import platform
import importlib.metadata
import hashlib
from pathlib import Path

import numpy as np
import torch
from stable_baselines3 import SAC
from stable_baselines3.common.monitor import Monitor

from reacher_env import make_env


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--steps', type=int, default=5000)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--eval-episodes', type=int, default=30)
    parser.add_argument('--out', type=Path, help='New output directory; existing results are never overwritten')
    parser.add_argument('--legacy-sampling', action='store_true')
    parser.add_argument('--max-seconds', type=float, default=1800,
                        help='Wall-clock cap for this training run; partial models are validated too')
    args = parser.parse_args()
    if args.steps < 1 or args.eval_episodes < 1 or args.seed < 0 or args.max_seconds <= 0:
        parser.error('steps/eval-episodes must be positive and seed nonnegative')
    torch.set_num_threads(1)
    out = args.out or Path(__file__).resolve().parent / 'outputs' / f'sac_seed_{args.seed}_sync'
    if out.exists():
        parser.error(f'Output already exists: {out}; choose a new --out directory')
    out.mkdir(parents=True)
    settings = {'seed': args.seed, 'requested_steps': args.steps, 'noise_sigma_m': 0.002,
                'synchronized': not args.legacy_sampling, 'noise_reset': 'only_explicit_noise_seed',
                'episode_steps': 100, 'python': platform.python_version(),
                'packages': {p: importlib.metadata.version(p) for p in
                             ('numpy', 'torch', 'gymnasium', 'mujoco', 'stable-baselines3')}}
    (out / 'training_config.json').write_text(json.dumps(settings, indent=2))
    env = Monitor(make_env(args.seed, synchronized=not args.legacy_sampling), filename=str(out / 'train'))
    model = SAC('MlpPolicy', env, seed=args.seed, device=args.device,
                buffer_size=100000, learning_starts=1000,
                tensorboard_log=str(out / 'tensorboard'), verbose=1)
    started = time.perf_counter()
    def within_budget(_locals, _globals):
        return time.perf_counter() - started < args.max_seconds
    model.learn(total_timesteps=args.steps, callback=within_budget)
    elapsed = time.perf_counter() - started
    model.save(out / 'model')
    env.close()
    model = SAC.load(out / 'model', device=args.device)
    evaluation = make_env(args.seed, synchronized=not args.legacy_sampling)
    trials = []
    for i in range(args.eval_episodes):
        # Validation-only seeds; calibration and held-out tests must use other sets.
        seed = 10000 + args.seed * 1000 + i
        obs, _ = evaluation.reset(seed=seed, options={'noise_seed': seed + 100000})
        distances = []
        for _ in range(100):
            action, _ = model.predict(obs, deterministic=True)
            obs, _, terminated, truncated, info = evaluation.step(action)
            distances.append(info['truth']['distance'])
            if terminated or truncated:
                break
        error = float(np.mean(distances[-10:]))
        trials.append({'seed': seed, 'final_10_mean_distance': error, 'success': error <= 0.03})
    evaluation.close()
    result = {'steps': args.steps, 'seed': args.seed, 'device': args.device,
              'actual_timesteps': model.num_timesteps, 'synchronized': not args.legacy_sampling,
              'wall_clock_cap_seconds': args.max_seconds,
              'stopped_at_time_cap': model.num_timesteps < args.steps,
              'model_sha256': hashlib.sha256((out / 'model.zip').read_bytes()).hexdigest(),
              'training_seconds': elapsed, 'steps_per_second': model.num_timesteps / elapsed,
              'validation_successes': sum(t['success'] for t in trials),
              'validation_episodes': len(trials), 'trials': trials}
    (out / 'validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'trials'}, indent=2))


if __name__ == '__main__':
    main()
