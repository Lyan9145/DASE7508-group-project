"""Continuous velocity prediction and IK-velocity fusion recovery defenses."""
from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np

from core.kinematics import solve_2link_ik, solve_q0_ik
from core.security import wrap
from .base import BaseDefense, DefenseContext, DefenseResult, register_defense


def _validate_threshold_factor(value: float) -> float:
    factor = float(value)
    if not np.isfinite(factor) or factor <= 0.0:
        raise ValueError("threshold_factor must be finite and > 0")
    return factor


@register_defense("continuous_velocity")
class ContinuousVelocityDefense(BaseDefense):
    """Continuous velocity-integrated prediction without alarm-streak count abort.

    Flags a step when the kinematic residual exceeds
    ``threshold_factor * calibration.threshold_m`` and dead-reckons joint 0 from
    the reported joint-0 velocity, without the fixed 20-step abort cap of
    ``original_fail_stop``, so sustained late-window attacks keep being corrected.

    ``threshold_factor=1.5`` removes the clean false alarms of the single-step
    p99 threshold (clean residuals are nearly independent across steps, so a p99
    threshold fires in about 1 - 0.99**99 ~ 63% of clean episodes; 1.5x gave 0%
    on the development and holdout blocks) at the cost of about one extra step of
    detection delay on ramps. ``threshold_factor=1.0`` reproduces the former
    detector.

    ``divergence_abort_m`` is the optional safety stop that replaces the step
    cap: it aborts when the *corrected* observation's residual (forward
    kinematics of the dead-reckoned angle versus the measured fingertip) exceeds
    the bound, i.e. when dead-reckoning has drifted away from the independent
    position channel. The reported (spoofed) residual is not used, because it
    measures attack magnitude rather than estimator drift and would abort at the
    onset of every large attack.
    """

    def __init__(
        self,
        divergence_abort_m: float | None = None,
        threshold_factor: float = 1.5,
    ) -> None:
        if divergence_abort_m is not None:
            divergence_abort_m = float(divergence_abort_m)
            if not np.isfinite(divergence_abort_m) or divergence_abort_m <= 0.0:
                raise ValueError("divergence_abort_m must be finite and > 0, or None")
        self.divergence_abort_m = divergence_abort_m
        self.threshold_factor = _validate_threshold_factor(threshold_factor)
        super().__init__(
            divergence_abort_m=self.divergence_abort_m,
            threshold_factor=self.threshold_factor,
        )
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
                metadata={"warmup": True, "corrected_residual_m": residual_m},
            )

        threshold_m = self.threshold_factor * context.calibration.threshold_m
        alarm = bool(residual_m > threshold_m)
        if alarm:
            self._angle = wrap(self._angle + self._prev_vel * context.dt)
            obs[0] = float(np.cos(self._angle))
            obs[2] = float(np.sin(self._angle))
            self._streak += 1
        else:
            self._angle = float(np.arctan2(obs[2], obs[0]))
            self._streak = 0

        self._prev_vel = float(reported_obs[6])
        corrected_residual_m = (
            float(context.geometry.residual(obs)) if alarm else residual_m
        )
        abort = bool(
            alarm
            and self.divergence_abort_m is not None
            and corrected_residual_m > self.divergence_abort_m
        )
        state = "aborted" if abort else "correcting" if alarm else "normal"
        return DefenseResult(
            policy_obs=obs,
            alarm=alarm,
            abort=abort,
            state=state,
            residual_m=residual_m,
            alarm_streak=self._streak,
            metadata={"warmup": False, "corrected_residual_m": corrected_residual_m},
        )


