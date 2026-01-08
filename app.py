import os
import eventlet
eventlet.monkey_patch(thread=False)
import sys, json, logging, threading, time, requests, webbrowser
import pandas as pd
import numpy as np
import pytz
from flask import Flask, render_template, jsonify, request, send_file
from flask_socketio import SocketIO
from datetime import datetime
from pathlib import Path
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

# --- LICENSE & SECURITY ---
def verify_license():
    EXPIRY_DATE = datetime(2026, 1, 14)
    try:
        response = requests.get('http://worldtimeapi.org/api/timezone/Etc/UTC', timeout=5)
        current_date = datetime.fromisoformat(response.json()['datetime'][:10])
    except:
        current_date = datetime.now()
    if current_date > EXPIRY_DATE:
        print("❌ LICENSE EXPIRED: Please contact developer.")
        sys.exit()

verify_license()

# --- RESOURCE & DATA PATHS ---
if getattr(sys, 'frozen', False):
    RESOURCE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
else:
    RESOURCE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_config_path():
    config_dir = Path.home() / ".sniper_ai"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.json"

CONFIG_PATH = get_config_path()

# --- CONFIGURATION ---
def load_config():
    cfg = {}
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r') as f: 
            cfg = json.load(f)
    
    # Securely pull keys from Render environment or local config
    cfg["alpaca_api_key"] = os.getenv("APCA_API_KEY_ID") or cfg.get("alpaca_api_key", "")
    cfg["alpaca_secret_key"] = os.getenv("APCA_API_SECRET_KEY") or cfg.get("alpaca_secret_key", "")
    
    # We force the slash here to prevent "Endpoint Not Found"
    cfg["current_symbol"] = "BTC/USD" 
    return cfg

CONFIG = load_config()

from src.indicator_calculator import calculate_indicators
from src.trade_executor import generate_prediction_and_risk
from src.execution import ExecutionEngine
from src.data_fetcher import fetch_market_data

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SNIPER")

def init_log_file():
    log_path = CONFIG_PATH.parent / "trade_log.csv"
    if not log_path.exists():
        with open(log_path, 'w') as f:
            f.write("TIME,SYMBOL,TYPE,ENTRY,CURRENT,P/L %,STATUS\n")
        logger.info(f"📝 Initialized new trade log at {log_path}")

init_log_file()

app = Flask(__name__, 
            template_folder=os.path.join(RESOURCE_DIR, 'templates'),
            static_folder=os.path.join(RESOURCE_DIR, 'static'))

socketio = SocketIO(app, 
                    async_mode='eventlet', 
                    cors_allowed_origins="*", 
                    ping_timeout=60, 
                    ping_interval=25)

# --- GLOBAL STATE ---
current_symbol = "BTC/USD"
trader = None
session_start_equity = 0.0
NY_TZ = pytz.timezone('America/New_York')

def init_trader():
    global trader, session_start_equity
    if CONFIG.get('alpaca_api_key'):
        try:
            trader = ExecutionEngine(CONFIG)
            account = trader.api.get_account()
            session_start_equity = float(account.equity)
            logger.info(f"✅ Broker Synced. Starting Balance: ${session_start_equity}")
        except Exception as e:
            logger.error(f"❌ Broker Connection Failed: {e}")

# NOTE: init_trader() call is REMOVED from here to prevent RuntimeError.

# --- HELPERS ---
def get_ny_timestamp(idx_name):
    utc_idx = idx_name.tz_localize(pytz.utc) if idx_name.tzinfo is None else idx_name
    return int(utc_idx.tz_convert(NY_TZ).timestamp())

def send_historical_data(symbol, sid=None):
    try:
        df = fetch_market_data(symbol, CONFIG, period="3d", interval="5m")
        if not df.empty:
            history = [{'time': get_ny_timestamp(idx), 'open': float(row['Open']), 'high': float(row['High']), 
                        'low': float(row['Low']), 'close': float(row['Close'])} for idx, row in df.iterrows()]
            socketio.emit('chart_history', {'symbol': symbol, 'candles': history}, to=sid)
    except Exception as e:
        logger.error(f"History Error: {e}")

@socketio.on('connect')
def handle_connect():
    send_historical_data(current_symbol, request.sid)

def market_scanner():
    global current_symbol, session_start_equity
    logger.info("🚀 Background Scanner Started")
    
    while True:
        try:
            live_profit = 0.0
            if trader:
                try:
                    acc = trader.api.get_account()
                    live_profit = float(acc.equity) - session_start_equity
                except: pass

            df = fetch_market_data(current_symbol, CONFIG, period="7d", interval="5m")
            
            if not df.empty:
                df = calculate_indicators(df)
                analysis = generate_prediction_and_risk(df)
                last_row = df.iloc[-1]
                
                clean_payload = {
                    'symbol': current_symbol,
                    'total_profit': round(float(live_profit), 2),
                    'signal': analysis.get('signal', 'HOLD'),
                    'regime': analysis.get('regime', 'RANGING'),
                    'confluence': analysis.get('confluence', 0),
                    'entry_price': round(float(last_row['Close']), 2),
                    'sl_price': round(float(analysis.get('sl_price', 0)), 2),
                    'tp_price': round(float(analysis.get('tp_price', 0)), 2),
                    'adx': round(float(last_row.get('ADX', 0)), 2),
                    'rsi': round(float(last_row.get('RSI', 0)), 2),
                    'atr': round(float(last_row.get('ATR', 0)), 2),
                    'dashboard': {
                        'Trend': 'BUY' if last_row['Fast_MA'] > last_row['Slow_MA'] else 'SELL',
                        'VWAP': 'BUY' if last_row['Close'] > last_row['VWAP'] else 'SELL',
                        'Bollinger': 'BUY' if last_row['Close'] <= last_row['BB_Lower'] else 'SELL' if last_row['Close'] >= last_row['BB_Upper'] else 'HOLD',
                        'MACD': 'BUY' if last_row['MACD_hist'] > 0 else 'SELL'
                    }
                }
                clean_payload = {k: (0.0 if isinstance(v, float) and (pd.isna(v) or np.isinf(v)) else v) for k, v in clean_payload.items()}
                socketio.emit('analysis_update', clean_payload)
                socketio.emit('chart_update', {
                    'time': get_ny_timestamp(last_row.name),
                    'open': float(last_row['Open']), 'high': float(last_row['High']), 
                    'low': float(last_row['Low']), 'close': float(last_row['Close'])
                })
        except Exception as e:
            logger.error(f"Scanner Logic Error: {e}")
        socketio.sleep(4)

@app.route('/')
@app.route('/<symbol>')
def index(symbol="BTC/USD"):
    if "favicon" in symbol.lower(): return "", 204
    global current_symbol
    symbol = symbol.upper().replace('-', '')
    if "USD" in symbol and "/" not in symbol:
        symbol = symbol.replace("USD", "/USD")
    current_symbol = symbol
    return render_template('index.html', config=CONFIG, initial_symbol=current_symbol)

# --- STARTUP LOGIC ---
def start_scanner(app_context):
    with app_context:
        logger.info("⏳ Waiting for server to settle...")
        eventlet.sleep(8) # Increased to 8 for Render stability
        init_trader() 
        logger.info("📡 Initializing Global Background Task...")
        market_scanner()

@app.before_request
def initialize_scanner():
    if not hasattr(app, 'scanner_started'):
        app.scanner_started = True
        socketio.start_background_task(start_scanner, app.app_context())

if __name__ == '__main__':
    socketio.run(app, host='127.0.0.1', port=5001, debug=False)
