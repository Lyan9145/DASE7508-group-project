"""Policy-level fallback defense switching to a hardened backup policy."""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np
import torch
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor

from .base import BaseDefense, DefenseContext, DefenseResult, register_defense
from .fusion_recovery import ContinuousVelocityDefense, IKVelocityFusionDefense


class MaskedObservationExtractor(BaseFeaturesExtractor):
    """Flatten features extractor that zeroes untrusted observation channels.

    Used as ``policy_kwargs={"features_extractor_class": MaskedObservationExtractor,
    "features_extractor_kwargs": {"masked_indices": [0, 2]}}`` when training a
    fallback SAC policy that must not depend on the joint-0 encoder. Because the
    mask lives inside the saved network, the resulting ``model.zip`` accepts the
    standard 10-dimensional Reacher-v5 observation and can be passed directly to
    ``--fallback-model`` / ``DefenseContext.fallback_policy``; whatever the
    masked channels contain at inference time cannot change its actions.
    """

    def __init__(
        self,
        observation_space: gym.spaces.Box,
        masked_indices: Sequence[int] = (0, 2),
    ) -> None:
        n_features = int(np.prod(observation_space.shape))
        super().__init__(observation_space, features_dim=n_features)
        indices = sorted({int(i) for i in masked_indices})
        if any(i < 0 or i >= n_features for i in indices):
            raise ValueError(f"masked_indices must lie in [0, {n_features})")
        self.masked_indices: tuple[int, ...] = tuple(indices)
        mask = torch.ones(n_features, dtype=torch.float32)
        mask[list(indices)] = 0.0
        self.register_buffer("mask", mask)

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        return torch.flatten(observations, start_dim=1) * self.mask


_FALLBACK_BASE_DEFENSES: tuple[str, ...] = ("continuous_velocity", "ik_velocity_fusion")


@register_defense("fallback_policy")
class FallbackPolicyDefense(BaseDefense):
    """Observation defense that hands control to a fallback policy on sustained alarms.

    A base observation defense (``continuous_velocity`` or
    ``ik_velocity_fusion``) detects and corrects the observation. When its
    ``alarm_streak`` reaches ``switch_streak``, the defense enters
    ``state='fallback'`` and computes ``action_override`` from
    ``context.fallback_policy`` (``--fallback-model``) or a lazy-loaded SAC
    checkpoint at ``fallback_model_path``, fed with the base defense's corrected
    observation. Without ``latch`` it returns to the main policy as soon as the
    streak breaks; with ``latch=True`` it stays in fallback for the rest of the
    episode.

    The intended fallback is a policy trained by ``train_fallback.py`` with the
    joint-0 encoder masked inside the network
    (``MaskedObservationExtractor``), e.g. ``models/sac_seed_1_robust``: once
    the main policy's view of joint 0 is no longer trusted, control passes to a
    policy that cannot be steered through that channel at all.

    Defaults ``base_defense="ik_velocity_fusion"`` and ``switch_streak=10``
    were chosen on the development block (``defenses/DEV_RESULTS.md``): the
    IK-fusion base also triggers on elbow flips and velocity tampering, which
    the former ``continuous_velocity`` base never saw (mean attack-case
    success 0.97 vs 0.76-0.79 with ``sac_seed_1_robust`` or an unmasked
    fallback), and a longer streak keeps the main policy in control unless an
    alarm is sustained. ``latch`` never helped.
    """

    def __init__(
        self,
        switch_streak: int = 10,
        fallback_model_path: str | Path | None = None,
        base_defense: str = "ik_velocity_fusion",
        latch: bool = False,
    ) -> None:
        self.switch_streak = int(switch_streak)
        if self.switch_streak < 1:
            raise ValueError("switch_streak must be >= 1")
        if base_defense not in _FALLBACK_BASE_DEFENSES:
            raise ValueError(
                f"base_defense must be one of {_FALLBACK_BASE_DEFENSES}, got {base_defense!r}"
            )
        self.base_defense = str(base_defense)
        self.latch = bool(latch)
        self.fallback_model_path: str | None = (
            None if fallback_model_path is None else str(fallback_model_path)
        )
        super().__init__(
            switch_streak=self.switch_streak,
            fallback_model_path=self.fallback_model_path,
            base_defense=self.base_defense,
            latch=self.latch,
        )
        self._base: BaseDefense = (
            IKVelocityFusionDefense()
            if self.base_defense == "ik_velocity_fusion"
            else ContinuousVelocityDefense(divergence_abort_m=None)
        )
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
        self._base.reset(context)
        self._fallback_active = False

    def process(
        self,
        reported_obs: np.ndarray,
        step: int,
        context: DefenseContext,
    ) -> DefenseResult:
        base_res = self._base.process(reported_obs, step, context)
        triggered = bool(base_res.alarm_streak >= self.switch_streak)
        self._fallback_active = triggered or (self.latch and self._fallback_active)

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
