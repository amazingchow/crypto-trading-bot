# -*- coding: utf-8 -*-
import argparse
import asyncio
import coloredlogs
import logging
import sys

from internal.config import get_config
from internal.config import load_config_file
from internal.db import MongoClient
from internal.grid_trading_bot import BinanceGridTradingBot

main_logger = logging.getLogger("Main")
coloredlogs.install(
    level="DEBUG",
    logger=main_logger,
    fmt="[%(asctime)s][%(levelname)s][%(name)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--conf",
        type=str,
        default="./etc/grid_trading_bot.json",
        help="bot config file",
    )
    args = parser.parse_args()

    cfile = args.conf
    if len(cfile) == 0:
        main_logger.error("Please provide config file.")
        sys.exit(-1)
    else:
        load_config_file(cfile)
    conf = get_config()

    g_event_loop = asyncio.get_event_loop()

    bot = BinanceGridTradingBot(use_proxy=False, use_testnet=False)
    bot.lower_range_price = 19000
    bot.upper_range_price = 21000
    bot.grids = 2000
    bot.total_investment = 50000
    try:
        m_cli = MongoClient(
            client_conf=conf["mongodb"],
            io_loop=g_event_loop
        )
        coro = m_cli.is_connected()
        g_event_loop.run_until_complete(coro)
        coro = bot.setup(db=m_cli)
        g_event_loop.run_until_complete(coro)
    except Exception as e:
        main_logger.error(e)
        sys.exit(-1)

    try:
        task_1 = asyncio.ensure_future(bot.feed_klines("BTCUSDT", "1m"))
        task_2 = asyncio.ensure_future(bot.persist_klines("BTCUSDT", "1m"))
        tasks = [task_1, task_2]
        g_event_loop.run_until_complete(asyncio.gather(*tasks))
    except Exception as e:
        main_logger.error(e)
        sys.exit(-1)

    g_event_loop.close()
