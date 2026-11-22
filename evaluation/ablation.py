"""Direction 4A velocity-noise and position-noise ablation sweeps."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any

import numpy as np
from stable_baselines3 import SAC
import torch

from attacks import create_attack
from defenses import create_defense
from core.env_wrapper import make_ablation_env
from core.security import ArmGeometry

from .metrics import aggregate_across_policies, collect_seed_set, summarize_matrix
from .presets import (
    ABLATION_BASE,
    AttackCaseSpec,
    DEFAULT_THREE_MODELS,
    validate_disjoint_seeds,
)
from .runner import (
    calibrate_policy,
    populate_paired_deltas,
    run_paired_trial,
    validate_model_paths,
    write_csv,
    write_json,
)

ABLATION_DEFENSES: tuple[str, ...] = (
    "no_defense",
    "original_fail_stop",
    "continuous_velocity",
    "ik_velocity_fusion",
)

DEFAULT_VEL_SIGMAS: dict[str, tuple[float, ...]] = {
    "smoke": (0.0, 0.5),
    "full": (0.0, 0.05, 0.2, 0.5, 1.0),
}

DEFAULT_POS_SIGMAS: dict[str, tuple[float, ...]] = {
    "smoke": (0.002, 0.008),
    "full": (0.002, 0.005, 0.010),
}

DEFAULT_VEL_ABLATION_SEEDS: dict[str, tuple[int, int]] = {
    "smoke": (1050000, ABLATION_BASE),
    "full": (1400000, 1450000),
}

DEFAULT_POS_ABLATION_SEEDS: dict[str, tuple[int, int]] = {
    "smoke": (1060000, 1350000),
    "full": (1500000, 1550000),
}


def resolve_ablation_seed_bases(
    mode: str,
    preset: str,
    seed_base: int | None = None,
    cal_base: int | None = None,
) -> tuple[int, int]:
    """Return ``(cal_base, seed_base)`` for an ablation sweep mode and preset."""
    if preset not in ("smoke", "full"):
        raise ValueError(f"Ablation preset must be 'smoke' or 'full', got {preset!r}")
    if mode == "velocity":
        default_cal, default_seed = DEFAULT_VEL_ABLATION_SEEDS[preset]
    elif mode == "position":
        default_cal, default_seed = DEFAULT_POS_ABLATION_SEEDS[preset]
    else:
        raise ValueError(f"Ablation mode must be 'velocity' or 'position', got {mode!r}")
    resolved_cal = default_cal if cal_base is None else int(cal_base)
    resolved_seed = default_seed if seed_base is None else int(seed_base)
    return resolved_cal, resolved_seed


def _resolve_ablation_defaults(
    models: Sequence[Path | str] | None,
    preset: str,
    episodes: int | None,
    calibration_episodes: int | None,
) -> tuple[list[Path], int, int]:
    if preset not in ("smoke", "full"):
        raise ValueError(f"Ablation preset must be 'smoke' or 'full', got {preset!r}")
    default_models = (
        ("models/sac_seed_1_sync/model.zip",)
        if preset == "smoke"
        else DEFAULT_THREE_MODELS
    )
    model_paths = validate_model_paths(
        [Path(m) for m in (models if models is not None else default_models)]
    )
    resolved_episodes = (
        int(episodes) if episodes is not None else (4 if preset == "smoke" else 30)
    )
    resolved_cal_episodes = (
        int(calibration_episodes)
        if calibration_episodes is not None
        else (10 if preset == "smoke" else 100)
    )
    if resolved_episodes < 1 or resolved_cal_episodes < 1:
        raise ValueError("episodes and calibration_episodes must be >= 1")
    if resolved_episodes > 1000 or resolved_cal_episodes > 1000:
        raise ValueError("episodes and calibration_episodes must be <= 1000")
    return model_paths, resolved_episodes, resolved_cal_episodes


def _run_noise_ablation(
    *,
    mode: str,
    noise_param: str,
    sigmas: Sequence[float],
    attack_spec: AttackCaseSpec,
    models: Sequence[Path | str] | None,
    out: Path,
    preset: str,
    episodes: int | None,
    calibration_episodes: int | None,
    seed_base: int,
    cal_base: int,
) -> dict[str, Any]:
    out_dir = Path(out)
    if out_dir.exists():
        raise FileExistsError(f"Output directory already exists: {out_dir}")

    sigma_values = [float(s) for s in sigmas]
    if not sigma_values or any((not np.isfinite(s) or s < 0.0) for s in sigma_values):
        raise ValueError(f"{noise_param} sigmas must be non-empty finite values >= 0")

    model_paths, resolved_episodes, resolved_cal_episodes = _resolve_ablation_defaults(
        models=models,
        preset=preset,
        episodes=episodes,
        calibration_episodes=calibration_episodes,
    )

    cal_seeds = collect_seed_set(int(cal_base), resolved_cal_episodes, len(model_paths))
    test_seeds = collect_seed_set(int(seed_base), resolved_episodes, len(model_paths))
    validate_disjoint_seeds(cal_seeds, test_seeds)

    # Validate attack and defense instantiation before creating output directory.
    _ = create_attack(attack_spec.attack_name, **attack_spec.params)
    for def_name in ABLATION_DEFENSES:
        _ = create_defense(def_name)

    out_dir.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(1)

    config: dict[str, Any] = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "noise_type": noise_param,
        "sigmas": sigma_values,
        "preset": preset,
        "models": [str(p.resolve()) for p in model_paths],
        "policy_names": [p.parent.name for p in model_paths],
        "attack": {
            "case_id": attack_spec.case_id,
            "attack_name": attack_spec.attack_name,
            "params": dict(attack_spec.params),
        },
        "defenses": list(ABLATION_DEFENSES),
        "episodes": resolved_episodes,
        "calibration_episodes": resolved_cal_episodes,
        "seed_base": int(seed_base),
        "cal_base": int(cal_base),
    }
    write_json(out_dir / "config.json", config)

    loaded_models = {p.parent.name: SAC.load(p, device="cpu") for p in model_paths}
    all_episodes: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    calibrations: dict[str, dict[str, Any]] = {}
    started = time.perf_counter()

    try:
        for sigma in sigma_values:
            pos_sigma = float(sigma) if noise_param == "pos_sigma" else 0.002
            vel_sigma = float(sigma) if noise_param == "vel_sigma" else 0.0
            sigma_key = f"{sigma:g}"
            calibrations[sigma_key] = {}
            sigma_episodes: list[dict[str, Any]] = []
            sigma_thresholds: list[float] = []

            for model_index, model_path in enumerate(model_paths):
                policy_name = model_path.parent.name
                model = loaded_models[policy_name]
                env = make_ablation_env(
                    seed=int(seed_base) + model_index * 1000,
                    pos_sigma=pos_sigma,
                    vel_sigma=vel_sigma,
                )
                geometry = ArmGeometry.from_model(env.unwrapped.model)
                try:
                    cal = calibrate_policy(
                        model=model,
                        geometry=geometry,
                        episodes=resolved_cal_episodes,
                        seed_base=int(cal_base) + model_index * 1000,
                        pos_sigma=pos_sigma,
                        vel_sigma=vel_sigma,
                    )
                    calibrations[sigma_key][policy_name] = cal.to_dict()
                    sigma_thresholds.append(float(cal.threshold_m))
                    write_json(out_dir / "calibration.json", calibrations)

                    for episode in range(resolved_episodes):
                        seed = int(seed_base) + model_index * 1000 + episode
                        sign = 1 if episode % 2 == 0 else -1
                        episode_rows: list[dict[str, Any]] = []
                        distances_map: dict[tuple[str, str, str, int], list[float]] = {}

                        conditions: list[tuple[AttackCaseSpec, str]] = [
                            (AttackCaseSpec("clean", "clean", {}), "no_defense")
                        ] + [(attack_spec, def_name) for def_name in ABLATION_DEFENSES]

                        for case_spec, def_name in conditions:
                            attack = create_attack(
                                case_spec.attack_name, **case_spec.params
                            )
                            defense = create_defense(def_name)
                            row = run_paired_trial(
                                model=model,
                                env=env,
                                geometry=geometry,
                                calibration=cal,
                                attack=attack,
                                defense=defense,
                                seed=seed,
                                policy_name=policy_name,
                                attack_case=case_spec.case_id,
                                defense_id=def_name,
                                sign=sign,
                            )
                            distances = row.pop("_distances")
                            distances_map[
                                (policy_name, case_spec.case_id, def_name, seed)
                            ] = distances
                            row["noise_type"] = noise_param
                            row["noise_sigma"] = float(sigma)
                            row["cal_threshold_m"] = float(cal.threshold_m)
                            episode_rows.append(row)

                        populate_paired_deltas(episode_rows, distances_map)
                        sigma_episodes.extend(episode_rows)
                finally:
                    env.close()

            all_episodes.extend(sigma_episodes)
            per_policy_sigma = summarize_matrix(sigma_episodes)
            across_sigma = aggregate_across_policies(per_policy_sigma)
            mean_thresh = float(np.mean(sigma_thresholds)) if sigma_thresholds else None
            for s_row in across_sigma:
                enriched = {
                    "noise_type": noise_param,
                    "noise_sigma": float(sigma),
                    "mean_cal_threshold_m": mean_thresh,
                    **s_row,
                }
                summary_rows.append(enriched)
            print(
                f"[{mode} ablation] {noise_param}={sigma:g} complete "
                f"({len(sigma_episodes)} episodes)",
                flush=True,
            )
    finally:
        write_csv(out_dir / "ablation_episodes.csv", all_episodes)
        write_csv(out_dir / "ablation_summary.csv", summary_rows)

    elapsed = time.perf_counter() - started
    status = {
        "complete": True,
        "mode": mode,
        "noise_type": noise_param,
        "sigmas": sigma_values,
        "evaluation_episodes": len(all_episodes),
        "calibration_episodes": resolved_cal_episodes * len(model_paths) * len(sigma_values),
        "elapsed_seconds": elapsed,
    }
    write_json(out_dir / "run_status.json", status)
    return {
        "out": out_dir,
        "status": status,
        "summary": summary_rows,
    }


def run_velocity_noise_ablation(
    models: Sequence[Path | str] | None,
    out: Path,
    preset: str = "smoke",
    episodes: int | None = None,
    calibration_episodes: int | None = None,
    vel_sigmas: Sequence[float] | None = None,
    seed_base: int | None = None,
    cal_base: int | None = None,
) -> dict[str, Any]:
    """Sweep velocity sensor noise under sustained bias with fresh calibration per sigma."""
    resolved_cal_base, resolved_seed_base = resolve_ablation_seed_bases(
        mode="velocity",
        preset=preset,
        seed_base=seed_base,
        cal_base=cal_base,
    )
    sigmas = (
        list(vel_sigmas)
        if vel_sigmas is not None
        else list(DEFAULT_VEL_SIGMAS.get(preset, DEFAULT_VEL_SIGMAS["full"]))
    )
    attack_spec = AttackCaseSpec(
        case_id="sustained_bias_e1.0_s40_d60",
        attack_name="bias",
        params={"epsilon": 1.0, "start": 40, "duration": 60},
    )
    return _run_noise_ablation(
        mode="velocity",
        noise_param="vel_sigma",
        sigmas=sigmas,
        attack_spec=attack_spec,
        models=models,
        out=out,
        preset=preset,
        episodes=episodes,
        calibration_episodes=calibration_episodes,
        seed_base=resolved_seed_base,
        cal_base=resolved_cal_base,
    )


def run_position_noise_ablation(
    models: Sequence[Path | str] | None,
    out: Path,
    preset: str = "smoke",
    episodes: int | None = None,
    calibration_episodes: int | None = None,
    pos_sigmas: Sequence[float] | None = None,
    seed_base: int | None = None,
    cal_base: int | None = None,
) -> dict[str, Any]:
    """Sweep position sensor noise under late strong bias with fresh calibration per sigma."""
    resolved_cal_base, resolved_seed_base = resolve_ablation_seed_bases(
        mode="position",
        preset=preset,
        seed_base=seed_base,
        cal_base=cal_base,
    )
    sigmas = (
        list(pos_sigmas)
        if pos_sigmas is not None
        else list(DEFAULT_POS_SIGMAS.get(preset, DEFAULT_POS_SIGMAS["full"]))
    )
    attack_spec = AttackCaseSpec(
        case_id="late_bias_e1.0_s80_d20",
        attack_name="bias",
        params={"epsilon": 1.0, "start": 80, "duration": 20},
    )
    return _run_noise_ablation(
        mode="position",
        noise_param="pos_sigma",
        sigmas=sigmas,
        attack_spec=attack_spec,
        models=models,
        out=out,
        preset=preset,
        episodes=episodes,
        calibration_episodes=calibration_episodes,
        seed_base=resolved_seed_base,
        cal_base=resolved_cal_base,
    )


__all__ = [
    "ABLATION_DEFENSES",
    "DEFAULT_POS_ABLATION_SEEDS",
    "DEFAULT_POS_SIGMAS",
    "DEFAULT_VEL_ABLATION_SEEDS",
    "DEFAULT_VEL_SIGMAS",
    "resolve_ablation_seed_bases",
    "run_position_noise_ablation",
    "run_velocity_noise_ablation",
]
