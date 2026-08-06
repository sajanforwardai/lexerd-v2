"""
Q-Learning agent with state discretization for baseline hedging policy.

Uses epsilon-greedy exploration and tabular Q-learning.
State discretization: Greeks into 5 buckets, regimes into categories.
Target: 100bps edge vs unhedged baseline.
"""

import numpy as np
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class QLearningConfig:
    """Configuration for Q-Learning agent."""
    learning_rate: float = 0.1
    discount_factor: float = 0.99
    epsilon_start: float = 1.0
    epsilon_end: float = 0.05
    epsilon_decay: float = 0.995
    num_buckets: int = 5  # Discretization buckets per dimension
    exploration_frames: int = 10000  # Frames before epsilon decay


class StateDiscretizer:
    """Discretize continuous state space into buckets."""

    def __init__(self, num_buckets: int = 5):
        """
        Initialize discretizer.

        Args:
            num_buckets: Number of buckets per dimension
        """
        self.num_buckets = num_buckets

    def discretize_greeks(self, delta: float, gamma: float, vega: float) -> Tuple[int, int, int]:
        """
        Discretize Greeks into bucket indices.

        Args:
            delta: Delta value (-1 to 1)
            gamma: Gamma value (0 to 0.01)
            vega: Vega value (-10000 to 10000)

        Returns:
            Tuple of bucket indices
        """
        # Delta: -1 to 1 → 5 buckets
        delta_bucket = int(np.clip((delta + 1) / 2 * (self.num_buckets - 1), 0, self.num_buckets - 1))

        # Gamma: 0 to 0.01 → 5 buckets
        gamma_bucket = int(np.clip(gamma / 0.01 * (self.num_buckets - 1), 0, self.num_buckets - 1))

        # Vega: -10000 to 10000 → 5 buckets
        vega_bucket = int(np.clip((vega + 10000) / 20000 * (self.num_buckets - 1), 0, self.num_buckets - 1))

        return delta_bucket, gamma_bucket, vega_bucket

    def discretize_regime(self, regime: int) -> int:
        """
        Discretize volatility regime.

        Args:
            regime: Regime value (0=LOW, 1=MEDIUM, 2=HIGH)

        Returns:
            Regime bucket index
        """
        return int(np.clip(regime, 0, 2))

    def discretize_state(self, observation: np.ndarray) -> Tuple:
        """
        Discretize full observation into state bucket.

        Args:
            observation: Full observation from environment (15 dims)

        Returns:
            Hashable state tuple (delta_b, gamma_b, vega_b, regime_b, portfolio_b, time_b)
        """
        # Extract Greeks from observation
        delta = observation[0]
        gamma = observation[1]
        vega = observation[2]

        # Regime (normalized, -1 to 1)
        regime_normalized = observation[6]
        regime = int(np.clip(regime_normalized + 1, 0, 2))

        # Portfolio value (normalized)
        portfolio_normalized = observation[7]
        portfolio_bucket = int(np.clip((portfolio_normalized + 5) / 10 * (self.num_buckets - 1), 0, self.num_buckets - 1))

        # Time remaining (normalized, 0 to 1)
        time_remaining = observation[-1]
        time_bucket = int(np.clip(time_remaining * (self.num_buckets - 1), 0, self.num_buckets - 1))

        # Discretize Greeks
        delta_b, gamma_b, vega_b = self.discretize_greeks(delta, gamma, vega)

        return (delta_b, gamma_b, vega_b, regime, portfolio_bucket, time_bucket)


