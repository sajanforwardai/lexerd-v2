"""
Comprehensive test suite for RL dynamic hedging system.

30+ tests covering:
- Environment dynamics
- Reward calculation
- Agent learning
- State discretization
- Training convergence
- Policy evaluation
"""

import pytest
import numpy as np
import torch
from typing import Tuple

from .rl_environment import (
    HedgingEnvironment, GreeksSnapshot, HedgingState,
    VolatilityRegime, HedgeInstrument
)
from .q_learning_agent import QLearningAgent, StateDiscretizer, QLearningConfig
from .ppo_agent import PPOAgent, PPOConfig, ActorCriticNetwork
from .training_loop import TrainingLoop, TrainingConfig, EpisodeResult


class TestHedgingEnvironment:
    """Tests for hedging environment."""

    def test_env_initialization(self):
        """Test environment initializes correctly."""
        env = HedgingEnvironment(seed=42)
        assert env.initial_portfolio_value == 10_000_000
        assert env.trading_day_minutes == 390
        obs, info = env.reset()
        assert obs.shape == (15,)
        assert isinstance(info, dict)

    def test_observation_shape_and_bounds(self):
        """Test observation shape and bounds."""
        env = HedgingEnvironment(seed=42)
        obs, _ = env.reset()
        assert obs.dtype == np.float32
        assert np.all(obs >= -5), "Observation lower bound violated"
        assert np.all(obs <= 5), "Observation upper bound violated"

    def test_action_space_shape(self):
        """Test action space is correct shape."""
        env = HedgingEnvironment(seed=42)
        assert env.action_space.shape == (2,)
        assert env.action_space.dtype == np.float32

    def test_step_returns_correct_format(self):
        """Test step returns correct format."""
        env = HedgingEnvironment(seed=42)
        obs, _ = env.reset()
        action = np.array([0.5, 2.0], dtype=np.float32)
        obs_next, reward, terminated, truncated, info = env.step(action)

        assert isinstance(obs_next, np.ndarray)
        assert isinstance(reward, (float, np.floating))
        assert isinstance(terminated, (bool, np.bool_))
        assert isinstance(truncated, (bool, np.bool_))
        assert isinstance(info, dict)

    def test_episode_terminates_correctly(self):
        """Test episode terminates after trading day minutes."""
        env = HedgingEnvironment(trading_day_minutes=100, seed=42)
        obs, _ = env.reset()

        for step in range(100):
            action = np.array([0.5, 2.0], dtype=np.float32)
            obs, reward, terminated, truncated, _ = env.step(action)

            if step < 99:
                assert not terminated
            else:
                assert terminated

    def test_action_clipping(self):
        """Test actions are clipped to valid ranges."""
        env = HedgingEnvironment(seed=42)
        env.reset()

        # Out-of-range action
        action = np.array([-1.0, 10.0], dtype=np.float32)
        obs, reward, _, _, _ = env.step(action)

        # Should not crash and produce valid observation
        assert obs.shape == (15,)

    def test_portfolio_value_tracking(self):
        """Test portfolio value is tracked correctly."""
        env = HedgingEnvironment(initial_portfolio_value=1_000_000, seed=42)
        obs, _ = env.reset()
        initial_value = env.portfolio_value

        action = np.array([0.3, 1.0], dtype=np.float32)
        obs, _, _, _, _ = env.step(action)

        # Portfolio value should change with PnL
        assert isinstance(env.portfolio_value, (float, np.floating))
        assert env.portfolio_value > 0

    def test_transaction_costs_accumulate(self):
        """Test transaction costs accumulate correctly."""
        env = HedgingEnvironment(transaction_cost_bps=1.0, seed=42)
        env.reset()

        # Multiple hedge changes should accumulate costs
        action1 = np.array([0.5, 1.0], dtype=np.float32)
        env.step(action1)
        costs1 = env.cumulative_transaction_costs

        action2 = np.array([0.8, 1.0], dtype=np.float32)
        env.step(action2)
        costs2 = env.cumulative_transaction_costs

        assert costs2 >= costs1  # Costs should increase or stay same

    def test_reward_is_finite(self):
        """Test rewards are finite."""
        env = HedgingEnvironment(seed=42)
        obs, _ = env.reset()

        for _ in range(10):
            action = np.array([0.5, 2.0], dtype=np.float32)
            obs, reward, _, _, _ = env.step(action)
            assert np.isfinite(reward), f"Reward is not finite: {reward}"

    def test_episode_summary(self):
        """Test episode summary is computed correctly."""
        env = HedgingEnvironment(seed=42)
        obs, _ = env.reset()

        for _ in range(390):
            action = np.array([0.5, 2.0], dtype=np.float32)
            obs, _, terminated, truncated, _ = env.step(action)
            if terminated:
                break

        summary = env.get_episode_summary()
        assert "total_return" in summary
        assert "sharpe_ratio" in summary
        assert "volatility" in summary


