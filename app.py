import eventlet
import eventlet.debug
# Absolute top to ensure all dependencies use green threads
eventlet.monkey_patch() 

import sys, os, json, logging, threading, time, requests, subprocess, webbrowser
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
import pytz
from datetime import datetime
from pathlib import Path

# --- 1. RESOURCE & DATA PATHS ---
if getattr(sys, 'frozen', False):
    # Path for PyInstaller .app bundle
    RESOURCE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
else:
    # Path for local development
    RESOURCE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_config_path():
    # Persistent writable data in User Home directory (~/.sniper_ai/)
    config_dir = Path.home() / ".sniper_ai"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.json"

CONFIG_PATH = get_config_path()

# --- 2. CONFIGURATION HANDLER ---
def load_config():
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                return json.load(f)
        return {
            "trading_enabled": False, 
            "short_enabled": False, 
            "app_name": "Sniper AI",
            "alpaca_api_key": "",
            "alpaca_secret_key": "",
            "broker": "paper",
            "risk_per_trade": 1.0,
            "max_daily_loss": 5.0,
            "telegram_enabled": False,
            "telegram_bot_token": "",
            "telegram_chat_id": ""
        }
    except Exception as e:
        print(f"Error loading config: {e}")
        return {"trading_enabled": False}

CONFIG = load_config()

# --- 3. BOT CORE IMPORTS ---
from src.indicator_calculator import calculate_indicators
from src.trade_executor import generate_prediction_and_risk
from src.execution import ExecutionEngine
from src.data_fetcher import fetch_market_data

# --- 4. INITIALIZATION ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SNIPER")

app = Flask(__name__, 
            template_folder=os.path.join(RESOURCE_DIR, 'templates'),
            static_folder=os.path.join(RESOURCE_DIR, 'static'))

socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

current_symbol = "BTC"
is_running = True
trader = None

# --- TELEGRAM NOTIFIER ---
def send_telegram_msg(message):
    """Sends a notification to Telegram if enabled in settings."""
    if CONFIG.get('telegram_enabled') and CONFIG.get('telegram_bot_token'):
        token = CONFIG.get('telegram_bot_token')
        chat_id = CONFIG.get('telegram_chat_id')
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        try:
            requests.post(url, json=payload, timeout=5)
            logger.info("📡 Telegram Alert Sent")
        except Exception as e:
            logger.error(f"Telegram Notification Failed: {e}")

def init_trader():
    global trader
    if CONFIG.get('alpaca_api_key') and CONFIG.get('alpaca_secret_key'):
        try:
            trader = ExecutionEngine(CONFIG)
            logger.info("✅ Execution Engine Initialized")
        except Exception as e:
            logger.error(f"Trader Init Failed: {e}")

init_trader()

# --- 5. CHART HISTORY (EST TIMEFIX) ---
def send_historical_data(symbol, sid=None):
    NY_TZ = pytz.timezone('America/New_York')
    try:
        df = fetch_market_data(symbol, period="2d", interval="5m")
        if not df.empty:
            history = []
            for idx, row in df.iterrows():
                utc_idx = idx.tz_localize(pytz.utc) if idx.tzinfo is None else idx
                ny_time = utc_idx.tz_convert(NY_TZ)
                history.append({
                    'time': int(ny_time.timestamp()), 
                    'open': row['Open'], 'high': row['High'], 
                    'low': row['Low'], 'close': row['Close']
                })
            socketio.emit('chart_history', {'symbol': symbol, 'candles': history}, room=sid)
    except Exception as e: 
        logger.error(f"History Error: {e}")

# --- 6. ROUTES & SOCKETS ---
@app.route('/')
def index():
    return render_template('index.html', config=CONFIG)

