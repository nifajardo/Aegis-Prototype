import ccxt
import pandas as pd
import streamlit as st
import datetime

@st.cache_data(ttl=datetime.timedelta(hours=1))
def fetch_historical_data(symbol: str, timeframe: str, limit: int = 1000):
    """
    Fetches historical OHLCV data for a given symbol and timeframe.
    Uses KuCoin because Binance, OKX, and Kraken might have regional restrictions.

    Args:
        symbol (str): Trading pair symbol (e.g., 'BTC/USDT').
        timeframe (str): Timeframe (e.g., '1d', '15m', '5m').
        limit (int): Number of candles to fetch.

    Returns:
        pd.DataFrame: DataFrame containing historical data.
    """
    try:
        # Initialize KuCoin market
        exchange = ccxt.kucoin({
            'enableRateLimit': True,
        })

        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

        # Convert to Pandas DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        # Set timestamp as index
        df.set_index('timestamp', inplace=True)

        # Ensure numerical types
        cols = ['open', 'high', 'low', 'close', 'volume']
        df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')

        # Sort index just in case
        df.sort_index(inplace=True)

        return df

    except Exception as e:
        st.error(f"Error fetching data for {symbol} ({timeframe}): {str(e)}")
        return pd.DataFrame()

if __name__ == "__main__":
    # Test the fetcher
    df = fetch_historical_data('BTC/USDT', '1d', limit=5)
    print(df)
