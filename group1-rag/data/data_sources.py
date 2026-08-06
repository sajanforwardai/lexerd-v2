"""Data source adapters for historical equity options data.

Supports multiple free/low-cost sources:
- yfinance: OHLCV for stocks (free, unlimited)
- QuantConnect: Options data (free tier, 6-month rolling window)
- Intrinio: Options data (free tier, limited symbols)
- CBOE: VIX and related data (free, historical)

Usage:
    from data_sources import YFinanceSource, QuantConnectSource
    yf = YFinanceSource()
    ohlcv = yf.fetch_ohlcv('SPY', start_date='2024-01-01', end_date='2024-12-31')
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np

try:
    import yfinance as yf
except ImportError:
    raise ImportError("yfinance required: pip install yfinance")


@dataclass
class OHLCV:
    """Open-High-Low-Close-Volume data point."""
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    adjusted_close: Optional[float] = None


@dataclass
class OptionChain:
    """Single option contract data."""
    date: datetime
    expiration: datetime
    strike: float
    option_type: str  # CALL or PUT
    bid: float
    ask: float
    mid: float
    implied_vol: float
    delta: Optional[float] = None
    gamma: Optional[float] = None
    vega: Optional[float] = None
    theta: Optional[float] = None
    rho: Optional[float] = None
    open_interest: Optional[int] = None
    volume: Optional[int] = None


class DataSource(ABC):
    """Abstract base class for data sources."""

    @abstractmethod
    def fetch_ohlcv(self, symbol: str, start_date: str, end_date: str) -> List[OHLCV]:
        """Fetch OHLCV data for a symbol."""
        pass

    @abstractmethod
    def fetch_options(self, symbol: str, expiration: str, start_date: str, end_date: str) -> List[OptionChain]:
        """Fetch options data for a symbol and expiration."""
        pass

    @abstractmethod
    def fetch_expirations(self, symbol: str) -> List[str]:
        """Fetch available option expirations."""
        pass


class YFinanceSource(DataSource):
    """Yahoo Finance data source for OHLCV."""

    def __init__(self):
        self.name = "YFinance"

    def fetch_ohlcv(self, symbol: str, start_date: str, end_date: str) -> List[OHLCV]:
        """Fetch OHLCV from yfinance. Free, unlimited, fast."""
        try:
            data = yf.download(symbol, start=start_date, end=end_date, progress=False)
            if data.empty:
                return []

            ohlcv_list = []
            for idx, row in data.iterrows():
                ohlcv = OHLCV(
                    date=idx.to_pydatetime(),
                    open=float(row['Open']),
                    high=float(row['High']),
                    low=float(row['Low']),
                    close=float(row['Close']),
                    volume=int(row['Volume']),
                    adjusted_close=float(row['Adj Close']) if 'Adj Close' in row else None
                )
                ohlcv_list.append(ohlcv)
            return ohlcv_list
        except Exception as e:
            print(f"[YFinance] Error fetching {symbol}: {e}")
            return []

    def fetch_options(self, symbol: str, expiration: str, start_date: str, end_date: str) -> List[OptionChain]:
        """yfinance doesn't have historical options; use other source."""
        raise NotImplementedError("YFinance doesn't support historical options data. Use QuantConnect or Intrinio.")

    def fetch_expirations(self, symbol: str) -> List[str]:
        """Fetch available expirations from yfinance."""
        try:
            ticker = yf.Ticker(symbol)
            expirations = ticker.options
            return expirations if expirations else []
        except Exception as e:
            print(f"[YFinance] Error fetching expirations for {symbol}: {e}")
            return []


