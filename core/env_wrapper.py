"""Non-breaking Gymnasium wrapper for velocity noise and fingertip ablation."""
from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np

from .reacher_env import make_env


def _validate_vel_sigma(vel_sigma: float) -> float:
    sigma = float(vel_sigma)
    if not np.isfinite(sigma) or sigma < 0.0:
        raise ValueError("vel_sigma must be finite and nonnegative")
    return sigma


class AblationNoiseWrapper(gym.Wrapper):
    """Add independent Gaussian velocity noise and optional fingertip-rel masking."""

    def __init__(
        self,
        env: gym.Env,
        vel_sigma: float = 0.0,
        vel_noise_seed: int = 0,
        mask_fingertip_rel: bool = False,
    ) -> None:
        super().__init__(env)
        self.vel_sigma = _validate_vel_sigma(vel_sigma)
        self.vel_noise_seed = int(vel_noise_seed)
        self.vel_rng = np.random.default_rng(self.vel_noise_seed)
        self.mask_fingertip_rel = bool(mask_fingertip_rel)

    def _apply_ablation(self, observation: np.ndarray) -> np.ndarray:
        result = np.array(observation, dtype=np.float64, copy=True)
        if self.vel_sigma > 0.0:
            result[6:8] += self.vel_rng.normal(0.0, self.vel_sigma, 2)
        if self.mask_fingertip_rel:
            result[8:10] = 0.0
        return result

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        opts = dict(options) if options is not None else None
        if opts is not None:
            vel_noise_seed = opts.pop("vel_noise_seed", None)
            if vel_noise_seed is not None:
                self.vel_rng = np.random.default_rng(int(vel_noise_seed))
            elif opts.get("noise_seed") is not None:
                self.vel_rng = np.random.default_rng(int(opts["noise_seed"]) + 50000000)
        obs, info = self.env.reset(seed=seed, options=opts)
        return self._apply_ablation(obs), info

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        obs, reward, terminated, truncated, info = self.env.step(action)
        return self._apply_ablation(obs), reward, terminated, truncated, info


def make_ablation_env(
    seed: int = 0,
    pos_sigma: float = 0.002,
    vel_sigma: float = 0.0,
    mask_fingertip_rel: bool = False,
    render_mode: str | None = None,
    synchronized: bool = True,
) -> gym.Env:
    """Create a synchronized Reacher-v5 env wrapped with ``AblationNoiseWrapper``."""
    _validate_vel_sigma(vel_sigma)
    base_env = make_env(
        seed=seed,
        noise_sigma=pos_sigma,
        render_mode=render_mode,
        synchronized=synchronized,
    )
    try:
        return AblationNoiseWrapper(
            base_env,
            vel_sigma=vel_sigma,
            vel_noise_seed=int(seed) + 50000000,
            mask_fingertip_rel=mask_fingertip_rel,
        )
    except Exception:
        base_env.close()
        raise
