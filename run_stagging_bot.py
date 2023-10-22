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
import time
import traceback

from internal.db import init_instance as init_db_instance
from internal.db import instance as db_instance
from internal.stagging_bot import BinanceStaggingBot
from internal.utils.loguru_logger import init_global_logger
from internal.utils.global_vars import set_config, get_config
from loguru import logger as loguru_logger

# Coroutine to be invoked when the event loop is shutting down.
_cleanup_coroutine = None


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="output debug-level message"
    )
    parser.add_argument(
        "--conf",
        type=str,
        default="./etc/stagging_bot.json",
        help="the bot config file",
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
        default="BUY",
        choices=["BUY"],
        help="action to trade: BUY",
        required=True,
    )
    trade_parser.add_argument(
        "--quantity",
        type=int,
        help="the amount you wants to spend of the quote asset",
        required=True,
    )
    trade_parser.add_argument(
        "--when",
        type=int,
        help="the absolute unix timestamp when you want to trade",
    )
    trade_parser.add_argument(
        "--elapse",
        type=int,
        help="the relative unix timestamp when you want to trade",
    )

    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_args()
    if args.action not in ["balances", "orders", "trade"]:
        loguru_logger(f"Unknown action: {args.action}")
    action = args.action
    
    set_config(args.conf)
    conf = get_config()
    init_global_logger()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    bot = BinanceStaggingBot(use_proxy=False, use_testnet=True)
    _cleanup_coroutine = bot.close
    try:
        task = asyncio.ensure_future(bot.is_ready())
        ready = loop.run_until_complete(task)
        if ready:
            if action == "balances":
                task = asyncio.ensure_future(bot.show_balances())
                loop.run_until_complete(task)
            elif action == "orders":
                if len(args.symbol) > 0:
                    task = asyncio.ensure_future(bot.show_recent_n_orders(sym=args.symbol, n=args.limit))
                    loop.run_until_complete(task)
                else:
                    loguru_logger(f"Invalid action: {action}")
            elif action == "trade":
                # Setup mongodb connection (pool).
                try:
                    init_db_instance(
                        client_conf={
                            "endpoint": conf["mongodb"]["endpoint"],
                            "username": conf["mongodb"]["username"],
                            "password": conf["mongodb"]["password"],
                            "auth_mechanism": conf["mongodb"]["auth_mechanism"],
                            "database": conf["mongodb"]["database"],
                            "collection": conf["mongodb"]["collection"],
                        },
                        io_loop=loop,
                    )
                except Exception as e:
                    loguru_logger.error(f"Failed to setup mongodb connection (pool), err{e}.")
                    sys.exit(-1)
                task = asyncio.ensure_future(db_instance().is_connected())
                connected = loop.run_until_complete(task)
                if connected:
                    loguru_logger.info("Setup mongodb connection (pool).")
                else:
                    loguru_logger.error("Cannot setup mongodb connection (pool).")
                    sys.exit(-1)

                if len(args.symbol) > 0:
                    if args.when is not None and args.when > 0:
                        task = asyncio.ensure_future(bot.trade(sym=args.symbol, quantity=args.quantity, when=args.when, side=args.side))
                        loop.run_until_complete(task)
                    elif args.elapse is not None and args.elapse > 0:
                        task = asyncio.ensure_future(bot.trade(sym=args.symbol, quantity=args.quantity, when=int(time.time()) + args.elapse, side=args.side))
                        loop.run_until_complete(task)
                    else:
                        loguru_logger(f"Invalid action: {action}")
                else:
                    loguru_logger(f"Invalid action: {action}")
    except Exception:
        traceback.print_exc()
    finally:
        tasks = []
        if _cleanup_coroutine is not None:
            tasks.append(asyncio.ensure_future(_cleanup_coroutine()))
        if action == "trade":
            # Release mongodb connection (pool).
            db_instance().close()
        # NOTE: Wait 250 ms for the underlying connections to close.
        # https://docs.aiohttp.org/en/stable/client_advanced.html#Graceful_Shutdown
        loop.run_until_complete(asyncio.sleep(0.250))
        loop.close()
