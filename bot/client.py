"""
Thin wrapper around the Binance Futures Testnet (USDT-M) REST API.

Implemented with plain `requests` calls (no python-binance dependency) so the
signing logic is fully visible and easy to audit. All requests, responses,
and errors are logged via the shared application logger.
"""

import hashlib
import hmac
import logging
import time
from urllib.parse import urlencode

import requests

logger = logging.getLogger("trading_bot.client")

DEFAULT_BASE_URL = "https://testnet.binancefuture.com"
ORDER_ENDPOINT = "/fapi/v1/order"
RECV_WINDOW = 5000


class APIError(Exception):
    """Raised when Binance returns a non-2xx / error-coded response."""

    def __init__(self, message, status_code=None, payload=None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class NetworkError(Exception):
    """Raised for connection/timeout problems talking to Binance."""


class BinanceFuturesTestnetClient:
    """Minimal client for placing orders on Binance Futures Testnet."""

    def __init__(self, api_key: str, api_secret: str, base_url: str = DEFAULT_BASE_URL,
                 timeout: int = 10):
        if not api_key or not api_secret:
            raise ValueError("API key and secret are required.")
        self.api_key = api_key
        self.api_secret = api_secret.encode("utf-8")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"X-MBX-APIKEY": self.api_key})

    # ---------- internal helpers ----------

    def _sign(self, params: dict) -> str:
        query_string = urlencode(params)
        signature = hmac.new(self.api_secret, query_string.encode("utf-8"), hashlib.sha256)
        return signature.hexdigest()

    def _signed_request(self, method: str, path: str, params: dict) -> dict:
        params = dict(params)
        params["timestamp"] = int(time.time() * 1000)
        params.setdefault("recvWindow", RECV_WINDOW)
        params["signature"] = self._sign(params)

        url = f"{self.base_url}{path}"
        safe_params = {k: v for k, v in params.items() if k != "signature"}
        logger.info("REQUEST %s %s params=%s", method, url, safe_params)

        try:
            response = self.session.request(method, url, params=params, timeout=self.timeout)
        except requests.exceptions.Timeout as exc:
            logger.error("Network timeout calling %s: %s", url, exc)
            raise NetworkError(f"Request to {url} timed out.") from exc
        except requests.exceptions.ConnectionError as exc:
            logger.error("Network connection error calling %s: %s", url, exc)
            raise NetworkError(f"Could not connect to {url}. Check your internet connection.") from exc
        except requests.exceptions.RequestException as exc:
            logger.error("Unexpected network error calling %s: %s", url, exc)
            raise NetworkError(f"Unexpected network error: {exc}") from exc

        logger.info("RESPONSE status=%s body=%s", response.status_code, response.text)

        try:
            data = response.json()
        except ValueError:
            data = {"raw": response.text}

        if not response.ok:
            error_msg = data.get("msg", "Unknown error") if isinstance(data, dict) else str(data)
            error_code = data.get("code") if isinstance(data, dict) else None
            logger.error(
                "API error status=%s code=%s msg=%s", response.status_code, error_code, error_msg
            )
            raise APIError(
                f"Binance API error ({response.status_code}): {error_msg}",
                status_code=response.status_code,
                payload=data,
            )

        return data

    # ---------- public API ----------

    def place_order(self, symbol: str, side: str, order_type: str, quantity: float,
                     price: float = None, time_in_force: str = "GTC") -> dict:
        """
        Place a MARKET or LIMIT order.

        Returns the parsed JSON response from Binance on success.
        Raises APIError or NetworkError on failure.
        """
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }

        if order_type == "LIMIT":
            params["price"] = price
            params["timeInForce"] = time_in_force

        return self._signed_request("POST", ORDER_ENDPOINT, params)

    def get_order(self, symbol: str, order_id: int) -> dict:
        """Fetch the current status of a previously placed order."""
        params = {"symbol": symbol, "orderId": order_id}
        return self._signed_request("GET", ORDER_ENDPOINT, params)
