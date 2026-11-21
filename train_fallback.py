"""Train a masked-observation SAC fallback policy for FallbackPolicyDefense.

The policy network zeroes the listed observation channels inside its features
extractor (``defenses.policy_level.MaskedObservationExtractor``), so it never
depends on them. The default masks the joint-0 encoder ``(cos q0, sin q0)``
(indices ``0 2``): joint 0 is then implied by the independent fingertip-position
channel and joint 1, so spoofing the joint-0 encoder cannot change the
fallback's actions. Also masking joint-0 velocity (``0 2 6``) was tried and
rejected: without it the policy cannot damp joint 0 and settled in only 4/30
validation episodes. The saved ``model.zip`` takes the normal 10-dimensional
observation and is passed to ``run_matrix.py --fallback-model``.

Example (77-101 minutes per seed on one CPU thread of a shared server in the dev runs):
    python train_fallback.py --seed 1 --steps 150000 --out outputs/fallback_seed_1_001
"""
import argparse
import hashlib
import importlib.metadata
import json
import platform
import time
from pathlib import Path

import numpy as np
import torch
from stable_baselines3 import SAC
from stable_baselines3.common.monitor import Monitor

from core.reacher_env import make_env
from defenses.policy_level import MaskedObservationExtractor


def validate(model, seed, episodes, synchronized, masked_indices):
    """Clean 100-step validation plus a check that masked channels are ignored."""
    env = make_env(seed, synchronized=synchronized)
    rng = np.random.default_rng(seed)
    trials = []
    max_masked_action_diff = 0.0
    for i in range(episodes):
        # Same validation-only seed convention as train.py; calibration and
        # held-out Phase-2 tests use disjoint blocks.
        ep_seed = 10000 + seed * 1000 + i
        obs, _ = env.reset(seed=ep_seed, options={'noise_seed': ep_seed + 100000})
        distances = []
        for _ in range(100):
            action, _ = model.predict(obs, deterministic=True)
            scrambled = np.array(obs, copy=True)
            scrambled[list(masked_indices)] = rng.uniform(-3.0, 3.0, len(masked_indices))
            scrambled_action, _ = model.predict(scrambled, deterministic=True)
            max_masked_action_diff = max(
                max_masked_action_diff, float(np.max(np.abs(action - scrambled_action)))
            )
            obs, _, terminated, truncated, info = env.step(action)
            distances.append(info['truth']['distance'])
            if terminated or truncated:
                break
        error = float(np.mean(distances[-10:]))
        trials.append({'seed': ep_seed, 'final_10_mean_distance': error, 'success': error <= 0.03})
    env.close()
    return trials, max_masked_action_diff


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--steps', type=int, default=150000)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--mask-indices', type=int, nargs='+', default=[0, 2],
                        help='Observation indices hidden from the policy (default: 0 2)')
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--eval-episodes', type=int, default=30)
    parser.add_argument('--out', type=Path, required=True,
                        help='New output directory; existing results are never overwritten')
    parser.add_argument('--legacy-sampling', action='store_true')
    parser.add_argument('--max-seconds', type=float, default=10800,
                        help='Wall-clock cap for training; partial models are validated too')
    args = parser.parse_args()
    if args.steps < 1 or args.eval_episodes < 1 or args.seed < 0 or args.max_seconds <= 0:
        parser.error('steps/eval-episodes/max-seconds must be positive and seed nonnegative')
    if any(i < 0 or i >= 10 for i in args.mask_indices):
        parser.error('mask indices must lie in [0, 10)')
    masked = sorted(set(args.mask_indices))
    if any(i in masked for i in (4, 5, 8, 9)):
        parser.error('target (4, 5) and fingertip-target (8, 9) channels cannot be masked')
    if args.out.exists():
        parser.error(f'Output already exists: {args.out}; choose a new --out directory')

    torch.set_num_threads(1)
    args.out.mkdir(parents=True)
    synchronized = not args.legacy_sampling
    settings = {
        'seed': args.seed, 'requested_steps': args.steps, 'noise_sigma_m': 0.002,
        'synchronized': synchronized, 'noise_reset': 'only_explicit_noise_seed',
        'episode_steps': 100, 'masked_indices': masked,
        'features_extractor': 'defenses.policy_level.MaskedObservationExtractor',
        'purpose': 'FallbackPolicyDefense backup policy independent of masked channels',
        'python': platform.python_version(),
        'packages': {p: importlib.metadata.version(p) for p in
                     ('numpy', 'torch', 'gymnasium', 'mujoco', 'stable-baselines3')},
    }
    (args.out / 'training_config.json').write_text(json.dumps(settings, indent=2))

    env = Monitor(make_env(args.seed, synchronized=synchronized), filename=str(args.out / 'train'))
    model = SAC(
        'MlpPolicy', env, seed=args.seed, device=args.device,
        buffer_size=100000, learning_starts=1000,
        policy_kwargs={
            'features_extractor_class': MaskedObservationExtractor,
            'features_extractor_kwargs': {'masked_indices': masked},
        },
        tensorboard_log=str(args.out / 'tensorboard'), verbose=1,
    )
    started = time.perf_counter()

    def within_budget(_locals, _globals):
        return time.perf_counter() - started < args.max_seconds

    model.learn(total_timesteps=args.steps, callback=within_budget)
    elapsed = time.perf_counter() - started
    model.save(args.out / 'model')
    env.close()

    model = SAC.load(args.out / 'model', device=args.device)
    trials, masked_diff = validate(model, args.seed, args.eval_episodes, synchronized, masked)
    result = {
        'steps': args.steps, 'seed': args.seed, 'device': args.device,
        'actual_timesteps': model.num_timesteps, 'synchronized': synchronized,
        'masked_indices': masked,
        'wall_clock_cap_seconds': args.max_seconds,
        'stopped_at_time_cap': model.num_timesteps < args.steps,
        'model_sha256': hashlib.sha256((args.out / 'model.zip').read_bytes()).hexdigest(),
        'training_seconds': elapsed, 'steps_per_second': model.num_timesteps / elapsed,
        'validation_successes': sum(t['success'] for t in trials),
        'validation_episodes': len(trials),
        'max_action_change_when_masked_channels_scrambled': masked_diff,
        'trials': trials,
    }
    (args.out / 'validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'trials'}, indent=2))


if __name__ == '__main__':
    main()