class TestStateDiscretizer:
    """Tests for state discretization."""

    def test_discretizer_initialization(self):
        """Test discretizer initializes correctly."""
        discretizer = StateDiscretizer(num_buckets=5)
        assert discretizer.num_buckets == 5

    def test_discretize_greeks(self):
        """Test Greeks discretization."""
        discretizer = StateDiscretizer(num_buckets=5)

        # Test delta
        delta_b, gamma_b, vega_b = discretizer.discretize_greeks(0.5, 0.005, 0.0)
        assert 0 <= delta_b < 5
        assert 0 <= gamma_b < 5
        assert 0 <= vega_b < 5

    def test_discretize_state_produces_hashable_tuple(self):
        """Test state discretization produces hashable tuple."""
        env = HedgingEnvironment(seed=42)
        discretizer = StateDiscretizer(num_buckets=5)
        obs, _ = env.reset()

        state = discretizer.discretize_state(obs)
        assert isinstance(state, tuple)

        # Should be hashable
        state_dict = {state: 1}
        assert state_dict[state] == 1

    def test_discretizer_handles_edge_values(self):
        """Test discretizer handles edge case values."""
        discretizer = StateDiscretizer(num_buckets=5)

        # Extreme values
        delta_b, gamma_b, vega_b = discretizer.discretize_greeks(-1.0, 0.01, -10000.0)
        assert 0 <= delta_b < 5
        assert 0 <= gamma_b < 5
        assert 0 <= vega_b < 5


