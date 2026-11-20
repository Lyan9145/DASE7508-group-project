"""Policy-level fallback defense switching to a hardened backup policy."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .base import BaseDefense, DefenseContext, DefenseResult, register_defense
from .fusion_recovery import ContinuousVelocityDefense


@register_defense("fallback_policy")
class FallbackPolicyDefense(BaseDefense):
    """Continuous velocity defense that switches to a fallback policy on sustained alarms.

    Runs the single-step residual check and joint-0 velocity integration on
    channels ``(0, 2)`` (without count-based abort). When ``alarm_streak`` reaches
    ``switch_streak``, enters ``state='fallback'`` and computes ``action_override``
    from ``context.fallback_policy`` or a lazy-loaded SAC checkpoint at
    ``fallback_model_path``. Recovers back to ``'normal'`` once the sensor
    residual returns within threshold.
    """

    def __init__(
        self,
        switch_streak: int = 5,
        fallback_model_path: str | Path | None = None,
    ) -> None:
        self.switch_streak = int(switch_streak)
        if self.switch_streak < 1:
            raise ValueError("switch_streak must be >= 1")
        self.fallback_model_path: str | None = (
            None if fallback_model_path is None else str(fallback_model_path)
        )
        super().__init__(
            switch_streak=self.switch_streak,
            fallback_model_path=self.fallback_model_path,
        )
        self._velocity_defense = ContinuousVelocityDefense(divergence_abort_m=None)
        self._fallback_active: bool = False
        self._cached_fallback_policy: Any | None = None
        self._cached_fallback_path: str | None = None

    def _resolve_fallback_policy(self, context: DefenseContext) -> Any | None:
        if context.fallback_policy is not None:
            return context.fallback_policy
        if self.fallback_model_path is None:
            return None
        if (
            self._cached_fallback_policy is None
            or self._cached_fallback_path != self.fallback_model_path
        ):
            from stable_baselines3 import SAC

            self._cached_fallback_policy = SAC.load(
                self.fallback_model_path, device="cpu"
            )
            self._cached_fallback_path = self.fallback_model_path
        return self._cached_fallback_policy

    def reset(self, context: DefenseContext) -> None:
        self._velocity_defense.reset(context)
        self._fallback_active = False

    def process(
        self,
        reported_obs: np.ndarray,
        step: int,
        context: DefenseContext,
    ) -> DefenseResult:
        base_res = self._velocity_defense.process(reported_obs, step, context)
        self._fallback_active = bool(base_res.alarm_streak >= self.switch_streak)

        action_override: np.ndarray | None = None
        if self._fallback_active:
            state = "fallback"
            fb = self._resolve_fallback_policy(context)
            if fb is not None:
                raw_action = fb.predict(base_res.policy_obs, deterministic=True)[0]
                action_override = np.asarray(raw_action, dtype=np.float64)
        else:
            state = base_res.state

        return DefenseResult(
            policy_obs=base_res.policy_obs,
            alarm=base_res.alarm,
            abort=False,
            state=state,
            residual_m=base_res.residual_m,
            alarm_streak=base_res.alarm_streak,
            action_override=action_override,
            metadata={
                **base_res.metadata,
                "fallback_active": self._fallback_active,
                "fallback_override": action_override is not None,
            },
        )

    # TODO (Teammate Task 2): Train a hardened fallback SAC policy (e.g., adversarially
    # trained under joint0 spoofing or trained with `mask_angles` / velocity+fingertip
    # observations via a gym observation wrapper) and pass its `.zip` path through
    # `fallback_model_path` or `DefenseContext.fallback_policy` / `--fallback-model`.
    # Optionally test a sticky latch (`self._fallback_active |= ...`) for the rest of
    # the episode vs the current recoverable switch when `alarm_streak < switch_streak`.
