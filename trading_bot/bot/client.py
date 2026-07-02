import time
import hmac
import hashlib
import requests
import urllib.parse
from typing import Dict, Any, Optional
from bot.logging_config import logger

class BinanceFuturesClient:
    """
    Binance Futures USDT-M Testnet API Client.
    Handles authentication, signature generation, time synchronization, and HTTP requests.
    """
    BASE_URL = "https://testnet.binancefuture.com"

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.time_offset_ms = 0
        
        # Mask credentials for logging safety
        masked_key = f"{api_key[:6]}...{api_key[-4:]}" if api_key else "None"
        logger.debug(f"Initializing BinanceFuturesClient with API Key: {masked_key}")

        # Synchronize clock with Binance server
        self.sync_time()

    def sync_time(self) -> None:
        """
        Synchronizes client system clock with Binance server clock to prevent
        'Timestamp for this request is outside of the recvWindow' errors.
        """
        logger.debug("Synchronizing clock with Binance Futures server...")
        try:
            url = f"{self.BASE_URL}/fapi/v1/time"
            start_time = time.time() * 1000
            response = requests.get(url, timeout=10)
            end_time = time.time() * 1000
            
            if response.status_code == 200:
                server_time = response.json().get("serverTime")
                # Estimate latency as half of the round trip time
                latency = (end_time - start_time) / 2
                # Calculate time offset: server_time - local_time
                local_time = end_time - latency
                self.time_offset_ms = int(server_time - local_time)
                logger.info(f"Clock synchronized. Offset: {self.time_offset_ms} ms (estimated latency: {latency:.2f} ms)")
            else:
                logger.warning(f"Could not synchronize time. Server responded with: {response.text}")
        except Exception as e:
            logger.error(f"Error synchronizing clock: {e}")
            logger.warning("Continuing with 0 time offset.")

    def get_timestamp(self) -> int:
        """Returns the synchronized current time in milliseconds."""
        return int(time.time() * 1000) + self.time_offset_ms

    def _sign(self, query_string: str) -> str:
        """Generates HMAC-SHA256 signature for signed endpoints."""
        if not self.api_secret:
            raise ValueError("API Secret is required to sign requests.")
        return hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def _request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None, signed: bool = False) -> Dict[str, Any]:
        """
        Base HTTP request wrapper. Handles header setup, signature generation, 
        and logging of requests/responses.
        """
        params = params or {}
        headers = {}

        # Add API key to headers for endpoints requiring it
        if signed or self.api_key:
            if not self.api_key:
                raise ValueError("API Key is required for this request.")
            headers["X-MBX-APIKEY"] = self.api_key

        # Prepare parameters and signature for signed endpoints
        if signed:
            params["timestamp"] = self.get_timestamp()
            # Set a standard recvWindow to handle latency
            if "recvWindow" not in params:
                params["recvWindow"] = 10000
            
            # Serialize params to a sorted query string for deterministic signing
            # Filter out None values
            filtered_params = {k: v for k, v in params.items() if v is not None}
            query_string = urllib.parse.urlencode(sorted(filtered_params.items()))
            signature = self._sign(query_string)
            query_string += f"&signature={signature}"
            
            # For GET/DELETE/POST, Binance accepts query parameters in the URL
            url = f"{self.BASE_URL}{endpoint}?{query_string}"
            req_params = {}
        else:
            url = f"{self.BASE_URL}{endpoint}"
            req_params = {k: v for k, v in params.items() if v is not None}

        # Mask API Key in headers for request logs
        logged_headers = headers.copy()
        if "X-MBX-APIKEY" in logged_headers:
            val = logged_headers["X-MBX-APIKEY"]
            logged_headers["X-MBX-APIKEY"] = f"{val[:6]}...{val[-4:]}" if len(val) > 10 else "***"

        logger.debug(f"HTTP Request: {method} {url} | Headers: {logged_headers} | Params: {req_params}")

        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=req_params, timeout=15)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, params=req_params, timeout=15)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers, params=req_params, timeout=15)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            # Log status and content summary (limit large JSON responses in logs)
            logger.debug(f"HTTP Response Status: {response.status_code}")
            
            # Try parsing JSON
            try:
                response_json = response.json()
            except ValueError:
                response_json = {"error": "Non-JSON response received", "raw_content": response.text}

            # If not a success status code, raise HTTPError
            if not (200 <= response.status_code < 300):
                error_msg = response_json.get("msg", response.text)
                code = response_json.get("code", "Unknown")
                logger.error(f"API Error Response: Code={code}, Msg={error_msg}")
                raise BinanceAPIError(f"Binance API Error {code}: {error_msg}", status_code=response.status_code, code=code)

            return response_json

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error occurred during API request: {e}")
            raise BinanceNetworkError(f"Connection to Binance failed: {e}")

    # Public Endpoints
    def ping(self) -> bool:
        """Pings the Binance server. Returns True if successful."""
        try:
            self._request("GET", "/fapi/v1/ping")
            return True
        except Exception:
            return False

    def get_exchange_info(self) -> Dict[str, Any]:
        """Fetches exchange rules and symbol specifications (precision, limits)."""
        return self._request("GET", "/fapi/v1/exchangeInfo")

    # Private / Signed Endpoints
    def get_account_balances(self) -> list:
        """Fetches account asset balances. Requires authentication."""
        # /fapi/v2/balance is the recommended endpoint for balances
        response = self._request("GET", "/fapi/v2/balance", signed=True)
        return response

    def get_open_orders(self, symbol: Optional[str] = None) -> list:
        """Fetches open orders. Optionally filtered by symbol. Requires authentication."""
        params = {"symbol": symbol} if symbol else {}
        return self._request("GET", "/fapi/v1/openOrders", params=params, signed=True)

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancels an active order. Requires authentication."""
        params = {"symbol": symbol, "orderId": order_id}
        return self._request("DELETE", "/fapi/v1/order", params=params, signed=True)

    def cancel_all_open_orders(self, symbol: str) -> Dict[str, Any]:
        """Cancels all open orders for a specific symbol. Requires authentication."""
        params = {"symbol": symbol}
        return self._request("DELETE", "/fapi/v1/allOpenOrders", params=params, signed=True)

    def place_order(self, symbol: str, side: str, order_type: str, quantity: float,
                    price: Optional[float] = None, stop_price: Optional[float] = None,
                    time_in_force: Optional[str] = None) -> Dict[str, Any]:
        """
        Places a new order. Requires authentication.
        
        :param symbol: e.g. 'BTCUSDT'
        :param side: 'BUY' or 'SELL'
        :param order_type: 'LIMIT', 'MARKET', 'STOP_MARKET', etc.
        :param quantity: Quantity of asset to trade.
        :param price: Price for LIMIT orders.
        :param stop_price: Trigger price for STOP_MARKET orders.
        :param time_in_force: Time in force for limit orders (e.g. 'GTC', 'IOC', 'FOK')
        """
        params = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": str(quantity)
        }

        if price is not None:
            params["price"] = str(price)

        if stop_price is not None:
            params["stopPrice"] = str(stop_price)

        if time_in_force:
            params["timeInForce"] = time_in_force
        elif order_type.upper() in ["LIMIT", "STOP"]:
            # Default to GTC (Good 'Til Canceled) for limit and stop limit orders
            params["timeInForce"] = "GTC"

        logger.info(f"Placing Order Request: {params['side']} {params['quantity']} {params['symbol']} Type={params['type']}")
        return self._request("POST", "/fapi/v1/order", params=params, signed=True)


class BinanceAPIError(Exception):
    """Exception raised for errors returned by the Binance API."""
    def __init__(self, message: str, status_code: int, code: Any):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class BinanceNetworkError(Exception):
    """Exception raised for network failure issues."""
    pass
