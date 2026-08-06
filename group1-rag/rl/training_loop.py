"""
Training loop for RL dynamic hedging system.

Handles initialization, training, validation, and evaluation.
Supports both Q-Learning (baseline) and PPO (production) agents.
"""

import numpy as np
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, field
import logging
from datetime import datetime
import json

from .rl_environment import HedgingEnvironment
from .q_learning_agent import QLearningAgent, QLearningConfig
from .ppo_agent import PPOAgent, PPOConfig

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Training configuration."""
    # Episodes
    num_episodes: int = 100  # Total episodes (trading days)
    train_episodes: int = 80
    val_episodes: int = 10
    test_episodes: int = 10

    # Agent
    agent_type: str = "ppo"  # "q_learning" or "ppo"
    ppo_config: PPOConfig = field(default_factory=PPOConfig)
    q_learning_config: QLearningConfig = field(default_factory=QLearningConfig)

    # Environment
    initial_portfolio: float = 10_000_000  # $10M
    transaction_cost_bps: float = 1.0

    # Training
    learning_rate: float = 3e-4
    target_sharpe: float = 1.5  # Target Sharpe ratio
    convergence_threshold: int = 30  # Episodes with stable Sharpe

    # Validation
    val_frequency: int = 10  # Validate every N episodes

    # Seed
    seed: int = 42


@dataclass
class EpisodeResult:
    """Result of a single episode."""
    episode_num: int
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    volatility: float
    final_portfolio_value: float
    cumulative_costs: float
    avg_reward: float
    num_actions: int


@dataclass
class TrainingResult:
    """Complete training result."""
    config: TrainingConfig
    timestamp: str

    # Training history
    train_results: List[EpisodeResult]
    val_results: List[EpisodeResult]
    test_results: List[EpisodeResult]

    # Metrics
    train_avg_sharpe: float
    val_avg_sharpe: float
    test_avg_sharpe: float
    test_max_sharpe: float
    test_min_sharpe: float

    # Status
    converged: bool
    convergence_episode: Optional[int]
    gate_passed: bool

    # Agent checkpoint
    agent_checkpoint_path: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "config": {
                "agent_type": self.config.agent_type,
                "num_episodes": self.config.num_episodes,
                "initial_portfolio": self.config.initial_portfolio,
            },
            "metrics": {
                "train_avg_sharpe": self.train_avg_sharpe,
                "val_avg_sharpe": self.val_avg_sharpe,
                "test_avg_sharpe": self.test_avg_sharpe,
                "test_max_sharpe": self.test_max_sharpe,
                "test_min_sharpe": self.test_min_sharpe,
            },
            "status": {
                "converged": self.converged,
                "convergence_episode": self.convergence_episode,
                "gate_passed": self.gate_passed,
            },
            "test_results": [
                {
                    "episode": r.episode_num,
                    "sharpe": r.sharpe_ratio,
                    "return": r.total_return * 100,
                    "max_dd": r.max_drawdown * 100,
                    "costs": r.cumulative_costs,
                }
                for r in self.test_results
            ],
        }


class TrainingLoop:
    """Main training loop orchestrator."""

    def __init__(self, config: TrainingConfig = None, verbose: bool = True):
        """
        Initialize training loop.

        Args:
            config: TrainingConfig object
            verbose: Whether to log detailed progress
        """
        self.config = config or TrainingConfig()
        self.verbose = verbose

        # Set random seeds
        np.random.seed(self.config.seed)

        # Initialize environment
        self.env = HedgingEnvironment(
            initial_portfolio_value=self.config.initial_portfolio,
            transaction_cost_bps=self.config.transaction_cost_bps,
            seed=self.config.seed,
            verbose=verbose,
        )

        # Initialize agent
        if self.config.agent_type == "ppo":
            self.agent = PPOAgent(
                observation_size=15,
                action_size=2,
                config=self.config.ppo_config,
                seed=self.config.seed,
            )
        else:
            self.agent = QLearningAgent(
                config=self.config.q_learning_config,
                seed=self.config.seed,
            )

        # Results storage
        self.train_results: List[EpisodeResult] = []
        self.val_results: List[EpisodeResult] = []
        self.test_results: List[EpisodeResult] = []

        logger.info(f"TrainingLoop initialized with config: {config}")

    def train(self) -> TrainingResult:
        """
        Run full training pipeline.

        Returns:
            TrainingResult object
        """
        logger.info("=" * 80)
        logger.info(f"Starting training: {self.config.num_episodes} episodes")
        logger.info("=" * 80)

        converged = False
        convergence_episode = None
        stable_sharpe_count = 0
        sharpe_history = []

        # Training episodes
        for episode in range(self.config.train_episodes):
            result = self._run_episode(episode, is_training=True)
            self.train_results.append(result)
            sharpe_history.append(result.sharpe_ratio)

            # Check convergence
            if len(sharpe_history) >= self.config.convergence_threshold:
                recent_sharpe = sharpe_history[-self.config.convergence_threshold:]
                std_dev = np.std(recent_sharpe)

                if std_dev < 0.1:  # Low variance = convergence
                    stable_sharpe_count += 1
                    if stable_sharpe_count >= 5:
                        converged = True
                        convergence_episode = episode
                        logger.info(f"Converged at episode {episode}")
                        break
                else:
                    stable_sharpe_count = 0

            # Validation
            if (episode + 1) % self.config.val_frequency == 0:
                val_sharpe = self._run_validation(episode)
                logger.info(f"Episode {episode}: Train Sharpe={result.sharpe_ratio:.3f}, Val Sharpe={val_sharpe:.3f}")

        # Test episodes
        logger.info(f"\nRunning {self.config.test_episodes} test episodes...")
        for test_ep in range(self.config.test_episodes):
            result = self._run_episode(
                self.config.train_episodes + test_ep,
                is_training=False,
            )
            self.test_results.append(result)

        # Compute final metrics
        train_sharpes = [r.sharpe_ratio for r in self.train_results]
        val_sharpes = [r.sharpe_ratio for r in self.val_results]
        test_sharpes = [r.sharpe_ratio for r in self.test_results]

        train_avg_sharpe = np.mean(train_sharpes) if train_sharpes else 0.0
        val_avg_sharpe = np.mean(val_sharpes) if val_sharpes else 0.0
        test_avg_sharpe = np.mean(test_sharpes) if test_sharpes else 0.0

        gate_passed = test_avg_sharpe >= self.config.target_sharpe

        result = TrainingResult(
            config=self.config,
            timestamp=datetime.now().isoformat(),
            train_results=self.train_results,
            val_results=self.val_results,
            test_results=self.test_results,
            train_avg_sharpe=train_avg_sharpe,
            val_avg_sharpe=val_avg_sharpe,
            test_avg_sharpe=test_avg_sharpe,
            test_max_sharpe=max(test_sharpes) if test_sharpes else 0.0,
            test_min_sharpe=min(test_sharpes) if test_sharpes else 0.0,
            converged=converged,
            convergence_episode=convergence_episode,
            gate_passed=gate_passed,
        )

        logger.info("=" * 80)
        logger.info(f"Training complete!")
        logger.info(f"Train Sharpe: {train_avg_sharpe:.3f}")
        logger.info(f"Val Sharpe: {val_avg_sharpe:.3f}")
        logger.info(f"Test Sharpe: {test_avg_sharpe:.3f} (target: {self.config.target_sharpe})")
        logger.info(f"Gate: {'PASSED' if gate_passed else 'FAILED'}")
        logger.info("=" * 80)

        return result

    def _run_episode(self, episode_num: int, is_training: bool = True) -> EpisodeResult:
        """
        Run a single episode.

        Args:
            episode_num: Episode number
            is_training: Whether in training mode

        Returns:
            EpisodeResult
        """
        observation, _ = self.env.reset()
        done = False
        episode_reward = 0.0

        while not done:
            # Select action
            if isinstance(self.agent, PPOAgent):
                action, log_prob, value = self.agent.select_action(observation, training=is_training)
            else:
                action = self.agent.select_action(observation, training=is_training)
                log_prob = 0.0
                value = 0.0

            # Take step
            next_observation, reward, terminated, truncated, info = self.env.step(action)
            done = terminated or truncated
            episode_reward += reward

            # Update agent
            if is_training:
                if isinstance(self.agent, PPOAgent):
                    self.agent.store_transition(observation, action, reward, value, log_prob, done)
                else:
                    self.agent.update(observation, action, reward, next_observation, done)

            observation = next_observation

        # PPO batch update at episode end
        if is_training and isinstance(self.agent, PPOAgent):
            self.agent.update()

        # Get episode summary
        summary = self.env.get_episode_summary()

        result = EpisodeResult(
            episode_num=episode_num,
            total_return=summary["total_return"] / 100,
            sharpe_ratio=summary["sharpe_ratio"],
            max_drawdown=summary["volatility"] * 2,  # Rough estimate
            volatility=summary["volatility"] / 100,
            final_portfolio_value=summary["final_portfolio_value"],
            cumulative_costs=summary["transaction_costs"],
            avg_reward=summary["avg_reward"],
            num_actions=self.env.current_minute,
        )

        if self.verbose and (episode_num + 1) % 10 == 0:
            logger.info(f"Episode {episode_num + 1}: Sharpe={result.sharpe_ratio:.3f}, "
                       f"Return={result.total_return:.4f}, Costs=${result.cumulative_costs:.2f}")

        return result

    def _run_validation(self, train_episode: int) -> float:
        """
        Run validation episodes.

        Args:
            train_episode: Current training episode

        Returns:
            Average Sharpe ratio on validation set
        """
        val_sharpes = []

        for _ in range(3):  # 3 validation episodes
            observation, _ = self.env.reset()
            done = False

            while not done:
                if isinstance(self.agent, PPOAgent):
                    action, _, _ = self.agent.select_action(observation, training=False)
                else:
                    action = self.agent.select_action(observation, training=False)

                observation, _, terminated, truncated, _ = self.env.step(action)
                done = terminated or truncated

            summary = self.env.get_episode_summary()
            val_sharpes.append(summary["sharpe_ratio"])
            self.val_results.append(EpisodeResult(
                episode_num=train_episode,
                total_return=summary["total_return"] / 100,
                sharpe_ratio=summary["sharpe_ratio"],
                max_drawdown=0.0,
                volatility=summary["volatility"] / 100,
                final_portfolio_value=summary["final_portfolio_value"],
                cumulative_costs=summary["transaction_costs"],
                avg_reward=summary["avg_reward"],
                num_actions=self.env.current_minute,
            ))

        return np.mean(val_sharpes)

    def save_result(self, filepath: str):
        """Save training result to file."""
        # This would be filled in after training
        pass

    def evaluate_policy(self, num_episodes: int = 10, deterministic: bool = True) -> Dict:
        """
        Evaluate trained policy on fresh episodes.

        Args:
            num_episodes: Number of evaluation episodes
            deterministic: Whether to use deterministic policy

        Returns:
            Evaluation metrics
        """
        results = []

        for _ in range(num_episodes):
            observation, _ = self.env.reset()
            done = False

            while not done:
                if isinstance(self.agent, PPOAgent):
                    action, _, _ = self.agent.select_action(observation, training=False)
                else:
                    action = self.agent.select_action(observation, training=False)

                observation, _, terminated, truncated, _ = self.env.step(action)
                done = terminated or truncated

            summary = self.env.get_episode_summary()
            results.append(summary)

        # Aggregate metrics
        sharpes = [r["sharpe_ratio"] for r in results]
        returns = [r["total_return"] for r in results]

        return {
            "avg_sharpe": np.mean(sharpes),
            "std_sharpe": np.std(sharpes),
            "max_sharpe": np.max(sharpes),
            "min_sharpe": np.min(sharpes),
            "avg_return": np.mean(returns),
            "avg_volatility": np.mean([r["volatility"] for r in results]),
            "results": results,
        }
