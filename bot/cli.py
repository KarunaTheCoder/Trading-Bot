"""
Command-line interface for the trading bot.

Example usage:
    python main.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01
    python main.py --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.01 --price 60000
"""

import argparse
import os
import sys

from bot.client import BinanceFuturesTestnetClient, DEFAULT_BASE_URL
from bot.logging_config import setup_logging
from bot.orders import place_order


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        description="Place MARKET or LIMIT orders on Binance Futures Testnet (USDT-M).",
    )
    parser.add_argument("--symbol", required=True, help="Trading pair, e.g. BTCUSDT")
    parser.add_argument("--side", required=True, choices=["BUY", "SELL", "buy", "sell"],
                         help="Order side")
    parser.add_argument("--type", required=True, dest="order_type",
                         choices=["MARKET", "LIMIT", "market", "limit"],
                         help="Order type")
    parser.add_argument("--quantity", required=True, help="Order quantity")
    parser.add_argument("--price", required=False, default=None,
                         help="Order price (required for LIMIT orders)")
    parser.add_argument("--api-key", dest="api_key", default=os.environ.get("BINANCE_API_KEY"),
                         help="Binance Futures Testnet API key (or set BINANCE_API_KEY env var)")
    parser.add_argument("--api-secret", dest="api_secret",
                         default=os.environ.get("BINANCE_API_SECRET"),
                         help="Binance Futures Testnet API secret (or set BINANCE_API_SECRET env var)")
    parser.add_argument("--base-url", dest="base_url", default=DEFAULT_BASE_URL,
                         help=f"API base URL (default: {DEFAULT_BASE_URL})")
    parser.add_argument("--log-level", dest="log_level", default="INFO",
                         choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                         help="Console log verbosity (file log always captures DEBUG+)")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logger = setup_logging(args.log_level)

    if not args.api_key or not args.api_secret:
        logger.error(
            "Missing API credentials. Provide --api-key/--api-secret or set "
            "BINANCE_API_KEY / BINANCE_API_SECRET environment variables."
        )
        print("ERROR: Missing API credentials. See README.md for setup instructions.")
        return 1

    try:
        client = BinanceFuturesTestnetClient(
            api_key=args.api_key,
            api_secret=args.api_secret,
            base_url=args.base_url,
        )
    except ValueError as exc:
        logger.error("Failed to initialize client: %s", exc)
        print(f"ERROR: {exc}")
        return 1

    result = place_order(
        client,
        symbol=args.symbol,
        side=args.side,
        order_type=args.order_type,
        quantity=args.quantity,
        price=args.price,
    )

    print()
    print(result.summary())
    print()

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