class VelocityConsistencyMonitor:
    """Encoder-increment versus reported joint-velocity consistency check.

    For each joint ``j`` it tracks the per-step mismatch
    ``e_j = wrap(q_j[t] - q_j[t-1]) - dt * (v_j[t] + v_j[t-1]) / 2`` between the
    reported encoder increment and the trapezoidal integral of the reported
    velocity. In clean Reacher-v5 rollouts this is below 1e-4 rad (the
    simulator integrates exactly this way), whereas a velocity bias ``b`` adds
    ``-b * dt`` per step and a time-varying angle offset adds its own increment.

    A joint is flagged when ``|median(e_j over window)| > max(tol_rad,
    z * sigma_ref)``. The median ignores the single-step spike at the onset or
    end of a constant angle offset. ``sigma_ref`` is a robust (MAD) noise scale
    of the *other* joint's mismatch over ``noise_window`` steps, which keeps the
    test quiet under Gaussian velocity noise (Direction 4A ablation) without a
    calibration field; the check stays disabled until ``warmup_steps`` mismatch
    samples exist. ``bias_rad_s`` is the velocity bias implied if the encoder
    increments are honest: ``-median(e_j) / dt``.
    """

    def __init__(
        self,
        window: int = 5,
        noise_window: int = 20,
        z: float = 4.0,
        tol_rad: float = 0.002,
        warmup_steps: int = 8,
    ) -> None:
        self.window = int(window)
        self.noise_window = int(noise_window)
        self.z = float(z)
        self.tol_rad = float(tol_rad)
        self.warmup_steps = int(warmup_steps)
        if self.window < 1 or self.noise_window < 1 or self.warmup_steps < 1:
            raise ValueError("window, noise_window and warmup_steps must be >= 1")
        if not np.isfinite(self.z) or self.z <= 0.0:
            raise ValueError("z must be finite and > 0")
        if not np.isfinite(self.tol_rad) or self.tol_rad <= 0.0:
            raise ValueError("tol_rad must be finite and > 0")
        self._errors = [deque(maxlen=self.window), deque(maxlen=self.window)]
        self._noise = [deque(maxlen=self.noise_window), deque(maxlen=self.noise_window)]
        self._prev_q: np.ndarray | None = None
        self._prev_v: np.ndarray | None = None
        self._samples = 0

    def reset(self, q: np.ndarray, v: np.ndarray) -> None:
        for buf in (*self._errors, *self._noise):
            buf.clear()
        self._prev_q = np.array(q, dtype=np.float64, copy=True)
        self._prev_v = np.array(v, dtype=np.float64, copy=True)
        self._samples = 0

    def update(self, q: np.ndarray, v: np.ndarray, dt: float) -> dict[str, Any]:
        q = np.asarray(q, dtype=np.float64)
        v = np.asarray(v, dtype=np.float64)
        if self._prev_q is None or self._prev_v is None:
            self.reset(q, v)
            return self._empty()
        err = np.array(
            [
                wrap(float(q[j] - self._prev_q[j])) - 0.5 * dt * float(v[j] + self._prev_v[j])
                for j in range(2)
            ]
        )
        self._prev_q = q.copy()
        self._prev_v = v.copy()
        self._samples += 1
        for j in range(2):
            self._errors[j].append(float(err[j]))
            self._noise[j].append(abs(float(err[j])))
        if self._samples < self.warmup_steps:
            return self._empty(err)
        median = np.array([float(np.median(self._errors[j])) for j in range(2)])
        sigma = np.array([1.4826 * float(np.median(self._noise[j])) for j in range(2)])
        # Each joint is judged against the other joint's noise scale, so a
        # biased joint cannot inflate its own tolerance.
        tol = np.maximum(self.tol_rad, self.z * sigma[::-1])
        flagged = np.abs(median) > tol
        return {
            "active": True,
            "error_rad": err,
            "median_rad": median,
            "tol_rad": tol,
            "flagged": flagged,
            "bias_rad_s": -median / dt,
        }

    def _empty(self, err: np.ndarray | None = None) -> dict[str, Any]:
        zeros = np.zeros(2)
        return {
            "active": False,
            "error_rad": zeros if err is None else err,
            "median_rad": zeros,
            "tol_rad": np.full(2, self.tol_rad),
            "flagged": np.zeros(2, dtype=bool),
            "bias_rad_s": zeros,
        }


