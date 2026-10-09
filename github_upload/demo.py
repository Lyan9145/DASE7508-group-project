"""Display the qualified SAC policy by default, or random actions on request."""
import argparse
import time
from pathlib import Path

from stable_baselines3 import SAC

from reacher_env import make_env


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=Path,
                        default=Path(__file__).resolve().parent / 'outputs' / 'sac_seed_1' / 'model.zip',
                        help='SAC model path (default: successful seed 1 model)')
    parser.add_argument('--random', action='store_true', help='Use random actions instead of the trained policy')
    parser.add_argument('--episodes', type=int, default=5)
    args = parser.parse_args()
    if not args.random and not args.model.is_file():
        parser.error(f'Model not found: {args.model}')
    policy = None if args.random else SAC.load(args.model, device='cpu')
    env = make_env(render_mode='human')
    try:
        for episode in range(args.episodes):
            obs, _ = env.reset(seed=episode, options={'noise_seed': episode})
            for _ in range(100):
                started = time.perf_counter()
                action = policy.predict(obs, deterministic=True)[0] if policy else env.action_space.sample()
                obs, _, terminated, truncated, _ = env.step(action)
                env.render()
                time.sleep(max(0, env.unwrapped.dt - (time.perf_counter() - started)))
                if terminated or truncated:
                    break
    finally:
        env.close()


if __name__ == '__main__':
    main()
