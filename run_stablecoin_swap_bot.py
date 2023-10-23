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
from internal.stablecoin_swap_bot import BinanceStablecoinSwapBot
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
        default="./etc/stablecoin_swap_bot.json",
        help="the bot config file",
    )
    subparsers = parser.add_subparsers(
        title="BINANCE_STABLECOIN_SWAP_BOT",
        dest="action",
        help="action to perform"
    )
    balances_parser = subparsers.add_parser(
        "balances",
        help="Show current balances.",
    )
    _ = balances_parser
    profit_parser = subparsers.add_parser(
        "profit",
        help="Show total profit.",
    )
    _ = profit_parser
    orderbook_parser = subparsers.add_parser(
        "orderbook",
        help="Get the Order Book for the BUSDUSDT market.",
    )
    _ = orderbook_parser
    orders_parser = subparsers.add_parser(
        "orders",
        help="Get recent n orders (include active, canceled, or filled) for BUSDUSDT.",
    )
    orders_parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="recent N BUSDUSDT swap orders",
    )
    swap_parser = subparsers.add_parser(
        "swap",
        help="Run USDT/BUSD swap for a long time.",
    )
    swap_parser.add_argument(
        "--when",
        type=int,
        help="the absolute unix timestamp when you want to start stablecoin-swap",
    )
    swap_parser.add_argument(
        "--elapse",
        type=int,
        help="the relative unix timestamp when you want to start stablecoin-swap",
    )
    check_order_parser = subparsers.add_parser(
        "check",
        help="Check an order's status.",
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
        "--order_id",
        type=str,
        help="the unique order id",
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

    bot = BinanceStablecoinSwapBot(use_proxy=False, use_testnet=True)
    _cleanup_coroutine = bot.close
    try:
        task = asyncio.ensure_future(bot.is_ready())
        ready = loop.run_until_complete(task)
        if ready:
            if action == "balances":
                task = asyncio.ensure_future(bot.show_balances())
                loop.run_until_complete(task)
            elif action == "profit":
                prepare_env(loop=loop)
                task = asyncio.ensure_future(bot.show_profit())
                loop.run_until_complete(task)
            elif action == "orderbook":
                task = asyncio.ensure_future(bot.orderbook_of_busd_usdt())
                loop.run_until_complete(task)
            elif action == "orders":
                task = asyncio.ensure_future(bot.show_recent_n_orders(n=args.limit))
                loop.run_until_complete(task)
            elif action == "swap":
                prepare_env(loop=loop)
                if args.when is not None and args.when > 0:
                    task = asyncio.ensure_future(bot.swap(when=args.when))
                    loop.run_until_complete(task)
                elif args.elapse is not None and args.elapse > 0:
                    task = asyncio.ensure_future(bot.swap(when=int(time.time()) + args.elapse))
                    loop.run_until_complete(task)
                else:
                    loguru_logger.error(f"Invalid action: {action}")
            elif action == "check":
                task = asyncio.ensure_future(bot.check_order(order_id=args.order_id))
                loop.run_until_complete(task)
            elif action == "cancel":
                task = asyncio.ensure_future(bot.cancel_order(order_id=args.order_id))
                loop.run_until_complete(task)
    except Exception:
        traceback.print_exc()
    finally:
        tasks = []
        if _cleanup_coroutine is not None:
            tasks.append(asyncio.ensure_future(_cleanup_coroutine()))
        if action == "profit" or action == "swap":
            clear_env()
        # NOTE: Wait 250 ms for the underlying connections to close.
        # https://docs.aiohttp.org/en/stable/client_advanced.html#Graceful_Shutdown
        loop.run_until_complete(asyncio.sleep(0.250))
        loop.close()
