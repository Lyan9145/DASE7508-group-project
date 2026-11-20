"""Experiment presets, attack/defense specs, and Phase-2 seed block guards."""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any


CAL_BASE: int = 1000000
DEV_BASE: int = 1100000
TEST_BASE: int = 1200000
ABLATION_BASE: int = 1300000

HISTORICAL_SEED_BLOCKS: tuple[tuple[int, int], ...] = (
    (10000, 13999),
    (200000, 202999),
    (300000, 302999),
    (500000, 502999),
    (800000, 802999),
    (900000, 932999),
)

DEFAULT_THREE_MODELS: tuple[str, ...] = (
    "models/sac_seed_1_sync/model.zip",
    "models/sac_seed_2_sync/model.zip",
    "models/sac_seed_3_sync/model.zip",
)

ALL_DEFENSE_NAMES: tuple[str, ...] = (
    "no_defense",
    "original_fail_stop",
    "grace1",
    "cusum",
    "sliding_window",
    "continuous_velocity",
    "ik_velocity_fusion",
    "fallback_policy",
)


@dataclass(frozen=True)
class AttackCaseSpec:
    """Named attack test case mapped to a registered attack and parameters."""

    case_id: str
    attack_name: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DefenseSpec:
    """Named defense configuration mapped to a registered defense and parameters."""

    defense_id: str
    defense_name: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PresetSpec:
    """Complete evaluation matrix preset."""

    name: str
    models: tuple[str, ...]
    episodes: int
    calibration_episodes: int
    cal_base: int
    test_base: int
    pos_sigma: float
    vel_sigma: float
    attacks: tuple[AttackCaseSpec, ...]
    defenses: tuple[DefenseSpec, ...]


def validate_disjoint_seeds(
    cal_seeds: Iterable[int],
    test_seeds: Iterable[int],
    *extra_seed_sets: Iterable[int],
    historical_blocks: Sequence[tuple[int, int]] = HISTORICAL_SEED_BLOCKS,
    check_historical: bool = True,
) -> None:
    """Verify calibration, test, extra, and historical seed sets are strictly disjoint."""
    cal_set = {int(s) for s in cal_seeds}
    test_set = {int(s) for s in test_seeds}

    overlap = cal_set & test_set
    if overlap:
        sample = sorted(overlap)[:5]
        raise ValueError(
            f"Calibration and test seeds overlap ({len(overlap)} seeds, e.g. {sample})"
        )

    for idx, extra in enumerate(extra_seed_sets):
        extra_set = {int(s) for s in extra}
        cal_overlap = cal_set & extra_set
        if cal_overlap:
            raise ValueError(
                f"Calibration seeds overlap extra seed set {idx}: {sorted(cal_overlap)[:5]}"
            )
        test_overlap = test_set & extra_set
        if test_overlap:
            raise ValueError(
                f"Test seeds overlap extra seed set {idx}: {sorted(test_overlap)[:5]}"
            )

    if check_historical:
        for label, seed_set in (("calibration", cal_set), ("test", test_set)):
            for lo, hi in historical_blocks:
                conflicts = [s for s in seed_set if lo <= s <= hi]
                if conflicts:
                    raise ValueError(
                        f"Phase-2 {label} seeds intersect historical block [{lo}..{hi}] "
                        f"(e.g. {sorted(conflicts)[:5]})"
                    )


def _format_eps(eps: float) -> str:
    if float(eps).is_integer():
        return f"{eps:.1f}"
    return f"{eps:g}"


def _late_strong_attacks() -> tuple[AttackCaseSpec, ...]:
    cases: list[AttackCaseSpec] = [AttackCaseSpec("clean", "clean", {})]
    windows = (("late", 80, 20), ("sustained", 60, 40))
    epsilons = (0.3, 0.5, 1.0, 1.57)
    for kind in ("bias", "ramp"):
        for label, start, duration in windows:
            for eps in epsilons:
                cases.append(
                    AttackCaseSpec(
                        case_id=f"{label}_{kind}_e{_format_eps(eps)}_s{start}_d{duration}",
                        attack_name=kind,
                        params={
                            "epsilon": float(eps),
                            "start": int(start),
                            "duration": int(duration),
                        },
                    )
                )
    cases.extend(
        [
            AttackCaseSpec(
                case_id="sinusoidal_e1.0_s80_d20",
                attack_name="sinusoidal",
                params={
                    "epsilon": 1.0,
                    "start": 80,
                    "duration": 20,
                    "freq_hz": 5.0,
                    "phase": 0.0,
                },
            ),
            AttackCaseSpec(
                case_id="freeze_s60_d40",
                attack_name="freeze",
                params={"start": 60, "duration": 40},
            ),
            AttackCaseSpec(
                case_id="replay_s60_d40",
                attack_name="replay",
                params={"start": 60, "duration": 40, "replay_len": 10},
            ),
        ]
    )
    return tuple(cases)


