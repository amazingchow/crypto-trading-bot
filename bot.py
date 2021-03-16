# -*- coding: utf-8 -*-
import coloredlogs, logging
logger = logging.getLogger(__name__)
coloredlogs.install(level="DEBUG", logger=logger, fmt="[%(asctime)s][%(levelname)s] %(message)s")
import datetime
import time
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from binance.client import Client
from binance.exceptions import BinanceAPIException

class BinanceTradeClient():
    '''
    币安自动交易机器人
    '''

    def __init__(self, ak: str, sk: str, proxies: dict):
        self.cli = Client(api_key=ak, api_secret=sk, requests_params={
                "proxies": proxies,
                "verify": False,
                "timeout": 10
            })
    
    def is_ready(self):
        ready = True
        try:
            self.cli.ping()
            ready = True
        except BinanceAPIException as e:
            logger.error("failed to setup the trade-bot, err: {}.".format(e))
            ready = False
        return ready

    def buy_market_ticker_price(self, sym: str, quantity: float):
        '''
        buy some quantities of a specific coin, like sym == PHABUSD
        '''
        try:
            order = self.cli.order_market_buy(symbol=sym, quoteOrderQty=quantity, recvWindow=200)
        except Exception as e:
            logger.error(e)
        finally:
            logger.info("buy {}".format(sym))


if __name__ == "__main__":
    import configparser
    cfg_parser = configparser.ConfigParser()
    cfg_parser.read("./config.ini")
    proxies = {
        "http": cfg_parser["DEFAULT"]["HttpProxy"],
        "https": cfg_parser["DEFAULT"]["HttpsProxy"]
    }

    bot = BinanceTradeClient(ak=cfg_parser["DEFAULT"]["APIKey"], sk=cfg_parser["DEFAULT"]["SecretKey"], proxies=proxies)

    # 2021年3月16号下午5点整, 切记: 一定一定要在4点59分以后运行
    target_time = datetime.datetime(2021, 3, 16, 17, 0).timestamp()
    current_time = time.time()
    while current_time < target_time:
        current_time = time.time()
        time.sleep(0.001)

    # 购入价值300 BUSD的BIFI, 尝试连续购买5次
    cnt = 0
    while cnt < 6:
        bot.buy_market_ticker_price("BIFIBUSD", 300)
        # 测试发现不用加延迟
        cnt += 1
    