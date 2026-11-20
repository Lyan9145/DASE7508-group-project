"""Legacy attack wrappers delegating to ``security.Attack``."""
from __future__ import annotations

import numpy as np

from core.security import Attack

from .base import AttackContext, AttackResult, BaseAttack, register_attack


class LegacyAttack(BaseAttack):
    """Adapter wrapping ``security.Attack`` with the ``BaseAttack`` interface."""

    name: str = "legacy"
    default_kind: str = "clean"

    def __init__(
        self,
        kind: str | None = None,
        epsilon: float = 0.0,
        duration: int = 5,
        start: int = 20,
        sign: int = 1,
    ) -> None:
        if type(self) is LegacyAttack:
            resolved_kind = self.default_kind if kind is None else str(kind)
        else:
            if kind is not None and str(kind) != self.default_kind:
                raise ValueError(
                    f"{type(self).__name__} fixes kind={self.default_kind!r}, got {kind!r}"
                )
            resolved_kind = self.default_kind

        resolved_epsilon = 0.0 if resolved_kind == "clean" else float(epsilon)
        resolved_duration = int(duration)
        resolved_start = int(start)
        resolved_sign = int(sign)

        super().__init__(
            kind=resolved_kind,
            epsilon=resolved_epsilon,
            duration=resolved_duration,
            start=resolved_start,
            sign=resolved_sign,
        )
        if type(self) is LegacyAttack:
            self.name = resolved_kind
        self.kind: str = resolved_kind
        self.epsilon: float = resolved_epsilon
        self.duration: int = resolved_duration
        self.start: int = resolved_start
        self._attack: Attack = self._build_attack(seed=0, sign=resolved_sign)

    def _build_attack(self, seed: int, sign: int) -> Attack:
        return Attack(
            kind=self.kind,
            epsilon=0.0 if self.kind == "clean" else self.epsilon,
            duration=self.duration,
            start=self.start,
            sign=int(sign),
            random_seed=int(seed) + 20000000,
        )

    def reset(
        self,
        seed: int,
        sign: int = 1,
        context: AttackContext | None = None,
    ) -> None:
        super().reset(seed, sign=sign, context=context)
        self._attack = self._build_attack(seed=self.seed, sign=self.sign)

    def apply(
        self,
        raw_obs: np.ndarray,
        step: int,
        context: AttackContext,
    ) -> AttackResult:
        del context
        raw = np.asarray(raw_obs, dtype=np.float64)
        reported = np.array(self._attack.apply(raw, step), dtype=np.float64, copy=True)
        delta = float(self._attack.delta(step))
        is_active = self.kind != "clean" and (self.start <= step < self.start + self.duration)
        return AttackResult(
            reported_obs=reported,
            is_active=bool(is_active),
            attacked_channels=(0, 2),
            delta_rad=delta,
            metadata={"kind": self.kind},
        )

    def window_bounds(self) -> tuple[int, int] | None:
        if self.kind == "clean":
            return None
        return (self.start, self.duration)


@register_attack("clean")
class CleanAttack(LegacyAttack):
    """Unattacked baseline observation pass-through."""

    default_kind = "clean"


@register_attack("bias")
class BiasAttack(LegacyAttack):
    """Constant joint-0 bias attack within the active window."""

    default_kind = "bias"


@register_attack("ramp")
class RampAttack(LegacyAttack):
    """Linearly ramping joint-0 attack within the active window."""

    default_kind = "ramp"


@register_attack("random_bias")
class RandomBiasAttack(LegacyAttack):
    """Sign-randomized constant-magnitude joint-0 attack."""

    default_kind = "random_bias"


@register_attack("random_ramp")
class RandomRampAttack(LegacyAttack):
    """Sign-randomized ramping-magnitude joint-0 attack."""

    default_kind = "random_ramp"
