"""Train a clean SAC baseline. A short run checks plumbing, not task success."""
import argparse
import json
import time
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
    args = parser.parse_args()
    torch.set_num_threads(1)
    out = Path('outputs') / f'sac_seed_{args.seed}'
    out.mkdir(parents=True, exist_ok=True)
    env = Monitor(make_env(args.seed), filename=str(out / 'train'))
    model = SAC('MlpPolicy', env, seed=args.seed, device=args.device,
                buffer_size=100000, learning_starts=1000,
                tensorboard_log=str(out / 'tensorboard'), verbose=1)
    started = time.perf_counter()
    model.learn(total_timesteps=args.steps)
    elapsed = time.perf_counter() - started
    model.save(out / 'model')
    env.close()
    model = SAC.load(out / 'model', device=args.device)
    evaluation = make_env(args.seed)
    trials = []
    for i in range(args.eval_episodes):
        # Validation-only seeds; calibration and held-out tests must use other sets.
        seed = 10000 + args.seed * 1000 + i
        obs, _ = evaluation.reset(seed=seed, options={'noise_seed': seed + 100000})
        distances = []
        for _ in range(100):
            action, _ = model.predict(obs, deterministic=True)
            obs, _, terminated, truncated, _ = evaluation.step(action)
            base = evaluation.unwrapped
            distances.append(float(np.linalg.norm(
                base.get_body_com('fingertip')[:2] - base.get_body_com('target')[:2])))
            if terminated or truncated:
                break
        error = float(np.mean(distances[-10:]))
        trials.append({'seed': seed, 'final_10_mean_distance': error, 'success': error <= 0.03})
    evaluation.close()
    result = {'steps': args.steps, 'seed': args.seed, 'device': args.device,
              'training_seconds': elapsed, 'steps_per_second': args.steps / elapsed,
              'validation_successes': sum(t['success'] for t in trials),
              'validation_episodes': len(trials), 'trials': trials}
    (out / 'validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'trials'}, indent=2))


if __name__ == '__main__':
    main()
