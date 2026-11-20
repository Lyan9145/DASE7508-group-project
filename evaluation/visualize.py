"""Visualization and trace-replay utilities for matrix and ablation runs."""
from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
from matplotlib.animation import FuncAnimation, PillowWriter
import matplotlib.pyplot as plt
import numpy as np

from core.security import ArmGeometry, rotation


def _opt_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _opt_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    return None


def _read_csv_dicts(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _load_matrix_rows(run_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    config_path = run_dir / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    json_path = run_dir / "matrix_summary.json"
    if json_path.exists():
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        rows = payload.get("across_policies", [])
        if rows:
            return rows, config
    csv_path = run_dir / "matrix_summary.csv"
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Expected matrix_summary.csv or matrix_summary.json in {run_dir}"
        )
    raw_rows = _read_csv_dicts(csv_path)
    parsed: list[dict[str, Any]] = []
    for r in raw_rows:
        parsed.append(
            {
                "attack_case": r["attack_case"],
                "attack_name": r.get("attack_name", r["attack_case"]),
                "defense": r["defense"],
                "defense_name": r.get("defense_name", r["defense"]),
                "task_success_rate": _opt_float(r.get("task_success_rate")),
                "attack_success_rate": _opt_float(r.get("attack_success_rate")),
                "paired_window_mean_delta_m": _opt_float(
                    r.get("paired_window_mean_delta_m")
                ),
                "clean_false_alarm_step_rate": _opt_float(
                    r.get("clean_false_alarm_step_rate")
                ),
                "clean_false_alarm_episode_rate": _opt_float(
                    r.get("clean_false_alarm_episode_rate")
                ),
                "in_window_detection_rate": _opt_float(
                    r.get("in_window_detection_rate")
                ),
                "abort_rate": _opt_float(r.get("abort_rate")),
                "mean_final_error_m": _opt_float(r.get("mean_final_error_m")),
                "mean_monitor_us": _opt_float(r.get("mean_monitor_us")),
            }
        )
    return parsed, config


def _ordered_labels(
    rows: Sequence[dict[str, Any]],
    config: dict[str, Any],
) -> tuple[list[str], list[str]]:
    cfg_attacks = [a["case_id"] for a in config.get("attacks", []) if "case_id" in a]
    cfg_defenses = [d["defense_id"] for d in config.get("defenses", []) if "defense_id" in d]

    seen_attacks = list(dict.fromkeys(str(r["attack_case"]) for r in rows))
    seen_defenses = list(dict.fromkeys(str(r["defense"]) for r in rows))

    attacks = [a for a in cfg_attacks if a in seen_attacks] + [
        a for a in seen_attacks if a not in cfg_attacks
    ]
    defenses = [d for d in cfg_defenses if d in seen_defenses] + [
        d for d in seen_defenses if d not in cfg_defenses
    ]
    if "clean" in attacks:
        attacks = ["clean"] + [a for a in attacks if a != "clean"]
    if "no_defense" in defenses:
        defenses = ["no_defense"] + [d for d in defenses if d != "no_defense"]
    return attacks, defenses


def plot_matrix_heatmap(run_dir: Path) -> Path:
    """Plot Attack x Defense task success rate (%) and paired window delta (cm)."""
    run_dir = Path(run_dir)
    rows, config = _load_matrix_rows(run_dir)
    if not rows:
        raise ValueError(f"No matrix summary rows found in {run_dir}")

    attacks, defenses = _ordered_labels(rows, config)
    lookup = {(str(r["attack_case"]), str(r["defense"])): r for r in rows}

    success_grid = np.full((len(attacks), len(defenses)), np.nan, dtype=float)
    delta_grid = np.full((len(attacks), len(defenses)), np.nan, dtype=float)
    for i, atk in enumerate(attacks):
        for j, dfn in enumerate(defenses):
            row = lookup.get((atk, dfn))
            if row is None:
                continue
            if row.get("task_success_rate") is not None:
                success_grid[i, j] = float(row["task_success_rate"]) * 100.0
            if row.get("paired_window_mean_delta_m") is not None:
                delta_grid[i, j] = float(row["paired_window_mean_delta_m"]) * 100.0

    fig_w = max(11.0, 2.2 * len(defenses) + 3.0)
    fig_h = max(4.5, 0.45 * len(attacks) + 2.5)
    fig, axes = plt.subplots(1, 2, figsize=(fig_w, fig_h), constrained_layout=True)

    # Panel 1: Task success rate (%)
    ax0 = axes[0]
    cmap0 = plt.get_cmap("RdYlGn").copy()
    cmap0.set_bad(color="#eeeeee")
    im0 = ax0.imshow(success_grid, aspect="auto", cmap=cmap0, vmin=0.0, vmax=100.0)
    ax0.set_title("Task Success Rate (%)", fontsize=11)
    ax0.set_xticks(range(len(defenses)), defenses, rotation=35, ha="right", fontsize=8)
    ax0.set_yticks(range(len(attacks)), attacks, fontsize=8)
    for i in range(len(attacks)):
        for j in range(len(defenses)):
            val = success_grid[i, j]
            text = "—" if np.isnan(val) else f"{val:.1f}"
            color = "black" if np.isnan(val) or (20.0 <= val <= 85.0) else "white"
            ax0.text(j, i, text, ha="center", va="center", fontsize=7, color=color)
    fig.colorbar(im0, ax=ax0, shrink=0.8)

    # Panel 2: Paired window mean delta (cm)
    ax1 = axes[1]
    finite_deltas = delta_grid[~np.isnan(delta_grid)]
    vlim = max(float(np.max(np.abs(finite_deltas))) if finite_deltas.size else 0.0, 0.5)
    cmap1 = plt.get_cmap("coolwarm").copy()
    cmap1.set_bad(color="#eeeeee")
    im1 = ax1.imshow(delta_grid, aspect="auto", cmap=cmap1, vmin=-vlim, vmax=vlim)
    ax1.set_title("Paired Window Mean Distance Delta vs Clean (cm)", fontsize=11)
    ax1.set_xticks(range(len(defenses)), defenses, rotation=35, ha="right", fontsize=8)
    ax1.set_yticks(range(len(attacks)), [""] * len(attacks))
    for i in range(len(attacks)):
        for j in range(len(defenses)):
            val = delta_grid[i, j]
            text = "—" if np.isnan(val) else f"{val:+.2f}"
            color = (
                "black"
                if np.isnan(val) or abs(val) < 0.7 * vlim
                else "white"
            )
            ax1.text(j, i, text, ha="center", va="center", fontsize=7, color=color)
    fig.colorbar(im1, ax=ax1, shrink=0.8)

    preset = config.get("preset", "matrix")
    episodes = config.get("episodes", "?")
    fig.suptitle(
        f"Attack x Defense Matrix ({preset}, {episodes} episodes/policy)",
        fontsize=12,
    )

    figures_dir = run_dir / "figures"
    figures_dir.mkdir(exist_ok=True)
    out_path = figures_dir / "matrix_heatmap.png"
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return out_path


def plot_detection_tradeoff(run_dir: Path) -> Path:
    """Plot clean false-alarm rate vs attack in-window detection rate across defenses."""
    run_dir = Path(run_dir)
    rows, config = _load_matrix_rows(run_dir)
    if not rows:
        raise ValueError(f"No matrix summary rows found in {run_dir}")

    _, defenses = _ordered_labels(rows, config)
    clean_ep_fa: dict[str, float] = {}
    clean_step_fa: dict[str, float] = {}
    det_rates: dict[str, list[float]] = {d: [] for d in defenses}

    for r in rows:
        dfn = str(r["defense"])
        if str(r["attack_case"]) == "clean" or str(r.get("attack_name", "")) == "clean":
            if r.get("clean_false_alarm_episode_rate") is not None:
                clean_ep_fa[dfn] = float(r["clean_false_alarm_episode_rate"]) * 100.0
            if r.get("clean_false_alarm_step_rate") is not None:
                clean_step_fa[dfn] = float(r["clean_false_alarm_step_rate"]) * 100.0
        else:
            if r.get("in_window_detection_rate") is not None:
                det_rates.setdefault(dfn, []).append(
                    float(r["in_window_detection_rate"]) * 100.0
                )

    fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.4), constrained_layout=True)
    panels = [
        (axes[0], clean_ep_fa, "Clean Episode False-Alarm Rate (%)"),
        (axes[1], clean_step_fa, "Clean Step False-Alarm Rate (%)"),
    ]
    markers = ("o", "s", "D", "^", "v", "P", "X", "*")

    for ax, fa_map, xlabel in panels:
        points: list[tuple[int, str, float, float, float, float]] = []
        for idx, dfn in enumerate(defenses):
            rates = det_rates.get(dfn, [])
            if dfn not in fa_map or not rates:
                continue
            x = fa_map[dfn]
            y_mean = float(np.mean(rates))
            y_min = float(np.min(rates))
            y_max = float(np.max(rates))
            points.append((idx, dfn, x, y_mean, y_min, y_max))

        if points:
            x_max = max([p[2] for p in points] + [1.0])
            x_span = 1.33 * x_max
            ax.set_xlim(-0.08 * x_max, 1.25 * x_max)
            placed_labels: list[tuple[float, float]] = []
            for idx, dfn, x, y_mean, y_min, y_max in sorted(
                points, key=lambda item: (item[2], item[3])
            ):
                color = f"C{idx % 10}"
                marker = markers[idx % len(markers)]
                ax.errorbar(
                    [x],
                    [y_mean],
                    yerr=[[y_mean - y_min], [y_max - y_mean]],
                    fmt=marker,
                    markersize=7.5,
                    capsize=4,
                    color=color,
                    label=dfn,
                    alpha=0.9,
                )
                on_right = x > 0.65 * x_max
                dx = -10 if on_right else 10
                ha = "right" if on_right else "left"
                x_anchor = (x / max(x_span, 1e-6)) + (-0.12 if on_right else 0.12)
                y_anchor = y_mean
                # Resolve vertical collisions against previously placed labels nearby in x.
                step_dir = -4.8 if y_mean > 88.0 else 4.8
                for _ in range(12):
                    conflict = any(
                        abs(x_anchor - px) < 0.25 and abs(y_anchor - py) < 4.5
                        for px, py in placed_labels
                    )
                    if not conflict:
                        break
                    y_anchor += step_dir
                    if y_anchor > 101.0 or y_anchor < -1.0:
                        step_dir = -step_dir
                        y_anchor = y_mean + step_dir
                placed_labels.append((x_anchor, y_anchor))
                ax.annotate(
                    dfn,
                    (x, y_mean),
                    xytext=(x + (-0.03 if on_right else 0.03) * x_span, y_anchor),
                    textcoords="data",
                    ha=ha,
                    va="center",
                    fontsize=8,
                    arrowprops={"arrowstyle": "-", "color": "#888888", "lw": 0.6},
                )
        else:
            ax.text(
                0.5,
                0.5,
                "Requires both 'clean' and attack cases",
                ha="center",
                va="center",
                transform=ax.transAxes,
                fontsize=9,
            )
            ax.set_xlim(-3.0, 103.0)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Mean In-Window Detection Rate (%)")
        ax.set_ylim(-5.0, 107.0)
        ax.grid(alpha=0.25)

    axes[0].set_title("Episode-Level FA vs Detection (mean & min-max)")
    axes[1].set_title("Step-Level FA vs Detection (mean & min-max)")
    handles, labels = axes[0].get_legend_handles_labels()
    if handles:
        fig.legend(
            handles,
            labels,
            loc="outside lower center",
            ncol=min(4, len(handles)),
            fontsize=8,
        )
    fig.suptitle("Defense Detection vs Clean False-Alarm Tradeoff", fontsize=12)

    figures_dir = run_dir / "figures"
    figures_dir.mkdir(exist_ok=True)
    out_path = figures_dir / "detection_tradeoff.png"
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return out_path