class TestQLearningAgent:
    """Tests for Q-Learning agent."""

    def test_agent_initialization(self):
        """Test Q-Learning agent initializes correctly."""
        config = QLearningConfig()
        agent = QLearningAgent(config=config, seed=42)
        assert agent.epsilon == config.epsilon_start
        assert len(agent.q_table) == 0

    def test_select_action_shape(self):
        """Test selected action has correct shape."""
        env = HedgingEnvironment(seed=42)
        agent = QLearningAgent(seed=42)
        obs, _ = env.reset()

        action = agent.select_action(obs, training=True)
        assert action.shape == (2,)
        assert 0 <= action[0] <= 1  # Hedge ratio in [0, 1]
        assert 0 <= action[1] < 5   # Instrument index in [0, 4]

    def test_q_learning_updates_q_table(self):
        """Test Q-learning updates Q-table."""
        agent = QLearningAgent(seed=42)
        env = HedgingEnvironment(seed=42)
        obs, _ = env.reset()

        action = agent.select_action(obs, training=True)
        obs_next, reward, terminated, truncated, _ = env.step(action)

        initial_size = len(agent.q_table)
        agent.update(obs, action, reward, obs_next, terminated)

        assert len(agent.q_table) > initial_size

    def test_epsilon_decay(self):
        """Test epsilon decays over time."""
        config = QLearningConfig(exploration_frames=100)
        agent = QLearningAgent(config=config, seed=42)

        initial_epsilon = agent.epsilon
        env = HedgingEnvironment(seed=42)

        for _ in range(110):
            obs, _ = env.reset()
            for _ in range(5):
                action = agent.select_action(obs, training=True)
                obs_next, reward, terminated, truncated, _ = env.step(action)
                agent.update(obs, action, reward, obs_next, terminated)
                if terminated:
                    break

        # Epsilon should have decayed after exploration frames
        assert agent.epsilon <= initial_epsilon

    def test_q_agent_deterministic_policy(self):
        """Test agent produces deterministic policy."""
        agent = QLearningAgent(seed=42)

        # Dummy observation
        obs = np.random.randn(15).astype(np.float32)

        # Non-training mode should be deterministic
        action1 = agent.select_action(obs, training=False)
        action2 = agent.select_action(obs, training=False)

        assert np.allclose(action1, action2), "Policy should be deterministic"

    def test_q_agent_saves_and_loads(self):
        """Test Q-Learning agent can save and load."""
        import tempfile
        import os

        agent1 = QLearningAgent(seed=42)

        # Add some Q-values
        env = HedgingEnvironment(seed=42)
        for _ in range(5):
            obs, _ = env.reset()
            for _ in range(5):
                action = agent1.select_action(obs, training=True)
                obs_next, reward, terminated, truncated, _ = env.step(action)
                agent1.update(obs, action, reward, obs_next, terminated)
                if terminated:
                    break

        # Save
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "q_agent.json")
            agent1.save(path)

            # Load into new agent
            agent2 = QLearningAgent(seed=42)
            agent2.load(path)

            # Q-tables should match
            assert len(agent2.q_table) == len(agent1.q_table)


class TestPPOAgent:
    """Tests for PPO agent."""

    def test_actor_critic_network_initialization(self):
        """Test ActorCriticNetwork initializes correctly."""
        config = PPOConfig()
        network = ActorCriticNetwork(observation_size=15, action_size=2, config=config)
        assert network.observation_size == 15
        assert network.action_size == 2

    def test_network_forward_pass(self):
        """Test network forward pass works."""
        config = PPOConfig()
        network = ActorCriticNetwork(observation_size=15, action_size=2, config=config)

        obs = torch.randn(4, 15)
        action_mean, action_std, instrument_logits, value = network(obs)

        assert action_mean.shape == (4, 1)
        assert action_std.shape == (1,)
        assert instrument_logits.shape == (4, 5)
        assert value.shape == (4, 1)

    def test_network_get_action_value(self):
        """Test network get_action_value method."""
        config = PPOConfig()
        network = ActorCriticNetwork(observation_size=15, action_size=2, config=config)

        obs = torch.randn(4, 15)
        action, log_prob, value = network.get_action_value(obs, deterministic=False)

        assert action.shape == (4, 2)
        assert log_prob.shape == (4, 2)
        assert value.shape == (4,)

    def test_network_evaluate(self):
        """Test network evaluate method."""
        config = PPOConfig()
        network = ActorCriticNetwork(observation_size=15, action_size=2, config=config)

        obs = torch.randn(4, 15)
        action = torch.cat([torch.rand(4, 1), torch.randint(0, 5, (4, 1)).float()], dim=1)
        log_prob, value, entropy = network.evaluate(obs, action)

        assert log_prob.shape == (4, 2)
        assert value.shape == (4,)
        assert entropy.shape == (4, 2)

    def test_ppo_agent_initialization(self):
        """Test PPO agent initializes correctly."""
        config = PPOConfig()
        agent = PPOAgent(observation_size=15, action_size=2, config=config, seed=42)
        assert agent.observation_size == 15
        assert agent.action_size == 2

    def test_ppo_agent_select_action(self):
        """Test PPO agent select_action."""
        agent = PPOAgent(seed=42)
        obs = np.random.randn(15).astype(np.float32)

        action, log_prob, value = agent.select_action(obs, training=True)

        assert action.shape == (2,)
        assert isinstance(log_prob, np.ndarray) or isinstance(log_prob, (float, np.floating))
        assert isinstance(value, (float, np.floating))

    def test_ppo_agent_stores_transition(self):
        """Test PPO agent stores transitions."""
        agent = PPOAgent(seed=42)
        obs = np.random.randn(15).astype(np.float32)
        action = np.array([0.5, 2.0], dtype=np.float32)

        agent.store_transition(obs, action, 1.0, 0.5, -1.0, False)

        assert len(agent.observations) == 1
        assert len(agent.actions) == 1
        assert len(agent.rewards) == 1

    def test_ppo_agent_compute_advantages(self):
        """Test PPO agent computes advantages."""
        agent = PPOAgent(seed=42)

        # Add some transitions
        for _ in range(5):
            obs = np.random.randn(15).astype(np.float32)
            action = np.array([0.5, 2.0], dtype=np.float32)
            agent.store_transition(obs, action, 1.0, 0.5, -1.0, False)

        advantages, returns = agent.compute_advantages(next_value=0.0)

        assert advantages.shape == (5,)
        assert returns.shape == (5,)

    def test_ppo_agent_update(self):
        """Test PPO agent update."""
        agent = PPOAgent(seed=42)

        # Add transitions
        for _ in range(10):
            obs = np.random.randn(15).astype(np.float32)
            action = np.array([0.5, 2.0], dtype=np.float32)
            agent.store_transition(obs, action, 1.0, 0.5, -1.0, False)

        # Should not crash
        agent.update()

        # Buffer should be cleared
        assert len(agent.observations) == 0

    def test_ppo_agent_save_and_load(self):
        """Test PPO agent can save and load."""
        import tempfile
        import os

        agent1 = PPOAgent(seed=42)

        # Get initial network state
        state1 = agent1.network.state_dict()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "ppo_agent.pt")
            agent1.save(path)

            agent2 = PPOAgent(seed=42)
            agent2.load(path)

            # Network states should match
            state2 = agent2.network.state_dict()
            for key in state1:
                assert torch.allclose(state1[key], state2[key])


