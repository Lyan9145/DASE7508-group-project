"""White-box adaptive policy-gradient attacks on observation space."""
from __future__ import annotations

import numpy as np
import torch

from .base import AttackContext, AttackResult, BaseAttack, register_attack


@register_attack("policy_gradient")
class PolicyGradientAttack(BaseAttack):
    """Multi-start projected ascent on action divergence, with optional residual penalty."""

    def __init__(
        self,
        epsilon: float = 0.5,
        duration: int = 20,
        start: int = 80,
        n_steps: int = 5,
        n_restarts: int = 3,
        residual_weight: float = 0.0,
        sign: int = 1,
    ) -> None:
        resolved_epsilon = float(epsilon)
        if not np.isfinite(resolved_epsilon) or resolved_epsilon < 0.0:
            raise ValueError("epsilon must be finite and nonnegative")
        resolved_duration = int(duration)
        resolved_start = int(start)
        resolved_n_steps = int(n_steps)
        resolved_n_restarts = int(n_restarts)
        resolved_residual_weight = float(residual_weight)
        resolved_sign = int(sign)
        if (
            resolved_duration < 1
            or resolved_start < 1
            or resolved_n_steps < 1
            or resolved_n_restarts < 1
            or resolved_sign not in (-1, 1)
        ):
            raise ValueError(
                "duration >= 1, start >= 1, n_steps >= 1, n_restarts >= 1, and sign in {-1, 1} are required"
            )
        if not np.isfinite(resolved_residual_weight) or resolved_residual_weight < 0.0:
            raise ValueError("residual_weight must be finite and nonnegative")

        super().__init__(
            epsilon=resolved_epsilon,
            duration=resolved_duration,
            start=resolved_start,
            n_steps=resolved_n_steps,
            n_restarts=resolved_n_restarts,
            residual_weight=resolved_residual_weight,
            sign=resolved_sign,
        )
        self.epsilon: float = resolved_epsilon
        self.duration: int = resolved_duration
        self.start: int = resolved_start
        self.n_steps: int = resolved_n_steps
        self.n_restarts: int = resolved_n_restarts
        self.residual_weight: float = resolved_residual_weight
        self._sign: int = resolved_sign

    def reset(
        self,
        seed: int,
        sign: int = 1,
        context: AttackContext | None = None,
    ) -> None:
        super().reset(seed, sign=sign, context=context)
        self._sign = self.sign

    def apply(
        self,
        raw_obs: np.ndarray,
        step: int,
        context: AttackContext,
    ) -> AttackResult:
        raw = np.asarray(raw_obs, dtype=np.float64)
        reported = np.array(raw_obs, dtype=np.float64, copy=True)
        step_idx = int(step)
        is_active = self.start <= step_idx < self.start + self.duration
        if not is_active:
            return AttackResult(
                reported_obs=reported,
                is_active=False,
                attacked_channels=(0, 2),
                delta_rad=0.0,
                metadata={"n_steps": self.n_steps},
            )

        if context.policy is None:
            raise ValueError("PolicyGradientAttack requires context.policy")

        policy_obj = getattr(context.policy, "policy", context.policy)
        actor = getattr(policy_obj, "actor", None)
        if actor is None:
            raise ValueError("PolicyGradientAttack requires context.policy with an actor")

        step_size = self.epsilon / max(self.n_steps, 1) * 1.5
        was_training = actor.training
        prev_req_grads = [param.requires_grad for param in actor.parameters()]

        try:
            actor.eval()
            for param in actor.parameters():
                param.requires_grad_(False)

            first_param = next(actor.parameters(), None)
            device = first_param.device if first_param is not None else torch.device("cpu")
            dtype = first_param.dtype if first_param is not None else torch.float32

            with torch.enable_grad():
                base_obs = torch.as_tensor(raw, dtype=dtype, device=device).unsqueeze(0)
                target_action = actor(base_obs, deterministic=True).detach()
                q0_base = torch.tensor(
                    float(np.arctan2(raw[2], raw[0])), dtype=dtype, device=device
                )
                q1_base = torch.tensor(
                    float(np.arctan2(raw[3], raw[1])), dtype=dtype, device=device
                )
                measured_tip = torch.as_tensor(
                    raw[4:6] + raw[8:10], dtype=dtype, device=device
                )
                geometry = context.geometry
                origin = torch.as_tensor(geometry.origin, dtype=dtype, device=device)
                link = torch.as_tensor(geometry.link, dtype=dtype, device=device)
                tip = torch.as_tensor(geometry.tip, dtype=dtype, device=device)
                threshold = (
                    0.006 if context.calibrated_threshold_m is None
                    else float(context.calibrated_threshold_m)
                )
                if not np.isfinite(threshold) or threshold < 0.0:
                    raise ValueError("calibrated_threshold_m must be finite and nonnegative")
                budget = threshold * 0.85

                def score(delta: torch.Tensor) -> torch.Tensor:
                    adv_obs = base_obs.clone()
                    adv_obs[:, 0] = torch.cos(q0_base + delta)
                    adv_obs[:, 2] = torch.sin(q0_base + delta)
                    adv_action = actor(adv_obs, deterministic=True)
                    value = ((adv_action - target_action) ** 2).sum()
                    if self.residual_weight:
                        a0, a1 = q0_base + delta, q0_base + delta + q1_base
                        predicted_tip = origin + torch.stack(
                            (
                                torch.cos(a0) * link[0] - torch.sin(a0) * link[1]
                                + torch.cos(a1) * tip[0] - torch.sin(a1) * tip[1],
                                torch.sin(a0) * link[0] + torch.cos(a0) * link[1]
                                + torch.sin(a1) * tip[0] + torch.cos(a1) * tip[1],
                            )
                        )
                        excess = torch.relu(
                            torch.linalg.vector_norm(predicted_tip - measured_tip) - budget
                        )
                        value = value - self.residual_weight * (excess / max(budget, 1e-6)) ** 2
                    return value

                small = min(0.05, 0.25 * self.epsilon)
                initial = [
                    self._sign * small,
                    -self._sign * self.epsilon,
                    self._sign * self.epsilon,
                ]
                if self.n_restarts > 3:
                    initial.extend(
                        np.linspace(-self.epsilon, self.epsilon, self.n_restarts - 1)[1:-1]
                    )
                best_score = -float("inf")
                final_delta = 0.0
                for start_delta in initial[:self.n_restarts]:
                    delta = torch.tensor(
                        float(start_delta), dtype=dtype, device=device, requires_grad=True
                    )
                    for iteration in range(self.n_steps + 1):
                        value = score(delta)
                        candidate = float(value.detach().item())
                        if np.isfinite(candidate) and candidate > best_score:
                            best_score = candidate
                            final_delta = float(delta.detach().item())
                        if iteration == self.n_steps:
                            break
                        (grad,) = torch.autograd.grad(value, delta)
                        with torch.no_grad():
                            grad_val = float(grad.item()) if torch.isfinite(grad) else 0.0
                            next_delta = float(
                                np.clip(
                                    float(delta.item()) + step_size * np.sign(grad_val),
                                    -self.epsilon,
                                    self.epsilon,
                                )
                            )
                            delta = torch.tensor(
                                next_delta, dtype=dtype, device=device, requires_grad=True
                            )
        finally:
            for param, prev_grad in zip(actor.parameters(), prev_req_grads):
                param.requires_grad_(prev_grad)
            actor.train(was_training)

        if final_delta != 0.0:
            q0_adv = float(np.arctan2(raw[2], raw[0])) + final_delta
            reported[0] = float(np.cos(q0_adv))
            reported[2] = float(np.sin(q0_adv))

        return AttackResult(
            reported_obs=reported,
            is_active=True,
            attacked_channels=(0, 2),
            delta_rad=final_delta,
            metadata={
                "n_steps": self.n_steps,
                "n_restarts": self.n_restarts,
                "residual_weight": self.residual_weight,
            },
        )
