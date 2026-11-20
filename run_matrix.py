"""CLI entry point for paired Phase-2 attack-defense matrix evaluation."""
from __future__ import annotations

import argparse
from pathlib import Path

from evaluation import list_presets, run_matrix


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--preset",
        choices=list_presets(),
        default="smoke",
        help="Evaluation preset (default: smoke)",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        type=Path,
        default=None,
        help="Policy model.zip paths (defaults to preset models)",
    )
    parser.add_argument(
        "--attacks",
        nargs="+",
        default=None,
        help="Subset of preset case_ids or registered attack names",
    )
    parser.add_argument(
        "--defenses",
        nargs="+",
        default=None,
        help="Subset of preset defense_ids or registered defense names",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=None,
        help="Paired test episodes per policy (defaults to preset)",
    )
    parser.add_argument(
        "--calibration-episodes",
        type=int,
        default=None,
        help="Clean calibration episodes per policy (defaults to preset)",
    )
    parser.add_argument(
        "--test-base",
        type=int,
        default=None,
        help="Starting seed for test block (defaults to preset Phase-2 block)",
    )
    parser.add_argument(
        "--cal-base",
        type=int,
        default=None,
        help="Starting seed for calibration block (defaults to preset CAL_BASE)",
    )
    parser.add_argument(
        "--fallback-model",
        type=Path,
        default=None,
        help="Optional fallback SAC model.zip passed to FallbackPolicyDefense",
    )
    parser.add_argument(
        "--no-traces",
        action="store_true",
        help="Disable writing compressed step-level traces.jsonl.gz",
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
    try:
        run_matrix(
            out=args.out,
            preset=args.preset,
            models=args.models,
            attacks=args.attacks,
            defenses=args.defenses,
            episodes=args.episodes,
            calibration_episodes=args.calibration_episodes,
            test_base=args.test_base,
            cal_base=args.cal_base,
            fallback_model=args.fallback_model,
            write_traces=not args.no_traces,
        )
    except (ValueError, KeyError, FileExistsError, FileNotFoundError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
