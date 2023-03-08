# -*- coding: utf-8 -*-
import asyncio
import time

from internal.grid_trading_bot import BinanceGridTradingBot


if __name__ == "__main__":
    bot = BinanceGridTradingBot(use_proxy=False, use_testnet=False)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(bot.init())
    loop.run_until_complete(bot.feed_kline())
    loop.close() 
