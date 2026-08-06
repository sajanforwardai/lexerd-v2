"""
Proximal Policy Optimization (PPO) agent with Actor-Critic architecture.

Production-grade continuous control for hedging.
Uses PyTorch for neural network approximation.
Target: 200-300bps edge vs Q-learning baseline.
"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class PPOConfig:
    """Configuration for PPO agent."""
    # Network architecture
    hidden_size: int = 128
    activation: str = "relu"  # relu, tanh

    # Training hyperparameters
    learning_rate: float = 3e-4
    gamma: float = 0.99  # Discount factor
    gae_lambda: float = 0.95  # GAE lambda for advantage estimation
    clip_ratio: float = 0.2  # PPO clipping
    entropy_coef: float = 0.01  # Entropy regularization
    value_coef: float = 0.5  # Value loss weight

    # Update parameters
    batch_size: int = 64
    n_epochs: int = 3  # Epochs per update
    max_grad_norm: float = 0.5  # Gradient clipping

    # Exploration
    std_init: float = 0.5  # Initial standard deviation for action distribution


class ActorCriticNetwork(nn.Module):
    """Actor-Critic network with shared feature representation."""

    def __init__(self, observation_size: int, action_size: int, config: PPOConfig):
        """
        Initialize actor-critic network.

        Args:
            observation_size: Size of observation space (15 for hedging)
            action_size: Size of action space (2: hedge_ratio, instrument)
            config: PPOConfig object
        """
        super().__init__()

        self.observation_size = observation_size
        self.action_size = action_size
        self.config = config

        # Shared feature network
        if config.activation == "relu":
            activation = nn.ReLU
        else:
            activation = nn.Tanh

        self.shared_net = nn.Sequential(
            nn.Linear(observation_size, config.hidden_size),
            activation(),
            nn.Linear(config.hidden_size, config.hidden_size),
            activation(),
        )

        # Actor head (continuous + discrete)
        self.actor_mean = nn.Linear(config.hidden_size, 1)  # Hedge ratio
        self.actor_logstd = nn.Parameter(torch.ones(1) * np.log(config.std_init))

        self.actor_instrument = nn.Linear(config.hidden_size, 5)  # 5 instruments (logits)

        # Critic head
        self.critic = nn.Linear(config.hidden_size, 1)

        # Initialize weights
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.orthogonal_(module.weight, gain=np.sqrt(2))
                nn.init.constant_(module.bias, 0)

    def forward(self, observation: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Forward pass computing actor and critic outputs.

        Args:
            observation: Observation tensor (batch_size, observation_size)

        Returns:
            (action_mean, action_std, value)
        """
        features = self.shared_net(observation)

        # Actor outputs
        action_mean = self.actor_mean(features)  # Hedge ratio mean
        action_mean = torch.sigmoid(action_mean)  # Clamp to [0, 1]

        action_std = torch.exp(self.actor_logstd)

        # Instrument logits (will be used for categorical)
        instrument_logits = self.actor_instrument(features)

        # Critic value
        value = self.critic(features)

        return action_mean, action_std, instrument_logits, value

    def get_action_value(self, observation: torch.Tensor, deterministic: bool = False):
        """
        Sample action and get value.

        Args:
            observation: Observation tensor
            deterministic: Whether to use mean action (no noise)

        Returns:
            action: [hedge_ratio, instrument_index]
            log_prob: Log probability of action
            value: Estimated value
        """
        action_mean, action_std, instrument_logits, value = self.forward(observation)

        # Sample hedge ratio
        if deterministic:
            hedge_ratio = action_mean
            log_prob_hedge = torch.zeros_like(hedge_ratio)
        else:
            dist_hedge = torch.distributions.Normal(action_mean, action_std)
            hedge_ratio = dist_hedge.rsample()
            hedge_ratio = torch.clamp(hedge_ratio, 0, 1)
            log_prob_hedge = dist_hedge.log_prob(hedge_ratio)

        # Sample instrument
        dist_instrument = torch.distributions.Categorical(logits=instrument_logits)
        if deterministic:
            instrument = torch.argmax(instrument_logits, dim=-1)
            log_prob_instrument = torch.zeros(instrument.shape[0], 1, device=instrument.device)
        else:
            instrument = dist_instrument.sample()
            log_prob_instrument = dist_instrument.log_prob(instrument).unsqueeze(-1)

        # Combine actions
        action = torch.cat([hedge_ratio, instrument.unsqueeze(-1).float()], dim=-1)
        log_prob = log_prob_hedge + log_prob_instrument

        return action, log_prob, value.squeeze(-1)

    def evaluate(self, observation: torch.Tensor, action: torch.Tensor):
        """
        Evaluate log probability and value for given action.

        Args:
            observation: Observation tensor
            action: Action tensor [hedge_ratio, instrument_index]

        Returns:
            log_prob, value, entropy
        """
        action_mean, action_std, instrument_logits, value = self.forward(observation)

        # Evaluate hedge ratio
        dist_hedge = torch.distributions.Normal(action_mean, action_std)
        log_prob_hedge = dist_hedge.log_prob(action[:, 0:1])
        entropy_hedge = dist_hedge.entropy()

        # Evaluate instrument
        dist_instrument = torch.distributions.Categorical(logits=instrument_logits)
        instrument_action = action[:, 1].long()
        log_prob_instrument = dist_instrument.log_prob(instrument_action).unsqueeze(-1)
        entropy_instrument = dist_instrument.entropy().unsqueeze(-1)

        log_prob = log_prob_hedge + log_prob_instrument
        entropy = entropy_hedge + entropy_instrument

        return log_prob, value.squeeze(-1), entropy


