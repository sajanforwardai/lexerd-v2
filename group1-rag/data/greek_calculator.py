"""Black-Scholes Greeks calculation for options pricing.

Includes:
- Black-Scholes European option pricing
- Greeks: delta, gamma, vega, theta, rho
- IV surface interpolation
- Numerical Greeks (fallback)

Usage:
    calc = GreekCalculator()
    greeks = calc.calculate_greeks(spot=450, strike=450, vol=0.20,
                                   rate=0.04, time_to_exp=0.1, opt_type='CALL')
"""

import numpy as np
from scipy.stats import norm
from dataclasses import dataclass
from typing import Tuple, Optional
import math


@dataclass
class Greeks:
    """Option Greeks."""
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    price: float


class GreekCalculator:
    """Black-Scholes Greeks calculator."""

    def __init__(self):
        self.norm = norm  # Standard normal distribution

    def d1_d2(self, spot: float, strike: float, rate: float, vol: float, time_to_exp: float) -> Tuple[float, float]:
        """Calculate d1 and d2 from Black-Scholes formula."""
        if time_to_exp <= 0 or vol <= 0:
            return 0.0, 0.0

        d1 = (np.log(spot / strike) + (rate + 0.5 * vol ** 2) * time_to_exp) / (vol * np.sqrt(time_to_exp))
        d2 = d1 - vol * np.sqrt(time_to_exp)
        return d1, d2

    def call_price(self, spot: float, strike: float, rate: float, vol: float, time_to_exp: float) -> float:
        """Black-Scholes call price."""
        if time_to_exp <= 0:
            return max(spot - strike, 0)

        d1, d2 = self.d1_d2(spot, strike, rate, vol, time_to_exp)
        call = spot * self.norm.cdf(d1) - strike * np.exp(-rate * time_to_exp) * self.norm.cdf(d2)
        return max(call, 0)

    def put_price(self, spot: float, strike: float, rate: float, vol: float, time_to_exp: float) -> float:
        """Black-Scholes put price."""
        if time_to_exp <= 0:
            return max(strike - spot, 0)

        d1, d2 = self.d1_d2(spot, strike, rate, vol, time_to_exp)
        put = strike * np.exp(-rate * time_to_exp) * self.norm.cdf(-d2) - spot * self.norm.cdf(-d1)
        return max(put, 0)

    def delta(self, spot: float, strike: float, rate: float, vol: float, time_to_exp: float, opt_type: str) -> float:
        """Option delta (rate of change w.r.t. spot price)."""
        if time_to_exp <= 0:
            return 1.0 if opt_type == 'CALL' and spot > strike else (0.0 if opt_type == 'CALL' else -1.0)

        d1, _ = self.d1_d2(spot, strike, rate, vol, time_to_exp)
        if opt_type == 'CALL':
            return self.norm.cdf(d1)
        else:  # PUT
            return self.norm.cdf(d1) - 1.0

    def gamma(self, spot: float, strike: float, rate: float, vol: float, time_to_exp: float) -> float:
        """Gamma (rate of change of delta)."""
        if time_to_exp <= 0 or vol <= 0:
            return 0.0

        d1, _ = self.d1_d2(spot, strike, rate, vol, time_to_exp)
        gamma = self.norm.pdf(d1) / (spot * vol * np.sqrt(time_to_exp))
        return gamma

    def vega(self, spot: float, strike: float, rate: float, vol: float, time_to_exp: float) -> float:
        """Vega (sensitivity to volatility). Per 1% vol change."""
        if time_to_exp <= 0 or vol <= 0:
            return 0.0

        d1, _ = self.d1_d2(spot, strike, rate, vol, time_to_exp)
        vega = spot * self.norm.pdf(d1) * np.sqrt(time_to_exp) / 100.0  # Per 1% vol
        return vega

    def theta(self, spot: float, strike: float, rate: float, vol: float, time_to_exp: float, opt_type: str) -> float:
        """Theta (time decay). Per 1 day."""
        if time_to_exp <= 0:
            return 0.0

        d1, d2 = self.d1_d2(spot, strike, rate, vol, time_to_exp)
        term1 = -spot * self.norm.pdf(d1) * vol / (2.0 * np.sqrt(time_to_exp))

        if opt_type == 'CALL':
            term2 = -rate * strike * np.exp(-rate * time_to_exp) * self.norm.cdf(d2)
            theta = (term1 + term2) / 365.0  # Per 1 day
        else:  # PUT
            term2 = rate * strike * np.exp(-rate * time_to_exp) * self.norm.cdf(-d2)
            theta = (term1 + term2) / 365.0

        return theta

    def rho(self, spot: float, strike: float, rate: float, vol: float, time_to_exp: float, opt_type: str) -> float:
        """Rho (sensitivity to interest rates). Per 1% rate change."""
        if time_to_exp <= 0:
            return 0.0

        d1, d2 = self.d1_d2(spot, strike, rate, vol, time_to_exp)

        if opt_type == 'CALL':
            rho = strike * time_to_exp * np.exp(-rate * time_to_exp) * self.norm.cdf(d2) / 100.0
        else:  # PUT
            rho = -strike * time_to_exp * np.exp(-rate * time_to_exp) * self.norm.cdf(-d2) / 100.0

        return rho

    def calculate_greeks(
        self,
        spot: float,
        strike: float,
        vol: float,
        rate: float = 0.04,
        time_to_exp: float = 0.1,
        opt_type: str = 'CALL'
    ) -> Greeks:
        """Calculate all Greeks for an option."""
        if vol < 0 or time_to_exp < 0:
            raise ValueError("vol and time_to_exp must be positive")

        if opt_type not in ['CALL', 'PUT']:
            raise ValueError("opt_type must be CALL or PUT")

        price = self.call_price(spot, strike, rate, vol, time_to_exp) if opt_type == 'CALL' else self.put_price(spot, strike, rate, vol, time_to_exp)

        return Greeks(
            delta=self.delta(spot, strike, rate, vol, time_to_exp, opt_type),
            gamma=self.gamma(spot, strike, rate, vol, time_to_exp),
            vega=self.vega(spot, strike, rate, vol, time_to_exp),
            theta=self.theta(spot, strike, rate, vol, time_to_exp, opt_type),
            rho=self.rho(spot, strike, rate, vol, time_to_exp, opt_type),
            price=price
        )

    def implied_vol(
        self,
        spot: float,
        strike: float,
        rate: float,
        time_to_exp: float,
        market_price: float,
        opt_type: str = 'CALL',
        initial_guess: float = 0.25,
        max_iterations: int = 100,
        tolerance: float = 1e-6
    ) -> Optional[float]:
        """Calculate implied volatility via Newton-Raphson."""
        if market_price <= 0 or time_to_exp <= 0:
            return None

        vol = initial_guess
        for i in range(max_iterations):
            # Calculate price and vega at current vol estimate
            price = self.call_price(spot, strike, rate, vol, time_to_exp) if opt_type == 'CALL' else self.put_price(spot, strike, rate, vol, time_to_exp)
            vega = self.vega(spot, strike, rate, vol, time_to_exp)

            if abs(vega) < 1e-10:
                return None  # Vega too small

            diff = price - market_price
            if abs(diff) < tolerance:
                return vol

            # Newton-Raphson step
            vol = vol - diff / vega
            vol = max(0.01, min(vol, 3.0))  # Keep vol in reasonable range

        return vol if abs(diff) < tolerance * 100 else None  # Relaxed convergence


