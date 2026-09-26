import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from data_fetcher import fetch_historical_data
from strategy import generate_signals
from backtester import run_backtest

st.set_page_config(page_title="Crypto Futures Backtester", layout="wide")

st.title("📈 Crypto Futures Backtester & Simulator")

st.sidebar.header("Settings")

# Sidebar inputs
symbol = st.sidebar.selectbox("Trading Pair", ["BTC/USDT", "ETH/USDT"])
timeframe = st.sidebar.selectbox("Timeframe", ["1d", "15m", "5m"])
limit = st.sidebar.slider("Number of Candles", 100, 1500, 1000)

st.sidebar.subheader("Strategy Parameters (Dual MA)")
fast_ma = st.sidebar.number_input("Fast MA Period", min_value=1, max_value=100, value=50)
slow_ma = st.sidebar.number_input("Slow MA Period", min_value=10, max_value=500, value=200)

st.sidebar.subheader("Futures Parameters")
initial_balance = st.sidebar.number_input("Initial Balance (USDT)", min_value=100, value=10000, step=100)
leverage = st.sidebar.slider("Leverage", min_value=1, max_value=100, value=10)

# Main Execution
with st.spinner('Fetching Data...'):
    df_raw = fetch_historical_data(symbol, timeframe, limit)

if df_raw.empty:
    st.error("Could not fetch data. Please try again.")
else:
    with st.spinner('Running Strategy & Simulation...'):
        # 1. Apply Strategy
        df_strategy = generate_signals(df_raw, fast_ma=fast_ma, slow_ma=slow_ma)

        # 2. Run Backtest
        metrics, df_results, trades = run_backtest(df_strategy, initial_balance=initial_balance, leverage=leverage)

    # --- UI Layout ---

    st.subheader("Performance Metrics")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Final Balance", f"${metrics['final_balance']:,.2f}", f"{metrics['total_return_pct']:.2f}%")
    col2.metric("Total Trades", metrics['total_trades'])
    col3.metric("Win Rate", f"{metrics['win_rate_pct']:.2f}%")
    col4.metric("Max Drawdown", f"{metrics['max_drawdown_pct']:.2f}%")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Profit Factor", f"{metrics['profit_factor']:.2f}" if metrics['profit_factor'] != float('inf') else "INF")
    col6.metric("Expectancy (Edge)", f"${metrics['expectancy_edge']:,.2f}")

    st.divider()

    # --- Charts ---
    st.subheader("Price & Strategy Chart")

    # Create Subplots: 1 for Price/MA, 1 for Equity
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, subplot_titles=('Price & Moving Averages', 'Account Equity'),
                        row_width=[0.3, 0.7])

    # Candlestick
    fig.add_trace(go.Candlestick(x=df_results.index,
                                 open=df_results['open'],
                                 high=df_results['high'],
                                 low=df_results['low'],
                                 close=df_results['close'],
                                 name='Price'), row=1, col=1)

    # Moving Averages
    fig.add_trace(go.Scatter(x=df_results.index, y=df_results['fast_ma'], line=dict(color='orange', width=1.5), name=f'Fast MA ({fast_ma})'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_results.index, y=df_results['slow_ma'], line=dict(color='blue', width=1.5), name=f'Slow MA ({slow_ma})'), row=1, col=1)

    # Entry Signals (Crossovers)
    long_signals = df_results[df_results['crossover'] == 1]
    short_signals = df_results[df_results['crossover'] == -1]

    fig.add_trace(go.Scatter(x=long_signals.index, y=long_signals['low'] * 0.99, mode='markers',
                             marker=dict(symbol='triangle-up', color='green', size=12), name='Long Signal'), row=1, col=1)

    fig.add_trace(go.Scatter(x=short_signals.index, y=short_signals['high'] * 1.01, mode='markers',
                             marker=dict(symbol='triangle-down', color='red', size=12), name='Short Signal'), row=1, col=1)

    # Equity Curve
    fig.add_trace(go.Scatter(x=df_results.index, y=df_results['equity'], line=dict(color='purple', width=2), name='Equity'), row=2, col=1)

    # Layout tuning
    fig.update_layout(height=800, xaxis_rangeslider_visible=False)

    st.plotly_chart(fig, use_container_width=True)

    # --- Trade Log ---
    st.subheader("Trade Log")
    if trades:
        import pandas as pd
        df_trades = pd.DataFrame(trades)
        # Format the dataframe
        if 'exit_time' in df_trades.columns:
            df_trades['exit_time'] = pd.to_datetime(df_trades['exit_time']).dt.strftime('%Y-%m-%d %H:%M:%S')
        st.dataframe(df_trades, use_container_width=True)
    else:
        st.write("No trades executed.")
