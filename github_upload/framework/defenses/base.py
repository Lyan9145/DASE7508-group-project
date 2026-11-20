"""Defense interfaces, calibration/context/result dataclasses, and registry."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, TypeVar

import numpy as np

from framework.core.security import ArmGeometry


VALID_DEFENSE_STATES: tuple[str, ...] = (
    "normal",
    "correcting",
    "recovery_pending",
    "fallback",
    "aborted",
)


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
class CalibrationStats:
    """Clean-rollout residual and joint-jump statistics for defense calibration."""

    threshold_m: float
    residual_mean_m: float
    residual_std_m: float
    residual_p95_m: float
    residual_p99_m: float
    q0_jump_p99_rad: float
    q0_jump_p999_rad: float
    q1_jump_p99_rad: float
    q1_jump_p999_rad: float
    control_dt_seconds: float
    episodes: int
    seed_base: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize calibration statistics to plain JSON-compatible primitives."""
        return {
            "threshold_m": float(self.threshold_m),
            "residual_mean_m": float(self.residual_mean_m),
            "residual_std_m": float(self.residual_std_m),
            "residual_p95_m": float(self.residual_p95_m),
            "residual_p99_m": float(self.residual_p99_m),
            "q0_jump_p99_rad": float(self.q0_jump_p99_rad),
            "q0_jump_p999_rad": float(self.q0_jump_p999_rad),
            "q1_jump_p99_rad": float(self.q1_jump_p99_rad),
            "q1_jump_p999_rad": float(self.q1_jump_p999_rad),
            "control_dt_seconds": float(self.control_dt_seconds),
            "episodes": int(self.episodes),
            "seed_base": int(self.seed_base),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CalibrationStats:
        """Deserialize calibration statistics from a mapping."""
        return cls(
            threshold_m=float(data["threshold_m"]),
            residual_mean_m=float(data["residual_mean_m"]),
            residual_std_m=float(data["residual_std_m"]),
            residual_p95_m=float(data["residual_p95_m"]),
            residual_p99_m=float(data["residual_p99_m"]),
            q0_jump_p99_rad=float(data["q0_jump_p99_rad"]),
            q0_jump_p999_rad=float(data["q0_jump_p999_rad"]),
            q1_jump_p99_rad=float(data["q1_jump_p99_rad"]),
            q1_jump_p999_rad=float(data["q1_jump_p999_rad"]),
            control_dt_seconds=float(data["control_dt_seconds"]),
            episodes=int(data["episodes"]),
            seed_base=int(data["seed_base"]),
        )


@dataclass(frozen=True)
class DefenseContext:
    """Read-only context passed to observation-space defenses."""

    geometry: ArmGeometry
    dt: float
    calibration: CalibrationStats
    fallback_policy: Any | None = None


@dataclass
class DefenseResult:
    """Output produced by processing a reported observation through a defense.

    ``state`` is one of ``'normal' | 'correcting' | 'recovery_pending' | 'fallback' | 'aborted'``.
    """

    policy_obs: np.ndarray
    alarm: bool
    abort: bool
    state: str
    residual_m: float
    alarm_streak: int = 0
    action_override: np.ndarray | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseDefense(ABC):
    """Abstract base class for observation-trust-boundary defenses."""

    name: str = ""

    def __init__(self, **params: Any) -> None:
        self.params: dict[str, Any] = dict(params)

    def reset(self, context: DefenseContext) -> None:
        del context

    @abstractmethod
    def process(
        self,
        reported_obs: np.ndarray,
        step: int,
        context: DefenseContext,
    ) -> DefenseResult:
        """Process ``reported_obs`` at episode step ``step``."""

    def config_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable configuration dictionary."""
        return {"name": self.name, "params": _to_json_value(self.params)}


DEFENSE_REGISTRY: dict[str, type[BaseDefense]] = {}
_TDefense = TypeVar("_TDefense", bound=BaseDefense)


def register_defense(name: str) -> Callable[[type[_TDefense]], type[_TDefense]]:
    """Register a ``BaseDefense`` subclass under ``name``."""
    if not isinstance(name, str) or not name:
        raise ValueError("Defense name must be a non-empty string")

    def decorator(cls: type[_TDefense]) -> type[_TDefense]:
        if not issubclass(cls, BaseDefense):
            raise TypeError(f"{cls.__name__} must subclass BaseDefense")
        cls.name = name
        DEFENSE_REGISTRY[name] = cls
        return cls

    return decorator


def create_defense(name: str, **params: Any) -> BaseDefense:
    """Instantiate a registered defense by ``name``."""
    if name not in DEFENSE_REGISTRY:
        available = ", ".join(sorted(DEFENSE_REGISTRY)) or "<none>"
        raise KeyError(f"Unknown defense {name!r}; registered: {available}")
    return DEFENSE_REGISTRY[name](**params)


def list_defenses() -> list[str]:
    """Return sorted registered defense names."""
    return sorted(DEFENSE_REGISTRY)