class IVSurfaceInterpolator:
    """Interpolate IV across strikes and expirations."""

    def __init__(self, strike_grid: np.ndarray, expiration_grid: np.ndarray, iv_surface: np.ndarray):
        """
        Initialize with strike grid, expiration grid, and IV surface.

        Args:
            strike_grid: 1D array of strikes
            expiration_grid: 1D array of time-to-expiration (in years)
            iv_surface: 2D array of IVs (shape: len(expiration_grid) x len(strike_grid))
        """
        self.strikes = strike_grid
        self.expirations = expiration_grid
        self.surface = iv_surface

    def interpolate(self, strike: float, time_to_exp: float) -> float:
        """Interpolate IV at given strike and expiration."""
        # Clamp to grid
        strike = np.clip(strike, self.strikes.min(), self.strikes.max())
        time_to_exp = np.clip(time_to_exp, self.expirations.min(), self.expirations.max())

        # Simple bilinear interpolation
        strike_idx = np.searchsorted(self.strikes, strike)
        time_idx = np.searchsorted(self.expirations, time_to_exp)

        if strike_idx == 0:
            return self.surface[time_idx, 0]
        if strike_idx >= len(self.strikes):
            return self.surface[time_idx, -1]
        if time_idx == 0:
            return self.surface[0, strike_idx]
        if time_idx >= len(self.expirations):
            return self.surface[-1, strike_idx]

        # Bilinear interpolation
        s0, s1 = self.strikes[strike_idx - 1], self.strikes[strike_idx]
        t0, t1 = self.expirations[time_idx - 1], self.expirations[time_idx]

        v00 = self.surface[time_idx - 1, strike_idx - 1]
        v01 = self.surface[time_idx - 1, strike_idx]
        v10 = self.surface[time_idx, strike_idx - 1]
        v11 = self.surface[time_idx, strike_idx]

        ws = (strike - s0) / (s1 - s0)
        wt = (time_to_exp - t0) / (t1 - t0)

        return (1 - ws) * (1 - wt) * v00 + ws * (1 - wt) * v01 + (1 - ws) * wt * v10 + ws * wt * v11


# Global calculator instance
calc = GreekCalculator()
