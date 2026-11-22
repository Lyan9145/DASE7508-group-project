"""Exploratory bounded recovery confirmation; same observation trust boundary."""
from .security import KinematicMonitor


class RecoveryMonitor(KinematicMonitor):
    def __init__(self, geometry, threshold, dt, grace=1):
        if grace not in (1, 3):
            raise ValueError('Predeclared grace candidates are 1 or 3')
        self.grace = grace
        super().__init__(geometry, threshold, dt)

    def process(self, reported):
        corrected, status = super().process(reported)
        # Same alarm/correction. Enter pending on alarm 21; a clean sample resets
        # immediately. Continued anomalies abort at 21+grace, never disabled.
        status['abort'] = self.alarm_streak > 20 + self.grace
        status['state'] = ('aborted' if status['abort'] else
                           'recovery_pending' if self.alarm_streak > 20 else
                           'correcting' if status['alarm'] else 'normal')
        return corrected, status
