# -*- coding: utf-8 -*-
import asyncio
import coloredlogs
import logging
import os
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from ..db.mongo import MongoClient
from ..singleton import Singleton
from binance.client import AsyncClient
from binance.streams import BinanceSocketManager
from typing import NoReturn
from typing import Optional

_g_logger = logging.getLogger("BinanceGridTradingBot")
coloredlogs.install(
    level="DEBUG",
    logger=_g_logger,
    fmt="[%(asctime)s][%(levelname)s][%(name)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class BinanceGridTradingBotSetupException(Exception):
    pass


class BinanceGridTradingBot(metaclass=Singleton):
    '''
    币安网格交易机器人
    '''

    def __init__(self, use_proxy: Optional[bool] = False, use_testnet: Optional[bool] = False):
        self._use_testnet = use_testnet

        self._ak, self._sk = None, None
        if use_testnet:
            self._ak = os.getenv("BINANCE_TESTNET_API_KEY")
            self._sk = os.getenv("BINANCE_TESTNET_SECRET_KEY")
            if self._ak is None or self._sk is None:
                err_msg = "Please set env for BINANCE_TESTNET_API_KEY and BINANCE_TESTNET_SECRET_KEY."
                _g_logger.critical(err_msg)
                raise BinanceGridTradingBotSetupException(err_msg)
        else:
            self._ak = os.getenv("BINANCE_MAINNET_API_KEY")
            self._sk = os.getenv("BINANCE_MAINNET_SECRET_KEY")
            if self._ak is None or self._sk is None:
                err_msg = "Please set env for BINANCE_MAINNET_API_KEY and BINANCE_MAINNET_SECRET_KEY."
                _g_logger.critical(err_msg)
                raise BinanceGridTradingBotSetupException(err_msg)
        
        self._requests_params = {"timeout": 10}
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
            self._requests_params[proxies] = proxies

    @property
    def lower_range_price(self):
        '''
        区间下限价格(USDT计价)
        '''
        return self._lower_range_price

    @lower_range_price.setter
    def lower_range_price(self, x: Optional[int] = None):
        self._lower_range_price = x

    @property
    def upper_range_price(self):
        '''
        区间上限价格(USDT计价)
        '''
        return self._upper_range_price

    @upper_range_price.setter
    def upper_range_price(self, x: Optional[int] = None):
        self._upper_range_price = x

    @property
    def grids(self):
        '''
        网格数量(50-5000)
        '''
        return self._grids

    @grids.setter
    def grids(self, x: Optional[int] = None):
        self._grids = x

    @property
    def total_investment(self):
        '''
        总投资额(USDT计价)
        '''
        return self._total_investment

    @total_investment.setter
    def total_investment(self, x: Optional[int] = None):
        self._total_investment = x

    async def setup(self, db: Optional[MongoClient] = None):
        try:
            api_aync_client = await AsyncClient.create(
                api_key=self._ak,
                api_secret=self._sk,
                requests_params=self._requests_params,
                testnet=self._use_testnet,
            )
        except asyncio.exceptions.TimeoutError:
            raise BinanceGridTradingBotSetupException("Please check your http(s) proxy.")
        self._sock_mgr = BinanceSocketManager(client=api_aync_client)
        self._store = db
        self._kline_q = asyncio.Queue()

    async def feed_klines(self, sym: Optional[str] = None, interval: Optional[str] = "1m") -> NoReturn:
        sock_client = self._sock_mgr.kline_socket(symbol=sym, interval=interval)
        await sock_client.connect()
        _g_logger.debug("Ready to receive k-lines<symbol:{}, interval:{}>...".format(sym, interval))
        while 1:
            res = await sock_client.recv()
            _g_logger.debug("Received one k-line<symbol:{}, interval:{}>.".format(sym, interval))
            _g_logger.debug("====================================================")
            _g_logger.debug(res)
            _g_logger.debug("====================================================")
            self._kline_q.put_nowait({"symbol": res["s"], "st_timestamp": res["k"]["t"], "ed_timestamp": res["k"]["T"], "kline": res["k"]})

    async def persist_klines(self, sym: Optional[str] = None, interval: Optional[str] = "1m") -> NoReturn:
        _g_logger.debug("Ready to persist k-lines<symbol:{}, interval:{}>...".format(sym, interval))
        while 1:
            kline = await self._kline_q.get()
            self._kline_q.task_done()
            _g_logger.debug("Prepare to persist one k-line<symbol:{}, interval:{}>.".format(sym, interval))
            await self._store.insert_kline(sym=sym, interval=interval, kline=kline)
