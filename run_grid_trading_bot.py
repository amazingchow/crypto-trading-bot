# -*- coding: utf-8 -*-
import os
import sys

curdir = os.path.abspath(os.curdir)
sys.path.append(os.path.join(curdir, "internal"))

import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import argparse
import asyncio
import shelve
import sys
import time
import traceback

from loguru import logger as loguru_logger

from internal.bot.grid_trading_bot import BinanceGridTradingBot
from internal.db import init_instance as init_db_instance
from internal.db import instance as db_instance
from internal.utils.global_vars import get_config, set_config
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
    parser.add_argument(
        "--conf",
        type=str,
        default="./etc/grid_trading_bot.json",
        help="the bot config file",
    )
    subparsers = parser.add_subparsers(
        title="BINANCE_GRID_TRADING_BOT",
        dest="action",
        help="action to perform"
    )
    balances_parser = subparsers.add_parser(
        "balances",
        help="Show current balances.",
    )
    balances_parser.add_argument(
        "--symbol",
        type=str,
        help="coin symbol, like BTCUSDT",
        required=True,
    )
    profit_parser = subparsers.add_parser(
        "profit",
        help="Show total profit.",
    )
    profit_parser.add_argument(
        "--symbol",
        type=str,
        help="coin symbol, like BTCUSDT",
        required=True,
    )
    symbol_info_parser = subparsers.add_parser(
        "info",
        help="Show information of coin symbol, like BTCUSDT.",
    )
    symbol_info_parser.add_argument(
        "--symbol",
        type=str,
        help="coin symbol, like BTCUSDT",
        required=True,
    )
    orderbook_parser = subparsers.add_parser(
        "orderbook",
        help="Get the Order Book for the BTCUSDT market.",
    )
    orderbook_parser.add_argument(
        "--symbol",
        type=str,
        help="coin symbol, like BTCUSDT",
        required=True,
    )
    orders_parser = subparsers.add_parser(
        "orders",
        help="Get recent n orders (include active, canceled, or filled) for BTCUSDT.",
    )
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
        help="recent n BTCUSDT orders",
    )
    trade_parser = subparsers.add_parser(
        "trade",
        help="Run grid-trading for a long time.",
    )
    trade_parser.add_argument(
        "--symbol",
        type=str,
        help="coin symbol, like BTCUSDT",
        required=True,
    )
    trade_parser.add_argument(
        "--lower_range_price",
        type=int,
        help="the lower range price in USDT curreny",
        required=True,
    )
    trade_parser.add_argument(
        "--upper_range_price",
        type=int,
        help="the upper range price in USDT curreny",
        required=True,
    )
    trade_parser.add_argument(
        "--grids",
        type=int,
        help="total grid quantity",
        required=True,
    )
    trade_parser.add_argument(
        "--total_investment",
        type=int,
        help="total investment in USDT curreny",
        required=True,
    )
    trade_parser.add_argument(
        "--when",
        type=int,
        help="the absolute unix timestamp when you want to start grid-trading",
    )
    trade_parser.add_argument(
        "--elapse",
        type=int,
        help="the relative unix timestamp when you want to start grid-trading",
    )
    check_order_parser = subparsers.add_parser(
        "check",
        help="Check an order's status.",
    )
    check_order_parser.add_argument(
        "--symbol",
        type=str,
        help="coin symbol, like BTCUSDT",
        required=True,
    )
    check_order_parser.add_argument(
        "--order_id",
        type=str,
        help="the unique order id",
        required=True,
    )
    cancel_order_parser = subparsers.add_parser(
        "cancel",
        help="Cancel an active order.",
    )
    cancel_order_parser.add_argument(
        "--symbol",
        type=str,
        help="coin symbol, like BTCUSDT",
        required=True,
    )
    cancel_order_parser.add_argument(
        "--order_id",
        type=str,
        help="the unique order id",
        required=True,
    )
    cancel_all_orders_parser = subparsers.add_parser(
        "cancelall",
        help="Cancel all active orders.",
    )
    cancel_all_orders_parser.add_argument(
        "--symbol",
        type=str,
        help="coin symbol, like BTCUSDT",
        required=True,
    )

    args = parser.parse_args()
    return args


def prepare_env(loop):
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


def clear_env():
    # Release mongodb connection (pool).
    db_instance().close()


if __name__ == "__main__":
    args = parse_args()
    action = args.action

    set_config(args.conf)
    conf = get_config()
    init_global_logger()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    bot = BinanceGridTradingBot(use_proxy=False, use_testnet=True)
    _cleanup_coroutine = bot.close
    try:
        task = asyncio.ensure_future(bot.is_ready())
        ready = loop.run_until_complete(task)
        if ready:
            bot.base_asset = args.symbol[:-4]
            bot.quote_asset = "USDT"
            if action == "balances":
                task = asyncio.ensure_future(bot.show_balances())
                loop.run_until_complete(task)
            elif action == "profit":
                prepare_env(loop=loop)
                task = asyncio.ensure_future(bot.show_profit(sym=args.symbol))
                loop.run_until_complete(task)
            elif action == "info":
                task = asyncio.ensure_future(bot.show_symbol_information(sym=args.symbol))
                loop.run_until_complete(task)
            elif action == "orderbook":
                task = asyncio.ensure_future(bot.latest_orderbook(sym=args.symbol))
                loop.run_until_complete(task)
            elif action == "orders":
                task = asyncio.ensure_future(bot.show_recent_n_orders(sym=args.symbol, n=args.limit))
                loop.run_until_complete(task)
            elif action == "trade":
                prepare_env(loop=loop)
                if args.when is not None and args.when > 0:
                    task = asyncio.ensure_future(bot.trade(sym=args.symbol, when=args.when))
                    loop.run_until_complete(task)
                elif args.elapse is not None and args.elapse > 0:
                    bot.lower_range_price = args.lower_range_price
                    bot.upper_range_price = args.upper_range_price
                    bot.grids = args.grids
                    bot.total_investment = args.total_investment
                    task = asyncio.ensure_future(bot.trade(sym=args.symbol, when=int(time.time()) + args.elapse))
                    loop.run_until_complete(task)
                else:
                    loguru_logger.error(f"Invalid action: {action}")
            elif action == "check":
                task = asyncio.ensure_future(bot.check_order(sym=args.symbol, order_id=args.order_id))
                loop.run_until_complete(task)
            elif action == "cancel":
                task = asyncio.ensure_future(bot.cancel_order(sym=args.symbol, order_id=args.order_id))
                loop.run_until_complete(task)
            elif action == "cancelall":
                with shelve.open("grid_trading_orders.db", flag="r") as db:
                    if "active_sell" in db.keys():
                        for order_id in db["active_sell"]:
                            task = asyncio.ensure_future(bot.cancel_order(sym=args.symbol, order_id=order_id))
                            loop.run_until_complete(task)
                    if "active_buy" in db.keys():
                        for order_id in db["active_buy"]:
                            task = asyncio.ensure_future(bot.cancel_order(sym=args.symbol, order_id=order_id))
                            loop.run_until_complete(task)
    except Exception:
        traceback.print_exc()
    finally:
        tasks = []
        if _cleanup_coroutine is not None:
            tasks.append(asyncio.ensure_future(_cleanup_coroutine()))
        if action == "profit" or action == "trade":
            clear_env()
        # NOTE: Wait 250 ms for the underlying connections to close.
        # https://docs.aiohttp.org/en/stable/client_advanced.html#Graceful_Shutdown
        loop.run_until_complete(asyncio.sleep(0.250))
        loop.close()
