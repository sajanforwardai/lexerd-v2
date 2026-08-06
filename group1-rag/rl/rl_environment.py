"""
Gymnasium-compatible environment for dynamic hedging.

State: Greeks (delta, gamma, vega, theta, rho), volatility regime, portfolio value
Action: Hedge ratio (0.0-1.0), instrument selection (5 common hedges)
Reward: Sharpe ratio improvement + transaction cost penalty
Episode: Trading day (390 minutes)
"""

import gymnasium as gym
import numpy as np
from dataclasses import dataclass
from typing import Tuple, Dict, Any, Optional, List
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class VolatilityRegime(Enum):
    """Volatility regime classification."""
    LOW = 0
    MEDIUM = 1
    HIGH = 2


class HedgeInstrument(Enum):
    """Available hedging instruments."""
    PUT_ATM = 0          # At-the-money put
    PUT_OTM_1 = 1        # Out-of-money put (-5%)
    PUT_OTM_2 = 2        # Out-of-money put (-10%)
    VIX_FUTURE = 3       # VIX future
    VARIANCE_SWAP = 4    # Variance swap


@dataclass
class GreeksSnapshot:
    """Current Greeks snapshot."""
    delta: float         # Position delta
    gamma: float         # Position gamma
    vega: float          # Position vega
    theta: float         # Position theta
    rho: float           # Position rho
    spot_price: float    # Current spot price


@dataclass
class HedgingState:
    """State representation for RL agent."""
    greeks: GreeksSnapshot
    volatility: float    # Implied volatility %
    regime: VolatilityRegime
    portfolio_value: float
    hedge_ratios: List[float]  # Current hedge ratios for each instrument
    inventory: float     # Current position inventory
    time_to_eod: int     # Minutes until end of day


@dataclass
class HedgeAction:
    """Action taken by agent."""
    hedge_ratio: float   # Target hedge ratio (0.0-1.0)
    instrument: HedgeInstrument
    size: float         # Position size to hedge


