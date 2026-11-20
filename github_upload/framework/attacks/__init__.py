"""Attack plugin registry and built-in observation-spoofing implementations."""
from __future__ import annotations

from . import adaptive, base, legacy, magnitude_timing, stealthy
from .adaptive import PolicyGradientAttack
from .base import (
    ATTACK_REGISTRY,
    AttackContext,
    AttackResult,
    BaseAttack,
    create_attack,
    list_attacks,
    register_attack,
)
from .legacy import (
    BiasAttack,
    CleanAttack,
    LegacyAttack,
    RampAttack,
    RandomBiasAttack,
    RandomRampAttack,
)
from .magnitude_timing import FreezeAttack, ReplayAttack, SinusoidalAttack
from .stealthy import (
    ElbowFlipAttack,
    JointVelocityCoupledAttack,
    ThresholdAwareRampAttack,
)

__all__ = [
    "adaptive",
    "base",
    "legacy",
    "magnitude_timing",
    "stealthy",
    "ATTACK_REGISTRY",
    "AttackContext",
    "AttackResult",
    "BaseAttack",
    "register_attack",
    "create_attack",
    "list_attacks",
    "LegacyAttack",
    "CleanAttack",
    "BiasAttack",
    "RampAttack",
    "RandomBiasAttack",
    "RandomRampAttack",
    "SinusoidalAttack",
    "FreezeAttack",
    "ReplayAttack",
    "ThresholdAwareRampAttack",
    "ElbowFlipAttack",
    "JointVelocityCoupledAttack",
    "PolicyGradientAttack",
]
