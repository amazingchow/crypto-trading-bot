# -*- coding: utf-8 -*-
import os
import sys
curdir = os.path.abspath(os.curdir)
sys.path.append(os.path.join(curdir, "internal"))

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import argparse
import asyncio
import sys
import traceback

from internal.bot.simple_trading_bot import BinanceSimpleTradingBot
from internal.utils.loguru_logger import init_global_logger

# Coroutine to be invoked when the event loop is shutting down.
_cleanup_coroutine = None


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="output debug-level message"
    )
    subparsers = parser.add_subparsers(
        title="BINANCE_STAGGING_BOT",
        dest="action",
        help="action to perform"
    )
    balances_parser = subparsers.add_parser("balances")
    _ = balances_parser
    orders_parser = subparsers.add_parser("orders")
    orders_parser.add_argument(
        "--symbol",
        type=str,
        help="coin symbol, like BTCUSDT",
        required=True,
    )
    orders_parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="recent N orders",
    )
    trade_parser = subparsers.add_parser("trade")
    trade_parser.add_argument(
        "--symbol",
        type=str,
        help="coin symbol, like BTCUSDT",
        required=True,
    )
    trade_parser.add_argument(
        "--side",
        type=str,
        choices=["BUY", "SELL"],
        help="action to trade: BUY | SELL",
        required=True,
    )
    trade_parser.add_argument(
        "--base_qty",
        type=float,
        help="the amount you wants to spend of the base asset",
    )
    trade_parser.add_argument(
        "--quote_qty",
        type=float,
        help="the amount you wants to spend of the quote asset",
    )

    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_args()
    action = args.action
    
    init_global_logger()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    bot = BinanceSimpleTradingBot(use_proxy=False, use_testnet=True)
    _cleanup_coroutine = bot.close
    try:
        task = asyncio.ensure_future(bot.is_ready())
        ready = loop.run_until_complete(task)
        if ready:
            if action == "balances":
                task = asyncio.ensure_future(bot.show_balances())
                loop.run_until_complete(task)
            elif action == "orders":
                task = asyncio.ensure_future(bot.show_recent_n_orders(sym=args.symbol, n=args.limit))
                loop.run_until_complete(task)
            elif action == "trade":
                if args.side == "BUY":
                    task = asyncio.ensure_future(bot.trade(sym=args.symbol, quote_qty=args.quote_qty, side=args.side))
                    loop.run_until_complete(task)
                elif args.side == "SELL":
                    task = asyncio.ensure_future(bot.trade(sym=args.symbol, base_qty=args.base_qty, side=args.side))
                    loop.run_until_complete(task)
    except Exception:
        traceback.print_exc()
    finally:
        tasks = []
        if _cleanup_coroutine is not None:
            tasks.append(asyncio.ensure_future(_cleanup_coroutine()))
        # NOTE: Wait 250 ms for the underlying connections to close.
        # https://docs.aiohttp.org/en/stable/client_advanced.html#Graceful_Shutdown
        loop.run_until_complete(asyncio.sleep(0.250))
        loop.close()
