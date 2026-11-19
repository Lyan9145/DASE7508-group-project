"""Behavior checks for experimental validity and the sensor trust boundary."""
import numpy as np
import pytest
from pathlib import Path
import subprocess
import sys

from reacher_env import make_env
from security import ArmGeometry, Attack, KinematicMonitor, wrap


def observation(geometry, q0=0.4, q1=-0.5, velocity=0.1):
    target = np.array([0.1, -0.02])
    return np.r_[np.cos([q0, q1]), np.sin([q0, q1]), target,
                 [velocity, 0.0], geometry.forward(q0, q1) - target]


@pytest.fixture
def geometry():
    env = make_env()
    result = ArmGeometry.from_model(env.unwrapped.model)
    env.close()
    return result


def test_attack_changes_only_joint0_and_respects_window(geometry):
    original = observation(geometry)
    attack = Attack('bias', 0.1, 5, 20, -1)
    for step in range(100):
        reported = attack.apply(original, step)
        np.testing.assert_array_equal(reported[[1, 3, 4, 5, 6, 7, 8, 9]],
                                      original[[1, 3, 4, 5, 6, 7, 8, 9]])
        expected = -0.1 if 20 <= step < 25 else 0.0
        assert wrap(np.arctan2(reported[2], reported[0]) - 0.4) == pytest.approx(expected)
        assert reported[0]**2 + reported[2]**2 == pytest.approx(1.0)
    np.testing.assert_array_equal(original, observation(geometry))


def test_ramp_and_random_control_have_matched_amplitudes():
    ramp = Attack('ramp', 0.1, 20)
    control = Attack('random_ramp', 0.1, 20, random_seed=91)
    values = [control.delta(t) for t in range(20, 40)]
    assert ramp.delta(20) == pytest.approx(0.005)
    assert ramp.delta(39) == pytest.approx(0.1)
    assert ramp.delta(40) == 0
    assert any(x > 0 for x in values) and any(x < 0 for x in values)
    for t in reversed(range(20, 40)):
        assert abs(control.delta(t)) == pytest.approx(abs(ramp.delta(t)))
        assert control.delta(t) == values[t-20]


def test_monitor_uses_previous_velocity_and_only_corrects_joint0(geometry):
    monitor = KinematicMonitor(geometry, threshold=0.001, dt=0.02)
    clean = observation(geometry, q0=0.4, velocity=0.7)
    _, status = monitor.process(clean)
    assert status['warmup'] and not status['alarm']
    physical = observation(geometry, q0=0.414, velocity=-0.9)
    reported = Attack('bias', 0.1).apply(physical, 20)
    corrected, status = monitor.process(reported)
    assert status['alarm']
    assert np.arctan2(corrected[2], corrected[0]) == pytest.approx(0.414)
    np.testing.assert_array_equal(corrected[[1, 3, 4, 5, 6, 7, 8, 9]],
                                  reported[[1, 3, 4, 5, 6, 7, 8, 9]])
    _, status = monitor.process(physical)
    assert not status['alarm'] and status['alarm_streak'] == 0


def test_abort_only_after_twenty_consecutive_alarms(geometry):
    monitor = KinematicMonitor(geometry, threshold=0.001, dt=0.02)
    clean = observation(geometry, velocity=0)
    monitor.process(clean)
    reported = Attack('bias', 0.1).apply(clean, 20)
    for count in range(1, 22):
        _, status = monitor.process(reported)
        assert status['alarm_streak'] == count
        assert status['abort'] == (count > 20)


def test_sampling_is_synchronized_without_changing_simulation_state(geometry):
    env = make_env(noise_sigma=0)
    reference = make_env(noise_sigma=0, synchronized=False)
    try:
        obs, _ = env.reset(seed=123)
        reference.reset(seed=123)
        rng = np.random.default_rng(8)
        for _ in range(100):
            assert geometry.residual(obs) < 1e-10
            action = rng.uniform(-1, 1, 2)
            obs, _, _, _, info = env.step(action)
            reference.step(action)
            np.testing.assert_array_equal(env.unwrapped.data.qpos, reference.unwrapped.data.qpos)
            np.testing.assert_array_equal(env.unwrapped.data.qvel, reference.unwrapped.data.qvel)
            np.testing.assert_allclose(obs[8:10] + obs[4:6], info['truth']['fingertip'], atol=1e-12)
    finally:
        env.close(); reference.close()


