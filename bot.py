# -*- coding: utf-8 -*-
import time

from internal.stagging_bot import BinanceStaggingBot


if __name__ == "__main__":
    bot = BinanceStaggingBot(use_proxy=False, use_testnet=True)
    while not bot.is_ready():
        time.sleep(3)
    bot.run("BIFIBUSD", 300, 1678270556, 5)
