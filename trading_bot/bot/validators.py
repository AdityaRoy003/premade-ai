import math
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from typing import Dict, Any, Tuple, Optional
from bot.logging_config import logger
from bot.client import BinanceFuturesClient

class ValidationError(ValueError):
    """Exception raised for validation failures."""
    pass

class InputValidator:
    """
    Validates trading parameters against Binance Futures symbol specifications
    (LOT_SIZE, PRICE_FILTER, MIN_NOTIONAL) and account balance.
    """
    def __init__(self, client: BinanceFuturesClient):
        self.client = client
        self._exchange_info: Optional[Dict[str, Any]] = None

    def get_exchange_info(self) -> Dict[str, Any]:
        """Lazy load exchange info."""
        if self._exchange_info is None:
            logger.debug("Fetching exchange information for validation...")
            self._exchange_info = self.client.get_exchange_info()
        return self._exchange_info

    def get_symbol_rules(self, symbol: str) -> Dict[str, Any]:
        """Retrieves trading rules and filters for a specific symbol."""
        info = self.get_exchange_info()
        for sym_data in info.get("symbols", []):
            if sym_data["symbol"] == symbol.upper():
                return sym_data
        raise ValidationError(f"Symbol '{symbol}' not found on Binance Futures. Please use a valid symbol (e.g., BTCUSDT).")

    @staticmethod
    def parse_filters(symbol_rules: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Extracts LOT_SIZE, PRICE_FILTER, and MIN_NOTIONAL rules from symbol filters."""
        filters = {}
        for f in symbol_rules.get("filters", []):
            filter_type = f.get("filterType")
            filters[filter_type] = f
        return filters

    @staticmethod
    def format_decimal(value: Any, step: Any) -> Tuple[float, str]:
        """
        Formats a value (float/str) to align with a step size.
        Returns a tuple of (float_value, formatted_string_value).
        """
        try:
            d_val = Decimal(str(value))
            d_step = Decimal(str(step))
            
            # Find the precision (number of decimal places) from step size
            # e.g., 0.001 has 3 decimal places
            step_str = str(d_step).rstrip('0')
            if '.' in step_str:
                precision = len(step_str.split('.')[1])
            else:
                precision = 0

            # Quantize down to match the step size
            quantized = d_val.quantize(d_step, rounding=ROUND_DOWN)
            
            # Generate string representation with exact decimal places
            formatted_str = f"{quantized:.{precision}f}"
            return float(formatted_str), formatted_str
        except (InvalidOperation, ValueError, TypeError) as e:
            raise ValidationError(f"Failed to format decimal value '{value}' with step '{step}': {e}")

    def validate_and_format(self, symbol: str, side: str, order_type: str, 
                            quantity: Any, price: Optional[Any] = None, 
                            stop_price: Optional[Any] = None) -> Dict[str, Any]:
        """
        Validates all order input parameters.
        Returns a dictionary of normalized and correctly formatted parameter strings ready for the API.
        """
        # 1. Basic type validation
        side = side.upper()
        if side not in ["BUY", "SELL"]:
            raise ValidationError(f"Invalid side: '{side}'. Must be 'BUY' or 'SELL'.")

        order_type = order_type.upper()
        allowed_types = ["MARKET", "LIMIT", "STOP_MARKET"]
        if order_type not in allowed_types:
            raise ValidationError(f"Unsupported order type: '{order_type}'. Supported types: {', '.join(allowed_types)}")

        # 2. Get Exchange Info Rules for Symbol
        rules = self.get_symbol_rules(symbol)
        filters = self.parse_filters(rules)

        status = rules.get("status")
        if status != "TRADING":
            raise ValidationError(f"Symbol '{symbol}' is not currently tradable (Status: {status}).")

        parsed_params = {
            "symbol": rules["symbol"],
            "side": side,
            "type": order_type,
        }

        # 3. Validate Quantity against LOT_SIZE filter
        lot_size = filters.get("LOT_SIZE")
        if not lot_size:
            raise ValidationError(f"LOT_SIZE filter rules not found for symbol {symbol}.")

        min_qty = float(lot_size["minQty"])
        max_qty = float(lot_size["maxQty"])
        step_size = float(lot_size["stepSize"])

        try:
            qty_val = float(quantity)
        except (ValueError, TypeError):
            raise ValidationError(f"Quantity must be a number, got '{quantity}'.")

        if qty_val < min_qty:
            raise ValidationError(f"Quantity {qty_val} is less than minimum quantity allowed ({min_qty}).")
        if qty_val > max_qty:
            raise ValidationError(f"Quantity {qty_val} is greater than maximum quantity allowed ({max_qty}).")

        # Align quantity to step size
        qty_aligned, qty_str = self.format_decimal(qty_val, step_size)
        parsed_params["quantity"] = qty_aligned
        logger.debug(f"Quantity aligned from {qty_val} to {qty_aligned} (step size: {step_size})")

        # 4. Price validations (Only for LIMIT orders)
        price_filter = filters.get("PRICE_FILTER")
        if order_type == "LIMIT":
            if price is None:
                raise ValidationError("Price is required for LIMIT orders.")
            
            if not price_filter:
                raise ValidationError(f"PRICE_FILTER rules not found for symbol {symbol}.")

            min_price = float(price_filter["minPrice"])
            max_price = float(price_filter["maxPrice"])
            tick_size = float(price_filter["tickSize"])

            try:
                price_val = float(price)
            except (ValueError, TypeError):
                raise ValidationError(f"Price must be a number, got '{price}'.")

            if price_val < min_price:
                raise ValidationError(f"Price {price_val} is less than minimum price allowed ({min_price}).")
            if price_val > max_price:
                raise ValidationError(f"Price {price_val} is greater than maximum price allowed ({max_price}).")

            price_aligned, price_str = self.format_decimal(price_val, tick_size)
            parsed_params["price"] = price_aligned
            logger.debug(f"Price aligned from {price_val} to {price_aligned} (tick size: {tick_size})")
        else:
            if price is not None:
                logger.warning(f"Price was provided for {order_type} order, but it will be ignored.")

        # 5. Stop Price validations (Only for STOP_MARKET orders)
        if order_type == "STOP_MARKET":
            if stop_price is None:
                raise ValidationError("Stop price is required for STOP_MARKET orders.")
            
            if not price_filter:
                raise ValidationError(f"PRICE_FILTER rules not found for symbol {symbol}.")

            min_price = float(price_filter["minPrice"])
            max_price = float(price_filter["maxPrice"])
            tick_size = float(price_filter["tickSize"])

            try:
                stop_val = float(stop_price)
            except (ValueError, TypeError):
                raise ValidationError(f"Stop price must be a number, got '{stop_price}'.")

            if stop_val < min_price:
                raise ValidationError(f"Stop price {stop_val} is less than minimum price allowed ({min_price}).")
            if stop_val > max_price:
                raise ValidationError(f"Stop price {stop_val} is greater than maximum price allowed ({max_price}).")

            stop_aligned, stop_str = self.format_decimal(stop_val, tick_size)
            parsed_params["stop_price"] = stop_aligned
            logger.debug(f"Stop Price aligned from {stop_val} to {stop_aligned} (tick size: {tick_size})")
        else:
            if stop_price is not None:
                logger.warning(f"Stop price was provided for {order_type} order, but it will be ignored.")

        # 6. Validate MIN_NOTIONAL filter
        # Notional value is quantity * price (or last price/mark price for market orders)
        min_notional_filter = filters.get("MIN_NOTIONAL")
        if min_notional_filter:
            min_notional = float(min_notional_filter["notional"])
            
            # For LIMIT, we use the specified price.
            # For MARKET/STOP_MARKET, we don't have a price immediately, but we can estimate
            # by fetching symbol order book or ticker price. Let's do ticker price if available.
            check_price = 0.0
            if order_type == "LIMIT":
                check_price = float(parsed_params["price"])
            elif order_type == "STOP_MARKET":
                check_price = float(parsed_params["stop_price"])
            else:
                # Estimate using ticker price (fall back to 1.0 to avoid crash if info fails)
                try:
                    logger.debug(f"Fetching recent price for {symbol} to check MIN_NOTIONAL...")
                    ticker_url = f"{self.client.BASE_URL}/fapi/v1/ticker/price?symbol={rules['symbol']}"
                    res = self.client._request("GET", f"/fapi/v1/ticker/price?symbol={rules['symbol']}")
                    check_price = float(res.get("price", 0.0))
                except Exception as e:
                    logger.warning(f"Could not check MIN_NOTIONAL accurately: ticker price fetch failed ({e}).")
                    check_price = 0.0

            if check_price > 0:
                est_notional = qty_aligned * check_price
                if est_notional < min_notional:
                    raise ValidationError(
                        f"Estimated order notional value ({est_notional:.2f} USDT) is below the minimum required "
                        f"({min_notional:.2f} USDT) for {symbol}. Try increasing the quantity."
                    )

        # 7. Balance check verification (Warn only, since users might use leverage)
        if self.client.api_key and self.client.api_secret:
            try:
                balances = self.client.get_account_balances()
                usdt_bal = next((b for b in balances if b["asset"] == "USDT"), None)
                if usdt_bal:
                    available = float(usdt_bal["availableBalance"])
                    
                    # Estimate total order cost
                    cost_price = parsed_params.get("price", parsed_params.get("stop_price", 0.0))
                    if cost_price == 0.0:
                        # Fallback for market orders if we didn't fetch check_price yet
                        if 'check_price' in locals() and check_price > 0:
                            cost_price = check_price
                        else:
                            res = self.client._request("GET", f"/fapi/v1/ticker/price?symbol={rules['symbol']}")
                            cost_price = float(res.get("price", 0.0))
                            
                    est_cost = qty_aligned * cost_price
                    if est_cost > available:
                        logger.warning(
                            f"Account Warning: Estimated order cost is {est_cost:.2f} USDT, but "
                            f"available USDT balance is {available:.2f} USDT. (Position may fail or require leverage)"
                        )
            except Exception as e:
                logger.debug(f"Could not perform pre-order balance check: {e}")

        return parsed_params
