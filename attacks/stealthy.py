"""Stealthy kinematics- and multi-channel-aware sensor spoofing attacks."""
from __future__ import annotations

import numpy as np

from core.security import wrap

from core.kinematics import elbow_flip_angles
from .base import AttackContext, AttackResult, BaseAttack, register_attack


def _validate_window_params(duration: int, start: int, sign: int) -> tuple[int, int, int]:
    """Validate and normalize episode window bounds and attack sign."""
    resolved_duration = int(duration)
    resolved_start = int(start)
    resolved_sign = int(sign)
    if resolved_duration < 1 or resolved_start < 1 or resolved_sign not in (-1, 1):
        raise ValueError("duration >= 1, start >= 1, and sign in {-1, 1} are required")
    return resolved_duration, resolved_start, resolved_sign


def _validate_nonneg_finite(value: float, name: str) -> float:
    """Validate that a numeric parameter is finite and nonnegative."""
    resolved = float(value)
    if not np.isfinite(resolved) or resolved < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return resolved


@register_attack("threshold_aware")
class ThresholdAwareRampAttack(BaseAttack):
    """Joint-0 ramp attack capped below the calibrated FK residual threshold."""

    def __init__(
        self,
        epsilon: float = 0.1,
        duration: int = 20,
        start: int = 80,
        margin: float = 0.85,
        sign: int = 1,
    ) -> None:
        resolved_epsilon = _validate_nonneg_finite(epsilon, "epsilon")
        resolved_duration, resolved_start, resolved_sign = _validate_window_params(
            duration, start, sign
        )
        resolved_margin = _validate_nonneg_finite(margin, "margin")

        super().__init__(
            epsilon=resolved_epsilon,
            duration=resolved_duration,
            start=resolved_start,
            margin=resolved_margin,
            sign=resolved_sign,
        )
        self.epsilon: float = resolved_epsilon
        self.duration: int = resolved_duration
        self.start: int = resolved_start
        self.margin: float = resolved_margin
        self._sign: int = resolved_sign

    def reset(
        self,
        seed: int,
        sign: int = 1,
        context: AttackContext | None = None,
    ) -> None:
        super().reset(seed, sign=sign, context=context)
        self._sign = self.sign

    def apply(
        self,
        raw_obs: np.ndarray,
        step: int,
        context: AttackContext,
    ) -> AttackResult:
        raw = np.asarray(raw_obs, dtype=np.float64)
        reported = np.array(raw_obs, dtype=np.float64, copy=True)
        step_idx = int(step)
        is_active = self.start <= step_idx < self.start + self.duration
        delta = 0.0
        metadata: dict[str, float] = {}

        if is_active:
            thresh = (
                float(context.calibrated_threshold_m)
                if context.calibrated_threshold_m is not None
                else 0.006
            )
            if not np.isfinite(thresh) or thresh < 0.0:
                raise ValueError("calibrated_threshold_m must be finite and nonnegative")

            q0, q1 = np.arctan2(raw[2:4], raw[:2])
            tip = context.geometry.forward(float(q0), float(q1))
            r = float(np.linalg.norm(tip - context.geometry.origin))
            delta_max = 2.0 * float(
                np.arcsin(np.clip((self.margin * thresh) / max(2.0 * r, 1e-6), 0.0, 1.0))
            )
            ramp_mag = self.epsilon * ((step_idx - self.start + 1) / self.duration)
            mag = min(ramp_mag, delta_max)
            delta = float(self._sign * mag)
            if delta != 0.0:
                q0_adv = float(q0) + delta
                reported[0] = float(np.cos(q0_adv))
                reported[2] = float(np.sin(q0_adv))
            metadata = {
                "threshold_m": thresh,
                "radius_m": r,
                "delta_max_rad": delta_max,
            }

        return AttackResult(
            reported_obs=reported,
            is_active=bool(is_active),
            attacked_channels=(0, 2),
            delta_rad=delta,
            metadata=metadata,
        )


