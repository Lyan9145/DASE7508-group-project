"""Attack interfaces, context/result dataclasses, and registry helpers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

import numpy as np

from core.security import ArmGeometry


def _to_json_value(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(k): _to_json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_value(v) for v in value]
    return value


@dataclass(frozen=True)
class AttackContext:
    """Read-only context passed to observation-space attacks."""

    geometry: ArmGeometry
    dt: float
    calibrated_threshold_m: float | None = None
    policy: Any | None = None


@dataclass
class AttackResult:
    """Output produced by applying an attack to an uncorrupted observation."""

    reported_obs: np.ndarray
    is_active: bool
    attacked_channels: tuple[int, ...] = (0, 2)
    delta_rad: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseAttack(ABC):
    """Abstract base class for observation-only attacks."""

    name: str = ""

    def __init__(self, **params: Any) -> None:
        self.params: dict[str, Any] = dict(params)
        self.seed: int = 0
        self.sign: int = int(self.params.get("sign", 1))

    def reset(
        self,
        seed: int,
        sign: int = 1,
        context: AttackContext | None = None,
    ) -> None:
        del context
        if sign not in (-1, 1):
            raise ValueError("sign must be in {-1, 1}")
        self.seed = int(seed)
        self.sign = int(sign)

    @abstractmethod
    def apply(
        self,
        raw_obs: np.ndarray,
        step: int,
        context: AttackContext,
    ) -> AttackResult:
        """Apply the attack to ``raw_obs`` at episode step ``step``."""

    def window_bounds(self) -> tuple[int, int] | None:
        """Return ``(start, duration)`` if configured in params, else ``None``."""
        start = self.params.get("start")
        duration = self.params.get("duration")
        if start is not None and duration is not None:
            return (int(start), int(duration))
        return None

    def config_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable configuration dictionary."""
        return {"name": self.name, "params": _to_json_value(self.params)}


ATTACK_REGISTRY: dict[str, type[BaseAttack]] = {}
_TAttack = TypeVar("_TAttack", bound=BaseAttack)


def register_attack(name: str) -> Callable[[type[_TAttack]], type[_TAttack]]:
    """Register a ``BaseAttack`` subclass under ``name``."""
    if not isinstance(name, str) or not name:
        raise ValueError("Attack name must be a non-empty string")

    def decorator(cls: type[_TAttack]) -> type[_TAttack]:
        if not issubclass(cls, BaseAttack):
            raise TypeError(f"{cls.__name__} must subclass BaseAttack")
        cls.name = name
        ATTACK_REGISTRY[name] = cls
        return cls

    return decorator


def create_attack(name: str, **params: Any) -> BaseAttack:
    """Instantiate a registered attack by ``name``."""
    if name not in ATTACK_REGISTRY:
        available = ", ".join(sorted(ATTACK_REGISTRY)) or "<none>"
        raise KeyError(f"Unknown attack {name!r}; registered: {available}")
    return ATTACK_REGISTRY[name](**params)


def list_attacks() -> list[str]:
    """Return sorted registered attack names."""
    return sorted(ATTACK_REGISTRY)
