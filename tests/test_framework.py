"""Independent verification suite for the Phase-2 attack/defense/evaluation framework."""
from __future__ import annotations

import ast
import csv
import inspect
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
from stable_baselines3 import SAC
import torch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from attacks import (  # noqa: E402
    AttackContext,
    BaseAttack,
    ElbowFlipAttack,
    FreezeAttack,
    JointVelocityCoupledAttack,
    PolicyGradientAttack,
    ReplayAttack,
    SinusoidalAttack,
    ThresholdAwareRampAttack,
    create_attack,
    list_attacks,
)
from defenses import (  # noqa: E402
    DEFENSE_REGISTRY,
    VALID_DEFENSE_STATES,
    BaseDefense,
    CalibrationStats,
    ContinuousVelocityDefense,
    CusumDefense,
    DefenseContext,
    FallbackPolicyDefense,
    Grace1Defense,
    IKVelocityFusionDefense,
    OriginalFailStopDefense,
    SlidingWindowDefense,
    create_defense,
    list_defenses,
)
from core.env_wrapper import AblationNoiseWrapper, make_ablation_env  # noqa: E402
from evaluation import (  # noqa: E402
    ABLATION_BASE,
    CAL_BASE,
    DEV_BASE,
    HISTORICAL_SEED_BLOCKS,
    TEST_BASE,
    calibrate_policy,
    collect_seed_set,
    get_preset,
    list_presets,
    recovery_time,
    run_matrix,
    run_velocity_noise_ablation,
    validate_disjoint_seeds,
)
from core.kinematics import (  # noqa: E402
    elbow_flip_angles,
    solve_2link_ik,
    solve_q0_ik,
)
from core.reacher_env import make_env  # noqa: E402
from core.recovery_monitor import RecoveryMonitor  # noqa: E402
from core.security import ArmGeometry, Attack, KinematicMonitor, wrap  # noqa: E402

MODEL_SEED1_PATH = ROOT / "models" / "sac_seed_1_sync" / "model.zip"


def _make_obs(
    geometry: ArmGeometry,
    q0: float = 0.4,
    q1: float = -0.5,
    v0: float = 0.1,
    v1: float = -0.2,
    target: tuple[float, float] = (0.1, -0.02),
) -> np.ndarray:
    target_arr = np.asarray(target, dtype=np.float64)
    tip = geometry.forward(q0, q1)
    return np.array(
        [
            np.cos(q0),
            np.cos(q1),
            np.sin(q0),
            np.sin(q1),
            target_arr[0],
            target_arr[1],
            v0,
            v1,
            tip[0] - target_arr[0],
            tip[1] - target_arr[1],
        ],
        dtype=np.float64,
    )


def _sample_cal_stats(
    threshold_m: float = 0.006,
    residual_mean_m: float = 0.0022,
    residual_std_m: float = 0.0012,
    q0_jump_p999_rad: float = 0.05,
    q1_jump_p999_rad: float = 0.05,
) -> CalibrationStats:
    return CalibrationStats(
        threshold_m=threshold_m,
        residual_mean_m=residual_mean_m,
        residual_std_m=residual_std_m,
        residual_p95_m=0.0045,
        residual_p99_m=threshold_m,
        q0_jump_p99_rad=0.03,
        q0_jump_p999_rad=q0_jump_p999_rad,
        q1_jump_p99_rad=0.03,
        q1_jump_p999_rad=q1_jump_p999_rad,
        control_dt_seconds=0.02,
        episodes=10,
        seed_base=CAL_BASE,
    )


def _rollout_observations(
    model: SAC,
    *,
    seed: int = DEV_BASE + 1,
    pos_sigma: float = 0.0,
    vel_sigma: float = 0.0,
    steps: int = 100,
) -> tuple[list[np.ndarray], list[dict], float]:
    env = make_ablation_env(seed=seed, pos_sigma=pos_sigma, vel_sigma=vel_sigma)
    dt = float(env.unwrapped.dt)
    observations: list[np.ndarray] = []
    infos: list[dict] = []
    try:
        obs, info = env.reset(
            seed=seed,
            options={"noise_seed": seed + 10000000, "vel_noise_seed": seed + 50000000},
        )
        observations.append(np.array(obs, dtype=np.float64, copy=True))
        infos.append(info)
        for _ in range(steps - 1):
            action, _ = model.predict(obs, deterministic=True)
            obs, _, terminated, truncated, info = env.step(action)
            observations.append(np.array(obs, dtype=np.float64, copy=True))
            infos.append(info)
            if terminated or truncated:
                break
    finally:
        env.close()
    return observations, infos, dt


@pytest.fixture(scope="module")
def geometry() -> ArmGeometry:
    env = make_env(noise_sigma=0.0)
    try:
        return ArmGeometry.from_model(env.unwrapped.model)
    finally:
        env.close()


@pytest.fixture(scope="module")
def sac_model() -> SAC:
    return SAC.load(MODEL_SEED1_PATH, device="cpu")


@pytest.fixture(scope="module")
def calibrated_stats(sac_model: SAC, geometry: ArmGeometry) -> CalibrationStats:
    return calibrate_policy(
        model=sac_model,
        geometry=geometry,
        episodes=10,
        seed_base=CAL_BASE,
        pos_sigma=0.002,
        vel_sigma=0.0,
    )


@pytest.fixture(scope="module")
def clean_trajectory(sac_model: SAC) -> tuple[list[np.ndarray], list[dict], float]:
    return _rollout_observations(sac_model, seed=DEV_BASE + 7, pos_sigma=0.0, vel_sigma=0.0)


@pytest.fixture(scope="module")
def noisy_pos_trajectory(sac_model: SAC) -> tuple[list[np.ndarray], list[dict], float]:
    return _rollout_observations(sac_model, seed=DEV_BASE + 8, pos_sigma=0.002, vel_sigma=0.0)


# =============================================================================
# 1. Kinematics Unit Tests
# =============================================================================


def _test_geometries(reacher_geom: ArmGeometry) -> list[ArmGeometry]:
    return [
        reacher_geom,
        ArmGeometry(
            origin=np.array([0.05, -0.03], dtype=float),
            link=np.array([0.12, 0.04], dtype=float),
            tip=np.array([0.09, -0.02], dtype=float),
        ),
        ArmGeometry(
            origin=np.zeros(2, dtype=float),
            link=np.array([0.08, 0.06], dtype=float),
            tip=np.array([0.07, -0.05], dtype=float),
        ),
    ]


def test_solve_q0_ik_round_trip(geometry: ArmGeometry) -> None:
    q0_values = (-2.9, -1.4, -0.25, 0.0, 0.65, 2.75)
    q1_values = (-2.6, -1.1, -0.35, 0.15, 1.3, 2.5)
    for geom in _test_geometries(geometry):
        for q0 in q0_values:
            for q1 in q1_values:
                tip = geom.forward(q0, q1)
                if float(np.linalg.norm(tip - geom.origin)) < 1e-9:
                    continue
                q0_est = solve_q0_ik(geom, q1, tip)
                assert abs(wrap(q0_est - q0)) < 1e-12
                assert float(np.linalg.norm(geom.forward(q0_est, q1) - tip)) < 1e-12


