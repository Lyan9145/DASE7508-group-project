"""CLI entry point to plot matrix or ablation figures and trace replays."""
from __future__ import annotations

import argparse
from pathlib import Path

from evaluation import (
    make_comparison_replay,
    plot_ablation_curves,
    plot_detection_tradeoff,
    plot_matrix_heatmap,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "run_dir",
        type=Path,
        help="Completed matrix or ablation output directory",
    )
    parser.add_argument(
        "--attack-case",
        type=str,
        default=None,
        help="Optional attack case_id for 3-panel trace replay selection",
    )
    parser.add_argument(
        "--no-replay",
        action="store_true",
        help="Skip rendering comparison_frame.png / comparison_replay.gif",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run_dir: Path = args.run_dir
    if not run_dir.is_dir():
        parser.error(f"Run directory does not exist: {run_dir}")

    is_matrix = (
        (run_dir / "matrix_summary.csv").exists()
        or (run_dir / "matrix_summary.json").exists()
    )
    is_ablation = (
        (run_dir / "ablation_summary.csv").exists()
        or (run_dir / "velocity" / "ablation_summary.csv").exists()
        or (run_dir / "position" / "ablation_summary.csv").exists()
    )
    if not is_matrix and not is_ablation:
        parser.error(
            f"Unrecognized run directory (missing matrix_summary.csv or ablation_summary.csv): {run_dir}"
        )

    generated: list[Path] = []
    if is_matrix:
        generated.append(plot_matrix_heatmap(run_dir))
        generated.append(plot_detection_tradeoff(run_dir))
        if not args.no_replay:
            replay = make_comparison_replay(run_dir, attack_case=args.attack_case)
            if replay is not None:
                generated.extend(replay)

    if is_ablation:
        generated.append(plot_ablation_curves(run_dir))

    for path in generated:
        print(f"Generated: {path}", flush=True)


if __name__ == "__main__":
    main()
