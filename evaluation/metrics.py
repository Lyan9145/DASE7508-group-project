"""Evaluation metrics and aggregation helpers for attack-defense matrices."""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np


def recovery_time(
    distances: Sequence[float],
    window_bounds: tuple[int, int] | None,
) -> int | None:
    """Return steps past ``start + duration`` to enter 5 consecutive <= 0.03 m states.

    Matches ``evaluate.recovery_time``: ``distances[k]`` is the true target
    distance at observation ``k``. Returns ``None`` for clean trials or trials
    that do not enter a 5-state ``<= 0.03`` m band at or after ``start + duration``.
    """
    if window_bounds is None:
        return None
    start = int(window_bounds[0])
    duration = int(window_bounds[1])
    end = start + duration
    for step in range(max(0, end), len(distances) - 4):
        if max(distances[step : step + 5]) <= 0.03:
            return step - end
    return None


def _is_clean_row(row: Mapping[str, Any]) -> bool:
    if "attack_name" in row:
        return str(row["attack_name"]) == "clean"
    return str(row.get("attack_case", "")) == "clean"


def _is_no_defense_row(row: Mapping[str, Any]) -> bool:
    if "defense" in row:
        return str(row["defense"]) == "no_defense"
    return str(row.get("defense_name", "")) == "no_defense"


def _mean_non_none(rows: Sequence[Mapping[str, Any]], key: str) -> float | None:
    values = [float(r[key]) for r in rows if r.get(key) is not None]
    return float(np.mean(values)) if values else None


def _weighted_mean(
    rows: Sequence[Mapping[str, Any]],
    value_key: str,
    weight_key: str,
) -> float | None:
    pairs = [
        (float(r[value_key]), float(r[weight_key]))
        for r in rows
        if r.get(value_key) is not None and r.get(weight_key) is not None and float(r[weight_key]) > 0.0
    ]
    if not pairs:
        return None
    total_weight = sum(w for _, w in pairs)
    if total_weight <= 0.0:
        return None
    return float(sum(v * w for v, w in pairs) / total_weight)