def _plot_single_ablation_into_axes(
    ax_succ: Any,
    ax_err: Any,
    summary_rows: Sequence[dict[str, str]],
    config: dict[str, Any],
) -> None:
    noise_type = str(
        config.get("noise_type") or summary_rows[0].get("noise_type", "sigma")
    )
    xlabel = (
        "Velocity Noise Sigma (rad/s)"
        if noise_type == "vel_sigma"
        else "Position Noise Sigma (m)"
        if noise_type == "pos_sigma"
        else noise_type
    )

    clean_pts: list[tuple[float, float, float]] = []
    by_defense: dict[str, list[tuple[float, float, float]]] = {}
    for row in summary_rows:
        sigma = float(row["noise_sigma"])
        succ = float(row["task_success_rate"]) * 100.0
        err_m = _opt_float(row.get("mean_final_error_m"))
        err_cm = err_m * 100.0 if err_m is not None else np.nan
        atk = str(row["attack_case"])
        dfn = str(row["defense"])
        if atk == "clean":
            clean_pts.append((sigma, succ, err_cm))
        else:
            by_defense.setdefault(dfn, []).append((sigma, succ, err_cm))

    if clean_pts:
        clean_pts.sort(key=lambda t: t[0])
        xs = [t[0] for t in clean_pts]
        ax_succ.plot(
            xs,
            [t[1] for t in clean_pts],
            linestyle="--",
            marker="s",
            color="black",
            label="clean (no_defense)",
        )
        ax_err.plot(
            xs,
            [t[2] for t in clean_pts],
            linestyle="--",
            marker="s",
            color="black",
            label="clean (no_defense)",
        )

    defense_order = config.get("defenses") or list(by_defense.keys())
    for idx, dfn in enumerate(defense_order):
        pts = sorted(by_defense.get(dfn, []), key=lambda t: t[0])
        if not pts:
            continue
        xs = [t[0] for t in pts]
        ax_succ.plot(
            xs,
            [t[1] for t in pts],
            marker="o",
            color=f"C{idx % 10}",
            label=dfn,
        )
        ax_err.plot(
            xs,
            [t[2] for t in pts],
            marker="o",
            color=f"C{idx % 10}",
            label=dfn,
        )

    ax_succ.set_xlabel(xlabel)
    ax_succ.set_ylabel("Task Success Rate (%)")
    ax_succ.set_ylim(-5.0, 105.0)
    ax_succ.grid(alpha=0.25)
    ax_succ.legend(fontsize=8)

    ax_err.set_xlabel(xlabel)
    ax_err.set_ylabel("Mean Final 10-Step Error (cm)")
    ax_err.axhline(3.0, color="grey", linestyle=":", linewidth=1.2, label="3 cm criterion")
    ax_err.grid(alpha=0.25)
    ax_err.legend(fontsize=8)


