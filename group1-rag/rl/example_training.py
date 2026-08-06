"""
End-to-end example: Training RL dynamic hedging system.

Demonstrates:
1. Environment setup
2. Agent initialization
3. Training with both Q-Learning and PPO
4. Policy evaluation
5. Results analysis
"""

import logging
import numpy as np
from pathlib import Path

from rl_environment import HedgingEnvironment
from q_learning_agent import QLearningAgent, QLearningConfig
from ppo_agent import PPOAgent, PPOConfig
from training_loop import TrainingLoop, TrainingConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def example_q_learning_training():
    """Example: Train Q-Learning baseline agent."""
    logger.info("=" * 80)
    logger.info("Q-LEARNING TRAINING EXAMPLE")
    logger.info("=" * 80)

    # Configuration
    config = TrainingConfig(
        num_episodes=50,
        train_episodes=40,
        val_episodes=5,
        test_episodes=5,
        agent_type="q_learning",
        target_sharpe=1.0,  # Q-Learning baseline target
        seed=42,
    )

    # Create training loop
    loop = TrainingLoop(config=config, verbose=True)

    # Train
    result = loop.train()

    # Print results
    logger.info("\nQ-LEARNING RESULTS:")
    logger.info(f"  Train Sharpe: {result.train_avg_sharpe:.3f}")
    logger.info(f"  Val Sharpe: {result.val_avg_sharpe:.3f}")
    logger.info(f"  Test Sharpe: {result.test_avg_sharpe:.3f} (target: {config.target_sharpe})")
    logger.info(f"  Converged: {result.converged}")
    logger.info(f"  Gate Passed: {result.gate_passed}")

    # Save agent
    if config.agent_type == "q_learning":
        agent_path = "/workspace/group1-rag/rl/models/q_learning_agent.json"
        Path(agent_path).parent.mkdir(parents=True, exist_ok=True)
        loop.agent.save(agent_path)
        logger.info(f"  Agent saved to {agent_path}")

    return result


def example_ppo_training():
    """Example: Train PPO production agent."""
    logger.info("=" * 80)
    logger.info("PPO TRAINING EXAMPLE")
    logger.info("=" * 80)

    # Configuration
    ppo_config = PPOConfig(
        hidden_size=128,
        learning_rate=3e-4,
        entropy_coef=0.01,
    )

    config = TrainingConfig(
        num_episodes=100,
        train_episodes=80,
        val_episodes=10,
        test_episodes=10,
        agent_type="ppo",
        ppo_config=ppo_config,
        target_sharpe=1.5,  # PPO target (higher than Q-Learning)
        seed=42,
    )

    # Create training loop
    loop = TrainingLoop(config=config, verbose=True)

    # Train
    result = loop.train()

    # Print results
    logger.info("\nPPO RESULTS:")
    logger.info(f"  Train Sharpe: {result.train_avg_sharpe:.3f}")
    logger.info(f"  Val Sharpe: {result.val_avg_sharpe:.3f}")
    logger.info(f"  Test Sharpe: {result.test_avg_sharpe:.3f} (target: {config.target_sharpe})")
    logger.info(f"  Test Sharpe Range: [{result.test_min_sharpe:.3f}, {result.test_max_sharpe:.3f}]")
    logger.info(f"  Converged: {result.converged} (episode {result.convergence_episode})")
    logger.info(f"  Gate Passed: {result.gate_passed}")

    # Print test episode details
    logger.info("\n  Test Episode Details:")
    for ep in result.test_results[:3]:  # First 3 episodes
        logger.info(f"    Episode {ep.episode_num}: Sharpe={ep.sharpe_ratio:.3f}, "
                   f"Return={ep.total_return*100:.2f}%, Costs=${ep.cumulative_costs:.0f}")

    # Save agent
    agent_path = "/workspace/group1-rag/rl/models/ppo_agent.pt"
    Path(agent_path).parent.mkdir(parents=True, exist_ok=True)
    loop.agent.save(agent_path)
    logger.info(f"  Agent saved to {agent_path}")

    return result


def example_policy_evaluation():
    """Example: Evaluate trained policy."""
    logger.info("=" * 80)
    logger.info("POLICY EVALUATION EXAMPLE")
    logger.info("=" * 80)

    # Create minimal training loop
    config = TrainingConfig(
        num_episodes=5,
        train_episodes=1,
        test_episodes=0,
        agent_type="ppo",
        seed=42,
    )

    loop = TrainingLoop(config=config, verbose=False)

    # Train briefly
    loop.train()

    # Evaluate policy on fresh episodes
    logger.info("Evaluating policy on 10 fresh episodes...")
    eval_result = loop.evaluate_policy(num_episodes=10, deterministic=True)

    logger.info("\nEVALUATION RESULTS:")
    logger.info(f"  Avg Sharpe: {eval_result['avg_sharpe']:.3f}")
    logger.info(f"  Sharpe Range: [{eval_result['min_sharpe']:.3f}, {eval_result['max_sharpe']:.3f}]")
    logger.info(f"  Std Dev: {eval_result['std_sharpe']:.3f}")
    logger.info(f"  Avg Return: {eval_result['avg_return']*100:.2f}%")
    logger.info(f"  Avg Volatility: {eval_result['avg_volatility']*100:.2f}%")

    return eval_result


