"""Continuous velocity prediction and IK-velocity fusion recovery defenses."""
from __future__ import annotations

import numpy as np

from core.kinematics import solve_2link_ik, solve_q0_ik
from core.security import wrap
from .base import BaseDefense, DefenseContext, DefenseResult, register_defense


@register_defense("continuous_velocity")
class ContinuousVelocityDefense(BaseDefense):
    """Continuous velocity-integrated prediction without alarm-streak count abort.

    Uses the same single-step kinematic residual threshold and joint-0 velocity
    dead-reckoning as ``original_fail_stop``, while removing the fixed 20-step
    abort cap so sustained late-window attacks can continue being corrected.
    """

    def __init__(self, divergence_abort_m: float | None = None) -> None:
        if divergence_abort_m is not None:
            divergence_abort_m = float(divergence_abort_m)
            if not np.isfinite(divergence_abort_m) or divergence_abort_m <= 0.0:
                raise ValueError("divergence_abort_m must be finite and > 0, or None")
        self.divergence_abort_m = divergence_abort_m
        super().__init__(divergence_abort_m=self.divergence_abort_m)
        self._angle: float | None = None
        self._prev_vel: float | None = None
        self._streak: int = 0

    def reset(self, context: DefenseContext) -> None:
        del context
        self._angle = None
        self._prev_vel = None
        self._streak = 0

    def process(
        self,
        reported_obs: np.ndarray,
        step: int,
        context: DefenseContext,
    ) -> DefenseResult:
        obs = np.array(reported_obs, dtype=np.float64, copy=True)
        residual_m = float(context.geometry.residual(obs))

        if step == 0 or self._angle is None or self._prev_vel is None:
            self._angle = float(np.arctan2(obs[2], obs[0]))
            self._prev_vel = float(reported_obs[6])
            self._streak = 0
            return DefenseResult(
                policy_obs=obs,
                alarm=False,
                abort=False,
                state="normal",
                residual_m=residual_m,
                alarm_streak=0,
                metadata={"warmup": True},
            )

        alarm = bool(residual_m > context.calibration.threshold_m)
        if alarm:
            self._angle = wrap(self._angle + self._prev_vel * context.dt)
            obs[0] = float(np.cos(self._angle))
            obs[2] = float(np.sin(self._angle))
            self._streak += 1
        else:
            self._angle = float(np.arctan2(obs[2], obs[0]))
            self._streak = 0

        self._prev_vel = float(reported_obs[6])
        abort = bool(
            self.divergence_abort_m is not None
            and residual_m > self.divergence_abort_m
        )
        state = "aborted" if abort else "correcting" if alarm else "normal"
        return DefenseResult(
            policy_obs=obs,
            alarm=alarm,
            abort=abort,
            state=state,
            residual_m=residual_m,
            alarm_streak=self._streak,
            metadata={"warmup": False},
        )

    # TODO (Teammate Task 2): Evaluate safe `divergence_abort_m` bounds and compare
    # drift under `vel_sigma > 0` or `joint_vel_coupled` attacks against `ik_velocity_fusion`.


