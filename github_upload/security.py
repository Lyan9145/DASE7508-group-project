"""Observation-only attacks and mitigation. No simulator state is accessible here."""
from dataclasses import dataclass

import numpy as np


def wrap(angle):
    return float(np.arctan2(np.sin(angle), np.cos(angle)))


def rotation(angle):
    return np.array([[np.cos(angle), -np.sin(angle)],
                     [np.sin(angle), np.cos(angle)]])


@dataclass
class ArmGeometry:
    origin: np.ndarray
    link: np.ndarray
    tip: np.ndarray

    @classmethod
    def from_model(cls, model):
        # Nominal, static model geometry only; never reads MjData.
        return cls(*(model.body_pos[model.body(name).id, :2].copy()
                     for name in ('body0', 'body1', 'fingertip')))

    def forward(self, q0, q1):
        return self.origin + rotation(q0) @ self.link + rotation(q0 + q1) @ self.tip

    def residual(self, observation):
        angles = np.arctan2(observation[2:4], observation[:2])
        measured_tip = observation[4:6] + observation[8:10]
        return float(np.linalg.norm(self.forward(*angles) - measured_tip))

    def to_dict(self):
        return {k: getattr(self, k).tolist() for k in ('origin', 'link', 'tip')}


@dataclass(frozen=True)
class Attack:
    kind: str = 'clean'
    epsilon: float = 0.0
    duration: int = 5
    start: int = 20
    sign: int = 1
    random_seed: int = 0

    def __post_init__(self):
        if self.kind not in ('clean', 'bias', 'ramp', 'random_bias', 'random_ramp'):
            raise ValueError('Unknown attack kind')
        if self.epsilon < 0 or not np.isfinite(self.epsilon):
            raise ValueError('epsilon must be finite and nonnegative')
        if self.duration < 1 or self.start < 1 or self.sign not in (-1, 1):
            raise ValueError('duration >= 1, start >= 1 and sign in {-1, 1} required')

    def delta(self, step):
        if self.kind == 'clean' or not self.start <= step < self.start + self.duration:
            return 0.0
        offset = step - self.start
        magnitude = self.epsilon
        if self.kind.endswith('ramp'):
            # First attacked observation has epsilon / duration; last has epsilon.
            magnitude *= (offset + 1) / self.duration
        sign = self.sign
        if self.kind.startswith('random_'):
            # Independent signs per observation; reproducible regardless of call order.
            rng = np.random.default_rng(self.random_seed)
            sign = int(rng.choice([-1, 1], size=self.duration)[offset])
        return float(sign * magnitude)

    def apply(self, observation, step):
        reported = observation.copy()
        delta = self.delta(step)
        if delta:
            angle = np.arctan2(observation[2], observation[0]) + delta
            reported[0], reported[2] = np.cos(angle), np.sin(angle)
        return reported


class KinematicMonitor:
    def __init__(self, geometry, threshold, dt, max_alarm_steps=20):
        if not np.isfinite(threshold) or threshold < 0 or dt <= 0:
            raise ValueError('Invalid threshold or control interval')
        self.geometry = geometry
        self.threshold = float(threshold)
        self.dt = float(dt)
        self.max_alarm_steps = max_alarm_steps
        self.reset()

    def reset(self):
        self.angle = None
        self.previous_velocity = None
        self.alarm_streak = 0

    def process(self, reported):
        corrected = reported.copy()
        residual = self.geometry.residual(reported)
        # The threat model starts after reset. Observation 0 initializes the
        # estimator from a known unattacked reading; no past angle exists yet.
        warmup = self.angle is None
        alarm = residual > self.threshold and not warmup
        if alarm:
            self.angle = wrap(self.angle + self.previous_velocity * self.dt)
            corrected[0], corrected[2] = np.cos(self.angle), np.sin(self.angle)
            self.alarm_streak += 1
        else:
            self.angle = float(np.arctan2(reported[2], reported[0]))
            self.alarm_streak = 0
        self.previous_velocity = float(reported[6])
        return corrected, {'residual_m': residual, 'alarm': bool(alarm),
                           'warmup': warmup, 'alarm_streak': self.alarm_streak,
                           'abort': self.alarm_streak > self.max_alarm_steps}