@register_attack("elbow_flip")
class ElbowFlipAttack(BaseAttack):
    """Exact 2-link mirror-pose attack preserving fingertip FK position."""

    def __init__(
        self,
        duration: int = 20,
        start: int = 60,
        sign: int = 1,
        epsilon: float = 0.0,
    ) -> None:
        resolved_duration, resolved_start, resolved_sign = _validate_window_params(
            duration, start, sign
        )
        resolved_epsilon = _validate_nonneg_finite(epsilon, "epsilon")

        super().__init__(
            duration=resolved_duration,
            start=resolved_start,
            sign=resolved_sign,
            epsilon=resolved_epsilon,
        )
        self.duration: int = resolved_duration
        self.start: int = resolved_start
        self.epsilon: float = resolved_epsilon
        self._sign: int = resolved_sign

    def reset(
        self,
        seed: int,
        sign: int = 1,
        context: AttackContext | None = None,
    ) -> None:
        super().reset(seed, sign=sign, context=context)
        self._sign = self.sign

    def apply(
        self,
        raw_obs: np.ndarray,
        step: int,
        context: AttackContext,
    ) -> AttackResult:
        raw = np.asarray(raw_obs, dtype=np.float64)
        reported = np.array(raw_obs, dtype=np.float64, copy=True)
        step_idx = int(step)
        is_active = self.start <= step_idx < self.start + self.duration
        delta_rad = 0.0
        metadata: dict[str, float] = {}

        if is_active:
            q0, q1 = np.arctan2(raw[2:4], raw[:2])
            q0_alt, q1_alt = elbow_flip_angles(context.geometry, float(q0), float(q1))
            reported[0], reported[2] = float(np.cos(q0_alt)), float(np.sin(q0_alt))
            reported[1], reported[3] = float(np.cos(q1_alt)), float(np.sin(q1_alt))
            delta_rad = wrap(q0_alt - float(q0))
            metadata = {"q1_delta_rad": wrap(q1_alt - float(q1))}

        return AttackResult(
            reported_obs=reported,
            is_active=bool(is_active),
            attacked_channels=(0, 1, 2, 3),
            delta_rad=delta_rad,
            metadata=metadata,
        )


@register_attack("joint_vel_coupled")
class JointVelocityCoupledAttack(BaseAttack):
    """Coordinated joint-0 angle and joint-0 velocity spoofing attack."""

    def __init__(
        self,
        epsilon: float = 0.5,
        duration: int = 20,
        start: int = 80,
        vel_bias: float = 0.5,
        sign: int = 1,
    ) -> None:
        resolved_epsilon = _validate_nonneg_finite(epsilon, "epsilon")
        resolved_duration, resolved_start, resolved_sign = _validate_window_params(
            duration, start, sign
        )
        resolved_vel_bias = float(vel_bias)
        if not np.isfinite(resolved_vel_bias):
            raise ValueError("vel_bias must be finite")

        super().__init__(
            epsilon=resolved_epsilon,
            duration=resolved_duration,
            start=resolved_start,
            vel_bias=resolved_vel_bias,
            sign=resolved_sign,
        )
        self.epsilon: float = resolved_epsilon
        self.duration: int = resolved_duration
        self.start: int = resolved_start
        self.vel_bias: float = resolved_vel_bias
        self._sign: int = resolved_sign

    def reset(
        self,
        seed: int,
        sign: int = 1,
        context: AttackContext | None = None,
    ) -> None:
        super().reset(seed, sign=sign, context=context)
        self._sign = self.sign

    def apply(
        self,
        raw_obs: np.ndarray,
        step: int,
        context: AttackContext,
    ) -> AttackResult:
        del context
        raw = np.asarray(raw_obs, dtype=np.float64)
        reported = np.array(raw_obs, dtype=np.float64, copy=True)
        step_idx = int(step)
        is_active = self.start <= step_idx < self.start + self.duration
        delta = 0.0
        metadata: dict[str, float] = {}

        if is_active:
            delta = float(self._sign * self.epsilon)
            if delta != 0.0:
                q0_adv = float(np.arctan2(raw[2], raw[0])) + delta
                reported[0] = float(np.cos(q0_adv))
                reported[2] = float(np.sin(q0_adv))
            vel_delta = float(self._sign * self.vel_bias)
            reported[6] = float(raw[6]) + vel_delta
            metadata = {"vel_bias_rad_s": vel_delta}

        return AttackResult(
            reported_obs=reported,
            is_active=bool(is_active),
            attacked_channels=(0, 2, 6),
            delta_rad=delta,
            metadata=metadata,
        )


# TODO (Teammate Task 1): Extend threshold-aware spoofing to evade CUSUM/sliding-window
# detectors (e.g., alternating pulses or fingertip-coupled offsets) and evaluate velocity
# coupling magnitudes against IKVelocityFusionDefense.