def test_solve_2link_ik_recovers_pose(geometry: ArmGeometry) -> None:
    q0_values = (-2.8, -1.1, 0.0, 0.85, 2.4)
    q1_values = (-2.4, -0.9, -0.1, 0.3, 1.6, 2.7)
    for geom in _test_geometries(geometry):
        phi1 = float(np.arctan2(geom.link[1], geom.link[0]))
        phi2 = float(np.arctan2(geom.tip[1], geom.tip[0]))
        aligned = wrap(phi1 - phi2)
        candidate_q1s = list(q1_values) + [aligned, wrap(aligned + np.pi)]
        for q0 in q0_values:
            for q1 in candidate_q1s:
                tip = geom.forward(q0, q1)
                if float(np.linalg.norm(tip - geom.origin)) < 1e-9:
                    continue
                solutions = solve_2link_ik(geom, tip)
                assert len(solutions) == 2
                for q0_sol, q1_sol in solutions:
                    assert float(np.linalg.norm(geom.forward(q0_sol, q1_sol) - tip)) < 1e-12
                diff_from_aligned = abs(wrap(q1 - aligned))
                is_boundary = diff_from_aligned <= 1e-6 or abs(diff_from_aligned - np.pi) <= 1e-6
                # At full-extension/fold singularities, |cos(alpha)|=1 introduces O(sqrt(eps_mach)) ~1e-8 angle jitter.
                tol = 1e-6 if is_boundary else 1e-12
                assert any(
                    abs(wrap(q0_sol - q0)) < tol and abs(wrap(q1_sol - q1)) < tol
                    for q0_sol, q1_sol in solutions
                )


def test_elbow_flip_angles_accuracy_and_involution(geometry: ArmGeometry) -> None:
    q0_values = (-2.6, -0.7, 0.0, 1.1, 2.5)
    q1_values = (-2.5, -1.0, -0.4, 0.25, 1.4, 2.6)
    for geom in _test_geometries(geometry):
        phi1 = float(np.arctan2(geom.link[1], geom.link[0]))
        phi2 = float(np.arctan2(geom.tip[1], geom.tip[0]))
        aligned = wrap(phi1 - phi2)
        for q0 in q0_values:
            for q1 in q1_values:
                tip = geom.forward(q0, q1)
                q0_alt, q1_alt = elbow_flip_angles(geom, q0, q1)
                assert float(np.linalg.norm(geom.forward(q0_alt, q1_alt) - tip)) < 1e-12
                diff_from_aligned = abs(wrap(q1 - aligned))
                if diff_from_aligned > 1e-6 and abs(diff_from_aligned - np.pi) > 1e-6:
                    assert abs(wrap(q1_alt - q1)) > 1e-6
                    q0_back, q1_back = elbow_flip_angles(geom, q0_alt, q1_alt)
                    assert abs(wrap(q0_back - q0)) < 1e-12
                    assert abs(wrap(q1_back - q1)) < 1e-12

        # Degenerate extended configuration still preserves tip position without error.
        q0_ext, q1_ext = elbow_flip_angles(geom, 0.4, aligned)
        assert float(np.linalg.norm(geom.forward(q0_ext, q1_ext) - geom.forward(0.4, aligned))) < 1e-12


# =============================================================================
# 2. Attack Contract Tests
# =============================================================================


EXPECTED_ATTACKS = [
    "bias",
    "clean",
    "elbow_flip",
    "freeze",
    "joint_vel_coupled",
    "policy_gradient",
    "pulse",
    "ramp",
    "random_bias",
    "random_ramp",
    "replay",
    "sinusoidal",
    "threshold_aware",
]


def test_registered_attacks_complete() -> None:
    assert list_attacks() == EXPECTED_ATTACKS


@pytest.mark.parametrize("attack_name", EXPECTED_ATTACKS)
def test_attack_contract_all_registered(
    attack_name: str,
    geometry: ArmGeometry,
    sac_model: SAC,
    clean_trajectory: tuple[list[np.ndarray], list[dict], float],
) -> None:
    observations, _, dt = clean_trajectory
    kwargs = {"epsilon": 0.5, "start": 20, "duration": 15}
    if attack_name in ("clean", "freeze", "replay", "elbow_flip"):
        kwargs = {"start": 20, "duration": 15}
    attack = create_attack(attack_name, **kwargs)
    assert isinstance(attack, BaseAttack)
    json.dumps(attack.config_dict())

    ctx = AttackContext(
        geometry=geometry,
        dt=dt,
        calibrated_threshold_m=0.006,
        policy=sac_model,
    )
    attack.reset(seed=DEV_BASE + 1, sign=1, context=ctx)

    bounds = attack.window_bounds()
    if attack_name == "clean":
        assert bounds is None
    else:
        assert bounds == (20, 15)

    first_pass_reported: list[np.ndarray] = []
    for step, raw in enumerate(observations):
        raw_snapshot = raw.copy()
        res = attack.apply(raw, step, ctx)

        # Input immutability and fresh float64 (10,) copy.
        np.testing.assert_array_equal(raw, raw_snapshot)
        assert res.reported_obs is not raw
        assert not np.shares_memory(res.reported_obs, raw)
        assert res.reported_obs.dtype == np.float64
        assert res.reported_obs.shape == (10,)

        # Channels outside attacked_channels are bit-for-bit identical.
        unattacked = [i for i in range(10) if i not in res.attacked_channels]
        if unattacked:
            np.testing.assert_array_equal(res.reported_obs[unattacked], raw[unattacked])

        # Unit-circle invariants on both joint (cos, sin) pairs.
        assert res.reported_obs[0] ** 2 + res.reported_obs[2] ** 2 == pytest.approx(1.0, abs=1e-12)
        assert res.reported_obs[1] ** 2 + res.reported_obs[3] ** 2 == pytest.approx(1.0, abs=1e-12)

        # Window bounds strictly respected.
        if bounds is None:
            assert res.is_active is False
            assert res.delta_rad == 0.0
            np.testing.assert_array_equal(res.reported_obs, raw)
        else:
            start, duration = bounds
            expected_active = start <= step < start + duration
            assert res.is_active is expected_active
            if not expected_active:
                assert res.delta_rad == 0.0
                np.testing.assert_array_equal(res.reported_obs, raw)

        first_pass_reported.append(res.reported_obs)

    # Resetting with the same seed and sign reproduces identical outputs.
    attack.reset(seed=DEV_BASE + 1, sign=1, context=ctx)
    for step, raw in enumerate(observations):
        res2 = attack.apply(raw, step, ctx)
        np.testing.assert_array_equal(res2.reported_obs, first_pass_reported[step])


