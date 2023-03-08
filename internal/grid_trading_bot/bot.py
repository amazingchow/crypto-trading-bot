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


class BinanceGridTradingBot():
    '''
    币安网格交易机器人
    '''
    def __init__(self, use_proxy: Optional[bool] = False, use_testnet: Optional[bool] = False):
        self._is_inited = False
        self._use_testnet = use_testnet

        self._ak, self._sk = None, None
        if use_testnet:
            self._ak = os.getenv("BINANCE_TESTNET_API_KEY")
            self._sk = os.getenv("BINANCE_TESTNET_SECRET_KEY")
            if self._ak is None or self._sk is None:
                _g_logger.critical("Please set env for BINANCE_TESTNET_API_KEY and BINANCE_TESTNET_SECRET_KEY.")
                return
        else:
            self._ak = os.getenv("BINANCE_MAINNET_API_KEY")
            self._sk = os.getenv("BINANCE_MAINNET_SECRET_KEY")
            if self._ak is None or self._sk is None:
                _g_logger.critical("Please set env for BINANCE_MAINNET_API_KEY and BINANCE_MAINNET_SECRET_KEY.")
                return
        
        self._requests_params: Dict[str, str] = {"verify": False, "timeout": 10}
        if use_proxy:
            http_proxy = os.getenv("HTTP_PROXY")
            https_proxy = os.getenv("HTTPS_PROXY")
            if http_proxy is None or https_proxy is None:
                _g_logger.critical("Please set env for HTTP_PROXY and HTTPS_PROXY.")
                return
            proxies = {
                "http": http_proxy,
                "https": https_proxy
            }
            self._requests_params[proxies] = proxies

    async def init(self) -> bool:
        api_aync_client = await AsyncClient.create(
            api_key=self._ak,
            api_secret=self._sk,
            requests_params=self._requests_params,
            testnet=self._use_testnet,
        )
        self._sock_mgr = BinanceSocketManager(client=api_aync_client)
        self._is_inited = True

    async def feed_kline(self, sym: Optional[str] = None, interval: Optional[str] = "1m"):
        sock_client = self._sock_mgr.kline_socket(symbol=sym, interval=interval)
        async with sock_client.connect() as sock:
            while 1:
                res = await sock.recv()
                _g_logger.debug("====================================================")
                _g_logger.debug(res)
                _g_logger.debug("====================================================")
