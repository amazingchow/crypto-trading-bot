# -*- coding: utf-8 -*-
import asyncio

from internal.grid_trading_bot import BinanceGridTradingBot


if __name__ == "__main__":
    bot = BinanceGridTradingBot(use_proxy=False, use_testnet=False)
    loop = asyncio.get_event_loop()
    coro = bot.init()
    loop.run_until_complete(coro)
    coro = bot.feed_kline()
    loop.run_until_complete(coro)
    loop.close() 