class QLearningAgent:
    """
    Q-Learning agent for baseline hedging policy.

    Uses tabular Q-learning with epsilon-greedy exploration.
    Action space: [hedge_ratio (3 levels: 0, 0.5, 1.0), instrument (5 options)]
    """

    # Discrete action levels for hedge ratio
    HEDGE_RATIOS = [0.0, 0.3, 0.5, 0.7, 1.0]  # 5 discrete levels
    N_INSTRUMENTS = 5  # 5 hedging instruments

    def __init__(self, config: QLearningConfig = None, seed: Optional[int] = None):
        """
        Initialize Q-Learning agent.

        Args:
            config: QLearningConfig object
            seed: Random seed for reproducibility
        """
        self.config = config or QLearningConfig()
        self.discretizer = StateDiscretizer(self.config.num_buckets)

        # Q-table: dict mapping (state, action) → Q-value
        self.q_table: Dict[Tuple, float] = defaultdict(float)

        # Epsilon for exploration
        self.epsilon = self.config.epsilon_start
        self.frame_count = 0

        # Statistics
        self.training_stats = {
            "total_steps": 0,
            "total_episodes": 0,
            "avg_reward": 0.0,
            "max_q_value": 0.0,
        }

        # Seed
        if seed is not None:
            self.np_random = np.random.default_rng(seed)
        else:
            self.np_random = np.random.default_rng()

        logger.info(f"QLearningAgent initialized with config: {config}")

    def select_action(self, observation: np.ndarray, training: bool = True) -> np.ndarray:
        """
        Select action using epsilon-greedy policy.

        Args:
            observation: Current observation from environment
            training: Whether in training mode (uses exploration)

        Returns:
            Action array: [hedge_ratio, instrument_index]
        """
        state = self.discretizer.discretize_state(observation)

        if training and self.np_random.random() < self.epsilon:
            # Explore: random action
            hedge_idx = self.np_random.integers(0, len(self.HEDGE_RATIOS))
            instrument_idx = self.np_random.integers(0, self.N_INSTRUMENTS)
        else:
            # Exploit: best action
            hedge_idx, instrument_idx = self._get_best_action(state)

        # Convert discrete indices to continuous values
        hedge_ratio = self.HEDGE_RATIOS[hedge_idx]
        action = np.array([hedge_ratio, float(instrument_idx)], dtype=np.float32)

        return action

    def _get_best_action(self, state: Tuple) -> Tuple[int, int]:
        """
        Get best action for state (exploitation).

        Args:
            state: Discretized state tuple

        Returns:
            (hedge_idx, instrument_idx) with highest Q-value
        """
        best_value = -np.inf
        best_action = (0, 0)

        for hedge_idx in range(len(self.HEDGE_RATIOS)):
            for instr_idx in range(self.N_INSTRUMENTS):
                action = (hedge_idx, instr_idx)
                q_value = self.q_table.get((state, action), 0.0)

                if q_value > best_value:
                    best_value = q_value
                    best_action = (hedge_idx, instr_idx)

        return best_action

    def update(self, observation: np.ndarray, action: np.ndarray, reward: float,
               next_observation: np.ndarray, done: bool):
        """
        Update Q-values using Q-learning update rule.

        Q(s,a) = Q(s,a) + α * [r + γ * max(Q(s',a')) - Q(s,a)]

        Args:
            observation: Current observation
            action: Action taken (continuous)
            reward: Reward received
            next_observation: Next observation
            done: Whether episode is done
        """
        # Discretize states
        state = self.discretizer.discretize_state(observation)
        next_state = self.discretizer.discretize_state(next_observation)

        # Convert continuous action back to discrete indices
        # Find closest hedge ratio
        hedge_idx = np.argmin(np.abs(np.array(self.HEDGE_RATIOS) - action[0]))
        instr_idx = int(np.clip(action[1], 0, self.N_INSTRUMENTS - 1))
        action_tuple = (hedge_idx, instr_idx)

        # Current Q-value
        current_q = self.q_table.get((state, action_tuple), 0.0)

        # Maximum Q-value for next state
        if done:
            max_next_q = 0.0  # Terminal state
        else:
            _, max_next_q = self._get_best_action_with_value(next_state)

        # Q-learning update
        new_q = current_q + self.config.learning_rate * (
            reward + self.config.discount_factor * max_next_q - current_q
        )

        self.q_table[(state, action_tuple)] = new_q

        # Update statistics
        self.training_stats["total_steps"] += 1
        self.training_stats["max_q_value"] = max(self.training_stats["max_q_value"], abs(new_q))

        # Decay epsilon
        if self.training_stats["total_steps"] < self.config.exploration_frames:
            self.epsilon = self.config.epsilon_start
        else:
            self.epsilon = max(
                self.config.epsilon_end,
                self.epsilon * self.config.epsilon_decay
            )

    def _get_best_action_with_value(self, state: Tuple) -> Tuple[Tuple[int, int], float]:
        """
        Get best action and its Q-value for state.

        Returns:
            ((hedge_idx, instr_idx), q_value)
        """
        best_value = -np.inf
        best_action = (0, 0)

        for hedge_idx in range(len(self.HEDGE_RATIOS)):
            for instr_idx in range(self.N_INSTRUMENTS):
                action = (hedge_idx, instr_idx)
                q_value = self.q_table.get((state, action), 0.0)

                if q_value > best_value:
                    best_value = q_value
                    best_action = (hedge_idx, instr_idx)

        return best_action, best_value

    def get_policy(self, state: np.ndarray) -> Tuple[float, int]:
        """
        Get deterministic policy (greedy) for state.

        Args:
            state: Observation from environment

        Returns:
            (hedge_ratio, instrument_index)
        """
        discretized_state = self.discretizer.discretize_state(state)
        hedge_idx, instr_idx = self._get_best_action(discretized_state)
        return self.HEDGE_RATIOS[hedge_idx], instr_idx

    def save(self, filepath: str):
        """Save Q-table to file."""
        import json
        # Convert tuple keys to strings for JSON serialization
        serializable_table = {}
        for key, value in self.q_table.items():
            key_str = str(key)
            serializable_table[key_str] = float(value)

        with open(filepath, "w") as f:
            json.dump({
                "q_table": serializable_table,
                "config": {
                    "learning_rate": self.config.learning_rate,
                    "discount_factor": self.config.discount_factor,
                    "epsilon": self.epsilon,
                },
                "stats": self.training_stats,
            }, f, indent=2)

        logger.info(f"Q-Learning agent saved to {filepath}")

    def load(self, filepath: str):
        """Load Q-table from file."""
        import json
        with open(filepath, "r") as f:
            data = json.load(f)

        # Reconstruct Q-table
        self.q_table.clear()
        for key_str, value in data["q_table"].items():
            # Parse string representation back to tuple
            key = eval(key_str)
            self.q_table[key] = value

        self.training_stats = data.get("stats", self.training_stats)
        logger.info(f"Q-Learning agent loaded from {filepath}")

    def reset_exploration(self):
        """Reset epsilon for new training cycle."""
        self.epsilon = self.config.epsilon_start
        self.frame_count = 0
