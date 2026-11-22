"""Regression checks for the Phase-2 defense extensions (Track 2)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import gymnasium as gym
import numpy as np
import pytest
import torch

from core.reacher_env import make_env
from core.security import ArmGeometry, wrap
from defenses import (
    CalibrationStats,
    ContinuousVelocityDefense,
    CusumDefense,
    DefenseContext,
    FallbackPolicyDefense,
    IKVelocityFusionDefense,
    SlidingWindowDefense,
)
from defenses.fusion_recovery import VelocityConsistencyMonitor
from defenses.policy_level import MaskedObservationExtractor
from evaluation import run_matrix

ROOT = Path(__file__).resolve().parents[1]
DT = 0.02
THRESHOLD_M = 0.006


@pytest.fixture(scope="module")
def geometry() -> ArmGeometry:
    env = make_env(noise_sigma=0.0)
    try:
        return ArmGeometry.from_model(env.unwrapped.model)
    finally:
        env.close()


def _cal() -> CalibrationStats:
    return CalibrationStats(
        threshold_m=THRESHOLD_M,
        residual_mean_m=0.0025,
        residual_std_m=0.0013,
        residual_p95_m=0.0048,
        residual_p99_m=THRESHOLD_M,
        q0_jump_p99_rad=0.012,
        q0_jump_p999_rad=0.016,
        q1_jump_p99_rad=0.012,
        q1_jump_p999_rad=0.017,
        control_dt_seconds=DT,
        episodes=10,
        seed_base=1000000,
    )


def _ctx(geometry: ArmGeometry, fallback_policy=None) -> DefenseContext:
    return DefenseContext(geometry=geometry, dt=DT, calibration=_cal(), fallback_policy=fallback_policy)


def _obs(geometry, q0, q1, v0, v1, tip_offset=(0.0, 0.0), target=(0.1, -0.02)):
    target_arr = np.asarray(target, dtype=np.float64)
    tip = geometry.forward(q0, q1) + np.asarray(tip_offset, dtype=np.float64)
    return np.array(
        [np.cos(q0), np.cos(q1), np.sin(q0), np.sin(q1), *target_arr, v0, v1, *(tip - target_arr)],
        dtype=np.float64,
    )


def _trajectory(steps=60, w0=0.6, w1=-0.4, q0=0.3, q1=-0.6):
    """Constant-velocity joint motion: encoder increments equal dt * velocity exactly."""
    t = np.arange(steps)
    return q0 + w0 * DT * t, q1 + w1 * DT * t, w0, w1


def _with_angle(geometry, raw_q0, raw_q1, v0, v1, rep_q0):
    """Observation whose fingertip follows the true angles but joint-0 encoder reports ``rep_q0``."""
    obs = _obs(geometry, raw_q0, raw_q1, v0, v1)
    obs[0], obs[2] = np.cos(rep_q0), np.sin(rep_q0)
    return obs


# --- Statistical detectors -------------------------------------------------


def test_tuned_statistical_defaults() -> None:
    assert CusumDefense().config_dict()["params"] == {
        "max_alarm_steps": None, "k": 1.0, "h": 5.0, "spike_factor": 1.5,
    }
    params = SlidingWindowDefense().config_dict()["params"]
    assert (params["window_size"], params["min_hits"], params["hit_factor"]) == (8, 4, 0.8)


def test_sliding_window_hit_factor_sees_subthreshold_offset(geometry: ArmGeometry) -> None:
    ctx = _ctx(geometry)
    tip_offset = (0.85 * THRESHOLD_M, 0.0)  # persistent residual just under the single-step threshold
    tuned, legacy = SlidingWindowDefense(), SlidingWindowDefense(window_size=5, min_hits=3, hit_factor=1.0)
    tuned.reset(ctx)
    legacy.reset(ctx)
    tuned_alarms, legacy_alarms = [], []
    for step in range(20):
        obs = _obs(geometry, 0.3, -0.6, 0.0, 0.0, tip_offset=tip_offset if step >= 1 else (0.0, 0.0))
        tuned_alarms.append(tuned.process(obs, step, ctx).alarm)
        legacy_alarms.append(legacy.process(obs, step, ctx).alarm)
    assert not any(legacy_alarms)
    assert tuned_alarms.index(True) == 4  # 4 of the last 8 steps are hits


# --- Continuous velocity -----------------------------------------------------


def test_continuous_velocity_threshold_factor(geometry: ArmGeometry) -> None:
    ctx = _ctx(geometry)
    obs0 = _obs(geometry, 0.3, -0.6, 0.0, 0.0)
    obs1 = _obs(geometry, 0.3, -0.6, 0.0, 0.0, tip_offset=(1.2 * THRESHOLD_M, 0.0))
    for factor, expected in ((1.5, False), (1.0, True)):
        defense = ContinuousVelocityDefense(threshold_factor=factor)
        defense.reset(ctx)
        defense.process(obs0, 0, ctx)
        assert defense.process(obs1, 1, ctx).alarm is expected


def test_divergence_abort_uses_corrected_estimate(geometry: ArmGeometry) -> None:
    ctx = _ctx(geometry)
    q0s, q1s, w0, w1 = _trajectory(steps=40)

    def run(vel_bias: float) -> list[bool]:
        defense = ContinuousVelocityDefense(divergence_abort_m=0.03)
        defense.reset(ctx)
        aborts = []
        for step in range(40):
            spoofed = step >= 10
            obs = _with_angle(geometry, q0s[step], q1s[step], w0 + (vel_bias if spoofed else 0.0), w1,
                              q0s[step] + (1.0 if spoofed else 0.0))
            res = defense.process(obs, step, ctx)
            aborts.append(res.abort)
            if res.abort:
                break
        return aborts

    # A 1 rad spoof gives a huge reported residual, but honest-velocity dead
    # reckoning stays on the measured fingertip, so it must not abort.
    assert not any(run(vel_bias=0.0))
    # A tampered velocity makes dead reckoning drift away from the fingertip.
    assert any(run(vel_bias=3.0))


# --- Velocity consistency and IK fusion --------------------------------------


def test_velocity_consistency_monitor_flags_bias_not_offsets() -> None:
    q0s, q1s, w0, w1 = _trajectory(steps=40)
    monitor = VelocityConsistencyMonitor()
    monitor.reset(np.array([q0s[0], q1s[0]]), np.array([w0, w1]))
    flagged = []
    for t in range(1, 40):
        offset = 0.8 if t >= 15 else 0.0  # constant angle offset: one-step increment spike only
        out = monitor.update(np.array([q0s[t] + offset, q1s[t]]), np.array([w0, w1]), DT)
        flagged.append(bool(out["flagged"][0]))
    assert not any(flagged)

    monitor.reset(np.array([q0s[0], q1s[0]]), np.array([w0, w1]))
    for t in range(1, 40):
        out = monitor.update(np.array([q0s[t], q1s[t]]), np.array([w0 + (1.0 if t >= 15 else 0.0), w1]), DT)
    assert out["flagged"][0] and not out["flagged"][1]
    assert out["bias_rad_s"][0] == pytest.approx(1.0, abs=1e-6)


def test_ik_fusion_clean_trajectory_has_no_alarms(geometry: ArmGeometry) -> None:
    ctx = _ctx(geometry)
    defense = IKVelocityFusionDefense()
    defense.reset(ctx)
    q0s, q1s, w0, w1 = _trajectory()
    for step in range(len(q0s)):
        res = defense.process(_obs(geometry, q0s[step], q1s[step], w0, w1), step, ctx)
        assert res.alarm is False
        np.testing.assert_allclose(res.policy_obs, _obs(geometry, q0s[step], q1s[step], w0, w1))


def test_ik_fusion_gates_velocity_only_tampering(geometry: ArmGeometry) -> None:
    ctx = _ctx(geometry)
    defense = IKVelocityFusionDefense()
    defense.reset(ctx)
    q0s, q1s, w0, w1 = _trajectory()
    results = []
    for step in range(len(q0s)):
        bias = 2.0 if step >= 20 else 0.0
        results.append(defense.process(_obs(geometry, q0s[step], q1s[step], w0 + bias, w1), step, ctx))
    assert not any(r.alarm for r in results[:20])
    late = results[26:]
    assert all(r.alarm and r.metadata["vel_gated"] for r in late)
    for r in late:
        assert r.policy_obs[6] == pytest.approx(w0, abs=1e-6)  # policy sees the de-biased velocity
        assert r.metadata["res_alarm"] is False


def test_ik_fusion_attributes_angle_ramp_to_encoder(geometry: ArmGeometry) -> None:
    ctx = _ctx(geometry)
    defense = IKVelocityFusionDefense()
    defense.reset(ctx)
    q0s, q1s, w0, w1 = _trajectory()
    results = []
    for step in range(len(q0s)):
        ramp = 0.004 * max(0, step - 19)  # slow encoder ramp, velocity honest
        obs = _with_angle(geometry, q0s[step], q1s[step], w0, w1, q0s[step] + ramp)
        results.append(defense.process(obs, step, ctx))
    flagged = [r for r in results[20:] if r.metadata["vel_alarm"]]
    assert flagged, "velocity-consistency check should see the encoder ramp"
    assert not any(r.metadata["vel_gated"] for r in flagged)
    for step, r in enumerate(results):
        assert r.policy_obs[6] == pytest.approx(w0)  # honest velocity is never rewritten
        if r.metadata.get("vel_alarm"):
            q0_pol = np.arctan2(r.policy_obs[2], r.policy_obs[0])
            ramp = 0.004 * max(0, step - 19)
            assert abs(wrap(q0_pol - q0s[step])) < ramp + 1e-9


# --- Policy-level fallback ---------------------------------------------------


def test_masked_extractor_ignores_masked_channels() -> None:
    space = gym.spaces.Box(-np.inf, np.inf, shape=(10,), dtype=np.float64)
    extractor = MaskedObservationExtractor(space, masked_indices=[0, 2, 6])
    obs = torch.randn(4, 10)
    scrambled = obs.clone()
    scrambled[:, [0, 2, 6]] = torch.randn(4, 3) * 10.0
    torch.testing.assert_close(extractor(obs), extractor(scrambled))
    assert torch.equal(extractor(obs)[:, 1], obs[:, 1])
    with pytest.raises(ValueError):
        MaskedObservationExtractor(space, masked_indices=[10])


class _ConstantPolicy:
    def predict(self, obs, deterministic=True):
        del obs, deterministic
        return np.array([0.25, -0.25], dtype=np.float32), None


def test_fallback_latch_and_base_options(geometry: ArmGeometry) -> None:
    defaults = FallbackPolicyDefense().config_dict()["params"]
    assert (defaults["base_defense"], defaults["switch_streak"], defaults["latch"]) == (
        "ik_velocity_fusion", 10, False,
    )
    with pytest.raises(ValueError):
        FallbackPolicyDefense(base_defense="cusum")
    ctx = _ctx(geometry, fallback_policy=_ConstantPolicy())
    q0s, q1s, w0, w1 = _trajectory(steps=40)

    def states(**params) -> list[str]:
        defense = FallbackPolicyDefense(switch_streak=3, **params)
        defense.reset(ctx)
        out = []
        for step in range(40):
            spoofed = 10 <= step < 20
            obs = _with_angle(geometry, q0s[step], q1s[step], w0, w1, q0s[step] + (1.0 if spoofed else 0.0))
            res = defense.process(obs, step, ctx)
            out.append(res.state)
            if res.state == "fallback":
                np.testing.assert_allclose(res.action_override, [0.25, -0.25])
        return out

    recoverable = states()
    assert recoverable[12] == "fallback" and recoverable[25] == "normal"
    latched = states(latch=True)
    assert latched[12:] == ["fallback"] * 28
    velocity_based = states(base_defense="continuous_velocity")
    assert velocity_based[12] == "fallback" and velocity_based[25] == "normal"


ROBUST_MODEL = ROOT / "models" / "sac_seed_1_robust" / "model.zip"


@pytest.mark.skipif(not ROBUST_MODEL.exists(), reason="robust fallback model not trained")
def test_robust_fallback_model_ignores_joint0_channels() -> None:
    from stable_baselines3 import SAC

    model = SAC.load(ROBUST_MODEL, device="cpu")
    masked = list(model.policy.actor.features_extractor.masked_indices)
    assert masked == [0, 2]
    rng = np.random.default_rng(1100000)
    obs = rng.normal(size=(32, 10))
    scrambled = obs.copy()
    scrambled[:, masked] = rng.uniform(-3.0, 3.0, size=(32, len(masked)))
    a, _ = model.predict(obs, deterministic=True)
    b, _ = model.predict(scrambled, deterministic=True)
    np.testing.assert_allclose(a, b, atol=1e-6)


@pytest.mark.parametrize("preset", ["late_strong", "full_matrix"])
def test_matrix_cli_requires_fallback_checkpoint(tmp_path: Path, preset: str) -> None:
    # fallback_policy without a checkpoint would label steps 'fallback' but never
    # override an action, so the matrix must refuse before writing any output.
    out_dir = tmp_path / "matrix"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "run_matrix.py"), "--preset", preset,
         "--episodes", "1", "--calibration-episodes", "1", "--out", str(out_dir)],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode != 0
    assert "--fallback-model" in proc.stderr
    assert "fallback_policy" in proc.stderr
    assert not out_dir.exists()

    with pytest.raises(ValueError, match="fallback checkpoint"):
        run_matrix(out=out_dir, preset="smoke", defenses=["fallback_policy"],
                   episodes=1, calibration_episodes=1)
    assert not out_dir.exists()
