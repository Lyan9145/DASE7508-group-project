"""Observation-trust-boundary defense registry and built-in defenses."""
from __future__ import annotations

from . import base, fusion_recovery, legacy, policy_level, statistical
from .base import (
    DEFENSE_REGISTRY,
    VALID_DEFENSE_STATES,
    BaseDefense,
    CalibrationStats,
    DefenseContext,
    DefenseResult,
    create_defense,
    list_defenses,
    register_defense,
)
from .fusion_recovery import ContinuousVelocityDefense, IKVelocityFusionDefense
from .legacy import Grace1Defense, NoDefense, OriginalFailStopDefense
from .policy_level import FallbackPolicyDefense
from .statistical import CusumDefense, SlidingWindowDefense

__all__ = [
    "base",
    "legacy",
    "statistical",
    "fusion_recovery",
    "policy_level",
    "VALID_DEFENSE_STATES",
    "CalibrationStats",
    "DefenseContext",
    "DefenseResult",
    "BaseDefense",
    "DEFENSE_REGISTRY",
    "register_defense",
    "create_defense",
    "list_defenses",
    "NoDefense",
    "OriginalFailStopDefense",
    "Grace1Defense",
    "CusumDefense",
    "SlidingWindowDefense",
    "ContinuousVelocityDefense",
    "IKVelocityFusionDefense",
    "FallbackPolicyDefense",
]
