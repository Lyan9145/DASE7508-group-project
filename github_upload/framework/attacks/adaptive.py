"""White-box adaptive policy-gradient attacks on observation space."""
from __future__ import annotations

import numpy as np
import torch

from .base import AttackContext, AttackResult, BaseAttack, register_attack


@register_attack("policy_gradient")
class PolicyGradientAttack(BaseAttack):
    """Projected gradient ascent maximizing action divergence on joint-0 angle."""

    def __init__(
        self,
        epsilon: float = 0.5,
        duration: int = 20,
        start: int = 80,
        n_steps: int = 5,
        sign: int = 1,
    ) -> None:
        resolved_epsilon = float(epsilon)
        if not np.isfinite(resolved_epsilon) or resolved_epsilon < 0.0:
            raise ValueError("epsilon must be finite and nonnegative")
        resolved_duration = int(duration)
        resolved_start = int(start)
        resolved_n_steps = int(n_steps)
        resolved_sign = int(sign)
        if (
            resolved_duration < 1
            or resolved_start < 1
            or resolved_n_steps < 1
            or resolved_sign not in (-1, 1)
        ):
            raise ValueError(
                "duration >= 1, start >= 1, n_steps >= 1, and sign in {-1, 1} are required"
            )

        super().__init__(
            epsilon=resolved_epsilon,
            duration=resolved_duration,
            start=resolved_start,
            n_steps=resolved_n_steps,
            sign=resolved_sign,
        )
        self.epsilon: float = resolved_epsilon
        self.duration: int = resolved_duration
        self.start: int = resolved_start
        self.n_steps: int = resolved_n_steps
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

        init_delta = float(
            np.clip(
                float(self._sign) * min(0.05, 0.25 * self.epsilon),
                -self.epsilon,
                self.epsilon,
            )
        )
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
                delta = torch.tensor(
                    init_delta, dtype=dtype, device=device, requires_grad=True
                )

                for _ in range(self.n_steps):
                    adv_obs = base_obs.clone()
                    adv_obs[:, 0] = torch.cos(q0_base + delta)
                    adv_obs[:, 2] = torch.sin(q0_base + delta)
                    adv_action = actor(adv_obs, deterministic=True)
                    loss = ((adv_action - target_action) ** 2).sum()
                    (grad,) = torch.autograd.grad(loss, delta)
                    with torch.no_grad():
                        grad_val = float(grad.item()) if torch.isfinite(grad) else 0.0
                        grad_sign = (
                            1.0 if grad_val > 0.0 else (-1.0 if grad_val < 0.0 else 0.0)
                        )
                        next_delta = float(
                            np.clip(
                                float(delta.item()) + step_size * grad_sign,
                                -self.epsilon,
                                self.epsilon,
                            )
                        )
                        delta = torch.tensor(
                            next_delta, dtype=dtype, device=device, requires_grad=True
                        )

                final_delta = float(delta.item())
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
            metadata={"n_steps": self.n_steps, "init_delta_rad": init_delta},
        )


# TODO (Teammate Task 1): Extend PGD with multi-channel perturbations (joint1 + velocity),
# bidirectional sign restarts, and Lagrangian residual penalties for defense evasion.
