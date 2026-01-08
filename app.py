import os
import eventlet
eventlet.monkey_patch(thread=False)
import sys, os, json, logging, threading, time, requests, webbrowser
import pandas as pd
import numpy as np
import pytz
from flask import Flask, render_template, jsonify, request, send_file
from flask_socketio import SocketIO
from datetime import datetime
from pathlib import Path
from threading import Timer
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

# --- 1. RESOURCE & DATA PATHS ---
if getattr(sys, 'frozen', False):
    RESOURCE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
else:
    RESOURCE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_config_path():
    config_dir = Path.home() / ".sniper_ai"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.json"

CONFIG_PATH = get_config_path()

# --- 2. CONFIGURATION ---
# --- 2. CONFIGURATION ---
def load_config():
    cfg = {}
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r') as f: 
            cfg = json.load(f)
    
    # Check for the standard names AND the SDK-specific names
    # os.getenv checks Render's environment variables first
    api_key = os.getenv("ALPACA_API_KEY") or os.getenv("APCA_API_KEY_ID") or cfg.get("alpaca_api_key", "")
    api_secret = os.getenv("ALPACA_SECRET_KEY") or os.getenv("APCA_API_SECRET_KEY") or cfg.get("alpaca_secret_key", "")
    
    cfg["alpaca_api_key"] = api_key
    cfg["alpaca_secret_key"] = api_secret
    cfg["current_symbol"] = cfg.get("current_symbol", "BTCUSD")
    
    return cfg

# ADD THIS LINE:
CONFIG = load_config()

from src.indicator_calculator import calculate_indicators
from src.trade_executor import generate_prediction_and_risk
from src.execution import ExecutionEngine
from src.data_fetcher import fetch_market_data

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SNIPER")

def init_log_file():
    # Use CONFIG_PATH.parent to ensure it's in the same hidden directory (~/.sniper_ai/)
    log_path = CONFIG_PATH.parent / "trade_log.csv"
    if not log_path.exists():
        with open(log_path, 'w') as f:
            # Add these specific headers for your UI table to read correctly
            f.write("TIME,SYMBOL,TYPE,ENTRY,CURRENT,P/L %,STATUS\n")
        logger.info(f"📝 Initialized new trade log at {log_path}")

init_log_file()



app = Flask(__name__, 
            template_folder=os.path.join(RESOURCE_DIR, 'templates'),
            static_folder=os.path.join(RESOURCE_DIR, 'static'))

# Using async_mode='eventlet' to ensure background tasks don't block the UI
socketio = SocketIO(app, 
                   async_mode='eventlet', 
                   cors_allowed_origins="*", 
                   ping_timeout=60, 
                   ping_interval=25)

# --- GLOBAL STATE ---
current_symbol = CONFIG.get('current_symbol', "BTC/USD")
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




# --- CHART HELPERS ---
def get_ny_timestamp(idx_name):
    utc_idx = idx_name.tz_localize(pytz.utc) if idx_name.tzinfo is None else idx_name
    return int(utc_idx.tz_convert(NY_TZ).timestamp())

def send_historical_data(symbol, sid=None):
    try:
        # Reduced period slightly to speed up initial symbol switching
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

# --- MARKET SCANNER (Optimized for SocketIO) ---
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

            # Fetch data for the current active symbol
            df = fetch_market_data(current_symbol,CONFIG, period="7d", interval="5m")
            
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

                # Sanitize NaN/Inf
                clean_payload = {k: (0.0 if isinstance(v, float) and (pd.isna(v) or np.isinf(v)) else v) for k, v in clean_payload.items()}
                
                # Emit to UI
                socketio.emit('analysis_update', clean_payload)
                socketio.emit('chart_update', {
                    'time': get_ny_timestamp(last_row.name),
                    'open': float(last_row['Open']), 'high': float(last_row['High']), 
                    'low': float(last_row['Low']), 'close': float(last_row['Close'])
                })

        except Exception as e:
            logger.error(f"Scanner Logic Error: {e}")
        
        # USE socketio.sleep instead of time.sleep to prevent blocking the Eventlet hub
        socketio.sleep(4)

# --- ROUTES ---

@app.route('/')
@app.route('/<symbol>')
def index(symbol="BTC/USD"):
    # 1. Ignore favicon requests so they don't change the symbol
    if "favicon" in symbol.lower():
        return "", 204

    global current_symbol
    # Standardize the symbol
    symbol = symbol.upper().replace('-', '')
    
    # Auto-correct Crypto format for Alpaca
    if "USD" in symbol and "/" not in symbol:
        symbol = symbol.replace("USD", "/USD")
    
    current_symbol = symbol
    
    # We pass the cleaned symbol to the frontend
    return render_template('index.html', config=CONFIG, initial_symbol=current_symbol)

@app.route('/change_symbol', methods=['POST'])
def change_symbol():
    global current_symbol
    try:
        data = request.get_json()
        new_symbol = data.get('symbol', 'BTCUSD').upper()
        
        # 1. Update global state
        current_symbol = new_symbol
        
        # 2. Immediately send cleanup to UI so user doesn't see "Stale" metrics
        socketio.emit('analysis_update', {
            'symbol': 'FETCHING...',
            'signal': 'Loading ...',
            'confluence': 0,
            'total_profit': 0
        })
        
        # 3. Request fresh history for the new symbol
        send_historical_data(current_symbol)
        
        logger.info(f"🔄 Symbol Changed to: {current_symbol}")
        return jsonify({"status": "success", "symbol": new_symbol})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/save_settings', methods=['POST'])
def save_settings():
    try:
        new_cfg = request.get_json()
        CONFIG.update(new_cfg)
        with open(CONFIG_PATH, 'w') as f:
            json.dump(CONFIG, f, indent=4)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/download_log')
def download_log():
    log_path = CONFIG_PATH.parent / "trade_log.csv"
    if log_path.exists():
        return send_file(log_path, as_attachment=True)
    return "Log file not found.", 404

@app.route('/panic_exit', methods=['POST'])
def panic_exit():
    global trader
    try:
        if trader:
            trader.api.close_all_positions()
            trader.api.cancel_all_orders()
            return jsonify({"status": "success", "message": "EMERGENCY EXIT COMPLETE."})
        return jsonify({"status": "error", "message": "Trader not active."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- NEW: Ensure scanner starts even under Gunicorn ---
# --- THE FINAL PRODUCTION STARTUP LOGIC ---

def start_scanner(app_context):
    # This allows the background thread to see your CONFIG and other Flask data
    with app_context:
        logger.info("⏳ Waiting for server to settle...")
        eventlet.sleep(5) 
        
        # 1. Connect to Alpaca safely inside the context
        init_trader() 
        
        # 2. Start the scanner loop
        logger.info("📡 Initializing Global Background Task...")
        market_scanner()

@app.before_request
def initialize_scanner():
    # We use app.app_context() to bridge the gap between Flask and Eventlet
    if not hasattr(app, 'scanner_started'):
        app.scanner_started = True
        socketio.start_background_task(start_scanner, app.app_context())

if __name__ == '__main__':
    # Local development settings
    socketio.run(app, host='127.0.0.1', port=5001, debug=False)
