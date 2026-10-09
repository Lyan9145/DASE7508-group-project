"""Check installed physics, observation semantics, geometry, rendering and SB3."""
import importlib.metadata
import json
import platform
import time
from pathlib import Path

import gymnasium as gym
import mujoco
import numpy as np
import torch
from PIL import Image
from stable_baselines3.common.env_checker import check_env

from reacher_env import make_env


def main():
    out = Path('outputs')
    out.mkdir(exist_ok=True)
    env = gym.make('Reacher-v5', max_episode_steps=100, render_mode='rgb_array')
    obs, _ = env.reset(seed=42)
    base = env.unwrapped
    assert obs.shape == (10,) and env.action_space.shape == (2,)
    b0, b1, tip = [base.model.body(name).id for name in ('body0', 'body1', 'fingertip')]
    origin = base.model.body_pos[b0, :2]
    link = base.model.body_pos[b1, :2]
    offset = base.model.body_pos[tip, :2]

    def rotation(q):
        return np.array([[np.cos(q), -np.sin(q)], [np.sin(q), np.cos(q)]])

    max_error = 0.0
    max_reported_position_lag = 0.0
    geometry_data = mujoco.MjData(base.model)
    started = time.perf_counter()
    for step in range(100):
        q = base.data.qpos[:2]
        np.testing.assert_allclose(obs[:2], np.cos(q), atol=1e-12)
        np.testing.assert_allclose(obs[2:4], np.sin(q), atol=1e-12)
        np.testing.assert_allclose(obs[4:6], base.get_body_com('target')[:2], atol=1e-12)
        np.testing.assert_allclose(obs[6:8], base.data.qvel[:2], atol=1e-12)
        actual = base.get_body_com('fingertip')[:2]
        np.testing.assert_allclose(obs[8:10], actual - obs[4:6], atol=1e-12)
        predicted = origin + rotation(q[0]) @ link + rotation(q.sum()) @ offset
        # mj_step may leave body positions at its last dynamics evaluation.
        # Recompute on separate data to verify FK without changing the environment.
        geometry_data.qpos[:] = base.data.qpos
        mujoco.mj_forward(base.model, geometry_data)
        forwarded = geometry_data.xipos[tip, :2]
        max_reported_position_lag = max(max_reported_position_lag,
                                       float(np.linalg.norm(forwarded - actual)))
        error = float(np.linalg.norm(predicted - forwarded))
        max_error = max(max_error, error)
        assert error < 1e-10, (predicted, actual)
        obs, reward, terminated, truncated, _ = env.step(env.action_space.sample())
        assert np.isfinite(obs).all() and np.isfinite(reward)
        assert not terminated and truncated == (step == 99)
    elapsed = time.perf_counter() - started
    frame = env.render()
    assert frame.ndim == 3 and frame.shape[2] == 3
    Image.fromarray(frame).save(out / 'reacher_preview.png')
    report = {'python': platform.python_version(), 'platform': platform.platform(),
              'packages': {p: importlib.metadata.version(p) for p in
                           ['mujoco', 'gymnasium', 'stable-baselines3', 'torch', 'numpy']},
              'cuda_available': torch.cuda.is_available(), 'torch_cuda': torch.version.cuda,
              'gpu': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
              'observation_shape': list(env.observation_space.shape),
              'episode_steps': 100, 'control_dt_seconds': base.dt,
              'body0_origin_xy': origin.tolist(), 'body1_offset_xy': link.tolist(),
              'fingertip_offset_xy': offset.tolist(), 'max_fk_error_m': max_error,
              'max_raw_body_position_lag_m': max_reported_position_lag,
              'checked_steps_per_second': 100 / elapsed,
              'render_shape': list(frame.shape)}
    env.close()
    noisy = make_env(42)
    check_env(noisy, warn=True)
    a, _ = noisy.reset(seed=1, options={'noise_seed': 2})
    b, _ = noisy.reset(seed=1, options={'noise_seed': 2})
    np.testing.assert_array_equal(a, b)
    noisy.close()
    (out / 'setup_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
