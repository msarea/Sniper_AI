import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

def generate_prediction_and_risk(df):
    try:
        # Require enough data for the longest indicator (MA_Long: 21 + some buffer)
        if df is None or len(df) < 35:
            return {'signal': 'HOLD', 'confluence_score': 0, 'entry_price': 0, 'sl_price': 0, 'tp_price': 0}

        # --- PART 1: INDICATOR CALCULATIONS ---
        # Using .copy() to avoid SettingWithCopyWarning
        df = df.copy()
        
        df['MA_Short'] = df['Close'].rolling(window=9).mean()
        df['MA_Long'] = df['Close'].rolling(window=21).mean()

        # VWAP calculation
        v = df['Volume'].values
        tp = (df['High'] + df['Low'] + df['Close']).values / 3
        cum_vol = v.cumsum()
        with np.errstate(divide='ignore', invalid='ignore'):
            df['VWAP'] = (tp * v).cumsum() / np.where(cum_vol == 0, 1, cum_vol)

        # Bollinger Bands
        std = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = df['MA_Short'] + (std * 2)
        df['BB_Lower'] = df['MA_Short'] - (std * 2)

        # MACD
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD_Line'] = exp1 - exp2
        df['MACD_Signal'] = df['MACD_Line'].ewm(span=9, adjust=False).mean()

        # ATR (Volatility)
        high_low = df['High'] - df['Low']
        high_cp = np.abs(df['High'] - df['Close'].shift())
        low_cp = np.abs(df['Low'] - df['Close'].shift())
        df['TR'] = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
        df['ATR'] = df['TR'].rolling(window=14).mean()

        # Final check for NaNs in critical indicators
        latest = df.iloc[-1]
        if pd.isna(latest['MA_Long']) or pd.isna(latest['ATR']):
            return {'signal': 'HOLD', 'confluence_score': 0, 'entry_price': 0, 'sl_price': 0, 'tp_price': 0}

    except Exception as e:
        logger.error(f"Error calculating indicators: {e}")
        return {'signal': 'HOLD', 'confluence_score': 0, 'entry_price': 0, 'sl_price': 0, 'tp_price': 0}

    # --- PART 2: THE DECISION ENGINE ---
    signals = {"Trend": "NEUTRAL", "VWAP": "NEUTRAL", "Bollinger": "NEUTRAL", "MACD": "NEUTRAL"}
    score = 0

    # 1. Trend (EMA)
    if latest['MA_Short'] > latest['MA_Long']:
        signals["Trend"], score = "BUY", score + 1
    elif latest['MA_Short'] < latest['MA_Long']:
        signals["Trend"], score = "SELL", score - 1

    # 2. Value (VWAP)
    if latest['Close'] > latest['VWAP']:
        signals["VWAP"], score = "BUY", score + 1
    elif latest['Close'] < latest['VWAP']:
        signals["VWAP"], score = "SELL", score - 1

    # 3. Volatility (Bollinger)
    if latest['Close'] < latest['BB_Lower']:
        signals["Bollinger"], score = "BUY", score + 1
    elif latest['Close'] > latest['BB_Upper']:
        signals["Bollinger"], score = "SELL", score - 1

    # 4. Momentum (MACD)
    if latest['MACD_Line'] > latest['MACD_Signal']:
        signals["MACD"], score = "BUY", score + 1
    elif latest['MACD_Line'] < latest['MACD_Signal']:
        signals["MACD"], score = "SELL", score - 1

    # --- PART 3: RISK MANAGEMENT & SIGNAL FILTER ---
    final_signal = "HOLD"
    # Strict filter: Require at least 3 points of agreement
    if score >= 3: final_signal = "BUY"
    elif score <= -3: final_signal = "SELL"

    entry_price = round(float(latest['Close']), 2)
    atr = latest['ATR']
    
    # Default values to prevent backtester "Instant Exit" glitch
    sl_price = 0
    tp_price = 0

    # Calculate TP/SL ONLY if we have a valid signal
    if final_signal == "BUY":
        sl_price = round(entry_price - (atr * 2), 2)
        tp_price = round(entry_price + (atr * 4), 2)
    elif final_signal == "SELL":
        sl_price = round(entry_price + (atr * 2), 2)
        tp_price = round(entry_price - (atr * 4), 2)

    return {
        'signal': final_signal,
        'confluence': abs(score),
        'entry_price': entry_price,
        'sl_price': sl_price,
        'tp_price': tp_price,
        'dashboard': signals
    }