def summarize_matrix(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate episode rows into per-``(policy, attack_case, defense)`` summaries."""
    if not rows:
        return []

    clean_no_def: dict[tuple[str, int], Mapping[str, Any]] = {
        (str(r["policy"]), int(r["seed"])): r
        for r in rows
        if _is_clean_row(r) and _is_no_defense_row(r)
    }

    groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        key = (
            str(row["policy"]),
            str(row["attack_case"]),
            str(row["defense"]),
        )
        groups.setdefault(key, []).append(row)

    summary: list[dict[str, Any]] = []
    for (policy, attack_case, defense), group in groups.items():
        first = group[0]
        is_clean = _is_clean_row(first)
        corrupt = not is_clean
        episodes = len(group)
        successes = int(sum(bool(r["task_success"]) for r in group))
        task_success_rate = float(successes / episodes)
        abort_rate = float(np.mean([bool(r["aborted"]) for r in group]))

        paired_clean = [
            (r, clean_no_def[(str(r["policy"]), int(r["seed"]))])
            for r in group
            if (str(r["policy"]), int(r["seed"])) in clean_no_def
        ]
        if len(paired_clean) == episodes:
            clean_success_rate = float(
                np.mean([bool(clean_row["task_success"]) for _, clean_row in paired_clean])
            )
            paired_success_difference_vs_clean: float | None = float(
                task_success_rate - clean_success_rate
            )
            eligible = [
                r for r, clean_row in paired_clean if bool(clean_row["task_success"])
            ]
            clean_success_denominator = len(eligible)
            attack_success_rate: float | None = (
                float(sum(not bool(r["task_success"]) for r in eligible) / len(eligible))
                if (eligible and corrupt)
                else None
            )
        else:
            paired_success_difference_vs_clean = None
            clean_success_denominator = 0
            attack_success_rate = None

        total_detection_steps = sum(int(r.get("detection_steps", 0)) for r in group)
        total_alarm_count = sum(int(r.get("alarm_count", 0)) for r in group)
        clean_false_alarm_step_rate = (
            float(total_alarm_count / max(1, total_detection_steps))
            if is_clean
            else None
        )
        clean_false_alarm_episode_rate = (
            float(np.mean([bool(r.get("any_alarm", False)) for r in group]))
            if is_clean
            else None
        )

        if corrupt:
            detected_flags = [
                bool(r["in_window_detected"])
                if r.get("in_window_detected") is not None
                else (not bool(r.get("missed_detection", False)))
                for r in group
            ]
            in_window_detection_rate: float | None = float(np.mean(detected_flags))
            missed_detections: int | None = int(sum(not d for d in detected_flags))
            mean_detection_delay_steps = _mean_non_none(group, "detection_delay_steps")
            recovered_count: int | None = int(
                sum(r.get("recovery_steps") is not None for r in group)
            )
            mean_recovery_steps = _mean_non_none(group, "recovery_steps")
        else:
            in_window_detection_rate = None
            missed_detections = None
            mean_detection_delay_steps = None
            recovered_count = None
            mean_recovery_steps = None

        total_monitor_ns = sum(int(r.get("monitor_total_ns", 0)) for r in group)
        total_monitor_calls = sum(int(r.get("monitor_calls", 0)) for r in group)
        mean_monitor_us = (
            float(total_monitor_ns / total_monitor_calls / 1000.0)
            if total_monitor_calls > 0
            else None
        )

        summary.append(
            {
                "policy": policy,
                "attack_case": attack_case,
                "attack_name": str(first.get("attack_name", attack_case)),
                "defense": defense,
                "defense_name": str(first.get("defense_name", defense)),
                "episodes": episodes,
                "successes": successes,
                "task_success_rate": task_success_rate,
                "clean_success_denominator": clean_success_denominator,
                "attack_success_rate": attack_success_rate,
                "paired_success_difference_vs_clean": paired_success_difference_vs_clean,
                "abort_rate": abort_rate,
                "mean_final_error_m": _mean_non_none(group, "final_10_mean_distance_m"),
                "mean_terminal_distance_m": _mean_non_none(group, "terminal_distance_m"),
                "mean_window_distance_m": _mean_non_none(group, "window_mean_distance_m"),
                "paired_window_mean_delta_m": _mean_non_none(
                    group, "paired_window_mean_delta_m"
                ),
                "mean_control_effort": _mean_non_none(group, "control_effort"),
                "clean_false_alarm_step_rate": clean_false_alarm_step_rate,
                "clean_false_alarm_episode_rate": clean_false_alarm_episode_rate,
                "in_window_detection_rate": in_window_detection_rate,
                "missed_detections": missed_detections,
                "mean_detection_delay_steps": mean_detection_delay_steps,
                "recovered_episodes": recovered_count,
                "mean_recovery_steps": mean_recovery_steps,
                "mean_applied_angle_mae_rad": _mean_non_none(
                    group, "applied_angle_mae_rad"
                ),
                "mean_applied_q1_mae_rad": _mean_non_none(
                    group, "applied_q1_mae_rad"
                ),
                "mean_monitor_us": mean_monitor_us,
                "_total_detection_steps": total_detection_steps,
                "_total_alarm_count": total_alarm_count,
                "_total_monitor_ns": total_monitor_ns,
                "_total_monitor_calls": total_monitor_calls,
            }
        )

    # Strip internal summation helper fields only when returning public dicts?
    # Keep summary dicts clean and JSON-serializable without underscore clutter;
    # aggregate_across_policies can weight cleanly by episodes/counts.
    for row in summary:
        for internal_key in (
            "_total_detection_steps",
            "_total_alarm_count",
            "_total_monitor_ns",
            "_total_monitor_calls",
        ):
            row.pop(internal_key, None)
    return summary


def aggregate_across_policies(
    summary_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Aggregate per-policy matrix summaries across policies by ``(attack_case, defense)``."""
    if not summary_rows:
        return []

    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in summary_rows:
        key = (str(row["attack_case"]), str(row["defense"]))
        groups.setdefault(key, []).append(row)

    aggregated: list[dict[str, Any]] = []
    for (attack_case, defense), group in groups.items():
        first = group[0]
        is_clean = _is_clean_row(first)
        corrupt = not is_clean

        episodes = int(sum(int(r["episodes"]) for r in group))
        successes = int(sum(int(r["successes"]) for r in group))
        task_success_rate = float(successes / episodes) if episodes > 0 else 0.0
        clean_success_denominator = int(
            sum(int(r.get("clean_success_denominator", 0)) for r in group)
        )

        attack_success_rate = (
            _weighted_mean(group, "attack_success_rate", "clean_success_denominator")
            if corrupt and clean_success_denominator > 0
            else None
        )
        paired_success_difference_vs_clean = _weighted_mean(
            group, "paired_success_difference_vs_clean", "episodes"
        )
        abort_rate = _weighted_mean(group, "abort_rate", "episodes")

        if is_clean:
            clean_false_alarm_step_rate = _weighted_mean(
                group, "clean_false_alarm_step_rate", "episodes"
            )
            clean_false_alarm_episode_rate = _weighted_mean(
                group, "clean_false_alarm_episode_rate", "episodes"
            )
        else:
            clean_false_alarm_step_rate = None
            clean_false_alarm_episode_rate = None

        if corrupt:
            missed_values = [
                int(r["missed_detections"])
                for r in group
                if r.get("missed_detections") is not None
            ]
            missed_detections: int | None = (
                int(sum(missed_values)) if len(missed_values) == len(group) else None
            )
            if missed_detections is not None and episodes > 0:
                in_window_detection_rate: float | None = float(
                    1.0 - (missed_detections / episodes)
                )
            else:
                in_window_detection_rate = _weighted_mean(
                    group, "in_window_detection_rate", "episodes"
                )

            # Weight delay by number of detected episodes in each policy when available.
            delay_pairs: list[tuple[float, float]] = []
            for r in group:
                if r.get("mean_detection_delay_steps") is None:
                    continue
                if r.get("missed_detections") is not None:
                    w = float(int(r["episodes"]) - int(r["missed_detections"]))
                else:
                    w = float(r["episodes"])
                if w > 0:
                    delay_pairs.append((float(r["mean_detection_delay_steps"]), w))
            mean_detection_delay_steps = (
                float(sum(v * w for v, w in delay_pairs) / sum(w for _, w in delay_pairs))
                if delay_pairs
                else None
            )

            recovered_values = [
                int(r["recovered_episodes"])
                for r in group
                if r.get("recovered_episodes") is not None
            ]
            recovered_episodes: int | None = (
                int(sum(recovered_values))
                if len(recovered_values) == len(group)
                else None
            )
            recovery_pairs = [
                (
                    float(r["mean_recovery_steps"]),
                    float(r["recovered_episodes"])
                    if r.get("recovered_episodes") is not None
                    else float(r["episodes"]),
                )
                for r in group
                if r.get("mean_recovery_steps") is not None
            ]
            recovery_pairs = [(v, w) for v, w in recovery_pairs if w > 0.0]
            mean_recovery_steps = (
                float(
                    sum(v * w for v, w in recovery_pairs)
                    / sum(w for _, w in recovery_pairs)
                )
                if recovery_pairs
                else None
            )
        else:
            in_window_detection_rate = None
            missed_detections = None
            mean_detection_delay_steps = None
            recovered_episodes = None
            mean_recovery_steps = None

        aggregated.append(
            {
                "attack_case": attack_case,
                "attack_name": str(first.get("attack_name", attack_case)),
                "defense": defense,
                "defense_name": str(first.get("defense_name", defense)),
                "policies": len({str(r["policy"]) for r in group if "policy" in r}) or len(group),
                "episodes": episodes,
                "successes": successes,
                "task_success_rate": task_success_rate,
                "clean_success_denominator": clean_success_denominator,
                "attack_success_rate": attack_success_rate,
                "paired_success_difference_vs_clean": paired_success_difference_vs_clean,
                "abort_rate": abort_rate,
                "mean_final_error_m": _weighted_mean(
                    group, "mean_final_error_m", "episodes"
                ),
                "mean_terminal_distance_m": _weighted_mean(
                    group, "mean_terminal_distance_m", "episodes"
                ),
                "mean_window_distance_m": _weighted_mean(
                    group, "mean_window_distance_m", "episodes"
                ),
                "paired_window_mean_delta_m": _weighted_mean(
                    group, "paired_window_mean_delta_m", "episodes"
                ),
                "mean_control_effort": _weighted_mean(
                    group, "mean_control_effort", "episodes"
                ),
                "clean_false_alarm_step_rate": clean_false_alarm_step_rate,
                "clean_false_alarm_episode_rate": clean_false_alarm_episode_rate,
                "in_window_detection_rate": in_window_detection_rate,
                "missed_detections": missed_detections,
                "mean_detection_delay_steps": mean_detection_delay_steps,
                "recovered_episodes": recovered_episodes,
                "mean_recovery_steps": mean_recovery_steps,
                "mean_applied_angle_mae_rad": _weighted_mean(
                    group, "mean_applied_angle_mae_rad", "episodes"
                ),
                "mean_applied_q1_mae_rad": _weighted_mean(
                    group, "mean_applied_q1_mae_rad", "episodes"
                ),
                "mean_monitor_us": _weighted_mean(group, "mean_monitor_us", "episodes"),
            }
        )

    return aggregated


def collect_seed_set(
    seed_base: int,
    episodes: int,
    num_models: int,
    stride: int = 1000,
) -> set[int]:
    """Expand per-model contiguous seed blocks into a flat set."""
    if episodes < 0 or num_models < 0 or episodes > stride:
        raise ValueError(
            f"Invalid seed block geometry: episodes={episodes}, num_models={num_models}, stride={stride}"
        )
    seeds: set[int] = set()
    for index in range(num_models):
        start = int(seed_base) + index * int(stride)
        seeds.update(range(start, start + int(episodes)))
    return seeds


__all__ = [
    "aggregate_across_policies",
    "collect_seed_set",
    "recovery_time",
    "summarize_matrix",
]
