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

    # 2. --- FAILOVER: ALPACA (STRICT 2025 SDK RULES) ---
    try:
        from app import CONFIG
        api = REST(CONFIG['alpaca_api_key'], CONFIG['alpaca_secret_key'], base_url="https://paper-api.alpaca.markets")
        
        search_symbol = f"{clean_symbol}/USD" if clean_symbol in ['BTC', 'ETH', 'SOL'] else clean_symbol
        val = int(''.join(filter(str.isdigit, interval)))
        tf_unit = TimeFrame.Minute if "m" in interval.lower() else TimeFrame.Hour
        
        # INCREASED LOOKBACK: ensures 200-period MA is fully primed
        start_time = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        if clean_symbol in ['BTC', 'ETH', 'SOL']:
            # 1000 bars ensures sufficient 'warm-up' data for calculations
            bars_obj = api.get_crypto_bars(symbol=[search_symbol], timeframe=TimeFrame(val, tf_unit), start=start_time, limit=1000)
        else:
            bars_obj = api.get_bars(symbol=[search_symbol], timeframe=TimeFrame(val, tf_unit), start=start_time, limit=1000)

        bars = bars_obj.df
        
        if not bars.empty:
            df = bars.rename(columns={'open':'Open', 'high':'High', 'low':'Low', 'close':'Close', 'volume':'Volume'})
            df.index = pd.to_datetime(df.index, utc=True)
            
            # CRITICAL FIX: Properly flatten Alpaca's MultiIndex for the chart and calculator
            if isinstance(df.index, pd.MultiIndex):
                df = df.xs(search_symbol, level=0)

            logger.info(f"🛡️ {symbol}: Alpaca Failover Success (Primed with 1000 bars).")
            return df
                
    except Exception as e:
        logger.error(f"❌ Critical Failure: {e}")
    
    return pd.DataFrame()