class PPOAgent:
    """
    Proximal Policy Optimization agent.

    Uses actor-critic network with advantage estimation (GAE).
    """

    def __init__(self, observation_size: int = 15, action_size: int = 2,
                 config: PPOConfig = None, device: str = "cpu", seed: Optional[int] = None):
        """
        Initialize PPO agent.

        Args:
            observation_size: Size of observation space
            action_size: Size of action space
            config: PPOConfig object
            device: Device to use (cpu or cuda)
            seed: Random seed
        """
        self.config = config or PPOConfig()
        self.device = torch.device(device)
        self.observation_size = observation_size
        self.action_size = action_size

        # Network
        self.network = ActorCriticNetwork(observation_size, action_size, self.config).to(self.device)

        # Optimizer
        self.optimizer = optim.Adam(self.network.parameters(), lr=self.config.learning_rate)

        # Storage for trajectory
        self.observations: List[np.ndarray] = []
        self.actions: List[np.ndarray] = []
        self.rewards: List[float] = []
        self.values: List[float] = []
        self.log_probs: List[float] = []
        self.dones: List[bool] = []

        # Statistics
        self.training_stats = {
            "total_updates": 0,
            "total_steps": 0,
            "policy_loss": 0.0,
            "value_loss": 0.0,
            "entropy_loss": 0.0,
        }

        # Seed
        if seed is not None:
            torch.manual_seed(seed)
            np.random.seed(seed)
            self.np_random = np.random.default_rng(seed)
        else:
            self.np_random = np.random.default_rng()

        logger.info(f"PPOAgent initialized with config: {config}")

    def select_action(self, observation: np.ndarray, training: bool = True) -> Tuple[np.ndarray, float]:
        """
        Select action for observation.

        Args:
            observation: Observation from environment
            training: Whether in training mode

        Returns:
            (action, log_prob)
        """
        obs_tensor = torch.from_numpy(observation).float().unsqueeze(0).to(self.device)

        with torch.no_grad():
            action, log_prob, value = self.network.get_action_value(obs_tensor, deterministic=not training)

        action_np = action.squeeze(0).cpu().numpy()
        log_prob_np = log_prob.squeeze(0).cpu().numpy()
        value_np = value.squeeze(0).cpu().item()

        return action_np, log_prob_np, value_np

    def store_transition(self, observation: np.ndarray, action: np.ndarray, reward: float,
                         value: float, log_prob: float, done: bool):
        """
        Store transition in trajectory buffer.

        Args:
            observation: Observation
            action: Action taken
            reward: Reward received
            value: Value estimate
            log_prob: Log probability of action
            done: Whether episode is done
        """
        self.observations.append(observation)
        self.actions.append(action)
        self.rewards.append(reward)
        self.values.append(value)
        self.log_probs.append(log_prob)
        self.dones.append(done)

    def compute_advantages(self, next_value: float = 0.0) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute advantages using Generalized Advantage Estimation (GAE).

        Args:
            next_value: Value estimate for terminal state

        Returns:
            (advantages, returns)
        """
        advantages = np.zeros_like(self.rewards)
        returns = np.zeros_like(self.rewards)

        gae = 0.0
        value = next_value

        # Backward pass for GAE
        for t in reversed(range(len(self.rewards))):
            if t == len(self.rewards) - 1:
                next_nonterminal = 1.0 - self.dones[t]
                next_value_t = next_value
            else:
                next_nonterminal = 1.0 - self.dones[t]
                next_value_t = self.values[t + 1]

            delta = self.rewards[t] + self.config.gamma * next_value_t * next_nonterminal - self.values[t]
            gae = delta + self.config.gamma * self.config.gae_lambda * next_nonterminal * gae
            advantages[t] = gae
            returns[t] = gae + self.values[t]

        return advantages, returns

    def update(self):
        """
        Perform PPO update on collected trajectory.
        """
        if len(self.observations) == 0:
            return

        # Compute advantages
        advantages, returns = self.compute_advantages()

        # Normalize advantages
        advantages = (advantages - np.mean(advantages)) / (np.std(advantages) + 1e-8)

        # Convert to tensors
        observations = torch.from_numpy(np.array(self.observations)).float().to(self.device)
        actions = torch.from_numpy(np.array(self.actions)).float().to(self.device)
        advantages_t = torch.from_numpy(advantages).float().to(self.device)
        returns_t = torch.from_numpy(returns).float().to(self.device)
        old_log_probs = torch.from_numpy(np.array(self.log_probs)).float().to(self.device)

        # Mini-batch updates
        n_samples = len(self.observations)
        indices = np.arange(n_samples)

        for epoch in range(self.config.n_epochs):
            np.random.shuffle(indices)

            for i in range(0, n_samples, self.config.batch_size):
                batch_idx = indices[i:i + self.config.batch_size]

                batch_obs = observations[batch_idx]
                batch_actions = actions[batch_idx]
                batch_advantages = advantages_t[batch_idx]
                batch_returns = returns_t[batch_idx]
                batch_old_log_probs = old_log_probs[batch_idx]

                # Forward pass
                new_log_probs, values, entropy = self.network.evaluate(batch_obs, batch_actions)

                # PPO clipped surrogate objective
                ratio = torch.exp(new_log_probs - batch_old_log_probs)
                surr1 = ratio * batch_advantages
                surr2 = torch.clamp(ratio, 1 - self.config.clip_ratio,
                                   1 + self.config.clip_ratio) * batch_advantages

                policy_loss = -torch.min(surr1, surr2).mean()
                value_loss = (batch_returns - values).pow(2).mean()
                entropy_loss = -entropy.mean()

                # Total loss
                loss = (policy_loss + self.config.value_coef * value_loss +
                       self.config.entropy_coef * entropy_loss)

                # Backward pass
                self.optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.network.parameters(), self.config.max_grad_norm)
                self.optimizer.step()

                # Update statistics
                self.training_stats["policy_loss"] = policy_loss.item()
                self.training_stats["value_loss"] = value_loss.item()
                self.training_stats["entropy_loss"] = entropy_loss.item()

        self.training_stats["total_updates"] += 1
        self.training_stats["total_steps"] += n_samples

        # Clear trajectory buffer
        self.clear_trajectory()

    def clear_trajectory(self):
        """Clear trajectory buffer after update."""
        self.observations.clear()
        self.actions.clear()
        self.rewards.clear()
        self.values.clear()
        self.log_probs.clear()
        self.dones.clear()

    def save(self, filepath: str):
        """Save network weights."""
        torch.save({
            "network_state": self.network.state_dict(),
            "optimizer_state": self.optimizer.state_dict(),
            "stats": self.training_stats,
        }, filepath)
        logger.info(f"PPO agent saved to {filepath}")

    def load(self, filepath: str):
        """Load network weights."""
        checkpoint = torch.load(filepath, map_location=self.device)
        self.network.load_state_dict(checkpoint["network_state"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state"])
        self.training_stats = checkpoint.get("stats", self.training_stats)
        logger.info(f"PPO agent loaded from {filepath}")
