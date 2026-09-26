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
symbol = st.sidebar.selectbox("Trading Pair", ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"])
timeframe = st.sidebar.selectbox("Timeframe", ["1d", "4h", "1h", "15m", "5m"])
limit = st.sidebar.slider("Number of Candles", 100, 1500, 1000)

st.sidebar.subheader("Strategy Selection")
strategy_type = st.sidebar.selectbox("Strategy", ["Dual MA", "MACD", "RSI Mean Reversion", "Bollinger Bands", "Dynamic Grid", "Time-Series Momentum (TSMOM)", "Multi-Timeframe (MTF) Alignment"])

# Dynamic parameter inputs based on selected strategy
strategy_params = {}
if strategy_type == "Dual MA":
    strategy_params['fast_ma'] = st.sidebar.number_input("Fast MA Period", min_value=1, max_value=100, value=50)
    strategy_params['slow_ma'] = st.sidebar.number_input("Slow MA Period", min_value=10, max_value=500, value=200)
elif strategy_type == "MACD":
    strategy_params['macd_fast'] = st.sidebar.number_input("MACD Fast", min_value=1, max_value=50, value=12)
    strategy_params['macd_slow'] = st.sidebar.number_input("MACD Slow", min_value=10, max_value=100, value=26)
    strategy_params['macd_sign'] = st.sidebar.number_input("MACD Signal", min_value=1, max_value=50, value=9)
elif strategy_type == "RSI Mean Reversion":
    strategy_params['rsi_window'] = st.sidebar.number_input("RSI Window", min_value=2, max_value=50, value=14)
    strategy_params['rsi_oversold'] = st.sidebar.number_input("RSI Oversold Level", min_value=10, max_value=50, value=30)
    strategy_params['rsi_overbought'] = st.sidebar.number_input("RSI Overbought Level", min_value=50, max_value=90, value=70)
elif strategy_type == "Bollinger Bands":
    strategy_params['bb_window'] = st.sidebar.number_input("BB Window", min_value=5, max_value=100, value=20)
    strategy_params['bb_dev'] = st.sidebar.number_input("BB Std Dev", min_value=1.0, max_value=5.0, value=2.0, step=0.1)
elif strategy_type == "Dynamic Grid":
    strategy_params['grid_window'] = st.sidebar.number_input("Grid Window (Lookback)", min_value=5, max_value=200, value=20)
    strategy_params['grid_dev'] = st.sidebar.number_input("Grid Width (Std Dev)", min_value=0.5, max_value=5.0, value=2.0, step=0.1)
    strategy_params['grid_levels'] = st.sidebar.number_input("Total Grid Levels", min_value=2, max_value=50, value=10)
elif strategy_type == "Time-Series Momentum (TSMOM)":
    strategy_params['tsmom_lookback'] = st.sidebar.number_input("Momentum Lookback (Periods)", min_value=10, max_value=500, value=30)
elif strategy_type == "Multi-Timeframe (MTF) Alignment":
    strategy_params['htf_window'] = st.sidebar.number_input("Daily Trend SMA Filter", min_value=10, max_value=200, value=50)
    strategy_params['ltf_fast'] = st.sidebar.number_input("LTF Fast MA Trigger", min_value=1, max_value=50, value=10)
    strategy_params['ltf_slow'] = st.sidebar.number_input("LTF Slow MA Trigger", min_value=10, max_value=200, value=30)

st.sidebar.subheader("Futures Parameters")
initial_balance = st.sidebar.number_input("Initial Balance (USDT)", min_value=100, value=10000, step=100)
leverage = st.sidebar.slider("Leverage", min_value=1, max_value=100, value=10)
stop_loss_pct = st.sidebar.number_input("Stop Loss (%)", min_value=0.0, max_value=100.0, value=2.0, step=0.1, help="Set to 0 to disable")
take_profit_pct = st.sidebar.number_input("Take Profit (%)", min_value=0.0, max_value=1000.0, value=5.0, step=0.1, help="Set to 0 to disable")
trailing_stop_pct = st.sidebar.number_input("Trailing Stop Loss (%)", min_value=0.0, max_value=100.0, value=1.5, step=0.1, help="Moves SL up with profit. Set to 0 to disable.")

# Main Execution
with st.spinner('Fetching Data...'):
    df_raw = fetch_historical_data(symbol, timeframe, limit)

if df_raw.empty:
    st.error("Could not fetch data. Please try again.")
else:
    with st.spinner('Running Strategy & Simulation...'):
        # 1. Apply Strategy
        df_strategy = generate_signals(df_raw, strategy_type=strategy_type, **strategy_params)

        # 2. Run Backtest
        metrics, df_results, trades = run_backtest(
            df_strategy,
            initial_balance=initial_balance,
            leverage=leverage,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            trailing_stop_pct=trailing_stop_pct
        )

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
    st.subheader(f"Strategy Analysis: {strategy_type}")

    # Create Subplots based on strategy
    has_oscillator = strategy_type in ["MACD", "RSI Mean Reversion", "Time-Series Momentum (TSMOM)"]
    if has_oscillator:
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                            vertical_spacing=0.03, subplot_titles=('Price & Signals', 'Oscillator', 'Account Equity'),
                            row_width=[0.25, 0.25, 0.5])
        price_row, osc_row, eq_row = 1, 2, 3
    else:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            vertical_spacing=0.03, subplot_titles=('Price & Signals', 'Account Equity'),
                            row_width=[0.3, 0.7])
        price_row, osc_row, eq_row = 1, None, 2

    # Candlestick
    fig.add_trace(go.Candlestick(x=df_results.index,
                                 open=df_results['open'],
                                 high=df_results['high'],
                                 low=df_results['low'],
                                 close=df_results['close'],
                                 name='Price'), row=price_row, col=1)

    # Overlay Indicators on Price Chart
    if strategy_type == "Dual MA":
        fig.add_trace(go.Scatter(x=df_results.index, y=df_results['fast_ma'], line=dict(color='orange', width=1.5), name='Fast MA'), row=price_row, col=1)
        fig.add_trace(go.Scatter(x=df_results.index, y=df_results['slow_ma'], line=dict(color='blue', width=1.5), name='Slow MA'), row=price_row, col=1)
    elif strategy_type == "Bollinger Bands":
        fig.add_trace(go.Scatter(x=df_results.index, y=df_results['bb_high'], line=dict(color='rgba(255,0,0,0.5)', width=1, dash='dash'), name='BB High'), row=price_row, col=1)
        fig.add_trace(go.Scatter(x=df_results.index, y=df_results['bb_low'], line=dict(color='rgba(0,255,0,0.5)', width=1, dash='dash'), name='BB Low'), row=price_row, col=1)
        fig.add_trace(go.Scatter(x=df_results.index, y=df_results['bb_mid'], line=dict(color='rgba(0,0,255,0.5)', width=1), name='BB Mid'), row=price_row, col=1)
    elif strategy_type == "Dynamic Grid":
        fig.add_trace(go.Scatter(x=df_results.index, y=df_results['grid_top'], line=dict(color='rgba(255,0,0,0.5)', width=1, dash='dot'), name='Grid Top'), row=price_row, col=1)
        fig.add_trace(go.Scatter(x=df_results.index, y=df_results['grid_bottom'], line=dict(color='rgba(0,255,0,0.5)', width=1, dash='dot'), name='Grid Bottom'), row=price_row, col=1)
        fig.add_trace(go.Scatter(x=df_results.index, y=df_results['grid_mid'], line=dict(color='rgba(0,0,0,0.5)', width=1), name='Grid Mid'), row=price_row, col=1)
    elif strategy_type == "Multi-Timeframe (MTF) Alignment":
        fig.add_trace(go.Scatter(x=df_results.index, y=df_results['htf_sma'], line=dict(color='black', width=3), name='Daily Trend (HTF)'), row=price_row, col=1)
        fig.add_trace(go.Scatter(x=df_results.index, y=df_results['ltf_fast_ma'], line=dict(color='orange', width=1.5), name='LTF Fast MA'), row=price_row, col=1)
        fig.add_trace(go.Scatter(x=df_results.index, y=df_results['ltf_slow_ma'], line=dict(color='blue', width=1.5), name='LTF Slow MA'), row=price_row, col=1)

    # Entry Signals (Crossovers)
    long_signals = df_results[df_results['crossover'] == 1]
    short_signals = df_results[df_results['crossover'] == -1]

    fig.add_trace(go.Scatter(x=long_signals.index, y=long_signals['low'] * 0.99, mode='markers',
                             marker=dict(symbol='triangle-up', color='green', size=12), name='Long Entry'), row=price_row, col=1)

    fig.add_trace(go.Scatter(x=short_signals.index, y=short_signals['high'] * 1.01, mode='markers',
                             marker=dict(symbol='triangle-down', color='red', size=12), name='Short Entry'), row=price_row, col=1)

    # Oscillator Subplot
    if has_oscillator:
        if strategy_type == "MACD":
            fig.add_trace(go.Scatter(x=df_results.index, y=df_results['macd'], line=dict(color='blue', width=1.5), name='MACD'), row=osc_row, col=1)
            fig.add_trace(go.Scatter(x=df_results.index, y=df_results['macd_signal'], line=dict(color='orange', width=1.5), name='Signal'), row=osc_row, col=1)
            fig.add_trace(go.Bar(x=df_results.index, y=df_results['macd_diff'], name='Histogram', marker_color='gray'), row=osc_row, col=1)
        elif strategy_type == "RSI Mean Reversion":
            fig.add_trace(go.Scatter(x=df_results.index, y=df_results['rsi'], line=dict(color='purple', width=1.5), name='RSI'), row=osc_row, col=1)
            # Overbought/Oversold lines
            fig.add_hline(y=strategy_params['rsi_overbought'], line_dash="dash", line_color="red", row=osc_row, col=1)
            fig.add_hline(y=strategy_params['rsi_oversold'], line_dash="dash", line_color="green", row=osc_row, col=1)
        elif strategy_type == "Time-Series Momentum (TSMOM)":
            fig.add_trace(go.Bar(x=df_results.index, y=df_results['momentum_return'], marker_color='blue', name='Momentum (Return)'), row=osc_row, col=1)
            fig.add_hline(y=0, line_dash="dash", line_color="black", row=osc_row, col=1)

    # Equity Curve
    fig.add_trace(go.Scatter(x=df_results.index, y=df_results['equity'], line=dict(color='purple', width=2), name='Equity'), row=eq_row, col=1)

    # Layout tuning
    height = 900 if has_oscillator else 700
    fig.update_layout(height=height, xaxis_rangeslider_visible=False)

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
