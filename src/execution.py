import alpaca_trade_api as tradeapi
import logging

logger = logging.getLogger(__name__)

class ExecutionEngine:
    def __init__(self, config):
        self.config = config
        self.api_key = config.get('alpaca_api_key')
        self.secret_key = config.get('alpaca_secret_key')
        
        # Base URL Selection
        self.base_url = "https://paper-api.alpaca.markets" if config.get('broker') == 'paper' else "https://api.alpaca.markets"

        if not self.api_key or not self.secret_key:
            raise ValueError("Alpaca API Keys missing in config.json")

        self.api = tradeapi.REST(
            key_id=self.api_key, 
            secret_key=self.secret_key, 
            base_url=self.base_url, 
            api_version='v2'
        )
        
        self.risk_pct = float(config.get('risk_per_trade', 1.0)) / 100.0

    def calculate_trade_qty(self, symbol, entry_price, sl_price):
        """Calculates quantity with fractional support for Crypto and whole numbers for Stocks."""
        try:
            account = self.api.get_account()
            equity = float(account.equity)
            # Use non_marginable_buying_power for safer paper trading limits
            available_cash = float(account.non_marginable_buying_power)

            # 1. Risk-Based Position Sizing (Risk Amount / Distance to Stop)
            risk_amount = equity * self.risk_pct
            risk_per_unit = abs(entry_price - sl_price)
            
            # Prevent Division by Zero with minimum tick
            if risk_per_unit < 0.01: risk_per_unit = 0.01
            
            intended_qty = risk_amount / risk_per_unit

            # 2. Safety Budget Cap (Don't use more than 95% of cash)
            max_affordable = (available_cash * 0.95) / entry_price
            qty = min(intended_qty, max_affordable)

            # 3. Precision Formatting based on asset type
            if "/USD" in symbol or any(c in symbol for c in ['BTC', 'ETH', 'SOL']):
                # Crypto lot sizes vary; 4 decimals is a safe universal standard for major coins
                return round(qty, 4) 
            else:
                # Standard US Stocks require whole shares for most bracket orders
                return int(qty)      

        except Exception as e:
            logger.error(f"Error calculating quantity for {symbol}: {e}")
            return 0

    def execute_long(self, symbol, entry, sl, tp):
        """Execute Long with Alpaca Safety Buffers and Bracket Logic."""
        qty = self.calculate_trade_qty(symbol, entry, sl)
        if qty <= 0:
            logger.warning(f"Quantity too low for {symbol}. Trade skipped.")
            return False

        try:
            # SAFETY BUFFERS: Alpaca requires a minimum spread for brackets
            valid_sl = round(min(entry - 0.01, sl), 2)
            valid_tp = round(max(entry + 0.01, tp), 2)

            if "/USD" in symbol:
                # Manual Bracket for Crypto (Alpaca API v2 constraint)
                # 1. Entry Order
                self.api.submit_order(symbol=symbol, qty=qty, side='buy', type='market', time_in_force='gtc')
                # 2. Stop Loss (Stop-Limit)
                self.api.submit_order(symbol=symbol, qty=qty, side='sell', type='stop_limit', 
                                      stop_price=valid_sl, limit_price=round(valid_sl * 0.995, 2), time_in_force='gtc')
                # 3. Take Profit
                self.api.submit_order(symbol=symbol, qty=qty, side='sell', type='limit', limit_price=valid_tp, time_in_force='gtc')
            else:
                # Native Bracket for Stocks
                self.api.submit_order(
                    symbol=symbol, qty=qty, side='buy', type='market', 
                    time_in_force='day', order_class='bracket',
                    take_profit={'limit_price': valid_tp},
                    stop_loss={'stop_price': valid_sl}
                )

            logger.info(f"✅ LONG PLACED: {symbol} | Qty: {qty} | SL: {valid_sl} | TP: {valid_tp}")
            return True
        except Exception as e:
            logger.error(f"❌ Long Execution Failed for {symbol}: {e}")
            return False

    def execute_short(self, symbol, entry, sl, tp):
        """Execute Short with Alpaca Safety Buffers."""
        qty = self.calculate_trade_qty(symbol, entry, sl)
        if qty <= 0: return False

        try:
            valid_sl = round(max(entry + 0.01, sl), 2)
            valid_tp = round(min(entry - 0.01, tp), 2)

            if "/USD" in symbol:
                self.api.submit_order(symbol=symbol, qty=qty, side='sell', type='market', time_in_force='gtc')
                self.api.submit_order(symbol=symbol, qty=qty, side='buy', type='stop_limit', 
                                      stop_price=valid_sl, limit_price=round(valid_sl * 1.005, 2), time_in_force='gtc')
                self.api.submit_order(symbol=symbol, qty=qty, side='buy', type='limit', limit_price=valid_tp, time_in_force='gtc')
            else:
                self.api.submit_order(
                    symbol=symbol, qty=qty, side='sell', type='market', 
                    time_in_force='day', order_class='bracket',
                    take_profit={'limit_price': valid_tp},
                    stop_loss={'stop_price': valid_sl}
                )

            logger.info(f"📉 SHORT PLACED: {symbol} | Qty: {qty} | SL: {valid_sl} | TP: {valid_tp}")
            return True
        except Exception as e:
            logger.error(f"❌ Short Execution Failed for {symbol}: {e}")
            return False

    def emergency_close_all(self):
        """Liquidates all positions and cancels all pending orders."""
        try:
            self.api.cancel_all_orders()
            self.api.close_all_positions()
            logger.info("🚨 EMERGENCY EXIT: Portfolio liquidated.")
            return True
        except Exception as e:
            logger.error(f"Panic Exit Error: {e}")
            return False
