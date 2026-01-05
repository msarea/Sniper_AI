import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

def generate_prediction_and_risk(df):
    try:
        # 1. VALIDATION & STABILITY CHECK
        # We check for at least 50 bars to stabilize the MAs
        if df is None or len(df) < 50: 
            return {
                'signal': 'HOLD', 'confluence': 0, 'regime': 'WAITING...',
                'entry_price': 0, 'sl_price': 0, 'tp_price': 0,
                'rsi': 0, 'adx': 0, 'atr': 0
            }

        latest = df.iloc[-1]
        prev = df.iloc[-2] # Required for the "Reclaim" cross-over logic
        
        entry_price = round(float(latest['Close']), 2)
        atr = float(latest.get('ATR', 0))
        adx = float(latest.get('ADX', 0))
        rsi = float(latest.get('RSI', 0))
        ema_9 = float(latest.get('Fast_MA', 0)) # Using 9/10 EMA proxy
        
        # --- PART 2: REGIME IDENTIFICATION (The Gatekeeper) ---
        # 9 EMA Sniper logic is only active in TRENDING regimes
        if adx > 25:
            regime = "TRENDING"
        elif adx < 20:
            regime = "RANGING"
        else:
            regime = "STABILIZING"

        final_signal = "HOLD"
        confluence_points = 0
        total_possible = 6 # Increased due to new Sniper trigger

        # --- PART 3: TRENDING LOGIC (With SMB Sniper Fusion) ---
        if regime == "TRENDING":
            # BULLISH ALIGNMENT
            if latest['Close'] > latest['Slow_MA'] and latest['Close'] > latest.get('Trend_MA', 0):
                
                # SNIPER TRIGGER: SMB Capital 9 EMA Reclaim
                # Logic: Previous candle closed below 9 EMA, Current candle closed above it
                if prev['Close'] < ema_9 and latest['Close'] >= ema_9:
                    confluence_points += 3 # High weight for precision entry
                
                # PLATINUM SAFETY FILTERS
                if latest.get('MACD_hist', 0) > 0: confluence_points += 1
                if latest['Close'] > latest.get('VWAP', 0): confluence_points += 1
                if 40 < rsi < 70: confluence_points += 1 

            # BEARISH ALIGNMENT
            elif latest['Close'] < latest['Slow_MA'] and latest['Close'] < latest.get('Trend_MA', 0):
                
                # SNIPER TRIGGER: 9 EMA Reclaim (Short)
                if prev['Close'] > ema_9 and latest['Close'] <= ema_9:
                    confluence_points -= 3
                
                if latest.get('MACD_hist', 0) < 0: confluence_points -= 1
                if latest['Close'] < latest.get('VWAP', 0): confluence_points -= 1
                if 30 < rsi < 60: confluence_points -= 1

            # SIGNAL THRESHOLD (Requires Sniper + at least 1 Platinum Filter)
            if confluence_points >= 4: final_signal = "BUY"
            elif confluence_points <= -4: final_signal = "SELL"

        # --- PART 4: RANGING LOGIC (Defensive Mean Reversion) ---
        # Prevents 9 EMA "Whipsaw" in choppy markets
        elif regime == "RANGING":
            if latest['Close'] <= latest.get('BB_Lower', 0) and rsi < 35:
                final_signal = "BUY"
                confluence_points = 5 
            elif latest['Close'] >= latest.get('BB_Upper', 0) and rsi > 65:
                final_signal = "SELL"
                confluence_points = 5

        # --- PART 5: RISK MANAGEMENT (ATR Platinum Shield) ---
        # Using ATR for safety instead of fixed SMB candle stops
        sl_price = 0
        tp_price = 0
        if final_signal == "BUY":
            sl_price = round(entry_price - (atr * 2.0), 2)
            tp_price = round(entry_price + (atr * 3.0), 2)
        elif final_signal == "SELL":
            sl_price = round(entry_price + (atr * 2.0), 2)
            tp_price = round(entry_price - (atr * 3.0), 2)

        return {
            'signal': final_signal,
            'confluence': min(100, int((abs(confluence_points) / total_possible) * 100)),
            'regime': regime,
            'entry_price': entry_price,
            'sl_price': sl_price,
            'tp_price': tp_price,
            'rsi': round(rsi, 2),
            'adx': round(adx, 2),
            'atr': round(atr, 2)
        }

    except Exception as e:
        logger.error(f"Error in Fusion Engine: {e}")
        return {'signal': 'HOLD', 'confluence': 0, 'regime': 'ERROR', 'entry_price': 0}
