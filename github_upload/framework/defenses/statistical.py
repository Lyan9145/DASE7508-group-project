"""Statistical temporal-accumulation defenses (CUSUM and sliding-window)."""
from __future__ import annotations

from abc import abstractmethod
from collections import deque
from typing import Any

import numpy as np

from framework.core.security import wrap

from .base import BaseDefense, DefenseContext, DefenseResult, register_defense


class _BaseStatisticalVelocityDefense(BaseDefense):
    """Shared velocity-prediction loop for temporal residual detectors."""

    max_alarm_steps: int | None

    def __init__(self, max_alarm_steps: int | None, **params: Any) -> None:
        if max_alarm_steps is not None:
            max_alarm_steps = int(max_alarm_steps)
            if max_alarm_steps < 0:
                raise ValueError("max_alarm_steps must be >= 0 or None")
        self.max_alarm_steps = max_alarm_steps
        super().__init__(max_alarm_steps=self.max_alarm_steps, **params)
        self._angle: float | None = None
        self._prev_vel: float | None = None
        self._streak: int = 0

    @abstractmethod
    def _reset_detector(self) -> None:
        """Reset detector-specific accumulation state."""

    @abstractmethod
    def _warmup_metadata(self) -> dict[str, Any]:
        """Return detector-specific metadata for step-0 warmup."""

    @abstractmethod
    def _detect(
        self,
        residual_m: float,
        context: DefenseContext,
    ) -> tuple[bool, dict[str, Any]]:
        """Update detector state and return ``(alarm, metadata)``."""

    def reset(self, context: DefenseContext) -> None:
        del context
        self._angle = None
        self._prev_vel = None
        self._streak = 0
        self._reset_detector()

    def process(
        self,
        reported_obs: np.ndarray,
        step: int,
        context: DefenseContext,
    ) -> DefenseResult:
        obs = np.array(reported_obs, dtype=np.float64, copy=True)
        residual_m = float(context.geometry.residual(obs))

        if step == 0 or self._angle is None or self._prev_vel is None:
            self._angle = float(np.arctan2(obs[2], obs[0]))
            self._prev_vel = float(reported_obs[6])
            self._streak = 0
            self._reset_detector()
            return DefenseResult(
                policy_obs=obs,
                alarm=False,
                abort=False,
                state="normal",
                residual_m=residual_m,
                alarm_streak=0,
                metadata=self._warmup_metadata(),
            )

        alarm, meta = self._detect(residual_m, context)
        if alarm:
            self._angle = wrap(self._angle + self._prev_vel * context.dt)
            obs[0] = float(np.cos(self._angle))
            obs[2] = float(np.sin(self._angle))
            self._streak += 1
        else:
            self._angle = float(np.arctan2(obs[2], obs[0]))
            self._streak = 0

        self._prev_vel = float(reported_obs[6])
        abort = bool(
            self.max_alarm_steps is not None and self._streak > self.max_alarm_steps
        )
        state = "aborted" if abort else "correcting" if alarm else "normal"
        return DefenseResult(
            policy_obs=obs,
            alarm=alarm,
            abort=abort,
            state=state,
            residual_m=residual_m,
            alarm_streak=self._streak,
            metadata=meta,
        )


