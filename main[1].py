"""Entry point: `python main.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01`"""

import sys

from bot.cli import main

if __name__ == "__main__":
    sys.exit(main())