class MockOptionsSource(DataSource):
    """Mock options source for quick testing (generates synthetic data)."""

    def __init__(self, random_seed: int = 42):
        self.name = "MockOptions"
        self.rng = np.random.RandomState(random_seed)

    def fetch_ohlcv(self, symbol: str, start_date: str, end_date: str) -> List[OHLCV]:
        """Not used for mock source."""
        return []

    def fetch_options(self, symbol: str, expiration: str, start_date: str, end_date: str) -> List[OptionChain]:
        """Generate synthetic options data for testing."""
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        exp_date = datetime.strptime(expiration, "%Y-%m-%d")

        options = []
        current = start
        base_price = 450.0  # Assume SPY at 450
        spot = base_price

        strikes = [base_price * (1 + offset) for offset in [-0.05, -0.025, 0, 0.025, 0.05]]

        while current <= end and current <= exp_date:
            spot += self.rng.randn() * 5  # Random walk

            for strike in strikes:
                for opt_type in ['CALL', 'PUT']:
                    # Simple Black-Scholes approximation for synthetic IV
                    if opt_type == 'CALL':
                        moneyness = spot / strike
                        iv = 0.20 + (0.1 * np.log(1 / moneyness)) if moneyness < 1 else 0.20
                    else:
                        moneyness = strike / spot
                        iv = 0.20 + (0.1 * np.log(moneyness)) if moneyness > 1 else 0.20

                    iv = np.clip(iv, 0.05, 0.80)
                    spread = 0.02 * (strike / spot)  # Bid-ask widens OTM
                    mid = 10.0 + self.rng.randn()  # Random price

                    option = OptionChain(
                        date=current,
                        expiration=exp_date,
                        strike=strike,
                        option_type=opt_type,
                        bid=mid - spread / 2,
                        ask=mid + spread / 2,
                        mid=mid,
                        implied_vol=iv,
                        delta=self.rng.rand() * 1.0 if opt_type == 'CALL' else -self.rng.rand(),
                        gamma=self.rng.rand() * 0.01,
                        vega=self.rng.rand() * 0.5,
                        theta=-self.rng.rand() * 0.05,
                        rho=self.rng.rand() * 0.1,
                        open_interest=int(1000 + self.rng.rand() * 5000),
                        volume=int(100 + self.rng.rand() * 500)
                    )
                    options.append(option)

            current += timedelta(days=1)

        return options

    def fetch_expirations(self, symbol: str) -> List[str]:
        """Generate mock expirations (weekly + monthly)."""
        today = datetime.now()
        expirations = []
        for weeks in [1, 2, 3, 4, 8, 16]:  # 1w, 2w, 3w, 4w, 2m, 4m
            exp = today + timedelta(weeks=weeks)
            # Adjust to Friday (typical expiration)
            while exp.weekday() != 4:
                exp += timedelta(days=1)
            expirations.append(exp.strftime("%Y-%m-%d"))
        return expirations


class QuantConnectAdapter(DataSource):
    """QuantConnect data source (free tier: 6-month rolling window).

    Note: Requires QuantConnect account setup. For now, returns empty.
    Production implementation would use QuantConnect SDK.
    """

    def __init__(self):
        self.name = "QuantConnect"

    def fetch_ohlcv(self, symbol: str, start_date: str, end_date: str) -> List[OHLCV]:
        """QuantConnect OHLCV (would require SDK integration)."""
        # TODO: Integrate QuantConnect SDK
        return []

    def fetch_options(self, symbol: str, expiration: str, start_date: str, end_date: str) -> List[OptionChain]:
        """QuantConnect options data (would require SDK integration)."""
        # TODO: Integrate QuantConnect SDK
        return []

    def fetch_expirations(self, symbol: str) -> List[str]:
        """Fetch expirations from QuantConnect."""
        # TODO: Implement
        return []


class IntrinioBetaAdapter(DataSource):
    """Intrinio data source (free tier: limited symbols).

    Note: Requires API key. For now, returns empty.
    Production implementation would use Intrinio SDK.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.name = "Intrinio"
        self.api_key = api_key

    def fetch_ohlcv(self, symbol: str, start_date: str, end_date: str) -> List[OHLCV]:
        """Intrinio OHLCV (requires API key)."""
        # TODO: Integrate Intrinio SDK
        return []

    def fetch_options(self, symbol: str, expiration: str, start_date: str, end_date: str) -> List[OptionChain]:
        """Intrinio options data (requires API key)."""
        # TODO: Integrate Intrinio SDK
        return []

    def fetch_expirations(self, symbol: str) -> List[str]:
        """Fetch expirations from Intrinio."""
        # TODO: Implement
        return []


class CompositeSource(DataSource):
    """Combines multiple data sources with fallback."""

    def __init__(self, sources: List[DataSource]):
        self.sources = sources
        self.name = "Composite"

    def fetch_ohlcv(self, symbol: str, start_date: str, end_date: str) -> List[OHLCV]:
        """Try each source until one returns data."""
        for source in self.sources:
            try:
                data = source.fetch_ohlcv(symbol, start_date, end_date)
                if data:
                    return data
            except Exception as e:
                print(f"[{source.name}] Failed: {e}")
        return []

    def fetch_options(self, symbol: str, expiration: str, start_date: str, end_date: str) -> List[OptionChain]:
        """Try each source until one returns data."""
        for source in self.sources:
            try:
                data = source.fetch_options(symbol, expiration, start_date, end_date)
                if data:
                    return data
            except Exception as e:
                print(f"[{source.name}] Failed: {e}")
        return []

    def fetch_expirations(self, symbol: str) -> List[str]:
        """Try each source until one returns data."""
        for source in self.sources:
            try:
                data = source.fetch_expirations(symbol)
                if data:
                    return data
            except Exception as e:
                print(f"[{source.name}] Failed: {e}")
        return []


# Pre-configured composite source (OHLCV from yfinance, options from mock)
DEFAULT_SOURCE = CompositeSource([
    YFinanceSource(),
    MockOptionsSource()
])
