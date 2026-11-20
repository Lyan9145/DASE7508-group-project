"""2-link planar inverse kinematics and elbow-flip helpers for Reacher-v5."""
from __future__ import annotations

import numpy as np

from .security import ArmGeometry, rotation, wrap


def solve_q0_ik(geometry: ArmGeometry, q1: float, measured_tip: np.ndarray) -> float:
    """Solve joint-0 angle given joint-1 angle ``q1`` and target fingertip position."""
    v = geometry.link + rotation(q1) @ geometry.tip
    d = np.asarray(measured_tip, dtype=float) - geometry.origin
    if float(np.linalg.norm(d)) < 1e-12 or float(np.linalg.norm(v)) < 1e-12:
        return 0.0
    return wrap(float(np.arctan2(d[1], d[0]) - np.arctan2(v[1], v[0])))


def solve_2link_ik(
    geometry: ArmGeometry,
    measured_tip: np.ndarray,
) -> list[tuple[float, float]]:
    """Return the two 2-link IK solutions ``[(q0, q1), ...]`` for ``measured_tip``."""
    d = np.asarray(measured_tip, dtype=float) - geometry.origin
    l1 = float(np.linalg.norm(geometry.link))
    l2 = float(np.linalg.norm(geometry.tip))
    phi1 = float(np.arctan2(geometry.link[1], geometry.link[0]))
    phi2 = float(np.arctan2(geometry.tip[1], geometry.tip[0]))
    r = float(np.linalg.norm(d))
    cos_alpha = float(
        np.clip((r * r - l1 * l1 - l2 * l2) / max(2.0 * l1 * l2, 1e-12), -1.0, 1.0)
    )
    alpha = float(np.arccos(cos_alpha))
    solutions: list[tuple[float, float]] = []
    for sign in (1.0, -1.0):
        q1 = wrap(sign * alpha + phi1 - phi2)
        q0 = solve_q0_ik(geometry, q1, measured_tip)
        solutions.append((q0, q1))
    return solutions


def elbow_flip_angles(
    geometry: ArmGeometry,
    q0: float,
    q1: float,
) -> tuple[float, float]:
    """Return the mirror pose ``(q0_alt, q1_alt)`` matching ``geometry.forward(q0, q1)``."""
    tip_pos = geometry.forward(q0, q1)
    phi1 = float(np.arctan2(geometry.link[1], geometry.link[0]))
    phi2 = float(np.arctan2(geometry.tip[1], geometry.tip[0]))
    q1_alt = wrap(2.0 * (phi1 - phi2) - q1)
    q0_alt = solve_q0_ik(geometry, q1_alt, tip_pos)
    return (q0_alt, q1_alt)