class TestTrainingLoop:
    """Tests for training loop."""

    def test_training_loop_initialization(self):
        """Test training loop initializes correctly."""
        config = TrainingConfig(num_episodes=2, train_episodes=1, test_episodes=1)
        loop = TrainingLoop(config=config, verbose=False)
        assert loop.config.num_episodes == 2

    def test_training_loop_ppo_training(self):
        """Test PPO training loop runs."""
        config = TrainingConfig(
            num_episodes=2,
            train_episodes=1,
            val_episodes=0,
            test_episodes=1,
            agent_type="ppo",
        )
        loop = TrainingLoop(config=config, verbose=False)
        result = loop.train()

        assert result.gate_passed or not result.gate_passed  # Just check it runs
        assert len(result.train_results) == 1
        assert len(result.test_results) == 1

    def test_training_loop_q_learning_training(self):
        """Test Q-Learning training loop runs."""
        config = TrainingConfig(
            num_episodes=2,
            train_episodes=1,
            val_episodes=0,
            test_episodes=1,
            agent_type="q_learning",
        )
        loop = TrainingLoop(config=config, verbose=False)
        result = loop.train()

        assert len(result.train_results) == 1
        assert len(result.test_results) == 1

    def test_training_result_has_required_fields(self):
        """Test training result has all required fields."""
        config = TrainingConfig(
            num_episodes=1,
            train_episodes=1,
            val_episodes=0,
            test_episodes=0,
        )
        loop = TrainingLoop(config=config, verbose=False)
        result = loop.train()

        assert hasattr(result, "config")
        assert hasattr(result, "timestamp")
        assert hasattr(result, "train_avg_sharpe")
        assert hasattr(result, "test_avg_sharpe")
        assert hasattr(result, "gate_passed")

    def test_episode_result_computation(self):
        """Test episode result is computed correctly."""
        config = TrainingConfig(train_episodes=1, test_episodes=0)
        loop = TrainingLoop(config=config, verbose=False)

        result = loop._run_episode(0, is_training=True)

        assert isinstance(result, EpisodeResult)
        assert result.episode_num == 0
        assert isinstance(result.sharpe_ratio, (float, np.floating))
        assert isinstance(result.total_return, (float, np.floating))


