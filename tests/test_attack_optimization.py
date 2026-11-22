"""Focused regression checks for the Phase-2 attack optimizations."""

import numpy as np

from pathlib import Path

from stable_baselines3 import SAC

from attacks import AttackContext, PolicyGradientAttack, PulseAttack, ThresholdAwareRampAttack
from core.reacher_env import make_env
from core.security import ArmGeometry


def test_threshold_aware_respects_noisy_position_budget() -> None:
    env = make_env(noise_sigma=0.0)
    try:
        geometry = ArmGeometry.from_model(env.unwrapped.model)
    finally:
        env.close()

    q0, q1 = 0.4, -0.5
    target = np.array([0.08, -0.02])
    tip = geometry.forward(q0, q1)
    measured_tip = tip + np.array([0.003, 0.0])
    raw = np.array([
        np.cos(q0), np.cos(q1), np.sin(q0), np.sin(q1),
        *target, 0.0, 0.0, *(measured_tip - target),
    ], dtype=np.float64)
    snapshot = raw.copy()
    threshold = 0.006
    margin = 0.85
    attack = ThresholdAwareRampAttack(epsilon=0.3, start=10, duration=20, margin=margin)
    context = AttackContext(geometry=geometry, dt=0.02, calibrated_threshold_m=threshold)
    attack.reset(seed=1100000, sign=1, context=context)

    result = attack.apply(raw, step=29, context=context)
    np.testing.assert_array_equal(raw, snapshot)
    np.testing.assert_array_equal(result.reported_obs[[1, 3, 4, 5, 6, 7, 8, 9]], raw[[1, 3, 4, 5, 6, 7, 8, 9]])
    assert result.delta_rad > 0.0
    assert geometry.residual(result.reported_obs) <= margin * threshold + 1e-9


def test_policy_gradient_residual_penalty_preserves_actor() -> None:
    model_path = Path(__file__).resolve().parent.parent / "models/sac_seed_1_sync/model.zip"
    model = SAC.load(model_path, device="cpu")
    actor = model.policy.actor
    before = [parameter.detach().clone() for parameter in actor.parameters()]
    env = make_env(noise_sigma=0.0)
    try:
        geometry = ArmGeometry.from_model(env.unwrapped.model)
        raw, _ = env.reset(seed=1100000)
        context = AttackContext(
            geometry=geometry,
            dt=float(env.unwrapped.dt),
            calibrated_threshold_m=0.006,
            policy=model,
        )
        attack = PolicyGradientAttack(
            epsilon=0.5, start=10, duration=5, n_restarts=3, residual_weight=0.1
        )
        attack.reset(seed=1100000, context=context)
        result = attack.apply(raw, step=10, context=context)
        assert abs(result.delta_rad) <= 0.5 + 1e-6
        assert np.isfinite(result.reported_obs).all()
        np.testing.assert_array_equal(result.reported_obs[1::2], raw[1::2])
        for current, original in zip(actor.parameters(), before):
            assert np.array_equal(current.detach().numpy(), original.numpy())
    finally:
        env.close()


def test_pulse_resets_observation_between_bursts() -> None:
    raw = np.array([1.0, 1.0, 0.0, 0.0, 0.1, 0.1, 0.0, 0.0, 0.1, 0.1])
    attack = PulseAttack(epsilon=0.5, start=10, duration=8, on_steps=3, off_steps=1)
    attack.reset(seed=1100000, sign=-1)
    for step in range(10, 18):
        result = attack.apply(raw, step, context=None)
        assert result.is_active
        if (step - 10) % 4 == 3:
            np.testing.assert_array_equal(result.reported_obs, raw)
            assert result.delta_rad == 0.0
        else:
            assert result.delta_rad == -0.5
            np.testing.assert_array_equal(result.reported_obs[[1, 3, 4, 5, 6, 7, 8, 9]], raw[[1, 3, 4, 5, 6, 7, 8, 9]])
