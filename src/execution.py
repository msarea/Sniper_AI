import alpaca_trade_api as tradeapi
import logging

logger = logging.getLogger(__name__)

class ExecutionEngine:
    def __init__(self, config):
        self.config = config
        self.api_key = config.get('alpaca_api_key')
        self.secret_key = config.get('alpaca_secret_key')
        
        # Determine Base URL (Paper vs Live)
        self.base_url = "https://paper-api.alpaca.markets" if config.get('broker') == 'paper' else "https://api.alpaca.markets"

        if not self.api_key or not self.secret_key:
            raise ValueError("Alpaca API Keys missing in config.json")

        # Initialize Alpaca REST
        self.api = tradeapi.REST(
            key_id=self.api_key, 
            secret_key=self.secret_key, 
            base_url=self.base_url, 
            api_version='v2'
        )
        
        # Risk percentage per trade (default 0.25%)
        self.risk_pct = config.get('risk_settings', {}).get('risk_per_trade_percent', 0.25) / 100.0

    def calculate_trade_qty(self, symbol, entry_price, sl_price):
        """
        Calculates the safest quantity based on risk settings and available cash.
        Includes the 95% Budget Cap protection.
        """
        try:
            account = self.api.get_account()
            equity = float(account.equity)
            available_cash = float(account.non_marginable_buying_power)

            # 1. Calculate risk-based quantity
            risk_amount = equity * self.risk_pct
            risk_per_unit = abs(entry_price - sl_price)
            
            if risk_per_unit == 0:
                return 0
            
            intended_qty = risk_amount / risk_per_unit

            # 2. Apply Budget Cap (Don't use more than 95% of cash)
            max_affordable = (available_cash * 0.95) / entry_price
            
            qty = min(intended_qty, max_affordable)

            # 3. Format based on asset type
            # Crypto allows decimals, Stocks usually require integers
            if "/USD" in symbol:
                return round(qty, 4)
            else:
                return int(qty)

        except Exception as e:
            logger.error(f"Error calculating quantity: {e}")
            return 0

    def execute_long(self, symbol, entry, sl, tp):
        """
        Dedicated Long Logic: Buy to Open -> Sell to Close.
        """
        qty = self.calculate_trade_qty(symbol, entry, sl)
        if qty <= 0:
            logger.warning(f"Quantity too low for {symbol} LONG")
            return {'success': False}

        try:
            if "/USD" in symbol:
                # Crypto: Manual Bracket (Market Entry + Stop Limit SL + Limit TP)
                self.api.submit_order(symbol=symbol, qty=qty, side='buy', type='market', time_in_force='gtc')
                
                # Stop Loss (Side is Sell)
                self.api.submit_order(
                    symbol=symbol, qty=qty, side='sell', type='stop_limit',
                    stop_price=round(sl, 2), limit_price=round(sl * 0.99, 2), time_in_force='gtc'
                )
                # Take Profit (Side is Sell)
                self.api.submit_order(symbol=symbol, qty=qty, side='sell', type='limit', limit_price=round(tp, 2), time_in_force='gtc')
            else:
                # Stocks: Native Alpaca Bracket
                self.api.submit_order(
                    symbol=symbol, qty=qty, side='buy', type='market', 
                    time_in_force='day', order_class='bracket',
                    take_profit={'limit_price': round(tp, 2)},
                    stop_loss={'stop_price': round(sl, 2)}
                )

            logger.info(f"✅ LONG ORDER PLACED: {qty} units of {symbol}")
            return {'success': True, 'quantity': qty}

        except Exception as e:
            logger.error(f"❌ Long Execution Failed: {e}")
            return {'success': False}

    def execute_short(self, symbol, entry, sl, tp):
        """
        Dedicated Short Logic: Sell to Open -> Buy to Close.
        Checks if asset is shortable before proceeding.
        """
        qty = self.calculate_trade_qty(symbol, entry, sl)
        if qty <= 0:
            logger.warning(f"Quantity too low for {symbol} SHORT")
            return {'success': False}

        try:
            # Short-selling guardrail for stocks
            if "/USD" not in symbol:
                asset = self.api.get_asset(symbol)
                if not asset.shortable:
                    logger.error(f"❌ {symbol} is NOT shortable on Alpaca.")
                    return {'success': False}

            if "/USD" in symbol:
                # Crypto: Manual Short Bracket (Sell Entry -> Buy SL -> Buy TP)
                self.api.submit_order(symbol=symbol, qty=qty, side='sell', type='market', time_in_force='gtc')
                
                # Stop Loss (Side is Buy for Short)
                self.api.submit_order(
                    symbol=symbol, qty=qty, side='buy', type='stop_limit',
                    stop_price=round(sl, 2), limit_price=round(sl * 1.01, 2), time_in_force='gtc'
                )
                # Take Profit (Side is Buy for Short)
                self.api.submit_order(symbol=symbol, qty=qty, side='buy', type='limit', limit_price=round(tp, 2), time_in_force='gtc')
            else:
                # Stocks: Native Alpaca Bracket
                self.api.submit_order(
                    symbol=symbol, qty=qty, side='sell', type='market', 
                    time_in_force='day', order_class='bracket',
                    take_profit={'limit_price': round(tp, 2)},
                    stop_loss={'stop_price': round(sl, 2)}
                )

            logger.info(f"📉 SHORT ORDER PLACED: {qty} units of {symbol}")
            return {'success': True, 'quantity': qty}

        except Exception as e:
            logger.error(f"❌ Short Execution Failed: {e}")
            return {'success': False}

    def emergency_close_all(self):
        """Cancels all pending orders and liquidates all positions."""
        try:
            self.api.cancel_all_orders()
            self.api.close_all_positions()
            logger.info("🚨 EMERGENCY EXIT: All positions closed.")
            return True
        except Exception as e:
            logger.error(f"Panic Exit Error: {e}")
            return False
