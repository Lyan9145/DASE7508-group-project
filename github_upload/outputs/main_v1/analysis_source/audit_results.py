"""Independently audit completed traces for pairing, trust boundaries and scoring."""
import argparse
import csv
import gzip
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np


def audit(run):
    config = json.loads((run / 'config.json').read_text())
    status = json.loads((run / 'run_status.json').read_text())
    calibration = json.loads((run / 'calibration.json').read_text())
    assert status['complete']
    if config['phase'] == 'main':
        assert status['evaluation_episodes'] == 4500
        assert hashlib.sha256((run / 'source' / 'main_plan.json').read_bytes()).hexdigest() == config['plan_sha256']
    for name, checksum in config['implementation_sha256'].items():
        assert hashlib.sha256((run / 'source' / name).read_bytes()).hexdigest() == checksum
    with (run / 'episodes.csv').open() as file:
        episodes = {(r['policy'], r['case'], r['monitor_on']=='True', int(r['seed'])): r
                    for r in csv.DictReader(file)}
    noise, initial_states, schedules = {}, {}, {}
    checked_rows = checked_episodes = 0
    with gzip.open(run / 'traces.jsonl.gz', 'rt') as file:
        records = (json.loads(line) for line in file)
        key = lambda r: (r['policy'], r['case'], r['monitor_on'], r['seed'])
        for identity, group in itertools.groupby(records, key=key):
            truth_distances, effort, steps, aborted = [], 0.0, 0, False
            previous_angle = previous_velocity = None
            metric = episodes[identity]
            for record in group:
                checked_rows += 1
                raw = np.array(record['raw_sensor'])
                reported = np.array(record['reported_sensor'])
                applied = np.array(record['policy_sensor'])
                safe = [1,3,4,5,6,7,8,9]
                np.testing.assert_array_equal(raw[safe], reported[safe])
                np.testing.assert_array_equal(reported[safe], applied[safe])
                expected = np.arctan2(raw[2], raw[0]) + record['delta_rad']
                np.testing.assert_allclose(reported[[0,2]], [np.cos(expected),np.sin(expected)],atol=1e-12)
                np.testing.assert_allclose(np.sum(applied[[0,2]]**2),1.0,atol=1e-12)
                step = record['observation_step']
                start = int(metric['attack_start']); duration = int(metric['duration'])
                amplitude = float(metric['epsilon_rad'])
                kind = metric['attack_kind']
                if kind == 'clean' or not start <= step < start+duration:
                    expected_magnitude = 0.0
                else:
                    expected_magnitude = amplitude * ((step-start+1)/duration if kind.endswith('ramp') else 1)
                np.testing.assert_allclose(abs(record['delta_rad']), expected_magnitude, atol=1e-12)
                schedule_key = identity[0], identity[1], identity[3], step
                if schedule_key in schedules:
                    assert record['delta_rad'] == schedules[schedule_key]
                else:
                    schedules[schedule_key] = record['delta_rad']
                if not record['monitor_on']:
                    np.testing.assert_array_equal(reported, applied)
                else:
                    if record['monitor']['alarm']:
                        dt = calibration[record['policy']].get('control_dt_seconds',0.02)
                        predicted = previous_angle + previous_velocity*dt
                        np.testing.assert_allclose(applied[[0,2]], [np.cos(predicted),np.sin(predicted)],atol=1e-12)
                    else:
                        np.testing.assert_array_equal(reported,applied)
                    previous_angle = np.arctan2(applied[2],applied[0])
                    previous_velocity = raw[6]
                actual_tip = np.array(record['truth_before']['fingertip'])
                target = np.array(record['truth_before']['target'])
                error = raw[8:10] - (actual_tip - target)
                noise_key = (record['policy'], record['seed'], record['observation_step'])
                if noise_key in noise:
                    np.testing.assert_allclose(error, noise[noise_key], rtol=0, atol=1e-13)
                else:
                    noise[noise_key] = error
                if record['observation_step'] == 0:
                    initial_key = record['policy'], record['seed']
                    if initial_key in initial_states:
                        assert record['truth_before'] == initial_states[initial_key]
                    else:
                        initial_states[initial_key] = record['truth_before']
                if record['action'] is not None:
                    steps += 1
                    effort += float(np.dot(record['action'], record['action']))
                    truth_distances.append(record['truth_after']['distance'])
                else:
                    aborted = True
                    assert record['monitor']['abort']
                    assert record['monitor']['alarm_streak'] > 20
            assert steps == int(metric['steps'])
            assert aborted == (metric['aborted']=='True')
            independent_success = steps == 100 and not aborted and np.mean(truth_distances[-10:]) <= 0.03
            assert bool(independent_success) == (metric['task_success']=='True')
            np.testing.assert_allclose(effort,float(metric['control_effort']),rtol=1e-6,atol=1e-6)
            checked_episodes += 1
    assert checked_episodes == status['evaluation_episodes'] == len(episodes)
    result = {'passed': True, 'episodes': checked_episodes, 'trace_rows': checked_rows,
              'paired_initial_states': len(initial_states),
              'noise_observation_keys': len(noise),
              'checks': ['snapshot hashes','unchanged protected channels','consistent angle encoding',
                         'attack window and amplitude','paired attack schedules',
                         'previous-velocity correction','paired initial states and noise','abort boundary','independent task scoring',
                         'control effort']}
    (run / 'audit.json').write_text(json.dumps(result,indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path)
    print(json.dumps(audit(parser.parse_args().run),indent=2))
