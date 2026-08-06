"""
RL Dynamic Hedging Module for Group One Trading.

Phase 3 implementation: RL-based position management for real-time hedging.
"""

from .rl_environment import HedgingEnvironment, HedgingState, HedgeAction
from .q_learning_agent import QLearningAgent, StateDiscretizer
from .ppo_agent import PPOAgent, ActorCriticNetwork
from .training_loop import TrainingLoop, TrainingConfig, TrainingResult

__all__ = [
    "HedgingEnvironment",
    "HedgingState",
    "HedgeAction",
    "QLearningAgent",
    "StateDiscretizer",
    "PPOAgent",
    "ActorCriticNetwork",
    "TrainingLoop",
    "TrainingConfig",
    "TrainingResult",
]

__version__ = "0.1.0"
