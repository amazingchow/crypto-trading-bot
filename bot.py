# -*- coding: utf-8 -*-
import coloredlogs, logging
logger = logging.getLogger(__name__)
coloredlogs.install(level="DEBUG", logger=logger, fmt="[%(asctime)s][%(levelname)s] %(message)s")

from binance.client import Client


class BinanceTradeClient():
    '''
    币安自动交易机器人
    '''

    def __init__(self, ak, sk, proxies):
        self.cli = Client(api_key=ak, api_secret=sk, requests_params={"proxies": proxies})
    
    def is_ready(self):
        ready = True
        try:
            self.cli.ping()
            ready = True
        except BinanceRequestException as e:
            logger.error("failed to setup the trade-bot, err: {}.".format(e))
            ready = False
        return ready


if __name__ == "__main__":
    import configparser
    cfg_parser = configparser.ConfigParser()
    cfg_parser.read("./config.ini")
    proxies = {
        "http": cfg_parser["DEFAULT"]["HttpProxy"],
        "https": cfg_parser["DEFAULT"]["HttpsProxy"]
    }

    bot = BinanceTradeClient(ak=cfg_parser["DEFAULT"]["APIKey"], sk=cfg_parser["DEFAULT"]["SecretKey"], proxies=proxies)
    if not bot.is_ready():
        logger.critical("destroy the trade-bot!!!")
    else:
        logger.info("trade-bot has been ready now!!!")