def test_noise_advances_by_default_and_can_be_explicitly_replayed():
    env = make_env(seed=4)
    try:
        a, _ = env.reset(seed=11)
        b, _ = env.reset(seed=11)
        np.testing.assert_array_equal(a[:8], b[:8])
        assert not np.array_equal(a[8:10], b[8:10])
        sequences = []
        for _ in range(2):
            obs, _ = env.reset(seed=11, options={'noise_seed': 22})
            sequence = [obs]
            for _ in range(10):
                obs, _, _, _, _ = env.step(np.array([0.2, -0.1]))
                sequence.append(obs)
            sequences.append(sequence)
        np.testing.assert_array_equal(sequences[0], sequences[1])
    finally:
        env.close()


def test_summary_keeps_same_clean_success_denominator():
    from evaluate import summarize
    common = dict(attack_kind='bias', final_10_mean_distance_m=0.01,
                  terminal_distance_m=0.01, window_complete=True,
                  window_mean_distance_m=0.02, window_max_distance_m=0.03,
                  control_effort=1.0, aborted=False, alarm_count=0, detection_steps=99,
                  any_alarm=False, detection_delay_steps=None, missed_detection=False,
                  recovery_steps=None, monitor_total_ns=0, monitor_calls=0)
    rows = []
    for seed, clean_success in [(1, True), (2, False)]:
        rows.append(dict(common, policy='p', case='clean', monitor_on=False,
                         seed=seed, task_success=clean_success, attack_kind='clean'))
        for defense in (False, True):
            rows.append(dict(common, policy='p', case='bias', monitor_on=defense,
                             seed=seed, task_success=defense))
    groups = summarize(rows)
    attacked = [r for r in groups if r['case'] == 'bias']
    assert all(r['clean_success_denominator'] == 1 for r in attacked)
    assert {r['monitor_on']: r['attack_success_rate'] for r in attacked} == {False: 1.0, True: 0.0}


def test_metric_timing_does_not_count_clean_or_pre_attack_alarms_as_detection(geometry):
    from evaluate import trial, recovery_time
    class Policy:
        def predict(self, obs, deterministic):
            return np.zeros(2), None
    class FixedEnvironment:
        dt = 0.02
        def __init__(self, spike):
            self.unwrapped = self
            self.spike = spike
        def sample(self):
            obs = observation(geometry, velocity=0)
            if self.t == self.spike:
                obs[8] += 0.02
            return obs
        def reset(self, **kwargs):
            self.t = 0
            return self.sample(), {'truth': {'distance': 0.01}}
        def step(self, action):
            self.t += 1
            return self.sample(), 0.0, False, self.t == 100, {'truth': {'distance': 0.01}}
    clean = trial(Policy(), FixedEnvironment(20), geometry, 0.001, Attack(), True,
                  1, None, 'policy', 'clean')
    assert clean['alarm_count'] == 1 and clean['detection_delay_steps'] is None
    assert clean['task_success'] and clean['steps'] == 100
    attacked = trial(Policy(), FixedEnvironment(19), geometry, 0.001,
                     Attack('bias', 0.00001), True, 1, None, 'policy', 'small_bias')
    assert attacked['alarm_count'] == 1
    assert attacked['missed_detection'] and attacked['detection_delay_steps'] is None
    distances = [0.1]*31
    distances[26:31] = [0.02]*5
    assert recovery_time(distances, Attack('bias', 0.1, 5, 20)) == 1


@pytest.mark.parametrize('script',['train.py','evaluate.py'])
def test_cli_protects_existing_results(tmp_path,script):
    output=tmp_path/'existing'; output.mkdir()
    sentinel=output/'keep.txt'; sentinel.write_text('preserve')
    root=Path(__file__).resolve().parent
    command=[sys.executable,str(root/script),'--out',str(output)]
    if script=='evaluate.py':
        command+=['--models',str(root/'outputs/sac_seed_1/model.zip')]
    result=subprocess.run(command,capture_output=True,text=True)
    assert result.returncode==2 and 'exists' in result.stderr.lower()
    assert sentinel.read_text()=='preserve'
    assert list(output.iterdir())==[sentinel]


def test_main_requires_frozen_plan_before_any_output(tmp_path):
    root=Path(__file__).resolve().parent
    output=tmp_path/'not_created'
    result=subprocess.run([sys.executable,str(root/'evaluate.py'),'--phase','main',
                           '--models',str(root/'outputs/sac_seed_1/model.zip'),
                           '--out',str(output)],capture_output=True,text=True)
    assert result.returncode==2 and '--plan' in result.stderr
    assert not output.exists()
