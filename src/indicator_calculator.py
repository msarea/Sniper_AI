import pandas as pd
import numpy as np

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    # 1. FIX: Only convert OHLCV columns to float. 
    # This prevents the "BTC/USD" string conversion error
    numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').astype(float)

    # 2. MOVING AVERAGES (Trend MA Support)
    # Using min_periods=1 ensures indicators appear immediately
    df['Fast_MA'] = df['Close'].rolling(window=10, min_periods=1).mean()
    df['Slow_MA'] = df['Close'].rolling(window=50, min_periods=1).mean()
    df['Trend_MA'] = df['Close'].rolling(window=200, min_periods=1).mean()

    # 3. RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
    rs = gain / (loss + 1e-10)
    df['RSI'] = 100 - (100 / (1 + rs))

    # 4. VWAP
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP'] = (df['TP'] * df['Volume']).cumsum() / (df['Volume'].cumsum() + 1e-10)

    # 5. BOLLINGER BANDS
    df['BB_Middle'] = df['Close'].rolling(window=20, min_periods=1).mean()
    std_dev = df['Close'].rolling(window=20, min_periods=1).std()
    df['BB_Upper'] = df['BB_Middle'] + (2 * std_dev)
    df['BB_Lower'] = df['BB_Middle'] - (2 * std_dev)

    # 6. MACD
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_hist'] = df['MACD'] - df['Signal_Line']

    # 7. ADX & ATR (Matching Dashboard Keys)
    window = 14
    df['tr0'] = abs(df['High'] - df['Low'])
    df['tr1'] = abs(df['High'] - df['Close'].shift())
    df['tr2'] = abs(df['Low'] - df['Close'].shift())
    df['TR'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)

    def wilders_smoothing(data, window):
        return data.ewm(alpha=1/window, adjust=False, min_periods=1).mean()

    df['ATR'] = wilders_smoothing(df['TR'], window)
    
    # Directional Movement
    df['plus_dm'] = np.where((df['High'] - df['High'].shift() > df['Low'].shift() - df['Low']) & (df['High'] - df['High'].shift() > 0), df['High'] - df['High'].shift(), 0)
    df['minus_dm'] = np.where((df['Low'].shift() - df['Low'] > df['High'] - df['High'].shift()) & (df['Low'].shift() - df['Low'] > 0), df['Low'].shift() - df['Low'], 0)

    df['plus_di'] = 100 * (wilders_smoothing(df['plus_dm'], window) / (df['ATR'] + 1e-10))
    df['minus_di'] = 100 * (wilders_smoothing(df['minus_dm'], window) / (df['ATR'] + 1e-10))
    dx = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'] + 1e-10)
    df['ADX'] = wilders_smoothing(dx, window)

    # 8. FINAL STABILIZATION
    # Modern fill methods to ensure no NaNs are sent to the UI
    df.fillna(0, inplace=True)
    df.replace([np.inf, -np.inf], 0, inplace=True)

    return df
