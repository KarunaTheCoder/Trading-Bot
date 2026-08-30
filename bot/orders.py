"""
Order placement logic: ties together validation, the API client, and
presentation of results. Kept separate from the CLI so it can be reused
(e.g. imported by a script, notebook, or future GUI).
"""

import logging

from bot.client import APIError, NetworkError
from bot.validators import ValidationError, validate_order_input

logger = logging.getLogger("trading_bot.orders")


class OrderResult:
    """Simple container describing the outcome of an order attempt."""

    def __init__(self, success: bool, request: dict, response: dict = None, error: str = None):
        self.success = success
        self.request = request
        self.response = response or {}
        self.error = error

    def summary(self) -> str:
        lines = ["--- Order Request ---"]
        for key, value in self.request.items():
            lines.append(f"  {key}: {value}")

        if self.success:
            lines.append("--- Order Response ---")
            lines.append(f"  orderId:      {self.response.get('orderId')}")
            lines.append(f"  status:       {self.response.get('status')}")
            lines.append(f"  executedQty:  {self.response.get('executedQty')}")
            avg_price = self.response.get("avgPrice")
            if avg_price is not None:
                lines.append(f"  avgPrice:     {avg_price}")
            lines.append("RESULT: SUCCESS")
        else:
            lines.append(f"RESULT: FAILED - {self.error}")

        return "\n".join(lines)


def place_order(client, symbol, side, order_type, quantity, price=None) -> OrderResult:
    """
    Validate input, place the order via the given client, and return an
    OrderResult describing what happened. Never raises: all expected error
    types are caught and converted into a failed OrderResult so the CLI
    layer can present a clean message.
    """
    try:
        clean = validate_order_input(symbol, side, order_type, quantity, price)
    except ValidationError as exc:
        logger.warning("Validation failed: %s", exc)
        request_echo = {
            "symbol": symbol, "side": side, "type": order_type,
            "quantity": quantity, "price": price,
        }
        return OrderResult(success=False, request=request_echo, error=str(exc))

    logger.info(
        "Placing %s %s order: symbol=%s qty=%s price=%s",
        clean["type"], clean["side"], clean["symbol"], clean["quantity"], clean["price"],
    )

    try:
        response = client.place_order(
            symbol=clean["symbol"],
            side=clean["side"],
            order_type=clean["type"],
            quantity=clean["quantity"],
            price=clean["price"],
        )
        logger.info("Order placed successfully: orderId=%s", response.get("orderId"))
        return OrderResult(success=True, request=clean, response=response)

    except APIError as exc:
        logger.error("Order failed (API error): %s", exc)
        return OrderResult(success=False, request=clean, error=str(exc))

    except NetworkError as exc:
        logger.error("Order failed (network error): %s", exc)
        return OrderResult(success=False, request=clean, error=str(exc))

    except Exception as exc:  # safety net for anything unforeseen
        logger.exception("Unexpected error while placing order")
        return OrderResult(success=False, request=clean, error=f"Unexpected error: {exc}")