def test_policy_gradient_preserves_weights_and_requires_policy(
    geometry: ArmGeometry,
    sac_model: SAC,
    clean_trajectory: tuple[list[np.ndarray], list[dict], float],
) -> None:
    observations, _, dt = clean_trajectory
    attack = PolicyGradientAttack(epsilon=0.5, duration=5, start=10, n_steps=5, sign=1)

    ctx_no_policy = AttackContext(geometry=geometry, dt=dt, calibrated_threshold_m=0.006, policy=None)
    attack.reset(seed=DEV_BASE + 2, sign=1, context=ctx_no_policy)
    # Inactive pre-window step does not require context.policy.
    pre_res = attack.apply(observations[9], 9, ctx_no_policy)
    assert pre_res.is_active is False
    # Active step raises ValueError when context.policy is None.
    with pytest.raises(ValueError, match="policy"):
        attack.apply(observations[10], 10, ctx_no_policy)

    actor = sac_model.policy.actor
    weights_before = {name: p.detach().clone() for name, p in actor.named_parameters()}
    req_grads_before = {name: p.requires_grad for name, p in actor.named_parameters()}
    training_before = actor.training

    ctx = AttackContext(geometry=geometry, dt=dt, calibrated_threshold_m=0.006, policy=sac_model)
    attack.reset(seed=DEV_BASE + 2, sign=1, context=ctx)

    with torch.no_grad():
        for step in range(10, 15):
            res = attack.apply(observations[step], step, ctx)
            assert res.is_active is True
            assert abs(res.delta_rad) <= 0.5 + 1e-12
            assert res.attacked_channels == (0, 2)

    assert actor.training == training_before
    for name, p in actor.named_parameters():
        assert torch.equal(p.detach(), weights_before[name])
        assert p.requires_grad == req_grads_before[name]
        assert p.grad is None


def test_threshold_aware_caps_noiseless_residual(
    geometry: ArmGeometry,
    clean_trajectory: tuple[list[np.ndarray], list[dict], float],
) -> None:
    observations, _, dt = clean_trajectory
    for threshold_m in (0.004, 0.006, 0.012):
        for sign in (1, -1):
            margin = 0.85
            attack = ThresholdAwareRampAttack(
                epsilon=1.5, duration=20, start=10, margin=margin, sign=sign
            )
            ctx = AttackContext(
                geometry=geometry,
                dt=dt,
                calibrated_threshold_m=threshold_m,
            )
            attack.reset(seed=DEV_BASE + 3, sign=sign, context=ctx)
            for step in range(10, 30):
                res = attack.apply(observations[step], step, ctx)
                residual = geometry.residual(res.reported_obs)
                assert residual <= margin * threshold_m + 1e-9
                assert res.delta_rad != 0.0


def test_elbow_flip_attack_alters_four_channels_with_near_zero_residual(
    geometry: ArmGeometry,
) -> None:
    raw = _make_obs(geometry, q0=0.5, q1=-0.8)
    attack = ElbowFlipAttack(duration=10, start=10)
    ctx = AttackContext(geometry=geometry, dt=0.02)
    attack.reset(seed=DEV_BASE + 4, sign=1, context=ctx)

    res = attack.apply(raw, 10, ctx)
    assert res.is_active is True
    assert res.attacked_channels == (0, 1, 2, 3)
    assert geometry.residual(res.reported_obs) < 1e-12
    assert not np.allclose(res.reported_obs[:4], raw[:4])
    np.testing.assert_array_equal(res.reported_obs[4:], raw[4:])


def test_magnitude_timing_and_coupled_attack_behaviors(
    geometry: ArmGeometry,
    clean_trajectory: tuple[list[np.ndarray], list[dict], float],
) -> None:
    observations, _, dt = clean_trajectory
    ctx = AttackContext(geometry=geometry, dt=dt, calibrated_threshold_m=0.006)

    # Freeze holds step start-1 joint-0 reading across the active window.
    freeze = FreezeAttack(duration=5, start=20)
    freeze.reset(seed=1, context=ctx)
    for step in range(25):
        res = freeze.apply(observations[step], step, ctx)
        if 20 <= step < 25:
            np.testing.assert_array_equal(res.reported_obs[[0, 2]], observations[19][[0, 2]])

    # Replay loops the last replay_len pre-attack observations.
    replay = ReplayAttack(duration=8, start=20, replay_len=4)
    replay.reset(seed=1, context=ctx)
    for step in range(28):
        res = replay.apply(observations[step], step, ctx)
        if 20 <= step < 28:
            src_step = 16 + ((step - 20) % 4)
            np.testing.assert_array_equal(res.reported_obs[[0, 2]], observations[src_step][[0, 2]])

    # Sinusoidal matches exact sin formula.
    sinu = SinusoidalAttack(epsilon=0.4, duration=10, start=10, freq_hz=5.0, phase=0.25, sign=-1)
    sinu.reset(seed=1, sign=-1, context=ctx)
    res_sinu = sinu.apply(observations[13], 13, ctx)
    expected_delta = -0.4 * np.sin(2.0 * np.pi * 5.0 * 3 * dt + 0.25)
    assert res_sinu.delta_rad == pytest.approx(expected_delta, abs=1e-12)

    # JointVelocityCoupled modifies channels (0, 2, 6).
    coupled = JointVelocityCoupledAttack(epsilon=0.5, duration=5, start=10, vel_bias=0.7, sign=1)
    coupled.reset(seed=1, sign=-1, context=ctx)
    res_c = coupled.apply(observations[10], 10, ctx)
    assert res_c.attacked_channels == (0, 2, 6)
    assert res_c.delta_rad == pytest.approx(-0.5)
    assert res_c.reported_obs[6] == pytest.approx(observations[10][6] - 0.7)


# =============================================================================
# 3. Defense Contract Tests
# =============================================================================


EXPECTED_DEFENSES = [
    "continuous_velocity",
    "cusum",
    "fallback_policy",
    "grace1",
    "ik_velocity_fusion",
    "no_defense",
    "original_fail_stop",
    "sliding_window",
]


