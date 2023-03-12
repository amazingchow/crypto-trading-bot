# -*- coding: utf-8 -*-
import coloredlogs
import logging
import os
import time
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from ..singleton import Singleton
from binance.client import Client
from binance.exceptions import BinanceAPIException
from binance.exceptions import BinanceRequestException
from pprint import pprint
from typing import Optional

_g_logger = logging.getLogger("BinanceStaggingBot")
coloredlogs.install(
    level="DEBUG",
    logger=_g_logger,
    fmt="[%(asctime)s][%(levelname)s][%(name)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class BinanceStaggingBot(metaclass=Singleton):
    '''
    币安打新机器人
    '''
    def __init__(self, use_proxy: Optional[bool] = False, use_testnet: Optional[bool] = False):
        self._is_inited = False

        ak, sk = None, None
        if use_testnet:
            ak = os.getenv("BINANCE_TESTNET_API_KEY")
            sk = os.getenv("BINANCE_TESTNET_SECRET_KEY")
            if ak is None or sk is None:
                _g_logger.critical("Please set env for BINANCE_TESTNET_API_KEY and BINANCE_TESTNET_SECRET_KEY.")
                return
        else:
            ak = os.getenv("BINANCE_MAINNET_API_KEY")
            sk = os.getenv("BINANCE_MAINNET_SECRET_KEY")
            if ak is None or sk is None:
                _g_logger.critical("Please set env for BINANCE_MAINNET_API_KEY and BINANCE_MAINNET_SECRET_KEY.")
                return
        
        requests_params = {"verify": False, "timeout": 10}
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
            requests_params[proxies] = proxies

        self._api_client = Client(
            api_key=ak,
            api_secret=sk,
            requests_params=requests_params,
            testnet=use_testnet,
        )
        self._is_inited = True
        self._is_ready = False
    
    def is_ready(self) -> bool:
        '''
        Test connectivity to the Rest API.
        '''
        ready = True
        try:
            self._api_client.ping()
        except BinanceRequestException as e:
            _g_logger.critical("BinanceStaggingBot is not ready, err:{}.".format(e))
            ready = False
        except BinanceAPIException as e:
            _g_logger.critical("BinanceStaggingBot is not ready, err:{}.".format(e))
            ready = False
        finally:
            self._is_ready = ready and self._is_inited
            if self._is_ready:
                _g_logger.info("BinanceStaggingBot is ready.")
            return self._is_ready

    def show_balances(self):
        '''
        Show current balances.
        '''
        account = None
        try:
            account = self._api_client.get_account(
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

    def show_recent_n_orders(self, sym: Optional[str] = None, limit: Optional[int] = None):
        '''
        Get recent n orders for a specific symbol.
        '''
        orders = None
        try:
            orders = self._api_client.get_all_orders(
                symbol=sym,
                limit=limit,
                recvWindow=2000,
            )
        except BinanceRequestException as e:
            _g_logger.error("Failed to get orders, err:{}.".format(e))
        except BinanceAPIException as e:
            _g_logger.error("Failed to get orders, err:{}.".format(e))
        finally:
            if orders is not None:
                _g_logger.debug("====================================================")
                pprint("Recent Orders:")
                for order in orders:
                    pprint(order, indent=4, depth=2)
                _g_logger.debug("====================================================")

    def trade(self, sym: Optional[str] = None, quantity: Optional[int] = None, new_arrival_time: Optional[int] = None, try_cnt: int = 5):
        '''
        Buy some quantities of a specific coin at particular time, like sym == PHABUSD
        '''
        now = time.time()
        while now < new_arrival_time:
            time.sleep(0.001)
            now = time.time()

        cnt = 0
        while cnt < try_cnt:
            try:
                self._api_client.order_market_buy(
                    symbol=sym,
                    quoteOrderQty=quantity,
                    recvWindow=2000,
                )
                break
                _g_logger.info("BinanceStaggingBot done")
            except Exception as e:
                time.sleep(0.01)
                cnt += 1
                _g_logger.error("BinanceStaggingBot failed, err:{}".format(e))