def plot_ablation_curves(ablation_dir: Path) -> Path:
    """Plot task success rate and mean final error vs noise sigma for each defense."""
    ablation_dir = Path(ablation_dir)
    summary_csv = ablation_dir / "ablation_summary.csv"
    if summary_csv.exists():
        rows = _read_csv_dicts(summary_csv)
        if not rows:
            raise ValueError(f"Empty ablation_summary.csv in {ablation_dir}")
        cfg_path = ablation_dir / "config.json"
        config = (
            json.loads(cfg_path.read_text(encoding="utf-8"))
            if cfg_path.exists()
            else {}
        )
        fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8), constrained_layout=True)
        _plot_single_ablation_into_axes(axes[0], axes[1], rows, config)
        mode = config.get("mode", rows[0].get("noise_type", "ablation"))
        atk_case = (config.get("attack") or {}).get("case_id", "")
        axes[0].set_title("Task Success vs Noise Sigma")
        axes[1].set_title("Final Target Distance vs Noise Sigma")
        fig.suptitle(f"Direction 4A Ablation ({mode}): {atk_case}", fontsize=12)

        figures_dir = ablation_dir / "figures"
        figures_dir.mkdir(exist_ok=True)
        out_path = figures_dir / "ablation_curves.png"
        fig.savefig(out_path, dpi=180)
        plt.close(fig)
        return out_path

    # Support parent directory containing both 'velocity/' and 'position/' ablations.
    sub_dirs = [
        d
        for d in (ablation_dir / "velocity", ablation_dir / "position")
        if (d / "ablation_summary.csv").exists()
    ]
    if not sub_dirs:
        raise FileNotFoundError(
            f"No ablation_summary.csv found in {ablation_dir} or velocity/position subdirs"
        )
    for sub in sub_dirs:
        plot_ablation_curves(sub)

    fig, axes = plt.subplots(
        len(sub_dirs),
        2,
        figsize=(11.5, 4.6 * len(sub_dirs)),
        squeeze=False,
        constrained_layout=True,
    )
    for idx, sub in enumerate(sub_dirs):
        rows = _read_csv_dicts(sub / "ablation_summary.csv")
        cfg_path = sub / "config.json"
        config = (
            json.loads(cfg_path.read_text(encoding="utf-8"))
            if cfg_path.exists()
            else {}
        )
        _plot_single_ablation_into_axes(axes[idx, 0], axes[idx, 1], rows, config)
        mode = config.get("mode", sub.name)
        axes[idx, 0].set_title(f"{mode}: Task Success vs Sigma")
        axes[idx, 1].set_title(f"{mode}: Final Distance vs Sigma")
    fig.suptitle("Direction 4A Noise Ablation Curves", fontsize=12)

    figures_dir = ablation_dir / "figures"
    figures_dir.mkdir(exist_ok=True)
    out_path = figures_dir / "ablation_curves.png"
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return out_path