def example_single_episode():
    """Example: Run a single episode with manual environment control."""
    logger.info("=" * 80)
    logger.info("SINGLE EPISODE EXAMPLE")
    logger.info("=" * 80)

    # Create environment
    env = HedgingEnvironment(
        initial_portfolio_value=10_000_000,
        transaction_cost_bps=1.0,
        seed=42,
        verbose=True,
    )

    # Create agent
    agent = PPOAgent(seed=42)

    # Run episode
    observation, _ = env.reset()
    done = False
    episode_reward = 0.0
    step_count = 0

    logger.info("Starting episode...")
    while not done:
        # Agent selects action
        action, _, _ = agent.select_action(observation, training=False)

        # Take step in environment
        observation, reward, terminated, truncated, info = env.step(action)
        done = terminated or truncated
        episode_reward += reward
        step_count += 1

        if step_count % 100 == 0:
            logger.info(f"  Step {step_count}: Reward={reward:.4f}, PV=${info['portfolio_value']:.0f}")

    # Get summary
    summary = env.get_episode_summary()

    logger.info("\nEpisode Summary:")
    logger.info(f"  Total Steps: {step_count}")
    logger.info(f"  Total Return: {summary['total_return']:.4f}%")
    logger.info(f"  Sharpe Ratio: {summary['sharpe_ratio']:.3f}")
    logger.info(f"  Volatility: {summary['volatility']:.3f}%")
    logger.info(f"  Max Reward: {summary['max_reward']:.4f}")
    logger.info(f"  Avg Reward: {summary['avg_reward']:.4f}")
    logger.info(f"  Transaction Costs: ${summary['transaction_costs']:.2f}")
    logger.info(f"  Final Portfolio Value: ${summary['final_portfolio_value']:.0f}")

    return summary


def example_compare_agents():
    """Example: Compare Q-Learning vs PPO baseline performance."""
    logger.info("=" * 80)
    logger.info("AGENT COMPARISON EXAMPLE")
    logger.info("=" * 80)

    # Quick training for both agents
    config_shared = TrainingConfig(
        num_episodes=20,
        train_episodes=15,
        test_episodes=5,
        seed=42,
    )

    results = {}

    for agent_type in ["q_learning", "ppo"]:
        logger.info(f"\nTraining {agent_type.upper()}...")
        config = TrainingConfig(
            **{**config_shared.__dict__, "agent_type": agent_type}
        )
        loop = TrainingLoop(config=config, verbose=False)
        result = loop.train()
        results[agent_type] = result

    # Compare
    logger.info("\n" + "=" * 80)
    logger.info("COMPARISON RESULTS")
    logger.info("=" * 80)

    for agent_type, result in results.items():
        logger.info(f"\n{agent_type.upper()}:")
        logger.info(f"  Train Sharpe: {result.train_avg_sharpe:.3f}")
        logger.info(f"  Test Sharpe: {result.test_avg_sharpe:.3f}")
        logger.info(f"  Test Range: [{result.test_min_sharpe:.3f}, {result.test_max_sharpe:.3f}]")
        logger.info(f"  Gate Passed: {result.gate_passed}")

    # Calculate improvement
    ppo_sharpe = results["ppo"].test_avg_sharpe
    q_sharpe = results["q_learning"].test_avg_sharpe
    improvement = (ppo_sharpe - q_sharpe) / abs(q_sharpe) * 100 if q_sharpe != 0 else 0

    logger.info(f"\nPPO Improvement over Q-Learning: {improvement:.1f}%")

    return results


if __name__ == "__main__":
    # Run examples
    print("\n" + "=" * 80)
    print("RL DYNAMIC HEDGING - EXAMPLE TRAINING SUITE")
    print("=" * 80)

    # Example 1: Single episode
    logger.info("\n>>> Running SINGLE EPISODE example...")
    example_single_episode()

    # Example 2: Q-Learning training
    logger.info("\n>>> Running Q-LEARNING TRAINING example...")
    q_result = example_q_learning_training()

    # Example 3: PPO training
    logger.info("\n>>> Running PPO TRAINING example...")
    ppo_result = example_ppo_training()

    # Example 4: Policy evaluation
    logger.info("\n>>> Running POLICY EVALUATION example...")
    eval_result = example_policy_evaluation()

    # Example 5: Agent comparison
    logger.info("\n>>> Running AGENT COMPARISON example...")
    comparison = example_compare_agents()

    logger.info("\n" + "=" * 80)
    logger.info("ALL EXAMPLES COMPLETED")
    logger.info("=" * 80)