def test_registered_defenses_and_trust_boundary() -> None:
    assert list_defenses() == EXPECTED_DEFENSES

    # DefenseContext must only expose observation-side / calibration fields.
    ctx_fields = set(DefenseContext.__dataclass_fields__.keys())
    assert ctx_fields == {"geometry", "dt", "calibration", "fallback_policy"}
    assert "raw_obs" not in ctx_fields
    assert "truth" not in ctx_fields

    # Every defense's process/reset signatures must reject raw_obs / truth inputs.
    for cls in [BaseDefense, *DEFENSE_REGISTRY.values()]:
        proc_params = list(inspect.signature(cls.process).parameters.keys())
        reset_params = list(inspect.signature(cls.reset).parameters.keys())
        assert proc_params == ["self", "reported_obs", "step", "context"]
        assert reset_params == ["self", "context"]

    # AST scan of all defense source modules to verify no truth/raw_obs access.
    defenses_dir = ROOT / "defenses"
    for py_file in sorted(defenses_dir.glob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                assert node.id not in {"raw_obs", "truth_before", "truth_after"}
            elif isinstance(node, ast.Attribute):
                assert node.attr not in {"raw_obs", "truth"}
            elif isinstance(node, ast.Constant) and node.value == "truth":
                pytest.fail(f"{py_file.name} references literal 'truth'")


@pytest.mark.parametrize("defense_name", EXPECTED_DEFENSES)
def test_defense_contract_all_registered(
    defense_name: str,
    geometry: ArmGeometry,
    sac_model: SAC,
    calibrated_stats: CalibrationStats,
    clean_trajectory: tuple[list[np.ndarray], list[dict], float],
) -> None:
    observations, _, dt = clean_trajectory
    defense = create_defense(defense_name)
    assert isinstance(defense, BaseDefense)
    json.dumps(defense.config_dict())

    ctx = DefenseContext(
        geometry=geometry,
        dt=dt,
        calibration=calibrated_stats,
        fallback_policy=sac_model,
    )
    defense.reset(ctx)

    attack = create_attack("bias", epsilon=1.0, start=20, duration=25)
    attack.reset(seed=DEV_BASE + 10, sign=1)
    atk_ctx = AttackContext(geometry=geometry, dt=dt)

    for step, raw in enumerate(observations):
        reported = attack.apply(raw, step, atk_ctx).reported_obs
        reported_snapshot = reported.copy()

        res = defense.process(reported, step, ctx)

        np.testing.assert_array_equal(reported, reported_snapshot)
        assert res.policy_obs is not reported
        assert not np.shares_memory(res.policy_obs, reported)
        assert res.policy_obs.dtype == np.float64
        assert res.policy_obs.shape == (10,)
        assert res.policy_obs[0] ** 2 + res.policy_obs[2] ** 2 == pytest.approx(1.0, abs=1e-12)
        assert res.policy_obs[1] ** 2 + res.policy_obs[3] ** 2 == pytest.approx(1.0, abs=1e-12)
        assert res.state in VALID_DEFENSE_STATES
        assert isinstance(res.alarm, bool)
        assert isinstance(res.abort, bool)
        assert np.isfinite(res.residual_m)
        if step == 0:
            assert res.alarm is False
            assert res.abort is False
            assert res.alarm_streak == 0


def test_cusum_detects_sustained_subthreshold_offset(
    geometry: ArmGeometry,
    clean_trajectory: tuple[list[np.ndarray], list[dict], float],
) -> None:
    observations, _, dt = clean_trajectory
    cal = _sample_cal_stats(threshold_m=0.006, residual_mean_m=0.002, residual_std_m=0.001)
    ctx = DefenseContext(geometry=geometry, dt=dt, calibration=cal)

    cusum = CusumDefense()
    fail_stop = OriginalFailStopDefense()
    cusum.reset(ctx)
    fail_stop.reset(ctx)

    attack = ThresholdAwareRampAttack(epsilon=0.5, duration=25, start=10, margin=0.85)
    atk_ctx = AttackContext(geometry=geometry, dt=dt, calibrated_threshold_m=cal.threshold_m)
    attack.reset(seed=1, sign=1, context=atk_ctx)

    cusum_alarms: list[int] = []
    fail_stop_alarms: list[int] = []
    for step in range(45):
        raw = observations[step]
        reported = attack.apply(raw, step, atk_ctx).reported_obs
        if 10 <= step < 35:
            assert geometry.residual(reported) < cal.threshold_m

        c_res = cusum.process(reported, step, ctx)
        f_res = fail_stop.process(reported, step, ctx)
        if c_res.alarm:
            cusum_alarms.append(step)
        if f_res.alarm:
            fail_stop_alarms.append(step)

    assert fail_stop_alarms == []
    assert any(10 <= s < 35 for s in cusum_alarms)
    # Clean steps after window ends reset CUSUM alarm back to normal.
    assert c_res.alarm is False
    assert c_res.state == "normal"


def test_sliding_window_detects_persistent_and_resets(geometry: ArmGeometry) -> None:
    cal = _sample_cal_stats(threshold_m=0.006)
    ctx = DefenseContext(geometry=geometry, dt=0.02, calibration=cal)
    sw = SlidingWindowDefense(window_size=5, min_hits=3, spike_factor=2.0)
    sw.reset(ctx)

    clean = _make_obs(geometry, q0=0.3, q1=-0.4, v0=0.0)
    small_bad = _make_obs(geometry, q0=0.35, q1=-0.4, v0=0.0)
    small_bad[0], small_bad[2] = clean[0], clean[2]  # residual ~0.008 > 0.006, < 0.012
    assert 0.006 < geometry.residual(small_bad) < 0.012

    assert sw.process(clean, 0, ctx).alarm is False
    assert sw.process(small_bad, 1, ctx).alarm is False
    assert sw.process(small_bad, 2, ctx).alarm is False
    res3 = sw.process(small_bad, 3, ctx)
    assert res3.alarm is True
    assert res3.state == "correcting"


def test_continuous_velocity_does_not_abort_past_step_21(
    geometry: ArmGeometry,
    calibrated_stats: CalibrationStats,
    clean_trajectory: tuple[list[np.ndarray], list[dict], float],
) -> None:
    observations, _, dt = clean_trajectory
    ctx = DefenseContext(geometry=geometry, dt=dt, calibration=calibrated_stats)
    defense = ContinuousVelocityDefense()
    defense.reset(ctx)

    attack = create_attack("bias", epsilon=1.0, start=10, duration=40)
    attack.reset(seed=DEV_BASE + 12, sign=1)
    atk_ctx = AttackContext(geometry=geometry, dt=dt)

    for step in range(55):
        reported = attack.apply(observations[step], step, atk_ctx).reported_obs
        res = defense.process(reported, step, ctx)
        assert res.abort is False
        if 10 <= step < 50:
            assert res.alarm is True
            assert res.state == "correcting"
            assert res.alarm_streak == step - 9
            # Joint-0 is corrected away from the spoofed angle toward true angle.
            true_q0 = float(np.arctan2(observations[step][2], observations[step][0]))
            rep_q0 = float(np.arctan2(reported[2], reported[0]))
            pol_q0 = float(np.arctan2(res.policy_obs[2], res.policy_obs[0]))
            assert abs(wrap(pol_q0 - true_q0)) < abs(wrap(rep_q0 - true_q0))
    assert res.state == "normal"
    assert res.alarm_streak == 0


def test_ik_velocity_fusion_catches_elbow_flip_and_beats_velocity_under_vel_noise(
    geometry: ArmGeometry,
    sac_model: SAC,
    calibrated_stats: CalibrationStats,
    clean_trajectory: tuple[list[np.ndarray], list[dict], float],
) -> None:
    observations, _, dt = clean_trajectory
    ctx = DefenseContext(geometry=geometry, dt=dt, calibration=calibrated_stats)
    fusion = IKVelocityFusionDefense()
    fusion.reset(ctx)

    flip = ElbowFlipAttack(duration=15, start=15)
    atk_ctx = AttackContext(geometry=geometry, dt=dt)
    flip.reset(seed=1, context=atk_ctx)

    for step in range(30):
        raw = observations[step]
        reported = flip.apply(raw, step, atk_ctx).reported_obs
        res = fusion.process(reported, step, ctx)
        if step == 15:
            assert res.metadata["res_alarm"] is False
            assert res.metadata["q1_jump"] is True
            assert res.alarm is True
            assert res.state == "correcting"
            true_q0, true_q1 = np.arctan2(raw[2:4], raw[:2])
            rec_q0, rec_q1 = np.arctan2(res.policy_obs[2:4], res.policy_obs[:2])
            assert abs(wrap(rec_q0 - float(true_q0))) < 0.05
            assert abs(wrap(rec_q1 - float(true_q1))) < 0.05

    # Part B: Prolonged bias under high velocity noise (vel_sigma=0.8).
    vel_sigma = 0.8
    cal_vel = calibrate_policy(
        model=sac_model,
        geometry=geometry,
        episodes=8,
        seed_base=CAL_BASE + 500,
        pos_sigma=0.002,
        vel_sigma=vel_sigma,
    )
    noisy_obs, noisy_infos, noisy_dt = _rollout_observations(
        sac_model,
        seed=DEV_BASE + 20,
        pos_sigma=0.002,
        vel_sigma=vel_sigma,
    )
    ctx_vel = DefenseContext(geometry=geometry, dt=noisy_dt, calibration=cal_vel)
    cont = ContinuousVelocityDefense()
    ik_fus = IKVelocityFusionDefense()
    cont.reset(ctx_vel)
    ik_fus.reset(ctx_vel)

    bias = create_attack("bias", epsilon=1.0, start=15, duration=55)
    bias.reset(seed=DEV_BASE + 20, sign=1)
    bias_ctx = AttackContext(geometry=geometry, dt=noisy_dt)

    cont_errors: list[float] = []
    ik_errors: list[float] = []
    for step in range(70):
        reported = bias.apply(noisy_obs[step], step, bias_ctx).reported_obs
        r_cont = cont.process(reported, step, ctx_vel)
        r_ik = ik_fus.process(reported, step, ctx_vel)
        if step >= 15:
            true_q0 = float(noisy_infos[step]["truth"]["angles"][0])
            cont_q0 = float(np.arctan2(r_cont.policy_obs[2], r_cont.policy_obs[0]))
            ik_q0 = float(np.arctan2(r_ik.policy_obs[2], r_ik.policy_obs[0]))
            cont_errors.append(abs(wrap(cont_q0 - true_q0)))
            ik_errors.append(abs(wrap(ik_q0 - true_q0)))

    assert float(np.mean(ik_errors)) < float(np.mean(cont_errors))
    assert float(np.mean(ik_errors[-15:])) < float(np.mean(cont_errors[-15:]))


def test_fallback_policy_triggers_override_and_recovers(
    geometry: ArmGeometry,
    sac_model: SAC,
    calibrated_stats: CalibrationStats,
    clean_trajectory: tuple[list[np.ndarray], list[dict], float],
) -> None:
    observations, _, dt = clean_trajectory
    ctx = DefenseContext(
        geometry=geometry,
        dt=dt,
        calibration=calibrated_stats,
        fallback_policy=sac_model,
    )
    defense = FallbackPolicyDefense(switch_streak=5)
    defense.reset(ctx)

    attack = create_attack("bias", epsilon=1.0, start=10, duration=12)
    attack.reset(seed=1, sign=1)
    atk_ctx = AttackContext(geometry=geometry, dt=dt)

    for step in range(25):
        reported = attack.apply(observations[step], step, atk_ctx).reported_obs
        res = defense.process(reported, step, ctx)
        if step < 10:
            assert res.state == "normal"
            assert res.action_override is None
        elif step < 14:
            assert res.state == "correcting"
            assert res.action_override is None
        elif step < 22:
            assert res.state == "fallback"
            assert res.alarm_streak >= 5
            assert res.action_override is not None
            assert res.action_override.shape == (2,)
            assert res.action_override.dtype == np.float64
            assert np.all(np.isfinite(res.action_override))
            expected_act, _ = sac_model.predict(res.policy_obs, deterministic=True)
            np.testing.assert_allclose(res.action_override, expected_act, atol=1e-6)
        else:
            assert res.state == "normal"
            assert res.alarm_streak == 0
            assert res.action_override is None

    # Without a fallback policy, state still transitions to 'fallback' with None override.
    ctx_no_fb = DefenseContext(geometry=geometry, dt=dt, calibration=calibrated_stats, fallback_policy=None)
    defense.reset(ctx_no_fb)
    for step in range(16):
        reported = attack.apply(observations[step], step, atk_ctx).reported_obs
        res = defense.process(reported, step, ctx_no_fb)
    assert res.state == "fallback"
    assert res.action_override is None


# =============================================================================
# 4. Legacy Parity Tests
# =============================================================================


def test_original_fail_stop_parity_with_kinematic_monitor(
    geometry: ArmGeometry,
    calibrated_stats: CalibrationStats,
    noisy_pos_trajectory: tuple[list[np.ndarray], list[dict], float],
) -> None:
    observations, _, dt = noisy_pos_trajectory
    ctx = DefenseContext(geometry=geometry, dt=dt, calibration=calibrated_stats)

    scenarios = [
        Attack("clean"),
        Attack("bias", epsilon=0.5, duration=10, start=20, sign=1),
        Attack("bias", epsilon=1.0, duration=30, start=20, sign=-1),
    ]
    for legacy_atk in scenarios:
        defense = OriginalFailStopDefense(max_alarm_steps=20)
        monitor = KinematicMonitor(
            geometry=geometry,
            threshold=calibrated_stats.threshold_m,
            dt=dt,
            max_alarm_steps=20,
        )
        defense.reset(ctx)
        for step, raw in enumerate(observations):
            reported = legacy_atk.apply(raw, step)
            d_res = defense.process(reported, step, ctx)
            m_corr, m_status = monitor.process(reported)

            np.testing.assert_array_equal(d_res.policy_obs, m_corr)
            assert d_res.residual_m == m_status["residual_m"]
            assert d_res.alarm is bool(m_status["alarm"])
            assert d_res.alarm_streak == m_status["alarm_streak"]
            assert d_res.abort is bool(m_status["abort"])
            assert d_res.metadata["warmup"] is bool(m_status["warmup"])


def test_grace1_parity_with_recovery_monitor(geometry: ArmGeometry) -> None:
    threshold = 0.006
    dt = 0.02
    cal = _sample_cal_stats(threshold_m=threshold)
    ctx = DefenseContext(geometry=geometry, dt=dt, calibration=cal)

    clean = _make_obs(geometry, q0=0.2, q1=-0.4, v0=0.0)
    bad = Attack("bias", epsilon=0.5, duration=50, start=1).apply(clean, 1)

    # Trajectory: warmup -> 21 alarms (recovery_pending) -> 1 clean (normal) -> 22 alarms (abort).
    sequence = [clean] + [bad] * 21 + [clean] + [bad] * 22

    defense = Grace1Defense(grace=1)
    monitor = RecoveryMonitor(geometry=geometry, threshold=threshold, dt=dt, grace=1)
    defense.reset(ctx)

    states_seen: list[str] = []
    for step, obs in enumerate(sequence):
        d_res = defense.process(obs, step, ctx)
        m_corr, m_status = monitor.process(obs)

        np.testing.assert_array_equal(d_res.policy_obs, m_corr)
        assert d_res.residual_m == m_status["residual_m"]
        assert d_res.alarm is bool(m_status["alarm"])
        assert d_res.alarm_streak == m_status["alarm_streak"]
        assert d_res.abort is bool(m_status["abort"])
        assert d_res.state == m_status["state"]
        states_seen.append(d_res.state)

    assert states_seen[21] == "recovery_pending"
    assert states_seen[22] == "normal"
    assert states_seen[-2] == "recovery_pending"
    assert states_seen[-1] == "aborted"


@pytest.mark.parametrize("kind", ["clean", "bias", "ramp", "random_bias", "random_ramp"])
def test_legacy_attacks_parity_with_security_attack(
    kind: str,
    geometry: ArmGeometry,
    clean_trajectory: tuple[list[np.ndarray], list[dict], float],
) -> None:
    observations, _, dt = clean_trajectory
    ctx = AttackContext(geometry=geometry, dt=dt)

    for seed, sign, eps, start, dur in [
        (DEV_BASE + 1, 1, 0.1, 20, 15),
        (DEV_BASE + 2, -1, 0.5, 60, 25),
    ]:
        fw_atk = create_attack(kind, epsilon=eps, duration=dur, start=start, sign=sign)
        fw_atk.reset(seed=seed, sign=sign, context=ctx)
        leg_atk = Attack(
            kind=kind,
            epsilon=0.0 if kind == "clean" else eps,
            duration=dur,
            start=start,
            sign=sign,
            random_seed=seed + 20000000,
        )

        for step, raw in enumerate(observations):
            fw_res = fw_atk.apply(raw, step, ctx)
            leg_rep = leg_atk.apply(raw, step)
            leg_delta = leg_atk.delta(step)

            np.testing.assert_array_equal(fw_res.reported_obs, leg_rep)
            assert fw_res.delta_rad == leg_delta


# =============================================================================
# 5. Seed Disjointness, Wrapper, & Non-Overwrite Protection Tests
# =============================================================================


def test_validate_disjoint_seeds_rejects_historical_and_cal_test_overlaps() -> None:
    # Reject overlaps across every historical block boundary and interior.
    conflict_probes = [
        10000,
        12000,
        13999,
        200000,
        202999,
        300000,
        302999,
        500000,
        502999,
        800000,
        802999,
        900000,
        916500,
        932999,
    ]
    assert len(HISTORICAL_SEED_BLOCKS) == 6
    for bad_seed in conflict_probes:
        with pytest.raises(ValueError, match="historical"):
            validate_disjoint_seeds({bad_seed}, {TEST_BASE})
        with pytest.raises(ValueError, match="historical"):
            validate_disjoint_seeds({CAL_BASE}, {bad_seed})

    # Reject overlap between calibration and test sets.
    with pytest.raises(ValueError, match="overlap"):
        validate_disjoint_seeds({CAL_BASE, CAL_BASE + 1}, {CAL_BASE + 1, TEST_BASE})

    # Reject overlap with extra seed sets (e.g. validation seeds).
    with pytest.raises(ValueError, match="extra"):
        validate_disjoint_seeds({CAL_BASE}, {TEST_BASE}, {CAL_BASE})
    with pytest.raises(ValueError, match="extra"):
        validate_disjoint_seeds({CAL_BASE}, {TEST_BASE}, {TEST_BASE})

    # Verify all Phase-2 presets and ablation blocks are valid and disjoint.
    for preset_name in list_presets():
        p = get_preset(preset_name)
        cal_seeds = collect_seed_set(p.cal_base, p.calibration_episodes, len(p.models))
        test_seeds = collect_seed_set(p.test_base, p.episodes, len(p.models))
        validate_disjoint_seeds(cal_seeds, test_seeds)

    validate_disjoint_seeds(
        collect_seed_set(1050000, 100, 3),
        collect_seed_set(ABLATION_BASE, 30, 3),
    )
    validate_disjoint_seeds(
        collect_seed_set(1060000, 100, 3),
        collect_seed_set(1350000, 30, 3),
    )


def test_ablation_wrapper_parity_replay_and_masking() -> None:
    seed = DEV_BASE + 50
    actions = [np.array([0.25 * np.sin(t), -0.2 * np.cos(t)], dtype=np.float32) for t in range(25)]

    # 1. Exact parity with reacher_env.make_env when vel_sigma=0.0.
    ref_env = make_env(seed=seed, noise_sigma=0.002)
    ab_env = make_ablation_env(seed=seed, pos_sigma=0.002, vel_sigma=0.0)
    try:
        obs_ref, info_ref = ref_env.reset(seed=seed, options={"noise_seed": 777})
        obs_ab, info_ab = ab_env.reset(seed=seed, options={"noise_seed": 777})
        np.testing.assert_array_equal(obs_ab, obs_ref)
        assert info_ab["truth"] == info_ref["truth"]
        for act in actions:
            obs_ref, r1, t1, tr1, info_ref = ref_env.step(act)
            obs_ab, r2, t2, tr2, info_ab = ab_env.step(act)
            np.testing.assert_array_equal(obs_ab, obs_ref)
            assert r2 == r1 and t2 == t1 and tr2 == tr1
            assert info_ab["truth"] == info_ref["truth"]
    finally:
        ref_env.close()
        ab_env.close()

    # 2. Reproducible velocity noise replay with explicit noise_seed & vel_noise_seed.
    env_vel = make_ablation_env(seed=seed, pos_sigma=0.002, vel_sigma=0.5)
    assert isinstance(env_vel, AblationNoiseWrapper)
    try:
        seq_a: list[np.ndarray] = []
        seq_b: list[np.ndarray] = []
        seq_diff_vel: list[np.ndarray] = []
        truths_a: list[dict] = []
        truths_diff_vel: list[dict] = []

        for seq, truths, vel_seed in [
            (seq_a, truths_a, 888),
            (seq_b, [], 888),
            (seq_diff_vel, truths_diff_vel, 999),
        ]:
            obs, info = env_vel.reset(
                seed=seed, options={"noise_seed": 777, "vel_noise_seed": vel_seed}
            )
            seq.append(obs)
            truths.append(info["truth"])
            for act in actions:
                obs, _, _, _, info = env_vel.step(act)
                seq.append(obs)
                truths.append(info["truth"])

        for oa, ob, oc, ta, tc in zip(seq_a, seq_b, seq_diff_vel, truths_a, truths_diff_vel):
            np.testing.assert_array_equal(oa, ob)
            np.testing.assert_array_equal(oa[:6], oc[:6])
            np.testing.assert_array_equal(oa[8:10], oc[8:10])
            assert not np.array_equal(oa[6:8], oc[6:8])
            assert ta == tc
    finally:
        env_vel.close()

    # 3. mask_fingertip_rel=True zeros obs[8:10] only, without altering info['truth'].
    env_unmasked = make_ablation_env(seed=seed, pos_sigma=0.002, vel_sigma=0.0, mask_fingertip_rel=False)
    env_masked = make_ablation_env(seed=seed, pos_sigma=0.002, vel_sigma=0.0, mask_fingertip_rel=True)
    try:
        ou, iu = env_unmasked.reset(seed=seed, options={"noise_seed": 777, "vel_noise_seed": 888})
        om, im = env_masked.reset(seed=seed, options={"noise_seed": 777, "vel_noise_seed": 888})
        np.testing.assert_array_equal(om[:8], ou[:8])
        np.testing.assert_array_equal(om[8:10], np.zeros(2, dtype=np.float64))
        assert im["truth"] == iu["truth"]
        for act in actions:
            ou, _, _, _, iu = env_unmasked.step(act)
            om, _, _, _, im = env_masked.step(act)
            np.testing.assert_array_equal(om[:8], ou[:8])
            np.testing.assert_array_equal(om[8:10], np.zeros(2, dtype=np.float64))
            assert im["truth"] == iu["truth"]
    finally:
        env_unmasked.close()
        env_masked.close()


@pytest.mark.parametrize("script", ["run_matrix.py", "run_ablation.py"])
def test_cli_refuses_existing_out_directory(tmp_path: Path, script: str) -> None:
    out_dir = tmp_path / "existing_out"
    out_dir.mkdir()
    sentinel = out_dir / "keep.txt"
    sentinel.write_text("preserve", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(ROOT / script), "--out", str(out_dir)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "exist" in proc.stderr.lower()
    assert sentinel.read_text(encoding="utf-8") == "preserve"
    assert list(out_dir.iterdir()) == [sentinel]

    if script == "run_matrix.py":
        with pytest.raises(FileExistsError):
            run_matrix(out=out_dir)
    else:
        with pytest.raises(FileExistsError):
            run_velocity_noise_ablation(models=None, out=out_dir)
    assert sentinel.read_text(encoding="utf-8") == "preserve"


# =============================================================================
# 6. End-to-End CLI Smoke Test & Contributor Guide Spot-Check
# =============================================================================


def test_end_to_end_cli_smoke_matrix_and_ablation(tmp_path: Path) -> None:
    matrix_dir = tmp_path / "matrix"
    ablation_dir = tmp_path / "ablation"

    cmds = [
        [sys.executable, str(ROOT / "run_matrix.py"), "--preset", "smoke", "--out", str(matrix_dir)],
        [sys.executable, str(ROOT / "plot_matrix.py"), str(matrix_dir)],
        [
            sys.executable,
            str(ROOT / "run_ablation.py"),
            "--mode",
            "both",
            "--preset",
            "smoke",
            "--out",
            str(ablation_dir),
        ],
        [sys.executable, str(ROOT / "plot_matrix.py"), str(ablation_dir)],
    ]
    for cmd in cmds:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        assert proc.returncode == 0, f"Command failed: {cmd}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"

    # Verify run_status.json completion flags.
    for status_path in (
        matrix_dir / "run_status.json",
        ablation_dir / "run_status.json",
        ablation_dir / "velocity" / "run_status.json",
        ablation_dir / "position" / "run_status.json",
    ):
        assert status_path.exists(), f"Missing {status_path}"
        status = json.loads(status_path.read_text(encoding="utf-8"))
        assert status["complete"] is True

    # Verify all expected CSV, JSON, PNG, and GIF outputs exist and are non-empty.
    expected_files = [
        matrix_dir / "episodes.csv",
        matrix_dir / "matrix_summary.csv",
        matrix_dir / "matrix_summary.json",
        ablation_dir / "velocity" / "ablation_summary.csv",
        ablation_dir / "position" / "ablation_summary.csv",
        matrix_dir / "figures" / "matrix_heatmap.png",
        matrix_dir / "figures" / "detection_tradeoff.png",
        matrix_dir / "figures" / "comparison_frame.png",
        matrix_dir / "figures" / "comparison_replay.gif",
        ablation_dir / "figures" / "ablation_curves.png",
        ablation_dir / "velocity" / "figures" / "ablation_curves.png",
        ablation_dir / "position" / "figures" / "ablation_curves.png",
    ]
    for path in expected_files:
        assert path.exists(), f"Missing output artifact: {path}"
        assert path.stat().st_size > 0, f"Empty output artifact: {path}"

    # Verify key matrix behavior on smoke results.
    matrix_payload = json.loads((matrix_dir / "matrix_summary.json").read_text(encoding="utf-8"))
    across = {(r["attack_case"], r["defense"]): r for r in matrix_payload["across_policies"]}

    late_no_def = across[("late_bias_e1.0_s80_d20", "no_defense")]
    late_cont = across[("late_bias_e1.0_s80_d20", "continuous_velocity")]
    late_ik = across[("late_bias_e1.0_s80_d20", "ik_velocity_fusion")]
    assert late_no_def["task_success_rate"] < late_cont["task_success_rate"]
    assert late_no_def["task_success_rate"] < late_ik["task_success_rate"]

    sust_fail_stop = across[("sustained_bias_e1.0_s60_d40", "original_fail_stop")]
    sust_grace1 = across[("sustained_bias_e1.0_s60_d40", "grace1")]
    sust_cont = across[("sustained_bias_e1.0_s60_d40", "continuous_velocity")]
    sust_ik = across[("sustained_bias_e1.0_s60_d40", "ik_velocity_fusion")]
    assert sust_fail_stop["abort_rate"] == pytest.approx(1.0)
    assert sust_grace1["abort_rate"] == pytest.approx(1.0)
    assert sust_cont["abort_rate"] == pytest.approx(0.0)
    assert sust_ik["abort_rate"] == pytest.approx(0.0)

    elbow_no_def = across[("elbow_flip_s60_d30", "no_defense")]
    elbow_ik = across[("elbow_flip_s60_d30", "ik_velocity_fusion")]
    assert elbow_ik["in_window_detection_rate"] == pytest.approx(1.0)
    assert elbow_ik["task_success_rate"] > elbow_no_def["task_success_rate"]

    # Verify velocity ablation shows ik_velocity_fusion resists vel_sigma=0.5 drift vs continuous_velocity.
    with (ablation_dir / "velocity" / "ablation_summary.csv").open("r", encoding="utf-8") as fh:
        vel_rows = list(csv.DictReader(fh))
    vel_high = {
        r["defense"]: r for r in vel_rows if float(r["noise_sigma"]) == pytest.approx(0.5)
    }
    assert float(vel_high["ik_velocity_fusion"]["mean_applied_angle_mae_rad"]) < float(
        vel_high["continuous_velocity"]["mean_applied_angle_mae_rad"]
    )
    assert recovery_time([0.1] * 31, None) is None


def test_core_position_noise_stream_and_synchronized_invariance() -> None:
    env_sync = make_env(seed=4, noise_sigma=0.0)
    env_legacy = make_env(seed=4, noise_sigma=0.0, synchronized=False)
    try:
        obs_sync, _ = env_sync.reset(seed=123)
        env_legacy.reset(seed=123)
        geom = ArmGeometry.from_model(env_sync.unwrapped.model)
        rng = np.random.default_rng(8)
        for _ in range(50):
            assert geom.residual(obs_sync) < 1e-10
            action = rng.uniform(-1.0, 1.0, 2)
            obs_sync, _, _, _, info = env_sync.step(action)
            env_legacy.step(action)
            np.testing.assert_array_equal(env_sync.unwrapped.data.qpos, env_legacy.unwrapped.data.qpos)
            np.testing.assert_array_equal(env_sync.unwrapped.data.qvel, env_legacy.unwrapped.data.qvel)
            np.testing.assert_allclose(obs_sync[8:10] + obs_sync[4:6], info["truth"]["fingertip"], atol=1e-12)
    finally:
        env_sync.close()
        env_legacy.close()

    noisy = make_env(seed=4)
    try:
        a, _ = noisy.reset(seed=11)
        b, _ = noisy.reset(seed=11)
        np.testing.assert_array_equal(a[:8], b[:8])
        assert not np.array_equal(a[8:10], b[8:10])
        seq_a, seq_b = [], []
        for seq in (seq_a, seq_b):
            obs, _ = noisy.reset(seed=11, options={"noise_seed": 22})
            seq.append(obs)
            for _ in range(10):
                obs, _, _, _, _ = noisy.step(np.array([0.2, -0.1]))
                seq.append(obs)
        np.testing.assert_array_equal(seq_a, seq_b)
    finally:
        noisy.close()


def test_top_level_entrypoints_cli(tmp_path: Path) -> None:
    top_py = sorted(p.name for p in ROOT.glob("*.py"))
    assert top_py == [
        "check_setup.py",
        "demo.py",
        "plot_matrix.py",
        "run_ablation.py",
        "run_matrix.py",
        "train.py",
        "train_fallback.py",
    ]
    assert (ROOT / "tests" / "test_framework.py").is_file()
    assert (ROOT / "legacy" / "README.md").is_file()
    assert not (ROOT / "github_upload").exists()

    setup_out = tmp_path / "setup_check"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "check_setup.py"), "--no-render", "--out", str(setup_out)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert (setup_out / "setup_report.json").is_file()

    for script in (
        "train.py",
        "train_fallback.py",
        "demo.py",
        "run_matrix.py",
        "run_ablation.py",
        "plot_matrix.py",
    ):
        help_proc = subprocess.run(
            [sys.executable, str(ROOT / script), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert help_proc.returncode == 0, f"{script} --help failed: {help_proc.stderr}"


def test_framework_guide_spot_check() -> None:
    import re

    guide_path = ROOT / "FRAMEWORK_GUIDE.md"
    text = guide_path.read_text(encoding="utf-8")

    # English-only documentation without personal machine paths.
    assert re.search(r"[\u4e00-\u9fff]", text) is None
    assert re.search(r"/home/[^/\s]+", text) is None
    for forbidden in ("/home/", "miniforge3", "C:\\Users", "C:/anaconda"):
        assert forbidden not in text

    # Documented framework files, core modules, legacy readme, and CLI scripts exist.
    expected_paths = [
        "check_setup.py",
        "train.py",
        "demo.py",
        "run_matrix.py",
        "run_ablation.py",
        "plot_matrix.py",
        "tests/test_framework.py",
        "FRAMEWORK_GUIDE.md",
        "README.md",
        "requirements.txt",
        "docs/PROTOCOL.md",
        "docs/ANALYSIS_NOTES.md",
        "legacy/README.md",
        "core/__init__.py",
        "core/kinematics.py",
        "core/env_wrapper.py",
        "core/reacher_env.py",
        "core/security.py",
        "core/recovery_monitor.py",
        "attacks/__init__.py",
        "attacks/base.py",
        "attacks/legacy.py",
        "attacks/magnitude_timing.py",
        "attacks/stealthy.py",
        "attacks/adaptive.py",
        "defenses/__init__.py",
        "defenses/base.py",
        "defenses/legacy.py",
        "defenses/statistical.py",
        "defenses/fusion_recovery.py",
        "defenses/policy_level.py",
        "evaluation/__init__.py",
        "evaluation/metrics.py",
        "evaluation/presets.py",
        "evaluation/runner.py",
        "evaluation/ablation.py",
        "evaluation/visualize.py",
        "models/sac_seed_1_sync/model.zip",
    ]
    for rel in expected_paths:
        assert (ROOT / rel).is_file(), f"Missing documented path: {rel}"
        assert Path(rel).name in text

    # All backticked paths in the guide resolve to real files on disk.
    referenced_paths = re.findall(
        r"`((?:core/|attacks/|defenses/|evaluation/|models/|tests/|docs/|env/|legacy/|check_setup\.py|train\.py|demo\.py|run_matrix\.py|run_ablation\.py|plot_matrix\.py|requirements\.txt|FRAMEWORK_GUIDE\.md|README\.md)[^`\s]*\.(?:py|zip|md|txt|ps1|json))`",
        text,
    )
    assert len(referenced_paths) >= 16
    for ref in referenced_paths:
        if "<" in ref or ">" in ref:
            continue
        target = ROOT / ref
        assert target.is_file(), f"Broken file reference in FRAMEWORK_GUIDE.md: {ref}"

    # All registered attacks, defenses, presets, and seed constants are documented.
    for atk in list_attacks():
        assert atk in text
    for dfn in list_defenses():
        assert dfn in text
    for preset in list_presets():
        assert preset in text
    for seed_const in (
        f"CAL_BASE={CAL_BASE}",
        f"DEV_BASE={DEV_BASE}",
        f"TEST_BASE={TEST_BASE}",
        f"ABLATION_BASE={ABLATION_BASE}",
    ):
        assert seed_const in text