def _select_replay_target(
    run_dir: Path,
    attack_case: str | None,
) -> tuple[str, str, int, list[str]]:
    episodes_csv = run_dir / "episodes.csv"
    preferred_defenses = ["no_defense", "original_fail_stop", "ik_velocity_fusion"]

    if episodes_csv.exists():
        ep_rows = _read_csv_dicts(episodes_csv)
        non_clean = [
            r
            for r in ep_rows
            if r.get("attack_name") != "clean" and r.get("attack_case") != "clean"
        ]
        if not non_clean:
            non_clean = ep_rows
        if attack_case is not None:
            candidates = [r for r in non_clean if r["attack_case"] == attack_case]
            if not candidates:
                raise ValueError(
                    f"Attack case {attack_case!r} not found in {episodes_csv}"
                )
        else:
            # Prefer strongest late/sustained bias case, then any bias, then anything.
            bias_rows = [
                r
                for r in non_clean
                if r.get("attack_name") == "bias" or "bias" in r.get("attack_case", "")
            ]
            pool = bias_rows or non_clean
            # Rank cases by no_defense failure count and mean final distance.
            by_case: dict[str, list[dict[str, str]]] = {}
            for r in pool:
                by_case.setdefault(r["attack_case"], []).append(r)
            def _case_score(case_name: str) -> tuple[int, float]:
                c_rows = [
                    r for r in by_case[case_name] if r["defense"] == "no_defense"
                ] or by_case[case_name]
                fails = sum(not bool(_opt_bool(r["task_success"])) for r in c_rows)
                mean_err = float(
                    np.mean([float(r["final_10_mean_distance_m"]) for r in c_rows])
                )
                return (fails, mean_err)

            chosen_case = max(by_case, key=_case_score)
            candidates = by_case[chosen_case]

        chosen_case = candidates[0]["attack_case"]
        available_defs = list(dict.fromkeys(r["defense"] for r in candidates))
        if all(d in available_defs for d in preferred_defenses):
            defenses = preferred_defenses
        else:
            defenses = (
                (["no_defense"] if "no_defense" in available_defs else [])
                + [d for d in available_defs if d != "no_defense"]
            )[:3]

        by_pair: dict[tuple[str, int], dict[str, dict[str, str]]] = {}
        for r in candidates:
            by_pair.setdefault((r["policy"], int(r["seed"])), {})[r["defense"]] = r

        def _pair_score(pair: tuple[str, int]) -> tuple[int, int, float]:
            dmap = by_pair[pair]
            no_def = dmap.get("no_defense")
            ik_def = dmap.get("ik_velocity_fusion")
            no_def_fail = int(
                no_def is not None and not bool(_opt_bool(no_def["task_success"]))
            )
            ik_succ = int(
                ik_def is not None and bool(_opt_bool(ik_def["task_success"]))
            )
            err = float(no_def["final_10_mean_distance_m"]) if no_def else 0.0
            return (no_def_fail and ik_succ, no_def_fail, err)

        best_policy, best_seed = max(by_pair, key=_pair_score)
        return best_policy, chosen_case, best_seed, defenses

    # Fallback if episodes.csv is absent: inspect config.json
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    policy = Path(config["models"][0]).parent.name
    seed = int(config["test_base"])
    cases = [a["case_id"] for a in config["attacks"] if a["attack_name"] != "clean"]
    chosen_case = attack_case or (cases[0] if cases else config["attacks"][0]["case_id"])
    avail = [d["defense_id"] for d in config["defenses"]]
    defenses = (
        preferred_defenses
        if all(d in avail for d in preferred_defenses)
        else avail[:3]
    )
    return policy, chosen_case, seed, defenses