@register_defense("cusum")
class CusumDefense(_BaseStatisticalVelocityDefense):
    """One-sided CUSUM residual detector with single-step spike guard and velocity prediction.

    Accumulates standardized kinematic residuals ``z = (r - mu) / max(sigma, 1e-6)``
    to catch sustained sub-threshold offsets (e.g., ``ThresholdAwareRampAttack``)
    while also immediately triggering on large spikes above ``spike_factor * threshold``.
    """

    def __init__(
        self,
        k: float = 1.5,
        h: float = 5.0,
        spike_factor: float = 1.5,
        max_alarm_steps: int | None = None,
    ) -> None:
        self.k = float(k)
        self.h = float(h)
        self.spike_factor = float(spike_factor)
        if not np.isfinite(self.k) or self.k < 0.0:
            raise ValueError("k must be finite and >= 0")
        if not np.isfinite(self.h) or self.h <= 0.0:
            raise ValueError("h must be finite and > 0")
        if not np.isfinite(self.spike_factor) or self.spike_factor <= 0.0:
            raise ValueError("spike_factor must be finite and > 0")
        self._cusum: float = 0.0
        super().__init__(
            max_alarm_steps=max_alarm_steps,
            k=self.k,
            h=self.h,
            spike_factor=self.spike_factor,
        )

    def _reset_detector(self) -> None:
        self._cusum = 0.0

    def _warmup_metadata(self) -> dict[str, Any]:
        return {"warmup": True, "cusum": 0.0, "z": 0.0}

    def _detect(
        self,
        residual_m: float,
        context: DefenseContext,
    ) -> tuple[bool, dict[str, Any]]:
        cal = context.calibration
        z = (residual_m - cal.residual_mean_m) / max(cal.residual_std_m, 1e-6)
        self._cusum = float(min(max(0.0, self._cusum + z - self.k), 2.0 * self.h))
        alarm = bool(
            (self._cusum > self.h)
            or (residual_m > self.spike_factor * cal.threshold_m)
        )
        return alarm, {"warmup": False, "cusum": self._cusum, "z": float(z)}

    # TODO (Teammate Task 2): Tune (k, h, spike_factor) against stealthy sub-threshold
    # attacks (`threshold_aware`, low-epsilon `ramp`) on the dev seed block (1100000+),
    # and optionally explore two-sided / velocity-channel CUSUM statistics.


@register_defense("sliding_window")
class SlidingWindowDefense(_BaseStatisticalVelocityDefense):
    """M-of-N sliding-window residual detector with single-step spike guard.

    Triggers an alarm when at least ``min_hits`` out of the last ``window_size``
    observations exceed ``calibration.threshold_m``, or when a single residual
    exceeds ``spike_factor * calibration.threshold_m``.
    """

    def __init__(
        self,
        window_size: int = 5,
        min_hits: int = 3,
        spike_factor: float = 1.5,
        max_alarm_steps: int | None = None,
    ) -> None:
        self.window_size = int(window_size)
        self.min_hits = int(min_hits)
        self.spike_factor = float(spike_factor)
        if self.window_size < 1:
            raise ValueError("window_size must be >= 1")
        if self.min_hits < 1 or self.min_hits > self.window_size:
            raise ValueError("min_hits must satisfy 1 <= min_hits <= window_size")
        if not np.isfinite(self.spike_factor) or self.spike_factor <= 0.0:
            raise ValueError("spike_factor must be finite and > 0")
        self._hits: deque[int] = deque(maxlen=self.window_size)
        super().__init__(
            max_alarm_steps=max_alarm_steps,
            window_size=self.window_size,
            min_hits=self.min_hits,
            spike_factor=self.spike_factor,
        )

    def _reset_detector(self) -> None:
        self._hits.clear()

    def _warmup_metadata(self) -> dict[str, Any]:
        return {"warmup": True, "window_hits": 0, "hit": False}

    def _detect(
        self,
        residual_m: float,
        context: DefenseContext,
    ) -> tuple[bool, dict[str, Any]]:
        cal = context.calibration
        hit = int(residual_m > cal.threshold_m)
        self._hits.append(hit)
        hit_sum = int(sum(self._hits))
        alarm = bool(
            (hit_sum >= self.min_hits)
            or (residual_m > self.spike_factor * cal.threshold_m)
        )
        return alarm, {"warmup": False, "window_hits": hit_sum, "hit": bool(hit)}

    # TODO (Teammate Task 2): Compare false-alarm vs detection-delay trade-offs across
    # (window_size, min_hits) under high position/velocity noise, or combine with
    # IK-based correction instead of pure velocity dead-reckoning during long alarms.
