import pandas as pd
import numpy as np

def run_backtest(df: pd.DataFrame, initial_balance: float = 10000.0, leverage: int = 1):
    """
    Simulates trading based on generated signals.
    Handles futures mechanics like leverage, liquidation, going long and short.

    Args:
        df (pd.DataFrame): Dataframe with OHLCV data and 'position' column from strategy.
        initial_balance (float): Starting balance in quote currency (e.g., USDT).
        leverage (int): Leverage multiplier.

    Returns:
        dict: Backtest metrics and history.
        pd.DataFrame: DataFrame with balance history and trades.
    """
    df_bt = df.copy()

    balance = initial_balance
    position_size = 0.0 # the amount of base currency (e.g., BTC) we hold
    entry_price = 0.0
    current_position = 0 # 1 for Long, -1 for Short, 0 for Flat

    equity_history = []
    trades = []

    # Pre-compute close prices for faster iteration
    closes = df_bt['close'].values
    highs = df_bt['high'].values
    lows = df_bt['low'].values
    positions = df_bt['position'].values
    timestamps = df_bt.index

    for i in range(len(df_bt)):
        price = closes[i]
        high = highs[i]
        low = lows[i]
        target_position = positions[i]
        ts = timestamps[i]

        # Check for liquidation if we are in a position
        if current_position != 0:
            # Liquidation distance = 100% / leverage
            liq_percentage = 1.0 / leverage

            is_liquidated = False

            if current_position == 1:
                # Long liquidation: Price drops by liq_percentage
                liq_price = entry_price * (1 - liq_percentage)
                if low <= liq_price:
                    is_liquidated = True
            elif current_position == -1:
                # Short liquidation: Price rises by liq_percentage
                liq_price = entry_price * (1 + liq_percentage)
                if high >= liq_price:
                    is_liquidated = True

            if is_liquidated:
                # Lose all margin for this trade.
                # Assuming isolated margin and we used all balance as margin
                loss = balance
                balance = 0
                trades.append({
                    'exit_time': ts,
                    'type': 'LIQUIDATION',
                    'entry_price': entry_price,
                    'exit_price': liq_price,
                    'pnl': -loss, # Lost everything
                    'return_pct': -100.0
                })
                current_position = 0
                equity_history.append(balance)
                break # Stop simulation if balance is 0

        # If position changes, close old position and open new one
        if target_position != current_position:
            # Close existing position
            if current_position != 0:
                # Calculate PNL
                if current_position == 1:
                    pnl = (price - entry_price) * position_size
                elif current_position == -1:
                    pnl = (entry_price - price) * position_size

                # Apply leverage to PNL (Actually, PNL is already in terms of position size, which is multiplied by leverage)
                # Let's ensure position_size was calculated with leverage.
                balance += pnl

                # Record trade
                trade_return_pct = (pnl / (balance - pnl)) * 100 if (balance - pnl) > 0 else 0
                trades.append({
                    'exit_time': ts,
                    'type': 'LONG' if current_position == 1 else 'SHORT',
                    'entry_price': entry_price,
                    'exit_price': price,
                    'pnl': pnl,
                    'return_pct': trade_return_pct
                })

            # Open new position
            current_position = target_position
            if current_position != 0:
                entry_price = price
                # We use all available balance for margin.
                # Total trade value = balance * leverage
                position_size = (balance * leverage) / entry_price
            else:
                position_size = 0.0
                entry_price = 0.0

        # Record equity (Mark to market)
        current_equity = balance
        if current_position != 0:
            if current_position == 1:
                unrealized_pnl = (price - entry_price) * position_size
            elif current_position == -1:
                unrealized_pnl = (entry_price - price) * position_size
            current_equity += unrealized_pnl

        equity_history.append(current_equity)

    # In case we stop early due to liquidation, pad the rest
    while len(equity_history) < len(df_bt):
        equity_history.append(0)

    df_bt['equity'] = equity_history

    # Calculate Metrics
    metrics = calculate_metrics(initial_balance, df_bt['equity'].tolist(), trades)

    return metrics, df_bt, trades


def calculate_metrics(initial_balance, equity_history, trades):
    final_balance = equity_history[-1]
    total_return = ((final_balance - initial_balance) / initial_balance) * 100

    win_trades = [t for t in trades if t['pnl'] > 0]
    loss_trades = [t for t in trades if t['pnl'] <= 0 and t['type'] != 'LIQUIDATION']

    total_trades = len(trades)
    win_rate = (len(win_trades) / total_trades * 100) if total_trades > 0 else 0

    avg_win = np.mean([t['pnl'] for t in win_trades]) if win_trades else 0
    avg_loss = np.mean([abs(t['pnl']) for t in loss_trades]) if loss_trades else 0

    # Profit Factor
    gross_profit = sum([t['pnl'] for t in win_trades])
    gross_loss = sum([abs(t['pnl']) for t in loss_trades])
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    # Expectancy (Edge)
    win_prob = len(win_trades) / total_trades if total_trades > 0 else 0
    loss_prob = len(loss_trades) / total_trades if total_trades > 0 else 0
    expectancy = (win_prob * avg_win) - (loss_prob * avg_loss)

    # Max Drawdown
    equity_series = pd.Series(equity_history)
    rolling_max = equity_series.cummax()
    drawdown = (equity_series - rolling_max) / rolling_max
    max_drawdown = drawdown.min() * 100 # in percentage

    return {
        'initial_balance': initial_balance,
        'final_balance': final_balance,
        'total_return_pct': total_return,
        'total_trades': total_trades,
        'win_rate_pct': win_rate,
        'profit_factor': profit_factor,
        'expectancy_edge': expectancy,
        'max_drawdown_pct': max_drawdown
    }

if __name__ == "__main__":
    # Test Backtester
    import datetime

    dates = pd.date_range('2023-01-01', periods=5)
    df_test = pd.DataFrame({
        'close': [100, 110, 90, 80, 120],
        'high': [105, 115, 95, 85, 125],
        'low': [95, 105, 85, 75, 115],
        'position': [1, 1, -1, -1, 1]
    }, index=dates)

    metrics, df_res, trades = run_backtest(df_test, leverage=2)
    print("Metrics:", metrics)
    print("Trades:", trades)
