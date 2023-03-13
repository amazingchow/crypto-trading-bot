# -*- coding: utf-8 -*-
import asyncio
import coloredlogs
import decimal
import logging
import os
import random
import string
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from ..db.mongo import MongoClient
from ..singleton import Singleton
from binance.client import AsyncClient
from binance.exceptions import BinanceAPIException
from binance.exceptions import BinanceRequestException
from binance.streams import BinanceSocketManager
from pprint import pprint
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

    def _new_client_order_id(self, size=22, chars=string.ascii_letters + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

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
        self._api_aync_client = api_aync_client
        self._sock_mgr = BinanceSocketManager(client=api_aync_client)
        self._store = db
        self._kline_q = asyncio.Queue()

    async def show_balances(self):
        '''
        Show current balances.
        '''
        account = None
        try:
            account = await self._api_aync_client.get_account(
                recvWindow=2000,
            )
        except BinanceRequestException as e:
            _g_logger.error("Failed to get balances, err:{}.".format(e))
        except BinanceAPIException as e:
            _g_logger.error("Failed to get balances, err:{}.".format(e))
        finally:
            if account is not None:
                _g_logger.debug("====================================================")
                pprint("Balances:")
                for balance in account["balances"]:
                    pprint(balance, indent=4, depth=2)
                _g_logger.debug("====================================================")

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

    async def swap_2_usdt(self, sym: Optional[str] = None, qty: Optional[int] = None):
        done = False
        try:
            res = await self._api_aync_client.create_order(
                symbol=sym,
                side="SELL",
                type="MARKET",
                quantity=decimal.Decimal("{:3f}".format(qty)),
                newOrderRespType="RESULT",
                recvWindow=2000,
            )
            if res["status"] == "FILLED":
                done = True
        except BinanceRequestException as e:
            _g_logger.error("Failed to create order for symbol:{}, err:{}.".format(sym, e))
        except BinanceAPIException as e:
            _g_logger.error("Failed to create order for symbol:{}, err:{}.".format(sym, e))
        finally:
            return done

    async def trade(self, sym: Optional[str] = None):
        _g_logger.debug("Ready to run grid trading for symbol:{}...".format(sym))

        spread = (self._upper_range_price - self._lower_range_price) // self._grids
        trading_capacity = self._total_investment // self._grids
        trading_price_list = [self._lower_range_price + i * spread for i in range(self._grids)]

        latest_price = None
        try:
            res = await self._api_aync_client.get_symbol_ticker(
                symbol=sym,
            )
            latest_price = float(res["price"])
        except BinanceRequestException as e:
            _g_logger.error("Failed to get latest price for symbol:{}, err:{}.".format(sym, e))
        except BinanceAPIException as e:
            _g_logger.error("Failed to get latest price for symbol:{}, err:{}.".format(sym, e))
        finally:
            if latest_price is None:
                _g_logger.error("Failed to get latest price for symbol:{}.".format(sym))
                return
        _g_logger.debug("Latest price for symbol:{} is {}".format(sym, latest_price))

        initial_tokens_spent = (self._upper_range_price - latest_price) / (self._upper_range_price - self._lower_range_price) * self._total_investment
        done = False
        try:
            res = await self._api_aync_client.create_order(
                symbol=sym,
                side="BUY",
                type="MARKET",
                quoteOrderQty=decimal.Decimal("{:3f}".format(initial_tokens_spent)),
                newOrderRespType="RESULT",
                recvWindow=2000,
            )
            _g_logger.debug("Created order for initial tokens, res:{}", res)
            if res["status"] == "FILLED":
                done = True
        except BinanceRequestException as e:
            _g_logger.error("Failed to create order for symbol:{}, err:{}.".format(sym, e))
        except BinanceAPIException as e:
            _g_logger.error("Failed to create order for symbol:{}, err:{}.".format(sym, e))
        finally:
            if not done:
                return

        _latest_price = None
        try:
            res = await self._api_aync_client.get_symbol_ticker(
                symbol=sym,
            )
            _latest_price = float(res["price"])
        except BinanceRequestException as e:
            _g_logger.error("Failed to get latest price for symbol:{}, err:{}.".format(sym, e))
        except BinanceAPIException as e:
            _g_logger.error("Failed to get latest price for symbol:{}, err:{}.".format(sym, e))
        finally:
            if _latest_price is not None:
                latest_price = _latest_price
        _g_logger.debug("Latest price for symbol:{} is {}".format(sym, latest_price))

        for trading_price in trading_price_list:
            side = "BUY"
            if trading_price < latest_price:
                side = "BUY"
            elif trading_price > latest_price:
                side = "SELL"
            try:
                res = await self._api_aync_client.create_order(
                    symbol=sym,
                    side=side,
                    type="LIMIT",
                    quoteOrderQty=decimal.Decimal("{:3f}".format(trading_capacity)),
                    price=decimal.Decimal("{:3f}".format(trading_price)),
                    newOrderRespType="RESULT",
                    newClientOrderId=self._new_client_order_id(),
                    recvWindow=2000,
                )
                _g_logger.debug("Created order, res:{}", res)
            except BinanceRequestException as e:
                _g_logger.error("Failed to create order for symbol:{}, err:{}.".format(sym, e))
            except BinanceAPIException as e:
                _g_logger.error("Failed to create order for symbol:{}, err:{}.".format(sym, e))
