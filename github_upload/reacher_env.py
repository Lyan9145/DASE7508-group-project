"""Clean sensing baseline for the proposal; attacks/monitor are future modules."""
import gymnasium as gym
import numpy as np


class PositionNoise(gym.Wrapper):
    def __init__(self, env, sigma=0.002, noise_seed=0):
        super().__init__(env)
        self.sigma = sigma
        self.noise_seed = noise_seed
        self.sensor_rng = np.random.default_rng(noise_seed)

    def observe(self, observation):
        result = observation.copy()
        result[8:10] += self.sensor_rng.normal(0, self.sigma, 2)
        return result

    def reset(self, *, seed=None, options=None):
        options = dict(options or {})
        noise_seed = options.pop('noise_seed', self.noise_seed)
        self.sensor_rng = np.random.default_rng(noise_seed)
        obs, info = self.env.reset(seed=seed, options=options)
        return self.observe(obs), info

    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        return self.observe(obs), reward, terminated, truncated, info


def make_env(seed=0, noise_sigma=0.002, render_mode=None):
    env = gym.make('Reacher-v5', max_episode_steps=100, render_mode=render_mode)
    env.action_space.seed(seed)
    return PositionNoise(env, sigma=noise_sigma, noise_seed=seed)
