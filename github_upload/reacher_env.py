"""Independent sensor sampling with reproducible, non-repeating noise streams."""
import gymnasium as gym
import mujoco
import numpy as np


class PositionNoise(gym.Wrapper):
    def __init__(self, env, sigma=0.002, noise_seed=0, synchronized=True):
        super().__init__(env)
        if not np.isfinite(sigma) or sigma < 0:
            raise ValueError('sigma must be finite and nonnegative')
        self.sigma = sigma
        self.noise_seed = noise_seed
        self.sensor_rng = np.random.default_rng(noise_seed)
        self.synchronized = synchronized
        self.geometry_data = mujoco.MjData(self.unwrapped.model)
        self.tip_id = self.unwrapped.model.body('fingertip').id
        self.target_id = self.unwrapped.model.body('target').id

    def observe(self, observation, info):
        result = observation.copy()
        # Recompute position on separate data, preserving the actual simulation
        # and its integrator/warm-start state. All channels refer to current qpos.
        base = self.unwrapped
        self.geometry_data.qpos[:] = base.data.qpos
        mujoco.mj_forward(base.model, self.geometry_data)
        tip = self.geometry_data.xipos[self.tip_id, :2].copy()
        target = self.geometry_data.xipos[self.target_id, :2].copy()
        if self.synchronized:
            result[8:10] = tip - target
        result[8:10] += self.sensor_rng.normal(0, self.sigma, 2)
        info = dict(info)
        # Privileged evaluation channel: never passed to policy or monitor.
        info['truth'] = {'fingertip': tip.tolist(), 'target': target.tolist(),
                         'angles': base.data.qpos[:2].copy().tolist(),
                         'distance': float(np.linalg.norm(tip - target))}
        return result, info

    def reset(self, *, seed=None, options=None):
        options = dict(options or {})
        noise_seed = options.pop('noise_seed', None)
        if noise_seed is not None:
            self.sensor_rng = np.random.default_rng(noise_seed)
        obs, info = self.env.reset(seed=seed, options=options)
        return self.observe(obs, info)

    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        obs, info = self.observe(obs, info)
        return obs, reward, terminated, truncated, info


def make_env(seed=0, noise_sigma=0.002, render_mode=None, synchronized=True):
    env = gym.make('Reacher-v5', max_episode_steps=100, render_mode=render_mode)
    env.action_space.seed(seed)
    return PositionNoise(env, sigma=noise_sigma, noise_seed=seed,
                         synchronized=synchronized)