def _full_matrix_attacks() -> tuple[AttackCaseSpec, ...]:
    cases = list(_late_strong_attacks())
    cases.extend(
        [
            AttackCaseSpec(
                case_id="random_bias_e1.0_s80_d20",
                attack_name="random_bias",
                params={"epsilon": 1.0, "start": 80, "duration": 20},
            ),
            AttackCaseSpec(
                case_id="random_ramp_e1.0_s80_d20",
                attack_name="random_ramp",
                params={"epsilon": 1.0, "start": 80, "duration": 20},
            ),
            AttackCaseSpec(
                case_id="threshold_aware_e0.1_s80_d20",
                attack_name="threshold_aware",
                params={
                    "epsilon": 0.1,
                    "start": 80,
                    "duration": 20,
                    "margin": 0.85,
                },
            ),
            AttackCaseSpec(
                case_id="threshold_aware_e0.3_s60_d40",
                attack_name="threshold_aware",
                params={
                    "epsilon": 0.3,
                    "start": 60,
                    "duration": 40,
                    "margin": 0.85,
                },
            ),
            AttackCaseSpec(
                case_id="elbow_flip_s60_d30",
                attack_name="elbow_flip",
                params={"start": 60, "duration": 30},
            ),
            AttackCaseSpec(
                case_id="elbow_flip_s80_d20",
                attack_name="elbow_flip",
                params={"start": 80, "duration": 20},
            ),
            AttackCaseSpec(
                case_id="joint_vel_coupled_e1.0_s60_d40",
                attack_name="joint_vel_coupled",
                params={
                    "epsilon": 1.0,
                    "start": 60,
                    "duration": 40,
                    "vel_bias": 0.5,
                },
            ),
            AttackCaseSpec(
                case_id="policy_gradient_e0.5_s80_d20",
                attack_name="policy_gradient",
                params={
                    "epsilon": 0.5,
                    "start": 80,
                    "duration": 20,
                    "n_steps": 5,
                },
            ),
            AttackCaseSpec(
                case_id="policy_gradient_e1.0_s60_d40",
                attack_name="policy_gradient",
                params={
                    "epsilon": 1.0,
                    "start": 60,
                    "duration": 40,
                    "n_steps": 5,
                },
            ),
        ]
    )
    return tuple(cases)


def _defense_specs(names: Sequence[str]) -> tuple[DefenseSpec, ...]:
    return tuple(DefenseSpec(defense_id=n, defense_name=n, params={}) for n in names)


def get_preset(name: str) -> PresetSpec:
    """Return a named Phase-2 evaluation preset: ``'smoke'``, ``'late_strong'``, or ``'full_matrix'``."""
    if name == "smoke":
        return PresetSpec(
            name="smoke",
            models=("models/sac_seed_1_sync/model.zip",),
            episodes=4,
            calibration_episodes=10,
            cal_base=CAL_BASE,
            test_base=DEV_BASE,
            pos_sigma=0.002,
            vel_sigma=0.0,
            attacks=(
                AttackCaseSpec("clean", "clean", {}),
                AttackCaseSpec(
                    "late_bias_e1.0_s80_d20",
                    "bias",
                    {"epsilon": 1.0, "start": 80, "duration": 20},
                ),
                AttackCaseSpec(
                    "sustained_bias_e1.0_s60_d40",
                    "bias",
                    {"epsilon": 1.0, "start": 60, "duration": 40},
                ),
                AttackCaseSpec(
                    "elbow_flip_s60_d30",
                    "elbow_flip",
                    {"start": 60, "duration": 30},
                ),
            ),
            defenses=_defense_specs(
                (
                    "no_defense",
                    "original_fail_stop",
                    "grace1",
                    "cusum",
                    "continuous_velocity",
                    "ik_velocity_fusion",
                )
            ),
        )
    if name == "late_strong":
        return PresetSpec(
            name="late_strong",
            models=DEFAULT_THREE_MODELS,
            episodes=30,
            calibration_episodes=100,
            cal_base=CAL_BASE,
            test_base=TEST_BASE,
            pos_sigma=0.002,
            vel_sigma=0.0,
            attacks=_late_strong_attacks(),
            defenses=_defense_specs(ALL_DEFENSE_NAMES),
        )
    if name == "full_matrix":
        return PresetSpec(
            name="full_matrix",
            models=DEFAULT_THREE_MODELS,
            episodes=30,
            calibration_episodes=100,
            cal_base=CAL_BASE,
            test_base=TEST_BASE,
            pos_sigma=0.002,
            vel_sigma=0.0,
            attacks=_full_matrix_attacks(),
            defenses=_defense_specs(ALL_DEFENSE_NAMES),
        )
    raise KeyError(
        f"Unknown preset {name!r}; expected one of: 'smoke', 'late_strong', 'full_matrix'"
    )


def list_presets() -> list[str]:
    """Return available preset names."""
    return ["smoke", "late_strong", "full_matrix"]


__all__ = [
    "ABLATION_BASE",
    "ALL_DEFENSE_NAMES",
    "AttackCaseSpec",
    "CAL_BASE",
    "DEFAULT_THREE_MODELS",
    "DEV_BASE",
    "DefenseSpec",
    "HISTORICAL_SEED_BLOCKS",
    "PresetSpec",
    "TEST_BASE",
    "get_preset",
    "list_presets",
    "validate_disjoint_seeds",
]