@register_defense("ik_velocity_fusion")
class IKVelocityFusionDefense(BaseDefense):
    """Residual + temporal-jump detector with 1-link / 2-link IK + velocity fusion.

    Combines kinematic residual checking with step-to-step angular jump checks on
    both joints so mirror/elbow-flip attacks (zero forward-kinematics residual) are
    also detected. On alarm, fuses inverse kinematics from the observed fingertip
    position with velocity-predicted joint angles using circular blending ``alpha``.
    """

    def __init__(
        self,
        alpha: float = 0.5,
        jump_factor: float = 2.5,
        min_jump_rad: float = 0.15,
    ) -> None:
        self.alpha = float(alpha)
        self.jump_factor = float(jump_factor)
        self.min_jump_rad = float(min_jump_rad)
        if not np.isfinite(self.alpha) or not (0.0 <= self.alpha <= 1.0):
            raise ValueError("alpha must be finite and in [0.0, 1.0]")
        if not np.isfinite(self.jump_factor) or self.jump_factor <= 0.0:
            raise ValueError("jump_factor must be finite and > 0")
        if not np.isfinite(self.min_jump_rad) or self.min_jump_rad < 0.0:
            raise ValueError("min_jump_rad must be finite and >= 0")
        super().__init__(
            alpha=self.alpha,
            jump_factor=self.jump_factor,
            min_jump_rad=self.min_jump_rad,
        )
        self._q0: float | None = None
        self._q1: float | None = None
        self._v0: float | None = None
        self._v1: float | None = None
        self._streak: int = 0

    def reset(self, context: DefenseContext) -> None:
        del context
        self._q0 = None
        self._q1 = None
        self._v0 = None
        self._v1 = None
        self._streak = 0

    def process(
        self,
        reported_obs: np.ndarray,
        step: int,
        context: DefenseContext,
    ) -> DefenseResult:
        obs = np.array(reported_obs, dtype=np.float64, copy=True)
        residual_m = float(context.geometry.residual(obs))

        if (
            step == 0
            or self._q0 is None
            or self._q1 is None
            or self._v0 is None
            or self._v1 is None
        ):
            self._q0 = float(np.arctan2(obs[2], obs[0]))
            self._q1 = float(np.arctan2(obs[3], obs[1]))
            self._v0 = float(reported_obs[6])
            self._v1 = float(reported_obs[7])
            self._streak = 0
            return DefenseResult(
                policy_obs=obs,
                alarm=False,
                abort=False,
                state="normal",
                residual_m=residual_m,
                alarm_streak=0,
                metadata={
                    "warmup": True,
                    "res_alarm": False,
                    "q0_jump": False,
                    "q1_jump": False,
                },
            )

        cal = context.calibration
        q0_pred = wrap(self._q0 + self._v0 * context.dt)
        q1_pred = wrap(self._q1 + self._v1 * context.dt)
        q0_rep = float(np.arctan2(obs[2], obs[0]))
        q1_rep = float(np.arctan2(obs[3], obs[1]))

        q0_thresh = max(self.jump_factor * cal.q0_jump_p999_rad, self.min_jump_rad)
        q1_thresh = max(self.jump_factor * cal.q1_jump_p999_rad, self.min_jump_rad)

        res_alarm = bool(residual_m > cal.threshold_m)
        q0_jump = bool(abs(wrap(q0_rep - q0_pred)) > q0_thresh)
        q1_jump = bool(abs(wrap(q1_rep - q1_pred)) > q1_thresh)
        alarm = bool(res_alarm or q0_jump or q1_jump)

        measured_tip = obs[4:6] + obs[8:10]
        if alarm:
            if not q1_jump:
                q0_ik = solve_q0_ik(context.geometry, q1_rep, measured_tip)
                q0_fused = wrap(q0_ik + self.alpha * wrap(q0_pred - q0_ik))
                q1_fused = q1_rep
                obs[0] = float(np.cos(q0_fused))
                obs[2] = float(np.sin(q0_fused))
            else:
                cands = solve_2link_ik(context.geometry, measured_tip)
                q0_ik, q1_ik = min(
                    cands,
                    key=lambda cand: (
                        wrap(cand[0] - q0_pred) ** 2 + wrap(cand[1] - q1_pred) ** 2
                    ),
                )
                q0_fused = wrap(q0_ik + self.alpha * wrap(q0_pred - q0_ik))
                q1_fused = wrap(q1_ik + self.alpha * wrap(q1_pred - q1_ik))
                obs[0] = float(np.cos(q0_fused))
                obs[1] = float(np.cos(q1_fused))
                obs[2] = float(np.sin(q0_fused))
                obs[3] = float(np.sin(q1_fused))
            self._q0 = q0_fused
            self._q1 = q1_fused
            self._streak += 1
        else:
            self._q0 = q0_rep
            self._q1 = q1_rep
            self._streak = 0

        self._v0 = float(reported_obs[6])
        self._v1 = float(reported_obs[7])
        return DefenseResult(
            policy_obs=obs,
            alarm=alarm,
            abort=False,
            state="correcting" if alarm else "normal",
            residual_m=residual_m,
            alarm_streak=self._streak,
            metadata={
                "warmup": False,
                "res_alarm": res_alarm,
                "q0_jump": q0_jump,
                "q1_jump": q1_jump,
            },
        )

    # TODO (Teammate Task 2): Tune `alpha` dynamically based on velocity/position noise
    # levels (smaller `alpha` when `vel_sigma` is large; larger `alpha` when `pos_sigma`
    # is large) and gate suspicious `reported_obs[6:8]` updates during `joint_vel_coupled`.
