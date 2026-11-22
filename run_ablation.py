"""CLI entry point for Direction 4A velocity- and position-noise ablations."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import time

from evaluation import (
    collect_seed_set,
    resolve_ablation_seed_bases,
    run_position_noise_ablation,
    run_velocity_noise_ablation,
    validate_disjoint_seeds,
    write_json,
)
from evaluation.ablation import _resolve_ablation_defaults


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["velocity", "position", "both"],
        default="both",
        help="Which noise ablation sweep to execute (default: both)",
    )
    parser.add_argument(
        "--preset",
        choices=["smoke", "full"],
        default="smoke",
        help="Sweep size preset (default: smoke)",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        type=Path,
        default=None,
        help="Policy model.zip paths (defaults to preset models)",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=None,
        help="Test episodes per policy per sigma (defaults to preset)",
    )
    parser.add_argument(
        "--calibration-episodes",
        type=int,
        default=None,
        help="Clean calibration episodes per policy per sigma (defaults to preset)",
    )
    for mode in ("velocity", "position"):
        parser.add_argument(
            f"--{mode}-seed-base",
            type=int,
            help=f"Evaluation seed base for the {mode} sweep",
        )
        parser.add_argument(
            f"--{mode}-cal-base",
            type=int,
            help=f"Calibration seed base for the {mode} sweep",
        )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="New output directory (must not already exist)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.out.exists():
        parser.error(f"Output directory exists; use a new directory: {args.out}")

    velocity_seeds = {
        key: value for key, value in (
            ("seed_base", args.velocity_seed_base), ("cal_base", args.velocity_cal_base)
        ) if value is not None
    }
    position_seeds = {
        key: value for key, value in (
            ("seed_base", args.position_seed_base), ("cal_base", args.position_cal_base)
        ) if value is not None
    }
    if args.mode == "velocity" and position_seeds:
        parser.error("Position seed options require --mode position or both")
    if args.mode == "position" and velocity_seeds:
        parser.error("Velocity seed options require --mode velocity or both")
    if any(seed < 0 for seed in (*velocity_seeds.values(), *position_seeds.values())):
        parser.error("Seed bases must be nonnegative")

    try:
        model_paths, resolved_episodes, resolved_cal_episodes = _resolve_ablation_defaults(
            models=args.models,
            preset=args.preset,
            episodes=args.episodes,
            calibration_episodes=args.calibration_episodes,
        )
        if args.mode == "velocity":
            run_velocity_noise_ablation(
                models=args.models,
                out=args.out,
                preset=args.preset,
                episodes=args.episodes,
                calibration_episodes=args.calibration_episodes,
                **velocity_seeds,
            )
        elif args.mode == "position":
            run_position_noise_ablation(
                models=args.models,
                out=args.out,
                preset=args.preset,
                episodes=args.episodes,
                calibration_episodes=args.calibration_episodes,
                **position_seeds,
            )
        else:
            vel_cal_base, vel_seed_base = resolve_ablation_seed_bases(
                mode="velocity",
                preset=args.preset,
                seed_base=args.velocity_seed_base,
                cal_base=args.velocity_cal_base,
            )
            pos_cal_base, pos_seed_base = resolve_ablation_seed_bases(
                mode="position",
                preset=args.preset,
                seed_base=args.position_seed_base,
                cal_base=args.position_cal_base,
            )
            n_models = len(model_paths)
            vel_cal = collect_seed_set(vel_cal_base, resolved_cal_episodes, n_models)
            vel_eval = collect_seed_set(vel_seed_base, resolved_episodes, n_models)
            pos_cal = collect_seed_set(pos_cal_base, resolved_cal_episodes, n_models)
            pos_eval = collect_seed_set(pos_seed_base, resolved_episodes, n_models)
            validate_disjoint_seeds(vel_cal, vel_eval, pos_cal, pos_eval)
            validate_disjoint_seeds(pos_cal, pos_eval)

            started = time.perf_counter()
            args.out.mkdir(parents=True, exist_ok=False)
            vel_dir = args.out / "velocity"
            pos_dir = args.out / "position"
            write_json(
                args.out / "config.json",
                {
                    "started_utc": datetime.now(timezone.utc).isoformat(),
                    "mode": "both",
                    "preset": args.preset,
                    "velocity_dir": "velocity",
                    "position_dir": "position",
                },
            )
            vel_res = run_velocity_noise_ablation(
                models=args.models,
                out=vel_dir,
                preset=args.preset,
                episodes=args.episodes,
                calibration_episodes=args.calibration_episodes,
                **velocity_seeds,
            )
            pos_res = run_position_noise_ablation(
                models=args.models,
                out=pos_dir,
                preset=args.preset,
                episodes=args.episodes,
                calibration_episodes=args.calibration_episodes,
                **position_seeds,
            )
            write_json(
                args.out / "run_status.json",
                {
                    "complete": True,
                    "mode": "both",
                    "preset": args.preset,
                    "evaluation_episodes": (
                        vel_res["status"]["evaluation_episodes"]
                        + pos_res["status"]["evaluation_episodes"]
                    ),
                    "calibration_episodes": (
                        vel_res["status"]["calibration_episodes"]
                        + pos_res["status"]["calibration_episodes"]
                    ),
                    "elapsed_seconds": time.perf_counter() - started,
                },
            )
    except (ValueError, KeyError, FileExistsError, FileNotFoundError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
