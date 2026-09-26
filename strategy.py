import pandas as pd
import numpy as np

def generate_signals(df: pd.DataFrame, fast_ma: int = 50, slow_ma: int = 200) -> pd.DataFrame:
    """
    Applies the Dual Moving Average Crossover strategy.

    Args:
        df (pd.DataFrame): DataFrame with OHLCV data.
        fast_ma (int): Period for the fast moving average.
        slow_ma (int): Period for the slow moving average.

    Returns:
        pd.DataFrame: The original DataFrame with added 'fast_ma', 'slow_ma', and 'signal' columns.
    """
    df_strategy = df.copy()

    # Calculate moving averages
    df_strategy['fast_ma'] = df_strategy['close'].rolling(window=fast_ma).mean()
    df_strategy['slow_ma'] = df_strategy['close'].rolling(window=slow_ma).mean()

    # Initialize signal column
    df_strategy['signal'] = 0

    # Generate signals:
    # 1 for Long (fast_ma crosses above slow_ma)
    # -1 for Short (fast_ma crosses below slow_ma)

    # We only care about the crossover points, but for a continuous position we can hold
    # the signal as long as fast > slow.
    # In a continuous system:
    # If fast_ma > slow_ma, position is LONG (1)
    # If fast_ma < slow_ma, position is SHORT (-1)
    df_strategy.loc[df_strategy['fast_ma'] > df_strategy['slow_ma'], 'position'] = 1
    df_strategy.loc[df_strategy['fast_ma'] < df_strategy['slow_ma'], 'position'] = -1

    # Forward fill positions for continuous holding
    # Wait, the above logic is already continuous. Let's make sure it handles NaNs.
    df_strategy['position'] = df_strategy['position'].ffill().fillna(0)

    # The 'signal' represents the change in position
    df_strategy['signal'] = df_strategy['position'].diff()

    # We can also identify the exact crossover point
    df_strategy['crossover'] = np.where(df_strategy['signal'] > 0, 1,
                                        np.where(df_strategy['signal'] < 0, -1, 0))

    return df_strategy

if __name__ == "__main__":
    # Test strategy generator
    import numpy as np

    # Create fake data
    dates = pd.date_range('2023-01-01', periods=100)
    prices = np.linspace(10, 20, 50).tolist() + np.linspace(20, 10, 50).tolist()
    df_test = pd.DataFrame({'close': prices}, index=dates)

    df_res = generate_signals(df_test, fast_ma=5, slow_ma=10)
    print(df_res[df_res['crossover'] != 0])
