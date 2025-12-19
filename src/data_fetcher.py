# src/data_fetcher.py

import pandas as pd
import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def fetch_market_data(symbol: str, period: str = "5d", interval: str = "5m") -> pd.DataFrame:
    """
    Directly fetches data from Yahoo's Query1 API.
    Bypasses yfinance library wrappers to avoid PyInstaller/Freezing issues.
    """
    try:
        clean_symbol = symbol.upper().strip()
        
        # 1. Handle Crypto Logic
        crypto_assets = ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'ADA', 'AVAX', 'DOT', 'LTC', 'LINK']
        if clean_symbol in crypto_assets:
            search_sym = f"{clean_symbol}-USD"
        else:
            search_sym = clean_symbol

        # 2. Yahoo Query API URL (Direct Access)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{search_sym}"
        
        params = {
            "interval": interval,
            "range": period,
            "includePrePost": "false"
        }
        
        # 3. Headers (Look like a standard Windows Chrome user)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        # 4. Request
        response = requests.get(url, params=params, headers=headers, timeout=5)
        data = response.json()

        # 5. Parse Response
        # The API returns a nested JSON structure. We dig into it.
        result = data['chart']['result'][0]
        timestamps = result['timestamp']
        quote = result['indicators']['quote'][0]
        
        # Create DataFrame with UTC timezone-aware index
        # Yahoo Finance timestamps are Unix timestamps (UTC)
        import pytz
        df = pd.DataFrame({
            'Open': quote['open'],
            'High': quote['high'],
            'Low': quote['low'],
            'Close': quote['close'],
            'Volume': quote['volume']
        }, index=pd.to_datetime(timestamps, unit='s', utc=True))

        # 6. Clean Data
        df.dropna(inplace=True)
        df.index.name = "Date"
        
        return df

    except Exception as e:
        logger.error(f"Direct API Error for {symbol}: {e}")
        return pd.DataFrame()