@app.route('/save_config', methods=['POST'])
def save_config():
    global CONFIG, trader
    try:
        new_data = request.json
        with open(CONFIG_PATH, 'w') as f:
            json.dump(new_data, f, indent=4)
        CONFIG = new_data
        init_trader() 
        threading.Thread(target=send_telegram_msg, args=("⚙️ *Configuration Updated Successfully*",), daemon=True).start()
        return jsonify({"status": "success", "message": "✅ Configuration Saved"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/panic', methods=['POST'])
def panic():
    if trader:
        trader.emergency_close_all()
        threading.Thread(target=send_telegram_msg, args=("🚨 *EMERGENCY EXIT EXECUTED*",), daemon=True).start()
        return jsonify({"status": "success", "message": "🚨 EMERGENCY EXIT SUCCESSFUL"})
    return jsonify({"status": "error", "message": "Engine not running"}), 400

@socketio.on('connect')
def handle_connect():
    send_historical_data(current_symbol, request.sid)

@socketio.on('change_symbol')
def handle_change_symbol(data):
    global current_symbol
    current_symbol = data.get('symbol', 'BTC').upper()
    send_historical_data(current_symbol)
    socketio.emit('symbol_changed', {'symbol': current_symbol})

# --- 7. MARKET SCANNER (WITH SMART FILTER) ---
def market_scanner():
    global current_symbol, CONFIG
    NY_TZ = pytz.timezone('America/New_York')
    last_trade_time = 0
    
    # State tracking for Telegram anti-spam
    last_notified_signal = None
    last_notified_price = 0.0

    while is_running:
        try:
            symbol = current_symbol
            df = fetch_market_data(symbol)
            if df.empty: continue

            df = calculate_indicators(df)
            analysis = generate_prediction_and_risk(df)
            
            last_row = df.iloc[-1]
            current_price = float(last_row['Close'])
            utc_ts = last_row.name.tz_localize(pytz.utc) if last_row.name.tzinfo is None else last_row.name
            
            # Dashboard UI always updates instantly
            socketio.emit('analysis_update', analysis)
            socketio.emit('chart_update', {
                'time': int(utc_ts.tz_convert(NY_TZ).timestamp()),
                'open': last_row['Open'], 'high': last_row['High'], 
                'low': last_row['Low'], 'close': current_price
            })

            # --- DYNAMIC NOTIFICATION FILTER ---
            current_signal = analysis['signal']
            
            # Calculate 0.1% Change Threshold (e.g., $85 for BTC @ $85k)
            price_threshold = last_notified_price * 0.001 
            price_moved_significantly = abs(current_price - last_notified_price) > price_threshold

            if current_signal in ['BUY', 'SELL']:
                # Alert only if Signal type changed OR Price moved > 0.1%
                if current_signal != last_notified_signal or price_moved_significantly:
                    # 🚀 for Long/Buy and 📉 for Short/Sell
                    icon = "🚀" if current_signal == "BUY" else "📉"
                    msg = (f"{icon} *NEW SIGNAL: {symbol}*\n"
                           f"Action: `{current_signal}`\n"
                           f"Price: `{current_price:.2f}`\n"
                           f"Target: `{analysis['tp_price']:.2f}`\n"
                           f"Stop: `{analysis['sl_price']:.2f}`")
                    
                    threading.Thread(target=send_telegram_msg, args=(msg,), daemon=True).start()
                    
                    # Store state for next comparison
                    last_notified_signal = current_signal
                    last_notified_price = current_price
            
            elif current_signal == 'HOLD':
                # Reset signal state so we alert immediately on next BUY/SELL
                last_notified_signal = 'HOLD'

            # Execution Logic
            if CONFIG.get('trading_enabled') and trader:
                if (time.time() - last_trade_time) > 3600:
                    trade_symbol = f"{symbol}/USD" if symbol in ['BTC', 'ETH'] else symbol
                    if current_signal == 'BUY':
                        if trader.execute_long(trade_symbol, analysis['entry_price'], analysis['sl_price'], analysis['tp_price']):
                            last_trade_time = time.time()
                    elif current_signal == 'SELL' and CONFIG.get('short_enabled'):
                        if trader.execute_short(trade_symbol, analysis['entry_price'], analysis['sl_price'], analysis['tp_price']):
                            last_trade_time = time.time()
                            
        except Exception as e:
            logger.error(f"Scanner Loop Error: {e}")
        time.sleep(3)

# --- 8. RUN ---
if __name__ == '__main__':
    # Startup Console Log
    logger.info("✅ Starting Sniper AI Platinum...")
    
    # Telegram Startup Message
    threading.Thread(target=send_telegram_msg, args=("✅ *Sniper AI Platinum is Online*",), daemon=True).start()
    
    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5001")).start()
    threading.Thread(target=market_scanner, daemon=True).start()
    socketio.run(app, host='127.0.0.1', port=5001, debug=False)
