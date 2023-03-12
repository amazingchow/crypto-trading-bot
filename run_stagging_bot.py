# -*- coding: utf-8 -*-
import argparse
import coloredlogs
import logging
import sys
import time

from internal.config import get_config
from internal.config import load_config_file
from internal.stagging_bot import BinanceStaggingBot

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
        default="./etc/stagging_bot.json",
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

    bot = BinanceStaggingBot(use_proxy=False, use_testnet=True)
    if bot.is_ready():
        bot.show_balances()
        bot.trade(sym="BTCUSDT", quantity=100, new_arrival_time=int(time.time()) + 5)
        bot.show_recent_n_orders(sym="BTCUSDT", limit=1)
        bot.show_balances()
