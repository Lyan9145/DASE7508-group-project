import numpy as np
import pytest
from security import ArmGeometry, Attack
from recovery_monitor import RecoveryMonitor


@pytest.mark.parametrize('grace', [1, 3])
def test_recovery_and_sustained_abort(grace):
    g = ArmGeometry(np.zeros(2), np.array([.1, 0]), np.array([.11, 0]))
    clean = np.array([1., 1., 0., 0., 0., 0., 0., 0., .21, 0.])
    bad = Attack('bias', .1, 40).apply(clean, 20)
    m = RecoveryMonitor(g, .006, .02, grace)
    m.process(clean)
    for i in range(1, 22):
        _, s = m.process(bad)
        assert not s['abort']
    assert s['state'] == 'recovery_pending'
    _, s = m.process(clean)
    assert s['state'] == 'normal' and s['alarm_streak'] == 0
    for i in range(1, 22 + grace):
        fixed, s = m.process(bad)
        assert s['abort'] == (i == 21 + grace)
        np.testing.assert_array_equal(fixed[[1,3,4,5,6,7,8,9]], bad[[1,3,4,5,6,7,8,9]])


def test_window_boundary():
    from exploration import validate_window
    validate_window(70, 20)
    with pytest.raises(ValueError):
        validate_window(71, 20)


def test_exploration_refuses_existing_output(tmp_path):
    from exploration import run
    sentinel=tmp_path/'keep.txt'
    sentinel.write_text('preserve')
    with pytest.raises(FileExistsError):
        run(tmp_path,'development')
    assert sentinel.read_text()=='preserve'
    assert list(tmp_path.iterdir())==[sentinel]


def test_sink_scores_prediction_without_controlling_monitor(tmp_path):
    import io
    import json
    from exploration import Sink
    file=io.StringIO()
    sink=Sink(file,'original')
    record=dict(monitor={'alarm':True}, observation_step=20,
                policy_sensor=[1,1,0,0,0,0,0,0,.21,0],
                raw_sensor=[1,1,0,0,0,0,0,0,.212,0],
                truth_before={'angles':[.1,0],'fingertip':[.21,0],'target':[0,0]})
    sink.write(json.dumps(record))
    assert sink.errors==pytest.approx([.1])
    assert sink.alarms==[20]
    np.testing.assert_allclose(sink.noise,[[.002,0]])
