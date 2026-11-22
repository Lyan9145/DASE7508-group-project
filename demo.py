"""Display a trained SAC policy (or random actions) under any registered attack and defense."""
from __future__ import annotations

import argparse
from pathlib import Path
import time

from stable_baselines3 import SAC

from attacks import AttackContext, create_attack, list_attacks
from core.reacher_env import make_env
from core.recovery_monitor import RecoveryMonitor
from core.security import ArmGeometry
from defenses import (
    CalibrationStats,
    DefenseContext,
    create_defense,
    list_defenses,
)


def _default_calibration(threshold_m: float, dt: float) -> CalibrationStats:
    return CalibrationStats(
        threshold_m=float(threshold_m),
        residual_mean_m=0.0025,
        residual_std_m=0.0013,
        residual_p95_m=0.0049,
        residual_p99_m=float(threshold_m),
        q0_jump_p99_rad=0.03,
        q0_jump_p999_rad=0.05,
        q1_jump_p99_rad=0.03,
        q1_jump_p999_rad=0.05,
        control_dt_seconds=float(dt),
        episodes=0,
        seed_base=0,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parent
    parser.add_argument(
        "--model",
        type=Path,
        default=root / "models" / "sac_seed_1_sync" / "model.zip",
        help="SAC model path (default: models/sac_seed_1_sync/model.zip)",
    )
    parser.add_argument(
        "--fallback-model",
        type=Path,
        default=None,
        help="Optional fallback SAC model.zip passed to FallbackPolicyDefense",
    )
    parser.add_argument(
        "--random",
        action="store_true",
        help="Use random actions instead of the trained policy",
    )
    parser.add_argument("--episodes", type=int, default=5)
    parser.add_argument(
        "--attack",
        choices=list_attacks(),
        default="clean",
        help="Registered attack name (default: clean)",
    )
    parser.add_argument("--epsilon", type=float, default=0.1)
    parser.add_argument("--duration", type=int, default=20)
    parser.add_argument("--start", type=int, default=20)
    parser.add_argument(
        "--defense",
        choices=list_defenses(),
        default=None,
        help="Registered defense name (overrides legacy --monitor-threshold default)",
    )
    parser.add_argument(
        "--monitor-threshold",
        type=float,
        default=None,
        help="Frozen calibrated threshold in metres (enables original/grace monitor or sets threshold for --defense)",
    )
    parser.add_argument("--legacy-sampling", action="store_true")
    parser.add_argument(
        "--recovery-grace",
        type=int,
        choices=[1, 3],
        default=None,
        help="Legacy exploratory recovery grace rule; requires --monitor-threshold when --defense is omitted",
    )
    args = parser.parse_args()

    if args.defense is None and args.recovery_grace is not None and args.monitor_threshold is None:
        parser.error("--recovery-grace requires --monitor-threshold")
    if not args.random and not args.model.is_file():
        parser.error(f"Model not found: {args.model}")
    if args.fallback_model is not None and not args.fallback_model.is_file():
        parser.error(f"Fallback model not found: {args.fallback_model}")

    policy = None if args.random else SAC.load(args.model, device="cpu")
    fallback_policy = (
        None if args.fallback_model is None else SAC.load(args.fallback_model, device="cpu")
    )
    env = make_env(render_mode="human", synchronized=not args.legacy_sampling)
    geometry = ArmGeometry.from_model(env.unwrapped.model)
    dt = float(env.unwrapped.dt)
    threshold_m = 0.006 if args.monitor_threshold is None else float(args.monitor_threshold)

    attack = create_attack(
        args.attack,
        epsilon=args.epsilon,
        duration=args.duration,
        start=args.start,
    )
    attack_ctx = AttackContext(
        geometry=geometry,
        dt=dt,
        calibrated_threshold_m=threshold_m,
        policy=policy,
    )
    defense_ctx = DefenseContext(
        geometry=geometry,
        dt=dt,
        calibration=_default_calibration(threshold_m, dt),
        fallback_policy=fallback_policy,
    )

    try:
        for episode in range(args.episodes):
            obs, _ = env.reset(seed=episode, options={"noise_seed": episode})
            attack.reset(seed=episode, sign=1 if episode % 2 == 0 else -1, context=attack_ctx)

            legacy_recovery = None
            defense = None
            if args.defense is not None:
                defense = create_defense(args.defense)
                defense.reset(defense_ctx)
            elif args.monitor_threshold is not None:
                if args.recovery_grace == 3:
                    legacy_recovery = RecoveryMonitor(geometry, threshold_m, dt, grace=3)
                elif args.recovery_grace == 1:
                    defense = create_defense("grace1")
                    defense.reset(defense_ctx)
                else:
                    defense = create_defense("original_fail_stop")
                    defense.reset(defense_ctx)
            else:
                defense = create_defense("no_defense")
                defense.reset(defense_ctx)

            for step in range(100):
                started = time.perf_counter()
                reported = attack.apply(obs, step, attack_ctx).reported_obs
                action_override = None
                if legacy_recovery is not None:
                    policy_obs, status = legacy_recovery.process(reported)
                    if status["abort"]:
                        print(
                            f"Episode {episode}: abort after {status['alarm_streak']} consecutive alarms"
                        )
                        break
                else:
                    assert defense is not None
                    def_res = defense.process(reported, step, defense_ctx)
                    policy_obs = def_res.policy_obs
                    action_override = def_res.action_override
                    if def_res.abort:
                        print(
                            f"Episode {episode}: abort ({def_res.state}) after {def_res.alarm_streak} alarms"
                        )
                        break

                if action_override is not None:
                    action = action_override
                elif policy is not None:
                    action = policy.predict(policy_obs, deterministic=True)[0]
                else:
                    action = env.action_space.sample()

                obs, _, terminated, truncated, _ = env.step(action)
                env.render()
                time.sleep(max(0.0, dt - (time.perf_counter() - started)))
                if terminated or truncated:
                    break
    finally:
        env.close()


if __name__ == "__main__":
    main()