def make_comparison_replay(
    run_dir: Path,
    attack_case: str | None = None,
) -> tuple[Path, Path] | None:
    """Render 3-panel trace comparison PNG and GIF if ``traces.jsonl.gz`` exists."""
    run_dir = Path(run_dir)
    traces_path = run_dir / "traces.jsonl.gz"
    if not traces_path.exists():
        return None

    policy, selected_case, selected_seed, defenses = _select_replay_target(
        run_dir, attack_case
    )
    cal_data = json.loads((run_dir / "calibration.json").read_text(encoding="utf-8"))
    geom_dict = cal_data[policy]["geometry"]
    geometry = ArmGeometry(
        origin=np.array(geom_dict["origin"], dtype=float),
        link=np.array(geom_dict["link"], dtype=float),
        tip=np.array(geom_dict["tip"], dtype=float),
    )

    groups: dict[str, list[dict[str, Any]]] = {d: [] for d in defenses}
    with gzip.open(traces_path, "rt", encoding="utf-8") as handle:
        for line in handle:
            rec = json.loads(line)
            if (
                rec["policy"] == policy
                and rec["attack_case"] == selected_case
                and int(rec["seed"]) == selected_seed
                and rec["defense"] in groups
            ):
                groups[rec["defense"]].append(rec)

    missing = [d for d, rows in groups.items() if not rows]
    if missing:
        raise ValueError(
            f"Missing trace rows for ({policy}, {selected_case}, seed={selected_seed}): {missing}"
        )

    for rows in groups.values():
        rows.sort(key=lambda r: int(r["observation_step"]))

    n_panels = len(defenses)
    fig, axes = plt.subplots(
        1,
        n_panels,
        figsize=(4.2 * n_panels, 4.4),
        squeeze=False,
        constrained_layout=True,
    )
    panel_axes = axes[0]
    artists: list[tuple[Any, Any, Any]] = []

    for ax, dfn in zip(panel_axes, defenses):
        ax.set_aspect("equal")
        ax.set_xlim(-0.24, 0.24)
        ax.set_ylim(-0.24, 0.24)
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
        ax.grid(alpha=0.2)
        ax.set_title(dfn, fontsize=10)
        (physical,) = ax.plot([], [], "o-", lw=3, color="#1565c0", label="Physical arm")
        (perceived,) = ax.plot(
            [], [], "--", lw=2, color="#ef6c00", label="Policy-observed angles"
        )
        target = groups[dfn][0]["truth_before"]["target"]
        ax.scatter(*target, marker="x", c="red", s=70, label="Target")
        note = ax.text(0.03, 0.97, "", transform=ax.transAxes, va="top", fontsize=7.5)
        artists.append((physical, perceived, note))

    panel_axes[0].legend(fontsize=7, loc="lower left")
    title = fig.suptitle("", fontsize=10.5)

    def _points(q: Sequence[float]) -> np.ndarray:
        return np.array(
            [
                geometry.origin,
                geometry.origin + rotation(q[0]) @ geometry.link,
                geometry.forward(*q),
            ]
        )

    def _draw_frame(step_idx: int) -> list[Any]:
        title.set_text(
            f"Trace replay — {policy}, {selected_case}, seed {selected_seed}, step {step_idx}"
        )
        for dfn, (physical, perceived, note) in zip(defenses, artists):
            rows = groups[dfn]
            row = rows[min(step_idx, len(rows) - 1)]
            actual = _points(row["truth_before"]["angles"])
            obs = np.array(row["policy_sensor"], dtype=float)
            inferred = _points(np.arctan2(obs[2:4], obs[:2]))
            physical.set_data(actual[:, 0], actual[:, 1])
            perceived.set_data(inferred[:, 0], inferred[:, 1])

            status = row.get("defense_status") or {}
            alarm = bool(status.get("alarm", False))
            aborted = bool(status.get("abort", False))
            state = str(status.get("state", "normal"))
            dist_cm = float(row["truth_before"]["distance"]) * 100.0
            note_lines = [
                f"delta={row['delta_rad']:+.3f} rad | active={row.get('is_active', False)}",
                f"state={state} | alarm={alarm}",
                f"true_dist={dist_cm:.2f} cm",
            ]
            if aborted:
                note_lines.append(f"ABORTED @ step {row['observation_step']}")
            note.set_text("\n".join(note_lines))
        return [title] + [artist for group in artists for artist in group]

    max_len = max(len(rows) for rows in groups.values())
    active_steps = [
        int(r["observation_step"])
        for r in groups[defenses[0]]
        if r.get("is_active")
    ]
    if active_steps:
        snapshot_step = active_steps[len(active_steps) // 2]
    else:
        snapshot_step = min(max_len // 2, max_len - 1)

    figures_dir = run_dir / "figures"
    figures_dir.mkdir(exist_ok=True)
    frame_path = figures_dir / "comparison_frame.png"
    gif_path = figures_dir / "comparison_replay.gif"

    _draw_frame(snapshot_step)
    fig.savefig(frame_path, dpi=170)

    frames = list(range(0, max_len, 2))
    if frames[-1] != max_len - 1:
        frames.append(max_len - 1)
    anim = FuncAnimation(fig, _draw_frame, frames=frames, interval=80, blit=False)
    anim.save(gif_path, writer=PillowWriter(fps=12))
    plt.close(fig)
    return frame_path, gif_path


__all__ = [
    "make_comparison_replay",
    "plot_ablation_curves",
    "plot_detection_tradeoff",
    "plot_matrix_heatmap",
]
