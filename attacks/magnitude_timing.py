"""Magnitude- and timing-scheduled joint-0 sensor spoofing attacks."""
from __future__ import annotations

from collections import deque

import numpy as np

from core.security import wrap

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


def _apply_joint0_delta(reported: np.ndarray, raw: np.ndarray, delta: float) -> None:
    """Rotate joint-0 (cos, sin) channels (0, 2) by ``delta`` radians on the unit circle."""
    if delta != 0.0:
        q0_adv = float(np.arctan2(raw[2], raw[0])) + delta
        reported[0] = float(np.cos(q0_adv))
        reported[2] = float(np.sin(q0_adv))


@register_attack("sinusoidal")
class SinusoidalAttack(BaseAttack):
    """Sinusoidally modulated joint-0 angle spoofing within the active window."""

    def __init__(
        self,
        epsilon: float = 0.5,
        duration: int = 20,
        start: int = 80,
        freq_hz: float = 5.0,
        phase: float = 0.0,
        sign: int = 1,
    ) -> None:
        resolved_epsilon = _validate_nonneg_finite(epsilon, "epsilon")
        resolved_duration, resolved_start, resolved_sign = _validate_window_params(
            duration, start, sign
        )
        resolved_freq_hz = _validate_nonneg_finite(freq_hz, "freq_hz")
        resolved_phase = float(phase)
        if not np.isfinite(resolved_phase):
            raise ValueError("phase must be finite")

        super().__init__(
            epsilon=resolved_epsilon,
            duration=resolved_duration,
            start=resolved_start,
            freq_hz=resolved_freq_hz,
            phase=resolved_phase,
            sign=resolved_sign,
        )
        self.epsilon: float = resolved_epsilon
        self.duration: int = resolved_duration
        self.start: int = resolved_start
        self.freq_hz: float = resolved_freq_hz
        self.phase: float = resolved_phase
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
        if is_active:
            delta = float(
                self._sign
                * self.epsilon
                * np.sin(
                    2.0 * np.pi * self.freq_hz * (step_idx - self.start) * float(context.dt)
                    + self.phase
                )
            )
            _apply_joint0_delta(reported, raw, delta)
        return AttackResult(
            reported_obs=reported,
            is_active=bool(is_active),
            attacked_channels=(0, 2),
            delta_rad=delta,
            metadata={"freq_hz": self.freq_hz, "phase": self.phase},
        )


@register_attack("freeze")
class FreezeAttack(BaseAttack):
    """Freeze joint-0 (cos, sin) readings at the last pre-attack observation."""

    def __init__(
        self,
        duration: int = 20,
        start: int = 80,
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
        self._frozen: tuple[float, float] | None = None

    def reset(
        self,
        seed: int,
        sign: int = 1,
        context: AttackContext | None = None,
    ) -> None:
        super().reset(seed, sign=sign, context=context)
        self._sign = self.sign
        self._frozen = None

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

        if step_idx == self.start - 1:
            self._frozen = (float(raw[0]), float(raw[2]))

        is_active = self.start <= step_idx < self.start + self.duration
        delta_rad = 0.0
        if is_active:
            if self._frozen is None:
                self._frozen = (float(raw[0]), float(raw[2]))
            reported[0], reported[2] = self._frozen
            delta_rad = wrap(
                float(
                    np.arctan2(self._frozen[1], self._frozen[0])
                    - np.arctan2(raw[2], raw[0])
                )
            )
        return AttackResult(
            reported_obs=reported,
            is_active=bool(is_active),
            attacked_channels=(0, 2),
            delta_rad=delta_rad,
            metadata={"frozen_captured": self._frozen is not None},
        )


@register_attack("replay")
class ReplayAttack(BaseAttack):
    """Loop pre-attack joint-0 (cos, sin) readings during the active window."""

    def __init__(
        self,
        duration: int = 20,
        start: int = 80,
        replay_len: int = 10,
        sign: int = 1,
        epsilon: float = 0.0,
    ) -> None:
        resolved_duration, resolved_start, resolved_sign = _validate_window_params(
            duration, start, sign
        )
        resolved_replay_len = int(replay_len)
        if resolved_replay_len < 1:
            raise ValueError("replay_len >= 1 is required")
        resolved_epsilon = _validate_nonneg_finite(epsilon, "epsilon")

        super().__init__(
            duration=resolved_duration,
            start=resolved_start,
            replay_len=resolved_replay_len,
            sign=resolved_sign,
            epsilon=resolved_epsilon,
        )
        self.duration: int = resolved_duration
        self.start: int = resolved_start
        self.replay_len: int = resolved_replay_len
        self.epsilon: float = resolved_epsilon
        self._sign: int = resolved_sign
        self._buffer: deque[tuple[float, float]] = deque(maxlen=resolved_replay_len)

    def reset(
        self,
        seed: int,
        sign: int = 1,
        context: AttackContext | None = None,
    ) -> None:
        super().reset(seed, sign=sign, context=context)
        self._sign = self.sign
        self._buffer.clear()

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

        if step_idx < self.start:
            self._buffer.append((float(raw[0]), float(raw[2])))

        is_active = self.start <= step_idx < self.start + self.duration
        delta_rad = 0.0
        if is_active:
            if self._buffer:
                rep_cos, rep_sin = self._buffer[(step_idx - self.start) % len(self._buffer)]
            else:
                rep_cos, rep_sin = float(raw[0]), float(raw[2])
            reported[0], reported[2] = rep_cos, rep_sin
            delta_rad = wrap(
                float(np.arctan2(rep_sin, rep_cos) - np.arctan2(raw[2], raw[0]))
            )
        return AttackResult(
            reported_obs=reported,
            is_active=bool(is_active),
            attacked_channels=(0, 2),
            delta_rad=delta_rad,
            metadata={"buffer_len": len(self._buffer)},
        )


# TODO (Teammate Task 1): Tune freq_hz/phase/replay_len sweeps, add chirp or bursty
# timing schedules, and optionally extend freeze/replay to joint-1 or velocity channels.
