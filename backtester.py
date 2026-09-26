import pandas as pd
import numpy as np

def run_backtest(df: pd.DataFrame, initial_balance: float = 10000.0, leverage: int = 1, stop_loss_pct: float = 0.0, take_profit_pct: float = 0.0):
    """
    Simulates trading based on generated signals.
    Handles futures mechanics like leverage, liquidation, stop losses, take profits, and going long and short.

    Args:
        df (pd.DataFrame): Dataframe with OHLCV data and 'position' column from strategy.
        initial_balance (float): Starting balance in quote currency (e.g., USDT).
        leverage (int): Leverage multiplier.
        stop_loss_pct (float): Stop loss percentage (e.g., 2.0 for 2%). 0 to disable.
        take_profit_pct (float): Take profit percentage (e.g., 5.0 for 5%). 0 to disable.

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

    # Pre-compute prices for faster iteration
    closes = df_bt['close'].values
    highs = df_bt['high'].values
    lows = df_bt['low'].values
    positions = df_bt['position'].values
    timestamps = df_bt.index

    sl_decimal = stop_loss_pct / 100.0 if stop_loss_pct > 0 else 0
    tp_decimal = take_profit_pct / 100.0 if take_profit_pct > 0 else 0

    for i in range(len(df_bt)):
        price = closes[i]
        high = highs[i]
        low = lows[i]
        target_position = positions[i]
        ts = timestamps[i]

        # 1. Check for constraints (Liquidation, Stop Loss, Take Profit) if in a position
        if current_position != 0:
            liq_percentage = 1.0 / leverage

            is_liquidated = False
            hit_sl = False
            hit_tp = False
            exit_reason = None
            exit_price = 0.0

            if current_position == 1:
                liq_price = entry_price * (1 - liq_percentage)
                sl_price = entry_price * (1 - sl_decimal) if sl_decimal > 0 else -1
                tp_price = entry_price * (1 + tp_decimal) if tp_decimal > 0 else float('inf')

                # Check hits in order of proximity to the entry price within the candle bounds
                # If SL is hit before Liquidation on a massive wick, SL should trigger first.
                if sl_decimal > 0 and low <= sl_price:
                    hit_sl = True
                    exit_reason = 'STOP_LOSS'
                    exit_price = sl_price
                elif low <= liq_price:
                    is_liquidated = True
                    exit_price = liq_price
                elif tp_decimal > 0 and high >= tp_price:
                    hit_tp = True
                    exit_reason = 'TAKE_PROFIT'
                    exit_price = tp_price

            elif current_position == -1:
                liq_price = entry_price * (1 + liq_percentage)
                sl_price = entry_price * (1 + sl_decimal) if sl_decimal > 0 else float('inf')
                tp_price = entry_price * (1 - tp_decimal) if tp_decimal > 0 else -1

                if sl_decimal > 0 and high >= sl_price:
                    hit_sl = True
                    exit_reason = 'STOP_LOSS'
                    exit_price = sl_price
                elif high >= liq_price:
                    is_liquidated = True
                    exit_price = liq_price
                elif tp_decimal > 0 and low <= tp_price:
                    hit_tp = True
                    exit_reason = 'TAKE_PROFIT'
                    exit_price = tp_price

            if is_liquidated:
                loss = balance
                balance = 0
                trades.append({
                    'exit_time': ts,
                    'type': 'LIQUIDATION',
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': -loss,
                    'return_pct': -100.0
                })
                current_position = 0
                target_position = 0 # Force flat until next signal change
                equity_history.append(balance)
                break # Stop simulation entirely if blown up

            elif hit_sl or hit_tp:
                # Calculate PNL at the constraint price
                if current_position == 1:
                    pnl = (exit_price - entry_price) * position_size
                else:
                    pnl = (entry_price - exit_price) * position_size

                balance += pnl
                trade_return_pct = (pnl / (balance - pnl)) * 100 if (balance - pnl) > 0 else 0

                trades.append({
                    'exit_time': ts,
                    'type': exit_reason,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'return_pct': trade_return_pct
                })

                current_position = 0
                # If we hit a constraint, we stay flat until the strategy signal flips again to enter a new trade
                target_position = 0
                # Note: This prevents instantly re-entering on the same candle if the signal is still the same.

        # 2. Check for Strategy Signal Changes
        if target_position != current_position and target_position != 0:
            # If SL/TP flattened us (current = 0), we only want to re-enter on a new explicit signal,
            # not just because the continuous strategy state is still 1.
            # We check the 'crossover' column if it exists to verify an explicit signal.
            if 'crossover' in df_bt.columns:
                crossover_signal = df_bt['crossover'].iloc[i]
                if crossover_signal != 0:
                    target_position = crossover_signal
                else:
                    # No new explicit signal, stay flat
                    target_position = current_position
            else:
                # Fallback for simple tests without a crossover column
                pass

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