@register_defense("ik_velocity_fusion")
class IKVelocityFusionDefense(BaseDefense):
    """Residual + joint-jump + velocity-consistency detector with IK/velocity fusion.

    Detection channels (any one raises ``alarm``):

    * kinematic residual above ``threshold_factor * calibration.threshold_m``;
    * step-to-step joint jump against the velocity prediction above
      ``max(jump_factor * q{j}_jump_p999_rad, min_jump_rad)``, which catches
      elbow-flip mirror poses with zero forward-kinematics residual;
    * encoder-increment versus reported-velocity inconsistency
      (``VelocityConsistencyMonitor``), which catches velocity tampering
      (``joint_vel_coupled``) and time-varying angle offsets (ramps,
      threshold-aware ramps) that stay under the residual threshold.

    When the velocity check fires, the defense decides which channel is lying
    by comparing the encoder increment and the integrated velocity over the
    check window against the increment of the joint angle recovered from the
    independent fingertip position (IK). If the velocity is the outlier, the
    estimated bias is removed from the velocity used for prediction *and* from
    the velocity passed to the policy (``velocity_gate=True``). Otherwise the
    encoder is treated as tampered and the angle is corrected like a joint jump.

    On an angle alarm the corrected angle is the circular blend
    ``q_ik + alpha * wrap(q_pred - q_ik)``: ``alpha=0`` trusts the noisy
    position-derived IK angle, ``alpha=1`` pure velocity dead-reckoning.
    """

    def __init__(
        self,
        alpha: float = 0.5,
        jump_factor: float = 2.5,
        min_jump_rad: float = 0.15,
        threshold_factor: float = 1.5,
        velocity_gate: bool = True,
        vel_window: int = 5,
        vel_z: float = 4.0,
        vel_tol_rad: float = 0.002,
    ) -> None:
        self.alpha = float(alpha)
        self.jump_factor = float(jump_factor)
        self.min_jump_rad = float(min_jump_rad)
        self.threshold_factor = _validate_threshold_factor(threshold_factor)
        self.velocity_gate = bool(velocity_gate)
        if not np.isfinite(self.alpha) or not (0.0 <= self.alpha <= 1.0):
            raise ValueError("alpha must be finite and in [0.0, 1.0]")
        if not np.isfinite(self.jump_factor) or self.jump_factor <= 0.0:
            raise ValueError("jump_factor must be finite and > 0")
        if not np.isfinite(self.min_jump_rad) or self.min_jump_rad < 0.0:
            raise ValueError("min_jump_rad must be finite and >= 0")
        self._velocity_monitor = VelocityConsistencyMonitor(
            window=vel_window, z=vel_z, tol_rad=vel_tol_rad
        )
        super().__init__(
            alpha=self.alpha,
            jump_factor=self.jump_factor,
            min_jump_rad=self.min_jump_rad,
            threshold_factor=self.threshold_factor,
            velocity_gate=self.velocity_gate,
            vel_window=self._velocity_monitor.window,
            vel_z=self._velocity_monitor.z,
            vel_tol_rad=self._velocity_monitor.tol_rad,
        )
        self._q0: float | None = None
        self._q1: float | None = None
        self._v0: float | None = None
        self._v1: float | None = None
        self._streak: int = 0
        window = self._velocity_monitor.window + 1
        self._enc_hist: deque[np.ndarray] = deque(maxlen=window)
        self._ik_hist: deque[np.ndarray] = deque(maxlen=window)
        self._vel_hist: deque[np.ndarray] = deque(maxlen=window)

    def reset(self, context: DefenseContext) -> None:
        del context
        self._q0 = None
        self._q1 = None
        self._v0 = None
        self._v1 = None
        self._streak = 0
        self._enc_hist.clear()
        self._ik_hist.clear()
        self._vel_hist.clear()

    @staticmethod
    def _ik_angles(
        context: DefenseContext, q_rep: np.ndarray, measured_tip: np.ndarray
    ) -> np.ndarray:
        """Joint angles implied by the fingertip, on the reported elbow branch."""
        q0_ik = solve_q0_ik(context.geometry, float(q_rep[1]), measured_tip)
        cands = solve_2link_ik(context.geometry, measured_tip)
        q1_ik = min(cands, key=lambda cand: abs(wrap(cand[1] - float(q_rep[1]))))[1]
        return np.array([q0_ik, q1_ik])

    def _velocity_is_outlier(self, dt: float) -> np.ndarray:
        """Per joint: is the integrated velocity farther from IK than the encoder is?"""
        if len(self._enc_hist) < 2:
            return np.zeros(2, dtype=bool)
        enc = np.array(self._enc_hist)
        ik = np.array(self._ik_hist)
        vel = np.array(self._vel_hist)
        d_enc = np.array([wrap(float(enc[-1, j] - enc[0, j])) for j in range(2)])
        d_ik = np.array([wrap(float(ik[-1, j] - ik[0, j])) for j in range(2)])
        d_vel = 0.5 * dt * (vel[1:] + vel[:-1]).sum(axis=0)
        return np.abs(d_vel - d_ik) > np.abs(d_enc - d_ik)

    def process(
        self,
        reported_obs: np.ndarray,
        step: int,
        context: DefenseContext,
    ) -> DefenseResult:
        obs = np.array(reported_obs, dtype=np.float64, copy=True)
        residual_m = float(context.geometry.residual(obs))
        q_rep = np.array(
            [float(np.arctan2(obs[2], obs[0])), float(np.arctan2(obs[3], obs[1]))]
        )
        v_rep = np.array([float(reported_obs[6]), float(reported_obs[7])])
        measured_tip = obs[4:6] + obs[8:10]

        if (
            step == 0
            or self._q0 is None
            or self._q1 is None
            or self._v0 is None
            or self._v1 is None
        ):
            self._q0, self._q1 = float(q_rep[0]), float(q_rep[1])
            self._v0, self._v1 = float(v_rep[0]), float(v_rep[1])
            self._streak = 0
            self._velocity_monitor.reset(q_rep, v_rep)
            self._enc_hist.clear()
            self._ik_hist.clear()
            self._vel_hist.clear()
            self._enc_hist.append(q_rep)
            self._ik_hist.append(self._ik_angles(context, q_rep, measured_tip))
            self._vel_hist.append(v_rep)
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
                    "vel_alarm": False,
                    "vel_gated": False,
                },
            )

        cal = context.calibration
        q0_pred = wrap(self._q0 + self._v0 * context.dt)
        q1_pred = wrap(self._q1 + self._v1 * context.dt)
        q0_rep, q1_rep = float(q_rep[0]), float(q_rep[1])

        q0_thresh = max(self.jump_factor * cal.q0_jump_p999_rad, self.min_jump_rad)
        q1_thresh = max(self.jump_factor * cal.q1_jump_p999_rad, self.min_jump_rad)

        res_alarm = bool(residual_m > self.threshold_factor * cal.threshold_m)
        q0_jump = bool(abs(wrap(q0_rep - q0_pred)) > q0_thresh)
        q1_jump = bool(abs(wrap(q1_rep - q1_pred)) > q1_thresh)

        self._enc_hist.append(q_rep)
        self._ik_hist.append(self._ik_angles(context, q_rep, measured_tip))
        self._vel_hist.append(v_rep)
        consistency = self._velocity_monitor.update(q_rep, v_rep, context.dt)
        vel_flagged = consistency["flagged"] if self.velocity_gate else np.zeros(2, bool)
        vel_alarm = bool(vel_flagged.any())

        # Attribute an inconsistency to the velocity channel only when the
        # position-derived IK increment sides with the encoder. A mirrored elbow
        # (q1 jump) corrupts the IK branch, so velocity gating is skipped then.
        vel_gated = np.zeros(2, dtype=bool)
        if vel_alarm and not q1_jump:
            vel_gated = vel_flagged & self._velocity_is_outlier(context.dt)
        enc_rate_alarm = vel_flagged & ~vel_gated

        v_used = v_rep.copy()
        if vel_gated.any():
            v_used[vel_gated] = v_rep[vel_gated] - consistency["bias_rad_s"][vel_gated]
            obs[6:8] = v_used

        q0_alarm = res_alarm or q0_jump or bool(enc_rate_alarm[0])
        q1_alarm = q1_jump or bool(enc_rate_alarm[1])
        angle_alarm = q0_alarm or q1_alarm
        alarm = bool(angle_alarm or vel_alarm)

        if angle_alarm:
            if not q1_alarm:
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
        else:
            self._q0 = q0_rep
            self._q1 = q1_rep
        self._streak = self._streak + 1 if alarm else 0

        self._v0 = float(v_used[0])
        self._v1 = float(v_used[1])
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
                "vel_alarm": vel_alarm,
                "vel_gated": bool(vel_gated.any()),
                "vel_bias_rad_s": [float(b) for b in consistency["bias_rad_s"]],
            },
        )
