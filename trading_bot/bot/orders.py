from typing import Dict, Any, Optional
from bot.client import BinanceFuturesClient
from bot.validators import InputValidator, ValidationError
from bot.logging_config import logger

class OrderManager:
    """
    Coordinates validation and placement of orders on Binance Futures Testnet.
    Provides clear feedback and logs API interactions.
    """
    def __init__(self, client: BinanceFuturesClient):
        self.client = client
        self.validator = InputValidator(client)

    def execute_order(self, symbol: str, side: str, order_type: str, quantity: float,
                      price: Optional[float] = None, stop_price: Optional[float] = None) -> Dict[str, Any]:
        """
        Validates parameters and places an order.
        
        :return: Dict containing execution details.
        :raises ValidationError: If parameters violate symbol limits or exchange rules.
        :raises BinanceAPIError: If the Binance exchange rejects the order.
        :raises BinanceNetworkError: If a connection error occurs.
        """
        logger.info(f"Initiating order request: {side} {quantity} {symbol} ({order_type})")

        # 1. Input and exchange rules validation
        validated = self.validator.validate_and_format(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price
        )

        # 2. Place the order via the client
        logger.debug(f"Parameters validated successfully. Submitting order: {validated}")
        
        response = self.client.place_order(
            symbol=validated["symbol"],
            side=validated["side"],
            order_type=validated["type"],
            quantity=validated["quantity"],
            price=validated.get("price"),
            stop_price=validated.get("stop_price")
        )

        logger.info(f"Order placed successfully! ID: {response.get('orderId')} | Status: {response.get('status')}")
        return response
