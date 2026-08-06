"""Example backtest using Group One Trading RAG + Historical Data Pipeline.

Scenario: Test gamma scalping strategy across different vol regimes.

Usage:
    python3 example_backtest.py
"""

from datetime import datetime, timedelta
import sys
import os

# Add parent paths for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from data_sources import DEFAULT_SOURCE, MockOptionsSource
from data_ingestion import DataIngestionPipeline
from greek_calculator import GreekCalculator


class SimpleBacktest:
    """Simple backtest harness using RAG data."""

    def __init__(self):
        self.pipeline = DataIngestionPipeline()
        self.greeks = GreekCalculator()
        self.positions = {}
        self.pnl = 0.0

    def load_data(self, symbol: str, start_date: str, end_date: str):
        """Load historical data."""
        print(f"\n[Backtest] Loading data for {symbol} ({start_date} to {end_date})")

        # Load OHLCV
        ohlcv = DEFAULT_SOURCE.fetch_ohlcv(symbol, start_date, end_date)
        print(f"  Loaded {len(ohlcv)} daily prices")

        # Load options
        expirations = DEFAULT_SOURCE.fetch_expirations(symbol)
        print(f"  Available expirations: {expirations[:3]}...")

        return ohlcv, expirations

    def run_gamma_scalping(self, symbol: str, start_date: str, end_date: str):
        """Backtest gamma scalping strategy.

        Strategy:
        1. Each Monday: sell 10 ATM straddles (2 weeks out)
        2. Daily: delta-hedge at +/-0.50 threshold
        3. Exit: 50% profit or T-2 days before expiration
        """
        print("\n" + "=" * 60)
        print(f"Gamma Scalping Backtest: {symbol}")
        print("=" * 60)

        # Load data
        ohlcv, expirations = self.load_data(symbol, start_date, end_date)

        if not ohlcv:
            print("ERROR: No data loaded")
            return None

        # Backtest parameters
        spot_init = ohlcv[0].close if ohlcv else 450
        rate = 0.04
        position = None
        pnl_history = []
        trades = []

        print(f"\nStarting backtest:")
        print(f"  Initial spot: ${spot_init:.2f}")
        print(f"  Strategy: Sell ATM straddles, delta hedge daily")
        print(f"  Backtest period: {start_date} to {end_date}")

        for i, day in enumerate(ohlcv):
            # Entry logic: sell straddle on Mondays (day % 5 == 0)
            if i % 5 == 0 and position is None:
                # Find 2-week expiration
                exp_idx = min(10, len(expirations) - 1)  # ~2 weeks out
                expiration = expirations[exp_idx]

                # Calculate Greeks for ATM straddle
                time_to_exp = 14 / 365.0  # 2 weeks
                greeks_call = self.greeks.calculate_greeks(
                    spot=day.close, strike=day.close, vol=0.25, rate=rate, time_to_exp=time_to_exp, opt_type='CALL'
                )
                greeks_put = self.greeks.calculate_greeks(
                    spot=day.close, strike=day.close, vol=0.25, rate=rate, time_to_exp=time_to_exp, opt_type='PUT'
                )

                straddle_price = greeks_call.price + greeks_put.price
                position = {
                    'entry_day': i,
                    'entry_spot': day.close,
                    'entry_price': straddle_price,
                    'entry_delta': greeks_call.delta + greeks_put.delta,
                    'expiration': expiration,
                    'strikes': day.close,
                    'gamma': greeks_call.gamma + greeks_put.gamma,
                    'delta_hedge_price': None,
                    'pnl': 0.0
                }
                trades.append({
                    'day': i,
                    'action': 'SELL_STRADDLE',
                    'price': straddle_price,
                    'spot': day.close
                })

            # Exit logic: 50% profit or T-2
            elif position is not None:
                time_to_exp = (datetime.strptime(position['expiration'], '%Y-%m-%d') - day.date).days / 365.0
                greeks_call = self.greeks.calculate_greeks(
                    spot=day.close, strike=position['strikes'], vol=0.25, rate=rate, time_to_exp=time_to_exp, opt_type='CALL'
                )
                greeks_put = self.greeks.calculate_greeks(
                    spot=day.close, strike=position['strikes'], vol=0.25, rate=rate, time_to_exp=time_to_exp, opt_type='PUT'
                )

                current_price = greeks_call.price + greeks_put.price
                current_pnl = position['entry_price'] - current_price  # Short straddle P&L
                position['pnl'] = current_pnl

                # Exit if 50% profit or T-2
                exit_trigger = (current_pnl > position['entry_price'] * 0.50) or time_to_exp < 2/365.0

                if exit_trigger:
                    pnl = current_pnl
                    self.pnl += pnl
                    pnl_history.append(pnl)

                    trades.append({
                        'day': i,
                        'action': 'CLOSE_STRADDLE',
                        'price': current_price,
                        'spot': day.close,
                        'pnl': pnl
                    })

                    position = None

            pnl_history.append(position['pnl'] if position else 0)

        # Report
        print("\n" + "-" * 60)
        print("Backtest Results")
        print("-" * 60)
        print(f"Total trades: {len(trades) // 2}")  # Divide by 2 (entry + exit pairs)
        print(f"Total P&L: ${self.pnl:.2f}")
        if pnl_history:
            print(f"Max P&L: ${max(pnl_history):.2f}")
            print(f"Min P&L: ${min(pnl_history):.2f}")
            print(f"Avg P&L per day: ${sum(pnl_history) / len(pnl_history):.2f}")

        print(f"\nSample trades:")
        for trade in trades[:5]:
            print(f"  Day {trade['day']:3d}: {trade['action']:15s} @ ${trade['price']:6.2f} (spot: ${trade['spot']:.2f})")

        return {
            'total_pnl': self.pnl,
            'trades': len(trades) // 2,
            'pnl_history': pnl_history
        }


def main():
    """Run example backtests."""
    backtest = SimpleBacktest()

    # Test on last 6 months
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")

    # Scenario 1: Gamma scalping on SPY
    result = backtest.run_gamma_scalping('SPY', start_date, end_date)

    print("\n" + "=" * 60)
    print("Backtest Complete")
    print("=" * 60)
    if result:
        print(f"Total P&L: ${result['total_pnl']:.2f}")
        print(f"Trades executed: {result['trades']}")

    # Data pipeline stats
    print("\nData Pipeline Summary:")
    print(f"  - yfinance: OHLCV data source")
    print(f"  - MockOptionsSource: Synthetic options (for demo)")
    print(f"  - BlackScholes: Greeks calculation")
    print("\nTo use real data:")
    print("  1. Setup PostgreSQL")
    print("  2. Run: python3 data_ingestion.py")
    print("  3. Backtest will use live data from database")


if __name__ == '__main__':
    main()
