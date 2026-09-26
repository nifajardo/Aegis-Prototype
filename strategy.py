import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import MACD
from ta.volatility import BollingerBands

def generate_signals(df: pd.DataFrame, strategy_type: str = 'Dual MA', **kwargs) -> pd.DataFrame:
    """
    Applies the selected trading strategy and generates entry/exit signals.

    Args:
        df (pd.DataFrame): DataFrame with OHLCV data.
        strategy_type (str): The strategy to apply.
        **kwargs: Strategy-specific parameters.

    Returns:
        pd.DataFrame: DataFrame with added indicator columns, 'position', and 'crossover'.
    """
    df_strategy = df.copy()
    df_strategy['position'] = 0
    df_strategy['crossover'] = 0

    if strategy_type == 'Dual MA':
        fast_ma = kwargs.get('fast_ma', 50)
        slow_ma = kwargs.get('slow_ma', 200)

        df_strategy['fast_ma'] = df_strategy['close'].rolling(window=fast_ma).mean()
        df_strategy['slow_ma'] = df_strategy['close'].rolling(window=slow_ma).mean()

        df_strategy.loc[df_strategy['fast_ma'] > df_strategy['slow_ma'], 'position'] = 1
        df_strategy.loc[df_strategy['fast_ma'] < df_strategy['slow_ma'], 'position'] = -1

    elif strategy_type == 'MACD':
        window_fast = kwargs.get('macd_fast', 12)
        window_slow = kwargs.get('macd_slow', 26)
        window_sign = kwargs.get('macd_sign', 9)

        macd_indicator = MACD(close=df_strategy['close'], window_fast=window_fast, window_slow=window_slow, window_sign=window_sign)
        df_strategy['macd'] = macd_indicator.macd()
        df_strategy['macd_signal'] = macd_indicator.macd_signal()
        df_strategy['macd_diff'] = macd_indicator.macd_diff()

        # Long when MACD > Signal, Short when MACD < Signal
        df_strategy.loc[df_strategy['macd'] > df_strategy['macd_signal'], 'position'] = 1
        df_strategy.loc[df_strategy['macd'] < df_strategy['macd_signal'], 'position'] = -1

    elif strategy_type == 'RSI Mean Reversion':
        rsi_window = kwargs.get('rsi_window', 14)
        rsi_oversold = kwargs.get('rsi_oversold', 30)
        rsi_overbought = kwargs.get('rsi_overbought', 70)

        rsi_indicator = RSIIndicator(close=df_strategy['close'], window=rsi_window)
        df_strategy['rsi'] = rsi_indicator.rsi()

        # We need a stateful approach for RSI (hold until opposite signal)
        # 1. Generate Raw Signals
        df_strategy['raw_signal'] = 0
        df_strategy.loc[df_strategy['rsi'] < rsi_oversold, 'raw_signal'] = 1 # Buy
        df_strategy.loc[df_strategy['rsi'] > rsi_overbought, 'raw_signal'] = -1 # Sell

        # 2. Forward fill the raw signals to create continuous positions
        df_strategy['position'] = df_strategy['raw_signal'].replace(0, np.nan).ffill().fillna(0)

    elif strategy_type == 'Bollinger Bands':
        bb_window = kwargs.get('bb_window', 20)
        bb_dev = kwargs.get('bb_dev', 2.0)

        bb_indicator = BollingerBands(close=df_strategy['close'], window=bb_window, window_dev=bb_dev)
        df_strategy['bb_high'] = bb_indicator.bollinger_hband()
        df_strategy['bb_low'] = bb_indicator.bollinger_lband()
        df_strategy['bb_mid'] = bb_indicator.bollinger_mavg()

        # Mean Reversion using BB:
        # Buy when price closes below Lower Band. Sell when price closes above Upper Band.
        df_strategy['raw_signal'] = 0
        df_strategy.loc[df_strategy['close'] < df_strategy['bb_low'], 'raw_signal'] = 1
        df_strategy.loc[df_strategy['close'] > df_strategy['bb_high'], 'raw_signal'] = -1

        df_strategy['position'] = df_strategy['raw_signal'].replace(0, np.nan).ffill().fillna(0)

    elif strategy_type == 'Dynamic Grid':
        grid_window = kwargs.get('grid_window', 20)
        grid_dev = kwargs.get('grid_dev', 2.0)
        grid_levels = kwargs.get('grid_levels', 5)

        # Calculate dynamic bounds (using SMA and ATR or StdDev)
        # We will use StdDev to define the total grid height
        df_strategy['grid_mid'] = df_strategy['close'].rolling(window=grid_window).mean()
        std_dev = df_strategy['close'].rolling(window=grid_window).std()

        df_strategy['grid_top'] = df_strategy['grid_mid'] + (std_dev * grid_dev)
        df_strategy['grid_bottom'] = df_strategy['grid_mid'] - (std_dev * grid_dev)

        # Generate logic based on crossing inner grid tiers
        # Simple Dynamic Grid logic (mean reversion back to mid):
        # We divide the lower half into buy zones and upper half into sell zones
        df_strategy['raw_signal'] = 0

        # For a simplified continuous simulation based on academic studies:
        # Go Long when price drops below the first grid tier in the lower half
        # Go Short when price rises above the first grid tier in the upper half
        step_size = (df_strategy['grid_top'] - df_strategy['grid_mid']) / (grid_levels / 2)
        lower_tier_1 = df_strategy['grid_mid'] - step_size
        upper_tier_1 = df_strategy['grid_mid'] + step_size

        df_strategy.loc[df_strategy['close'] < lower_tier_1, 'raw_signal'] = 1
        df_strategy.loc[df_strategy['close'] > upper_tier_1, 'raw_signal'] = -1

        df_strategy['position'] = df_strategy['raw_signal'].replace(0, np.nan).ffill().fillna(0)

    elif strategy_type == 'Time-Series Momentum (TSMOM)':
        tsmom_lookback = kwargs.get('tsmom_lookback', 30)

        # Calculate the return over the lookback period
        # TSMOM goes Long if the past return is positive, Short if negative.
        df_strategy['momentum_return'] = df_strategy['close'].pct_change(periods=tsmom_lookback)

        # We can also add an SMA filter to ensure we are trading with the primary trend
        # as noted in many trend-following studies.
        sma_filter = df_strategy['close'].rolling(window=tsmom_lookback).mean()

        df_strategy['raw_signal'] = 0
        # Basic TSMOM: Signal is the sign of the past return
        df_strategy.loc[(df_strategy['momentum_return'] > 0) & (df_strategy['close'] > sma_filter), 'raw_signal'] = 1
        df_strategy.loc[(df_strategy['momentum_return'] < 0) & (df_strategy['close'] < sma_filter), 'raw_signal'] = -1

        df_strategy['position'] = df_strategy['raw_signal'].replace(0, np.nan).ffill().fillna(0)

    # Clean up position and calculate crossovers
    df_strategy['position'] = df_strategy['position'].ffill().fillna(0)
    df_strategy['signal'] = df_strategy['position'].diff()
    df_strategy['crossover'] = np.where(df_strategy['signal'] > 0, 1,
                                        np.where(df_strategy['signal'] < 0, -1, 0))

    return df_strategy
