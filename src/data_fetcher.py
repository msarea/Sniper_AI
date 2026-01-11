import pandas as pd
import requests
import logging
from datetime import datetime, timedelta
from alpaca_trade_api.rest import REST, TimeFrame

logger = logging.getLogger(__name__)

def fetch_market_data(symbol: str, config: dict, period: str = "7d", interval: str = "5m") -> pd.DataFrame:
    """
    Unified Data Fetcher with extended lookback for indicator 'warm-up'.
    Period increased to 7d and Alpaca limit to 1000 bars.
    """
    clean_symbol = symbol.upper().strip()
    
    # 1. --- PRIMARY: YAHOO FINANCE ---
    try:
        yahoo_sym = f"{clean_symbol}-USD" if clean_symbol in ['BTC', 'ETH', 'SOL'] else clean_symbol
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{yahoo_sym}"
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/131.0.0.0 Safari/537.36"}
        
        # We use a 7-day range to ensure 200+ candles are always available for indicators
        response = requests.get(url, params={"interval": interval, "range": "7d"}, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('chart') and data['chart'].get('result'):
                result = data['chart']['result'][0]
                df = pd.DataFrame(result['indicators']['quote'][0], index=pd.to_datetime(result['timestamp'], unit='s', utc=True))
                df.columns = [c.capitalize() for c in df.columns]
                df.dropna(subset=['Close'], inplace=True)
                
                # Standardize resampling to handle small gaps in market data
                df = df.resample(interval.replace('m', 'min')).ffill()
                logger.info(f"📊 {symbol}: Data via Yahoo.")
                return df
    except Exception:
        pass

    # 2. --- FAILOVER: ALPACA (STRICT 2026 SDK RULES) ---
    try:
        # Use the passed 'config' argument instead of importing from app.py
        api_key = config.get('alpaca_api_key')
        api_secret = config.get('alpaca_secret_key')
        
        # Explicitly set the base_url to paper to avoid 401 Unauthorized errors
        api = REST(api_key, api_secret, base_url="https://paper-api.alpaca.markets")
        
        search_symbol = f"{clean_symbol}/USD" if clean_symbol in ['BTC', 'ETH', 'SOL'] else clean_symbol
        
        # Standardize timeframe to 5m if interval is weird
        val = 5 if "51" in interval else int(''.join(filter(str.isdigit, interval)))
        tf_unit = TimeFrame.Minute if "m" in interval.lower() else TimeFrame.Hour
        
        start_time = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        if clean_symbol in ['BTC', 'ETH', 'SOL']:
            # Force Crypto endpoint
            bars_obj = api.get_crypto_bars(symbol=[search_symbol], timeframe=TimeFrame(val, tf_unit), start=start_time, limit=1000)
        else:
            # Force Stock endpoint
            bars_obj = api.get_bars(symbol=[search_symbol], timeframe=TimeFrame(val, tf_unit), start=start_time, limit=1000)

        bars = bars_obj.df
        if not bars.empty:
            df = bars.rename(columns={'open':'Open', 'high':'High', 'low':'Low', 'close':'Close', 'volume':'Volume'})
            df.index = pd.to_datetime(df.index, utc=True)
            
            if isinstance(df.index, pd.MultiIndex):
                df = df.xs(search_symbol, level=0)

            logger.info(f"🛡️ {symbol}: Alpaca Failover Success.")
            return df
                
    except Exception as e:
        logger.error(f"❌ Alpaca Failover Failed: {e}")
        
    return pd.DataFrame()
