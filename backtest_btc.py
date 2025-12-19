import pandas as pd
import numpy as np
from src.data_fetcher import fetch_market_data
from src.indicator_calculator import calculate_indicators
from src.trade_executor import generate_prediction_and_risk

pd.options.mode.chained_assignment = None 

def run_10_day_test(symbol="BTC"):
    print(f"🔍 Fetching last 10 days of data for {symbol}...")
    df = fetch_market_data(symbol, period="10d", interval="15m")
    if df.empty: return

    df = calculate_indicators(df)
    
    balance = 10000.0
    position_type = None # None, 'LONG', or 'SHORT'
    units = 0.0
    locked_tp = 0.0
    locked_sl = 0.0
    trade_count = 0
    wins = 0

    print(f"🚀 Starting BI-DIRECTIONAL Backtest with ${balance}...")
    print("-" * 60)

    for i in range(35, len(df)):
        current_data = df.iloc[:i+1]
        analysis = generate_prediction_and_risk(current_data)
        price = float(df.iloc[i]['Close'])
        
        # --- 1. ENTRY LOGIC ---
        if position_type is None:
            if analysis['signal'] == 'BUY':
                position_type = 'LONG'
                units = balance / price
                locked_tp = analysis['tp_price']
                locked_sl = analysis['sl_price']
                balance = 0
                trade_count += 1
                print(f"🚀 LONG at ${price:.2f} | TP: {locked_tp:.2f} | SL: {locked_sl:.2f}")

            elif analysis['signal'] == 'SELL':
                position_type = 'SHORT'
                units = balance / price
                locked_tp = analysis['tp_price']
                locked_sl = analysis['sl_price']
                balance = 0
                trade_count += 1
                print(f"📉 SHORT at ${price:.2f} | TP: {locked_tp:.2f} | SL: {locked_sl:.2f}")

        # --- 2. EXIT LOGIC (LONG) ---
        elif position_type == 'LONG':
            if price >= locked_tp:
                balance = units * price
                wins += 1
                print(f"✅ TP LONG at ${price:.2f}")
                position_type = None
            elif price <= locked_sl:
                balance = units * price
                print(f"❌ SL LONG at ${price:.2f}")
                position_type = None

        # --- 3. EXIT LOGIC (SHORT) ---
        elif position_type == 'SHORT':
            # For Shorts, TP is BELOW entry and SL is ABOVE entry
            if price <= locked_tp:
                # Profit = (Entry - Exit) * units + Original Capital
                # Simplest way: Entry Price + (Entry Price - Exit Price)
                # But since we use 'units', it's:
                profit = (units * locked_sl) - (units * price) # conceptual
                balance = units * (analysis['entry_price'] + (analysis['entry_price'] - price))
                balance = units * analysis['entry_price'] * (1 + (analysis['entry_price'] - price)/analysis['entry_price'])
                # Standard PnL math for backtest:
                entry_val = units * analysis['entry_price']
                balance = entry_val + (entry_val - (units * price))
                wins += 1
                print(f"✅ TP SHORT at ${price:.2f}")
                position_type = None
            elif price >= locked_sl:
                entry_val = units * analysis['entry_price']
                balance = entry_val + (entry_val - (units * price))
                print(f"❌ SL SHORT at ${price:.2f}")
                position_type = None

    final_value = balance if position_type is None else 10000 # fallback
    total_profit = final_value - 10000
    
    print("-" * 60)
    print(f"📊 FINAL RESULTS FOR {symbol}")
    print(f"Total Trades: {trade_count}")
    if trade_count > 0:
        print(f"Win Rate: {(wins/trade_count)*100:.1f}%")
        print(f"Total Profit/Loss: ${total_profit:.2f} ({ (total_profit/10000)*100:.2f}%)")

if __name__ == "__main__":
    run_10_day_test("TSLA") # Let's try Tesla!