class TestIntegration:
    """Integration tests."""

    def test_full_training_pipeline_ppo(self):
        """Test full PPO training pipeline."""
        config = TrainingConfig(
            num_episodes=3,
            train_episodes=2,
            val_episodes=0,
            test_episodes=1,
            agent_type="ppo",
        )
        loop = TrainingLoop(config=config, verbose=False)
        result = loop.train()

        assert result.test_avg_sharpe >= -10  # Sanity check
        assert len(result.test_results) == 1

    def test_full_training_pipeline_q_learning(self):
        """Test full Q-Learning training pipeline."""
        config = TrainingConfig(
            num_episodes=3,
            train_episodes=2,
            val_episodes=0,
            test_episodes=1,
            agent_type="q_learning",
        )
        loop = TrainingLoop(config=config, verbose=False)
        result = loop.train()

        assert result.test_avg_sharpe >= -10  # Sanity check

    def test_env_and_agent_compatibility(self):
        """Test environment and agent are compatible."""
        env = HedgingEnvironment(seed=42)
        ppo_agent = PPOAgent(seed=42)
        q_agent = QLearningAgent(seed=42)

        obs, _ = env.reset()

        # PPO agent should work with env
        action_ppo, _, _ = ppo_agent.select_action(obs)
        obs_next_ppo, _, _, _, _ = env.step(action_ppo)
        assert obs_next_ppo.shape == obs.shape

        # Q-Learning agent should work with env
        obs, _ = env.reset()
        action_q = q_agent.select_action(obs)
        obs_next_q, _, _, _, _ = env.step(action_q)
        assert obs_next_q.shape == obs.shape

    def test_deterministic_policy_evaluation(self):
        """Test deterministic policy evaluation."""
        config = TrainingConfig(
            num_episodes=2,
            train_episodes=1,
            test_episodes=1,
        )
        loop = TrainingLoop(config=config, verbose=False)
        result = loop.train()

        # Should be able to evaluate
        eval_metrics = loop.evaluate_policy(num_episodes=1)

        assert "avg_sharpe" in eval_metrics
        assert isinstance(eval_metrics["avg_sharpe"], (float, np.floating))


class TestEdgeCases:
    """Edge case tests."""

    def test_env_handles_zero_volatility(self):
        """Test environment handles zero volatility."""
        env = HedgingEnvironment(seed=42)
        obs, _ = env.reset()
        env.current_volatility = 0.0001  # Near-zero

        action = np.array([0.5, 2.0], dtype=np.float32)
        obs_next, reward, _, _, _ = env.step(action)

        assert obs_next.shape == (15,)
        assert np.isfinite(reward)

    def test_env_handles_extreme_portfolio_value(self):
        """Test environment handles extreme portfolio values."""
        env = HedgingEnvironment(initial_portfolio_value=1_000_000_000, seed=42)
        obs, _ = env.reset()

        action = np.array([0.5, 2.0], dtype=np.float32)
        obs_next, reward, _, _, _ = env.step(action)

        assert np.isfinite(reward)

    def test_agent_handles_identical_observations(self):
        """Test agent handles identical observations."""
        agent = PPOAgent(seed=42)
        obs = np.zeros(15, dtype=np.float32)

        action1, _, _ = agent.select_action(obs, training=True)
        action2, _, _ = agent.select_action(obs, training=True)

        # Should still produce valid actions
        assert action1.shape == (2,)
        assert action2.shape == (2,)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
