"""Calibration, paired trial execution, and evaluation matrix runner."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import time
from typing import Any, Sequence, TextIO

import gymnasium as gym
import numpy as np
from stable_baselines3 import SAC
import torch

from attacks import AttackContext, BaseAttack, create_attack, list_attacks
from defenses import (
    BaseDefense,
    CalibrationStats,
    DefenseContext,
    VALID_DEFENSE_STATES,
    create_defense,
    list_defenses,
)
from core.env_wrapper import make_ablation_env
from core.security import ArmGeometry, wrap

from .metrics import (
    aggregate_across_policies,
    collect_seed_set,
    recovery_time,
    summarize_matrix,
)
from .presets import (
    AttackCaseSpec,
    DefenseSpec,
    get_preset,
    validate_disjoint_seeds,
)


_DEFAULT_CLI_ATTACK_PARAMS: dict[str, dict[str, Any]] = {
    "clean": {},
    "bias": {"epsilon": 1.0, "start": 80, "duration": 20},
    "ramp": {"epsilon": 1.0, "start": 80, "duration": 20},
    "random_bias": {"epsilon": 1.0, "start": 80, "duration": 20},
    "random_ramp": {"epsilon": 1.0, "start": 80, "duration": 20},
    "sinusoidal": {"epsilon": 1.0, "start": 80, "duration": 20, "freq_hz": 5.0, "phase": 0.0},
    "freeze": {"start": 60, "duration": 40},
    "replay": {"start": 60, "duration": 40, "replay_len": 10},
    "threshold_aware": {"epsilon": 0.1, "start": 80, "duration": 20, "margin": 0.85},
    "elbow_flip": {"start": 60, "duration": 30},
    "joint_vel_coupled": {"epsilon": 1.0, "start": 60, "duration": 40, "vel_bias": 0.5},
    "policy_gradient": {"epsilon": 0.5, "start": 80, "duration": 20, "n_steps": 5},
}


def write_json(path: Path, value: Any) -> None:
    """Serialize ``value`` as formatted UTF-8 JSON (disallowing NaN/Infinity)."""
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    """Write a sequence of uniform row dictionaries to CSV."""
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for pkg in ("torch", "numpy", "gymnasium", "mujoco", "stable-baselines3", "matplotlib"):
        try:
            versions[pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            versions[pkg] = "unavailable"
    return versions


def _git_head(cwd: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.stdout.strip()
    except OSError:
        return ""


def calibrate_policy(
    model: Any,
    geometry: ArmGeometry,
    episodes: int,
    seed_base: int,
    pos_sigma: float = 0.002,
    vel_sigma: float = 0.0,
) -> CalibrationStats:
    """Calibrate residual and joint-jump statistics over clean rollouts."""
    if int(episodes) < 1:
        raise ValueError("episodes must be >= 1")

    residuals: list[float] = []
    q0_jumps: list[float] = []
    q1_jumps: list[float] = []
    env = make_ablation_env(
        seed=int(seed_base),
        pos_sigma=float(pos_sigma),
        vel_sigma=float(vel_sigma),
    )
    dt = float(env.unwrapped.dt)
    try:
        for index in range(int(episodes)):
            seed = int(seed_base) + index
            obs, _ = env.reset(
                seed=seed,
                options={
                    "noise_seed": seed + 10000000,
                    "vel_noise_seed": seed + 50000000,
                },
            )
            prev_q0: float | None = None
            prev_q1: float | None = None
            prev_v0: float = 0.0
            prev_v1: float = 0.0
            for step in range(100):
                residuals.append(float(geometry.residual(obs)))
                q0 = float(np.arctan2(obs[2], obs[0]))
                q1 = float(np.arctan2(obs[3], obs[1]))
                v0 = float(obs[6])
                v1 = float(obs[7])
                if step >= 1 and prev_q0 is not None and prev_q1 is not None:
                    q0_jumps.append(abs(wrap(q0 - (prev_q0 + prev_v0 * dt))))
                    q1_jumps.append(abs(wrap(q1 - (prev_q1 + prev_v1 * dt))))
                prev_q0, prev_q1, prev_v0, prev_v1 = q0, q1, v0, v1
                action, _ = model.predict(obs, deterministic=True)
                obs, _, terminated, truncated, _ = env.step(action)
                if terminated or truncated:
                    break
    finally:
        env.close()

    return CalibrationStats(
        threshold_m=float(np.quantile(residuals, 0.99, method="linear")),
        residual_mean_m=float(np.mean(residuals)),
        residual_std_m=float(np.std(residuals)),
        residual_p95_m=float(np.quantile(residuals, 0.95, method="linear")),
        residual_p99_m=float(np.quantile(residuals, 0.99, method="linear")),
        q0_jump_p99_rad=float(np.quantile(q0_jumps, 0.99, method="linear")),
        q0_jump_p999_rad=float(np.quantile(q0_jumps, 0.999, method="linear")),
        q1_jump_p99_rad=float(np.quantile(q1_jumps, 0.99, method="linear")),
        q1_jump_p999_rad=float(np.quantile(q1_jumps, 0.999, method="linear")),
        control_dt_seconds=dt,
        episodes=int(episodes),
        seed_base=int(seed_base),
    )


def run_paired_trial(
    model: Any,
    env: gym.Env,
    geometry: ArmGeometry,
    calibration: CalibrationStats,
    attack: BaseAttack,
    defense: BaseDefense,
    seed: int,
    *,
    policy_name: str,
    attack_case: str,
    defense_id: str,
    sign: int = 1,
    fallback_policy: Any | None = None,
    trace_file: TextIO | None = None,
    noise_seed: int | None = None,
    vel_noise_seed: int | None = None,
) -> dict[str, Any]:
    """Run one paired episode enforcing the Attack -> Defense trust boundary."""
    resolved_seed = int(seed)
    resolved_noise_seed = (
        resolved_seed + 10000000 if noise_seed is None else int(noise_seed)
    )
    resolved_vel_seed = (
        resolved_seed + 50000000 if vel_noise_seed is None else int(vel_noise_seed)
    )
    obs, info = env.reset(
        seed=resolved_seed,
        options={
            "noise_seed": resolved_noise_seed,
            "vel_noise_seed": resolved_vel_seed,
        },
    )
    dt = float(env.unwrapped.dt)

    attack_ctx = AttackContext(
        geometry=geometry,
        dt=dt,
        calibrated_threshold_m=float(calibration.threshold_m),
        policy=model,
    )
    # Trust boundary: DefenseContext never receives raw_obs, info['truth'], or AttackResult.
    defense_ctx = DefenseContext(
        geometry=geometry,
        dt=dt,
        calibration=calibration,
        fallback_policy=fallback_policy,
    )
    attack.reset(seed=resolved_seed, sign=int(sign), context=attack_ctx)
    defense.reset(context=defense_ctx)

    distances: list[float] = [float(info["truth"]["distance"])]
    action_norms: list[float] = []
    alarm_steps: list[int] = []
    timings_ns: list[int] = []
    q0_errors: list[float] = []
    q1_errors: list[float] = []
    detection_steps = 0
    aborted = False

    for step in range(100):
        raw_snapshot = np.array(obs, dtype=np.float64, copy=True)
        attack_res = attack.apply(raw_snapshot, step, attack_ctx)
        if not np.array_equal(raw_snapshot, obs):
            raise AssertionError(
                f"Attack {attack.name!r} mutated raw_obs at step {step}"
            )

        reported = np.asarray(attack_res.reported_obs, dtype=np.float64)
        if reported.shape != raw_snapshot.shape:
            raise AssertionError(
                f"Attack {attack.name!r} returned shape {reported.shape}, expected {raw_snapshot.shape}"
            )
        unattacked = [
            idx
            for idx in range(reported.shape[0])
            if idx not in attack_res.attacked_channels
        ]
        if unattacked and not np.array_equal(
            reported[unattacked], raw_snapshot[unattacked]
        ):
            raise AssertionError(
                f"Attack {attack.name!r} altered unattacked channels {unattacked} at step {step}"
            )

        reported_copy = np.array(reported, dtype=np.float64, copy=True)
        started_ns = time.perf_counter_ns()
        defense_res = defense.process(reported_copy, step, defense_ctx)
        duration_ns = time.perf_counter_ns() - started_ns
        if not np.array_equal(reported_copy, reported):
            raise AssertionError(
                f"Defense {defense.name!r} mutated reported_obs at step {step}"
            )
        if defense_res.state not in VALID_DEFENSE_STATES:
            raise AssertionError(
                f"Defense {defense.name!r} returned invalid state {defense_res.state!r}"
            )

        policy_obs = np.asarray(defense_res.policy_obs, dtype=np.float64)
        # Step 0 initializes estimators and is excluded from alarm opportunities.
        if step >= 1:
            detection_steps += 1
            timings_ns.append(int(duration_ns))
            if defense_res.alarm:
                alarm_steps.append(step)

        aborted = bool(defense_res.abort)
        if not aborted:
            q0_applied = float(np.arctan2(policy_obs[2], policy_obs[0]))
            q1_applied = float(np.arctan2(policy_obs[3], policy_obs[1]))
            true_angles = info["truth"]["angles"]
            q0_errors.append(abs(wrap(q0_applied - float(true_angles[0]))))
            q1_errors.append(abs(wrap(q1_applied - float(true_angles[1]))))

        record: dict[str, Any] | None = None
        if trace_file is not None:
            record = {
                "policy": policy_name,
                "attack_case": attack_case,
                "attack_name": attack.name,
                "defense": defense_id,
                "defense_name": defense.name,
                "seed": resolved_seed,
                "noise_seed": resolved_noise_seed,
                "vel_noise_seed": resolved_vel_seed,
                "observation_step": step,
                "delta_rad": float(attack_res.delta_rad),
                "is_active": bool(attack_res.is_active),
                "raw_sensor": raw_snapshot.tolist(),
                "reported_sensor": reported.tolist(),
                "policy_sensor": policy_obs.tolist(),
                "truth_before": info["truth"],
                "defense_status": {
                    "alarm": bool(defense_res.alarm),
                    "abort": bool(defense_res.abort),
                    "state": str(defense_res.state),
                    "residual_m": float(defense_res.residual_m),
                    "alarm_streak": int(defense_res.alarm_streak),
                    "action_overridden": defense_res.action_override is not None,
                },
                "monitor_ns": int(duration_ns),
                "action": None,
                "truth_after": None,
            }

        if not aborted:
            if defense_res.action_override is not None:
                action = np.asarray(defense_res.action_override, dtype=np.float32)
            else:
                action, _ = model.predict(policy_obs, deterministic=True)
            action_norms.append(float(np.sum(np.square(action))))
            obs, _, terminated, truncated, info = env.step(action)
            distances.append(float(info["truth"]["distance"]))
            if record is not None:
                record["action"] = np.asarray(action, dtype=float).tolist()
                record["truth_after"] = info["truth"]
        else:
            terminated = False
            truncated = False

        if trace_file is not None and record is not None:
            trace_file.write(json.dumps(record, allow_nan=False) + "\n")

        if aborted or terminated or truncated:
            break

    bounds = attack.window_bounds()
    is_clean = attack.name == "clean" or bounds is None
    if not is_clean and bounds is not None:
        attack_start, duration = int(bounds[0]), int(bounds[1])
        end = attack_start + duration
        window = distances[attack_start + 1 : min(end + 11, len(distances))]
        relevant_alarms = [t for t in alarm_steps if attack_start <= t < end]
        in_window_detected: bool | None = bool(relevant_alarms)
        detection_delay_steps = (
            relevant_alarms[0] - attack_start if relevant_alarms else None
        )
        missed_detection = not bool(relevant_alarms)
        recovery_steps = None if aborted else recovery_time(distances, bounds)
        expected_window_samples = max(0, min(100, end + 10) - attack_start)
        window_complete: bool | None = len(window) == expected_window_samples
    else:
        attack_start = None
        duration = None
        window = []
        in_window_detected = None
        detection_delay_steps = None
        missed_detection = False
        recovery_steps = None
        window_complete = None

    final_mean = float(np.mean(distances[-10:]))
    task_success = bool(
        not aborted and len(action_norms) == 100 and final_mean <= 0.03
    )

    return {
        "_distances": distances,
        "policy": policy_name,
        "attack_case": attack_case,
        "attack_name": attack.name,
        "defense": defense_id,
        "defense_name": defense.name,
        "seed": resolved_seed,
        "noise_seed": resolved_noise_seed,
        "vel_noise_seed": resolved_vel_seed,
        "sign": int(sign),
        "attack_start": attack_start,
        "duration": duration,
        "steps": len(action_norms),
        "aborted": aborted,
        "task_success": task_success,
        "final_10_mean_distance_m": final_mean,
        "terminal_distance_m": float(distances[-1]),
        "window_mean_distance_m": float(np.mean(window)) if window else None,
        "window_max_distance_m": float(max(window)) if window else None,
        "window_samples": len(window),
        "window_complete": window_complete,
        "paired_window_mean_delta_m": None,
        "paired_window_max_delta_m": None,
        "control_effort": float(sum(action_norms)),
        "alarm_count": len(alarm_steps),
        "detection_steps": detection_steps,
        "any_alarm": bool(alarm_steps),
        "in_window_detected": in_window_detected,
        "detection_delay_steps": detection_delay_steps,
        "missed_detection": missed_detection,
        "recovery_steps": recovery_steps,
        "applied_angle_mae_rad": float(np.mean(q0_errors)) if q0_errors else 0.0,
        "applied_q1_mae_rad": float(np.mean(q1_errors)) if q1_errors else 0.0,
        "monitor_total_ns": int(sum(timings_ns)),
        "monitor_calls": len(timings_ns),
        "monitor_median_us": (
            float(np.median(timings_ns) / 1000.0) if timings_ns else None
        ),
        "monitor_p95_us": (
            float(np.quantile(timings_ns, 0.95) / 1000.0) if timings_ns else None
        ),
    }


def resolve_attack_specs(
    tokens: Sequence[str] | None,
    preset_attacks: Sequence[AttackCaseSpec],
) -> list[AttackCaseSpec]:
    """Resolve CLI/API attack selectors from preset case IDs or registered attack names."""
    if tokens is None:
        return list(preset_attacks)

    preset_map = {spec.case_id: spec for spec in preset_attacks}
    full_map = {spec.case_id: spec for spec in get_preset("full_matrix").attacks}
    registered = set(list_attacks())
    resolved: list[AttackCaseSpec] = []
    seen_ids: set[str] = set()
    for token in tokens:
        if token in preset_map:
            spec = preset_map[token]
        elif token in full_map:
            spec = full_map[token]
        elif token in registered:
            spec = AttackCaseSpec(
                case_id=token,
                attack_name=token,
                params=dict(_DEFAULT_CLI_ATTACK_PARAMS.get(token, {})),
            )
        else:
            valid = sorted(set(preset_map) | set(full_map) | registered)
            raise ValueError(f"Unknown attack selector {token!r}; valid: {valid}")
        if spec.case_id in seen_ids:
            raise ValueError(f"Duplicate attack case {spec.case_id!r}")
        seen_ids.add(spec.case_id)
        resolved.append(spec)
    return resolved


def resolve_defense_specs(
    tokens: Sequence[str] | None,
    preset_defenses: Sequence[DefenseSpec],
) -> list[DefenseSpec]:
    """Resolve CLI/API defense selectors from preset IDs or registered defense names."""
    if tokens is None:
        return list(preset_defenses)

    preset_map = {spec.defense_id: spec for spec in preset_defenses}
    registered = set(list_defenses())
    resolved: list[DefenseSpec] = []
    seen_ids: set[str] = set()
    for token in tokens:
        if token in preset_map:
            spec = preset_map[token]
        elif token in registered:
            spec = DefenseSpec(defense_id=token, defense_name=token, params={})
        else:
            valid = sorted(set(preset_map) | registered)
            raise ValueError(f"Unknown defense selector {token!r}; valid: {valid}")
        if spec.defense_id in seen_ids:
            raise ValueError(f"Duplicate defense selector {spec.defense_id!r}")
        seen_ids.add(spec.defense_id)
        resolved.append(spec)
    return resolved


def validate_model_paths(model_paths: Sequence[Path]) -> list[Path]:
    """Validate existence, uniqueness, and distinct policy names for model paths."""
    paths = [Path(p) for p in model_paths]
    if not paths:
        raise ValueError("At least one model path is required")
    for p in paths:
        if not p.exists():
            raise FileNotFoundError(f"Model file does not exist: {p}")
    if len({p.resolve() for p in paths}) != len(paths):
        raise ValueError("Duplicate model paths provided")
    if len({p.parent.name for p in paths}) != len(paths):
        raise ValueError("Models must have unique parent directory names")
    return paths


def populate_paired_deltas(
    episode_rows: Sequence[dict[str, Any]],
    distances_by_key: dict[tuple[str, str, str, int], list[float]],
) -> None:
    """Fill ``paired_window_*_delta_m`` relative to paired ``clean`` + ``no_defense``."""
    clean_refs: dict[tuple[str, int], list[float]] = {}
    for (policy, attack_case, defense_id, seed), distances in distances_by_key.items():
        if attack_case == "clean" and defense_id == "no_defense":
            clean_refs[(policy, seed)] = distances[1:]

    for row in episode_rows:
        if row["attack_start"] is None or row["window_samples"] <= 0:
            continue
        clean_post = clean_refs.get((str(row["policy"]), int(row["seed"])))
        if clean_post is None:
            continue
        start = int(row["attack_start"])
        samples = int(row["window_samples"])
        reference = clean_post[start : start + samples]
        if not reference:
            continue
        if row["window_mean_distance_m"] is not None:
            row["paired_window_mean_delta_m"] = float(
                row["window_mean_distance_m"] - float(np.mean(reference))
            )
        if row["window_max_distance_m"] is not None:
            row["paired_window_max_delta_m"] = float(
                row["window_max_distance_m"] - float(max(reference))
            )


def run_matrix(
    out: Path,
    preset: str = "smoke",
    models: Sequence[Path] | None = None,
    attacks: Sequence[str] | None = None,
    defenses: Sequence[str] | None = None,
    episodes: int | None = None,
    calibration_episodes: int | None = None,
    test_base: int | None = None,
    cal_base: int | None = None,
    fallback_model: Path | None = None,
    write_traces: bool = True,
    pos_sigma: float | None = None,
    vel_sigma: float | None = None,
) -> dict[str, Any]:
    """Run calibration and paired attack-defense matrix evaluation into a new directory."""
    out_dir = Path(out)
    if out_dir.exists():
        raise FileExistsError(f"Output directory already exists: {out_dir}")

    preset_spec = get_preset(preset)
    model_paths = validate_model_paths(
        [Path(m) for m in (models if models is not None else preset_spec.models)]
    )
    attack_specs = resolve_attack_specs(attacks, preset_spec.attacks)
    defense_specs = resolve_defense_specs(defenses, preset_spec.defenses)
    if not attack_specs:
        raise ValueError("At least one attack case is required")
    if not defense_specs:
        raise ValueError("At least one defense is required")

    resolved_episodes = (
        int(episodes) if episodes is not None else int(preset_spec.episodes)
    )
    resolved_cal_episodes = (
        int(calibration_episodes)
        if calibration_episodes is not None
        else int(preset_spec.calibration_episodes)
    )
    resolved_test_base = (
        int(test_base) if test_base is not None else int(preset_spec.test_base)
    )
    resolved_cal_base = (
        int(cal_base) if cal_base is not None else int(preset_spec.cal_base)
    )
    resolved_pos_sigma = (
        float(pos_sigma) if pos_sigma is not None else float(preset_spec.pos_sigma)
    )
    resolved_vel_sigma = (
        float(vel_sigma) if vel_sigma is not None else float(preset_spec.vel_sigma)
    )

    if resolved_episodes < 1 or resolved_cal_episodes < 1:
        raise ValueError("episodes and calibration_episodes must be >= 1")
    if resolved_episodes > 1000 or resolved_cal_episodes > 1000:
        raise ValueError("episodes and calibration_episodes must be <= 1000 per seed block")

    cal_seeds = collect_seed_set(
        resolved_cal_base, resolved_cal_episodes, len(model_paths)
    )
    test_seeds = collect_seed_set(
        resolved_test_base, resolved_episodes, len(model_paths)
    )
    validation_seeds: set[int] = set()
    for path in model_paths:
        val_file = path.parent / "validation.json"
        if val_file.exists():
            val_data = json.loads(val_file.read_text(encoding="utf-8"))
            validation_seeds.update(
                int(t["seed"]) for t in val_data.get("trials", []) if "seed" in t
            )
    validate_disjoint_seeds(cal_seeds, test_seeds, validation_seeds)

    # Validate attack/defense instantiation before creating output directory.
    for a_spec in attack_specs:
        _ = create_attack(a_spec.attack_name, **a_spec.params)
    for d_spec in defense_specs:
        _ = create_defense(d_spec.defense_name, **d_spec.params)

    loaded_fallback: Any | None = None
    fallback_path_resolved: str | None = None
    if fallback_model is not None:
        fb_path = Path(fallback_model)
        if not fb_path.exists():
            raise FileNotFoundError(f"Fallback model does not exist: {fb_path}")
        loaded_fallback = SAC.load(fb_path, device="cpu")
        fallback_path_resolved = str(fb_path.resolve())

    out_dir.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(1)

    config: dict[str, Any] = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "preset": preset_spec.name,
        "models": [str(p.resolve()) for p in model_paths],
        "policy_names": [p.parent.name for p in model_paths],
        "model_sha256": {
            str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in model_paths
        },
        "attacks": [
            {
                "case_id": a.case_id,
                "attack_name": a.attack_name,
                "params": dict(a.params),
            }
            for a in attack_specs
        ],
        "defenses": [
            {
                "defense_id": d.defense_id,
                "defense_name": d.defense_name,
                "params": dict(d.params),
            }
            for d in defense_specs
        ],
        "episodes": resolved_episodes,
        "calibration_episodes": resolved_cal_episodes,
        "cal_base": resolved_cal_base,
        "test_base": resolved_test_base,
        "pos_sigma": resolved_pos_sigma,
        "vel_sigma": resolved_vel_sigma,
        "fallback_model": fallback_path_resolved,
        "write_traces": bool(write_traces),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": _package_versions(),
        "git_head": _git_head(Path(__file__).resolve().parent),
    }
    write_json(out_dir / "config.json", config)

    records: list[dict[str, Any]] = []
    calibration_records: dict[str, Any] = {}
    trace_handle = (
        gzip.open(out_dir / "traces.jsonl.gz", "wt", encoding="utf-8")
        if write_traces
        else None
    )
    started = time.perf_counter()

    try:
        for model_index, model_path in enumerate(model_paths):
            policy_name = model_path.parent.name
            model = SAC.load(model_path, device="cpu")
            env = make_ablation_env(
                seed=resolved_test_base + model_index * 1000,
                pos_sigma=resolved_pos_sigma,
                vel_sigma=resolved_vel_sigma,
            )
            geometry = ArmGeometry.from_model(env.unwrapped.model)
            try:
                cal = calibrate_policy(
                    model=model,
                    geometry=geometry,
                    episodes=resolved_cal_episodes,
                    seed_base=resolved_cal_base + model_index * 1000,
                    pos_sigma=resolved_pos_sigma,
                    vel_sigma=resolved_vel_sigma,
                )
                cal_entry = cal.to_dict()
                cal_entry["geometry"] = geometry.to_dict()
                calibration_records[policy_name] = cal_entry
                write_json(out_dir / "calibration.json", calibration_records)
                print(
                    f"[{policy_name}] calibrated threshold={cal.threshold_m:.6f} m "
                    f"(p999_q0_jump={cal.q0_jump_p999_rad:.4f}, p999_q1_jump={cal.q1_jump_p999_rad:.4f})",
                    flush=True,
                )

                for episode in range(resolved_episodes):
                    seed = resolved_test_base + model_index * 1000 + episode
                    sign = 1 if episode % 2 == 0 else -1
                    episode_rows: list[dict[str, Any]] = []
                    distances_map: dict[tuple[str, str, str, int], list[float]] = {}

                    for a_spec in attack_specs:
                        for d_spec in defense_specs:
                            attack = create_attack(a_spec.attack_name, **a_spec.params)
                            defense = create_defense(d_spec.defense_name, **d_spec.params)
                            row = run_paired_trial(
                                model=model,
                                env=env,
                                geometry=geometry,
                                calibration=cal,
                                attack=attack,
                                defense=defense,
                                seed=seed,
                                policy_name=policy_name,
                                attack_case=a_spec.case_id,
                                defense_id=d_spec.defense_id,
                                sign=sign,
                                fallback_policy=loaded_fallback,
                                trace_file=trace_handle,
                            )
                            distances = row.pop("_distances")
                            distances_map[
                                (policy_name, a_spec.case_id, d_spec.defense_id, seed)
                            ] = distances
                            episode_rows.append(row)

                    populate_paired_deltas(episode_rows, distances_map)
                    records.extend(episode_rows)
                    print(
                        f"[{policy_name}] paired state {episode + 1}/{resolved_episodes} complete",
                        flush=True,
                    )
            finally:
                env.close()
    finally:
        if trace_handle is not None:
            trace_handle.close()
        write_csv(out_dir / "episodes.csv", records)

    summary = summarize_matrix(records)
    matrix_summary = aggregate_across_policies(summary)
    write_csv(out_dir / "summary.csv", summary)
    write_csv(out_dir / "matrix_summary.csv", matrix_summary)
    write_json(
        out_dir / "matrix_summary.json",
        {"per_policy": summary, "across_policies": matrix_summary},
    )

    elapsed = time.perf_counter() - started
    status = {
        "complete": True,
        "preset": preset_spec.name,
        "evaluation_episodes": len(records),
        "calibration_episodes": resolved_cal_episodes * len(model_paths),
        "elapsed_seconds": elapsed,
    }
    write_json(out_dir / "run_status.json", status)
    print(
        f"Matrix complete: {len(records)} episodes written to {out_dir} in {elapsed:.1f}s",
        flush=True,
    )
    return {
        "out": out_dir,
        "status": status,
        "summary": summary,
        "matrix_summary": matrix_summary,
    }


__all__ = [
    "calibrate_policy",
    "populate_paired_deltas",
    "resolve_attack_specs",
    "resolve_defense_specs",
    "run_matrix",
    "run_paired_trial",
    "validate_model_paths",
    "write_csv",
    "write_json",
]
