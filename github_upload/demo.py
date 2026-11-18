"""Display the qualified SAC policy by default, or random actions on request."""
import argparse
import time
from pathlib import Path

from stable_baselines3 import SAC

from reacher_env import make_env
from security import ArmGeometry, Attack, KinematicMonitor


def main():
    parser = argparse.ArgumentParser()
    root = Path(__file__).resolve().parent
    synchronized_model = root / 'outputs' / 'sac_seed_1_sync' / 'model.zip'
    parser.add_argument('--model', type=Path,
                        default=synchronized_model if synchronized_model.is_file() else root / 'outputs' / 'sac_seed_1' / 'model.zip',
                        help='SAC model path (prefers synchronized seed 1 when available)')
    parser.add_argument('--random', action='store_true', help='Use random actions instead of the trained policy')
    parser.add_argument('--episodes', type=int, default=5)
    parser.add_argument('--attack', choices=['clean', 'bias', 'ramp', 'random_bias', 'random_ramp'], default='clean')
    parser.add_argument('--epsilon', type=float, default=0.1)
    parser.add_argument('--duration', type=int, default=20)
    parser.add_argument('--monitor-threshold', type=float, help='Frozen calibrated threshold in metres; enables correction')
    parser.add_argument('--legacy-sampling', action='store_true')
    args = parser.parse_args()
    if not args.random and not args.model.is_file():
        parser.error(f'Model not found: {args.model}')
    policy = None if args.random else SAC.load(args.model, device='cpu')
    env = make_env(render_mode='human', synchronized=not args.legacy_sampling)
    geometry = ArmGeometry.from_model(env.unwrapped.model)
    attack = Attack(args.attack, args.epsilon, args.duration)
    try:
        for episode in range(args.episodes):
            obs, _ = env.reset(seed=episode, options={'noise_seed': episode})
            monitor = KinematicMonitor(geometry, args.monitor_threshold, env.unwrapped.dt) if args.monitor_threshold is not None else None
            for step in range(100):
                started = time.perf_counter()
                reported = attack.apply(obs, step)
                if monitor is not None:
                    reported, status = monitor.process(reported)
                    if status['abort']:
                        print(f'Episode {episode}: abort after {status["alarm_streak"]} consecutive alarms')
                        break
                action = policy.predict(reported, deterministic=True)[0] if policy else env.action_space.sample()
                obs, _, terminated, truncated, _ = env.step(action)
                env.render()
                time.sleep(max(0, env.unwrapped.dt - (time.perf_counter() - started)))
                if terminated or truncated:
                    break
    finally:
        env.close()


if __name__ == '__main__':
    main()
