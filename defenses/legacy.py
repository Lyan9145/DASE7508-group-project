"""Legacy defense wrappers for pass-through, fail-stop, and grace-1 monitors."""
from __future__ import annotations

import numpy as np

from core.recovery_monitor import RecoveryMonitor
from core.security import KinematicMonitor

from .base import BaseDefense, DefenseContext, DefenseResult, register_defense


@register_defense("no_defense")
class NoDefense(BaseDefense):
    """Pass-through defense that computes residual without modifying observations."""

    def __init__(self) -> None:
        super().__init__()

    def process(
        self,
        reported_obs: np.ndarray,
        step: int,
        context: DefenseContext,
    ) -> DefenseResult:
        del step
        obs = np.array(reported_obs, dtype=float, copy=True)
        residual_m = float(context.geometry.residual(obs))
        return DefenseResult(
            policy_obs=obs,
            alarm=False,
            abort=False,
            state="normal",
            residual_m=residual_m,
            alarm_streak=0,
        )


@register_defense("original_fail_stop")
class OriginalFailStopDefense(BaseDefense):
    """Bit-for-bit wrapper around ``security.KinematicMonitor``."""

    def __init__(self, max_alarm_steps: int = 20) -> None:
        self.max_alarm_steps = int(max_alarm_steps)
        super().__init__(max_alarm_steps=self.max_alarm_steps)
        self._monitor: KinematicMonitor | None = None

    def reset(self, context: DefenseContext) -> None:
        self._monitor = KinematicMonitor(
            geometry=context.geometry,
            threshold=context.calibration.threshold_m,
            dt=context.dt,
            max_alarm_steps=self.max_alarm_steps,
        )

    def process(
        self,
        reported_obs: np.ndarray,
        step: int,
        context: DefenseContext,
    ) -> DefenseResult:
        del step
        if self._monitor is None:
            self.reset(context)
        assert self._monitor is not None
        obs = np.array(reported_obs, dtype=float, copy=True)
        corrected, status = self._monitor.process(obs)
        state = (
            "aborted"
            if status["abort"]
            else "correcting"
            if status["alarm"]
            else "normal"
        )
        return DefenseResult(
            policy_obs=np.array(corrected, dtype=float, copy=True),
            alarm=bool(status["alarm"]),
            abort=bool(status["abort"]),
            state=state,
            residual_m=float(status["residual_m"]),
            alarm_streak=int(status["alarm_streak"]),
            metadata={"warmup": bool(status["warmup"])},
        )


@register_defense("grace1")
class Grace1Defense(BaseDefense):
    """Bit-for-bit wrapper around ``recovery_monitor.RecoveryMonitor(grace=1)``."""

    def __init__(self, grace: int = 1) -> None:
        if int(grace) != 1:
            raise ValueError("Grace1Defense requires grace=1")
        self.grace = 1
        super().__init__(grace=1)
        self._monitor: RecoveryMonitor | None = None

    def reset(self, context: DefenseContext) -> None:
        self._monitor = RecoveryMonitor(
            geometry=context.geometry,
            threshold=context.calibration.threshold_m,
            dt=context.dt,
            grace=1,
        )

    def process(
        self,
        reported_obs: np.ndarray,
        step: int,
        context: DefenseContext,
    ) -> DefenseResult:
        del step
        if self._monitor is None:
            self.reset(context)
        assert self._monitor is not None
        obs = np.array(reported_obs, dtype=float, copy=True)
        corrected, status = self._monitor.process(obs)
        return DefenseResult(
            policy_obs=np.array(corrected, dtype=float, copy=True),
            alarm=bool(status["alarm"]),
            abort=bool(status["abort"]),
            state=str(status["state"]),
            residual_m=float(status["residual_m"]),
            alarm_streak=int(status["alarm_streak"]),
            metadata={"warmup": bool(status["warmup"]), "grace": self.grace},
        )