class HedgingEnvironment(gym.Env):
    """
    Gymnasium environment for dynamic hedging.

    Continuous action space: hedge ratio [0, 1]
    Discrete instrument selection: 5 instruments

    Action space: Box((2,), dtype=float32) for [hedge_ratio, instrument_index]
    State space: Box((13,), dtype=float32) for Greeks + vol + regime + portfolio + hedge_ratios + inventory + time
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        initial_portfolio_value: float = 10_000_000,  # $10M portfolio
        trading_day_minutes: int = 390,
        transaction_cost_bps: float = 1.0,  # 1 basis point
        seed: Optional[int] = None,
        verbose: bool = False,
    ):
        """
        Initialize hedging environment.

        Args:
            initial_portfolio_value: Starting portfolio value ($)
            trading_day_minutes: Length of trading day (390 min = 6.5 hours)
            transaction_cost_bps: Transaction cost in basis points
            seed: Random seed for reproducibility
            verbose: Whether to log detailed info
        """
        super().__init__()

        self.initial_portfolio_value = initial_portfolio_value
        self.trading_day_minutes = trading_day_minutes
        self.transaction_cost_bps = transaction_cost_bps / 10000  # Convert bps to decimal
        self.verbose = verbose

        # Seed the environment
        if seed is not None:
            self.np_random = np.random.default_rng(seed)
        else:
            self.np_random = np.random.default_rng()

        # Action space: [hedge_ratio (continuous), instrument_index (discrete)]
        # We'll use Box and wrap the discrete choice
        self.action_space = gym.spaces.Box(
            low=np.array([0.0, 0.0], dtype=np.float32),
            high=np.array([1.0, 4.99], dtype=np.float32),  # 5 instruments (0-4)
            dtype=np.float32
        )

        # Observation space: [delta, gamma, vega, theta, rho, volatility,
        #                     regime, portfolio_value_normalized,
        #                     hedge_ratio_1, hedge_ratio_2, hedge_ratio_3,
        #                     hedge_ratio_4, hedge_ratio_5, inventory, time_remaining]
        # Normalized to roughly [-5, 5] for stable learning
        self.observation_space = gym.spaces.Box(
            low=-5.0,
            high=5.0,
            shape=(15,),
            dtype=np.float32
        )

        # Initialize state
        self.reset()

    def reset(self, seed: Optional[int] = None, options: Optional[Dict] = None):
        """
        Reset environment to initial state.

        Args:
            seed: Random seed
            options: Additional options (not used)

        Returns:
            observation: Initial observation
            info: Additional info dict
        """
        if seed is not None:
            self.np_random = np.random.default_rng(seed)

        # Initialize Greeks randomly (realistic ranges)
        self.current_greeks = GreeksSnapshot(
            delta=self.np_random.uniform(-0.5, 0.5),      # Delta: -0.5 to +0.5
            gamma=self.np_random.uniform(0.001, 0.01),    # Gamma: positive
            vega=self.np_random.uniform(-5000, 5000),     # Vega: -5k to +5k notional
            theta=self.np_random.uniform(-1000, 1000),    # Theta: daily decay
            rho=self.np_random.uniform(-500, 500),        # Rho: rate sensitivity
            spot_price=self.np_random.uniform(100, 500),  # Spot: 100-500
        )

        # Initialize volatility randomly
        self.current_volatility = self.np_random.uniform(0.15, 0.35)  # 15% - 35% IV

        # Initialize regime based on volatility
        if self.current_volatility < 0.20:
            self.current_regime = VolatilityRegime.LOW
        elif self.current_volatility < 0.27:
            self.current_regime = VolatilityRegime.MEDIUM
        else:
            self.current_regime = VolatilityRegime.HIGH

        # Initialize portfolio state
        self.portfolio_value = self.initial_portfolio_value
        self.unrealized_pnl = 0.0
        self.hedge_ratios = [0.0] * 5  # Initial hedge ratios all zero
        self.inventory = self.np_random.uniform(0.5, 2.0)  # Position size (in millions)

        # Time tracking
        self.current_minute = 0
        self.episode_returns = []
        self.episode_actions = []
        self.episode_rewards = []
        self.cumulative_transaction_costs = 0.0

        return self._get_observation(), {}

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """
        Execute one step in the environment.

        Args:
            action: [hedge_ratio (0-1), instrument_index (0-4)]

        Returns:
            observation, reward, terminated, truncated, info
        """
        # Parse action
        hedge_ratio = np.clip(action[0], 0.0, 1.0)
        instrument_idx = int(np.clip(action[1], 0, 4))
        instrument = HedgeInstrument(instrument_idx)

        # Calculate transaction cost
        prev_hedge_ratio = self.hedge_ratios[instrument_idx]
        hedge_change = abs(hedge_ratio - prev_hedge_ratio)
        transaction_cost = self.inventory * self.transaction_cost_bps * hedge_change
        self.cumulative_transaction_costs += transaction_cost

        # Update hedge position
        self.hedge_ratios[instrument_idx] = hedge_ratio

        # Simulate market movement
        self._simulate_market_movement()

        # Calculate daily return (Sharpe component)
        daily_return = self._calculate_daily_return()

        # Calculate reward
        reward = self._calculate_reward(daily_return, transaction_cost)

        # Track episode data
        self.episode_returns.append(daily_return)
        self.episode_actions.append(hedge_ratio)
        self.episode_rewards.append(reward)

        # Update time
        self.current_minute += 1

        # Determine if episode is done
        terminated = self.current_minute >= self.trading_day_minutes
        truncated = False  # No early truncation

        info = {
            "portfolio_value": self.portfolio_value,
            "cumulative_cost": self.cumulative_transaction_costs,
            "daily_return": daily_return,
            "hedge_ratio": hedge_ratio,
            "instrument": instrument.name,
        }

        if self.verbose and self.current_minute % 60 == 0:
            logger.info(f"Minute {self.current_minute}: PnL={self.unrealized_pnl:.2f}, "
                       f"Hedge={hedge_ratio:.2f}, Costs={self.cumulative_transaction_costs:.2f}")

        observation = self._get_observation()

        return observation, reward, terminated, truncated, info

    def _simulate_market_movement(self):
        """Simulate realistic market movement for one minute."""
        # Simulate spot price movement (GBM-like)
        drift = 0.0001  # Small positive drift
        volatility = self.current_volatility / np.sqrt(252 * 390)  # Minute-level volatility
        price_change = drift + volatility * self.np_random.standard_normal()

        self.current_greeks.spot_price *= (1 + price_change)

        # Update Greeks based on market movement
        # Delta increases with spot price (simplified)
        self.current_greeks.delta += price_change * 0.5  # Delta drift
        self.current_greeks.delta = np.clip(self.current_greeks.delta, -1.0, 1.0)

        # Gamma decay and realignment
        self.current_greeks.gamma = max(0.001, self.current_greeks.gamma - 0.0001)

        # Theta decay (negative)
        self.current_greeks.theta -= 10  # ~$10 daily decay

        # Volatility mean reversion
        vol_drift = 0.25 - self.current_volatility  # Mean revert to 25%
        vol_change = 0.01 * vol_drift + 0.02 * self.np_random.standard_normal()
        self.current_volatility = np.clip(self.current_volatility + vol_change, 0.10, 0.50)

        # Update regime
        if self.current_volatility < 0.20:
            self.current_regime = VolatilityRegime.LOW
        elif self.current_volatility < 0.27:
            self.current_regime = VolatilityRegime.MEDIUM
        else:
            self.current_regime = VolatilityRegime.HIGH

        # Simulate vega P&L
        self.unrealized_pnl += self.current_greeks.vega * (self.current_volatility - 0.25) * 0.001
        self.portfolio_value = self.initial_portfolio_value + self.unrealized_pnl

    def _calculate_daily_return(self) -> float:
        """Calculate return accounting for hedge effectiveness."""
        # Unhedged P&L
        unhedged_pnl = self.unrealized_pnl

        # Hedge effectiveness: reduces delta exposure based on hedge ratio
        hedge_effectiveness = sum(self.hedge_ratios) * 0.5  # Each hedge removes some risk
        hedged_pnl = unhedged_pnl * (1 - hedge_effectiveness)

        # Return calculation
        portfolio_return = hedged_pnl / self.initial_portfolio_value
        return portfolio_return

    def _calculate_reward(self, daily_return: float, transaction_cost: float) -> float:
        """
        Calculate reward for the agent.

        Reward = Sharpe ratio component + transaction cost penalty
        """
        # Sharpe component: reward positive returns, penalize losses
        if daily_return > 0:
            sharpe_component = daily_return * 100  # Scale up positive returns
        else:
            sharpe_component = daily_return * 50   # Less penalty for losses

        # Transaction cost penalty (in bps)
        cost_penalty = -transaction_cost / self.initial_portfolio_value * 10000

        # Hedge efficiency bonus: reward reducing volatility without excessive hedging
        avg_hedge_ratio = np.mean(self.hedge_ratios)
        if 0.3 <= avg_hedge_ratio <= 0.7:  # Optimal hedge range
            hedge_bonus = 0.5
        else:
            hedge_bonus = -0.2

        reward = sharpe_component + cost_penalty + hedge_bonus

        return reward

    def _get_observation(self) -> np.ndarray:
        """Convert current state to normalized observation."""
        # Normalize Greeks (divide by typical ranges)
        obs_delta = np.clip(self.current_greeks.delta / 1.0, -5, 5)
        obs_gamma = np.clip(self.current_greeks.gamma / 0.01, 0, 5)
        obs_vega = np.clip(self.current_greeks.vega / 10000, -5, 5)
        obs_theta = np.clip(self.current_greeks.theta / 1000, -5, 5)
        obs_rho = np.clip(self.current_greeks.rho / 1000, -5, 5)

        # Volatility
        obs_vol = (self.current_volatility - 0.25) / 0.15  # Centered on 25%

        # Regime (as numeric)
        obs_regime = float(self.current_regime.value) - 1  # -1, 0, 1 for LOW, MED, HIGH

        # Portfolio value (normalized)
        obs_portfolio = (self.portfolio_value - self.initial_portfolio_value) / self.initial_portfolio_value * 10

        # Hedge ratios
        obs_hedge_ratios = np.array(self.hedge_ratios)

        # Inventory
        obs_inventory = (self.inventory - 1.0) / 1.0

        # Time remaining
        obs_time = (self.trading_day_minutes - self.current_minute) / self.trading_day_minutes

        # Combine all observations
        observation = np.array([
            obs_delta,
            obs_gamma,
            obs_vega,
            obs_theta,
            obs_rho,
            obs_vol,
            obs_regime,
            obs_portfolio,
            *obs_hedge_ratios,  # 5 values
            obs_inventory,
            obs_time,
        ], dtype=np.float32)

        # Ensure we have 15 elements (1+1+1+1+1+1+1+1+5+1+1 = 15)
        assert observation.shape == (15,), f"Observation shape mismatch: {observation.shape}"

        return np.clip(observation, -5, 5).astype(np.float32)

    def get_episode_summary(self) -> Dict[str, float]:
        """Get summary statistics for current episode."""
        if not self.episode_returns:
            return {}

        returns = np.array(self.episode_returns)
        total_return = np.sum(returns)
        mean_return = np.mean(returns)
        std_return = np.std(returns) if len(returns) > 1 else 0

        # Sharpe ratio (daily)
        sharpe = mean_return / (std_return + 1e-6) * np.sqrt(252) if std_return > 0 else 0

        return {
            "total_return": total_return * 100,
            "mean_return": mean_return * 100,
            "volatility": std_return * 100 * np.sqrt(252),
            "sharpe_ratio": sharpe,
            "max_reward": np.max(self.episode_rewards),
            "avg_reward": np.mean(self.episode_rewards),
            "transaction_costs": self.cumulative_transaction_costs,
            "final_portfolio_value": self.portfolio_value,
        }

    def render(self, mode: str = "human"):
        """Render current state (optional)."""
        summary = self.get_episode_summary()
        logger.info(f"Episode Summary: {summary}")
