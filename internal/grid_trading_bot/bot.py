# -*- coding: utf-8 -*-
import coloredlogs
import logging
_g_logger = logging.getLogger("BinanceGridTradingBot")
coloredlogs.install(level="DEBUG", logger=_g_logger, fmt="[%(asctime)s][%(levelname)s] %(message)s")

import os
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from binance.client import AsyncClient
from binance.streams import BinanceSocketManager
from typing import Dict
from typing import Optional


class BinanceGridTradingBotSetupException(Exception):
    pass


class BinanceGridTradingBot():
    '''
    币安网格交易机器人
    '''

    ak = None
    sk = None
    requests_params = None

    def __init__(self, use_proxy: Optional[bool] = False, use_testnet: Optional[bool] = False):
        self._use_testnet = use_testnet

        self.ak, self.sk = None, None
        if use_testnet:
            self.ak = os.getenv("BINANCE_TESTNET_API_KEY")
            self.sk = os.getenv("BINANCE_TESTNET_SECRET_KEY")
            if self.ak is None or self.sk is None:
                err_msg = "Please set env for BINANCE_TESTNET_API_KEY and BINANCE_TESTNET_SECRET_KEY."
                _g_logger.critical(err_msg)
                raise BinanceGridTradingBotSetupException(err_msg)
        else:
            self.ak = os.getenv("BINANCE_MAINNET_API_KEY")
            self.sk = os.getenv("BINANCE_MAINNET_SECRET_KEY")
            if self.ak is None or self.sk is None:
                err_msg = "Please set env for BINANCE_MAINNET_API_KEY and BINANCE_MAINNET_SECRET_KEY."
                _g_logger.critical(err_msg)
                raise BinanceGridTradingBotSetupException(err_msg)
        
        self.requests_params = {"timeout": 10}
        if use_proxy:
            http_proxy = os.getenv("HTTP_PROXY")
            https_proxy = os.getenv("HTTPS_PROXY")
            if http_proxy is None or https_proxy is None:
                err_msg = "Please set env for HTTP_PROXY and HTTPS_PROXY."
                _g_logger.critical(err_msg)
                raise BinanceGridTradingBotSetupException(err_msg)
            proxies = {
                "http": http_proxy,
                "https": https_proxy
            }
            self.requests_params[proxies] = proxies

    async def init(self) -> bool:
        api_aync_client = await AsyncClient.create(
            api_key=self.ak,
            api_secret=self.sk,
            requests_params=self.requests_params,
            testnet=self._use_testnet,
        )
        self._sock_mgr = BinanceSocketManager(client=api_aync_client)

    async def feed_kline(self, sym: Optional[str] = None, interval: Optional[str] = "1m"):
        sock_client = self._sock_mgr.kline_socket(symbol=sym, interval=interval)
        async with sock_client.connect() as sock:
            while 1:
                res = await sock.recv()
                _g_logger.debug("====================================================")
                _g_logger.debug(res)
                _g_logger.debug("====================================================")
