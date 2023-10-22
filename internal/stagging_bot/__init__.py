# -*- coding: utf-8 -*-
import asyncio
import os
import pprint
import time

from binance.client import AsyncClient as AsyncBinanceRestAPIClient
from binance.client import Client as BinanceRestAPIClient
from binance.exceptions import BinanceAPIException, BinanceRequestException, BinanceOrderException
from colorama import Fore, Style
from internal.db import instance as db_instance
from internal.singleton import Singleton
from internal.utils.helper import timeit, gen_n_digit_nums_and_letters
from loguru import logger as loguru_logger


class BinanceStaggingBot(metaclass=Singleton):
    """
    币安打新机器人
    """
    
    def __init__(self, use_proxy: bool = False, use_testnet: bool = False):
        self._inited = False
        self._is_ready = False
        self._aclient = None
        self._client = None

        ak, sk = None, None
        if use_testnet:
            ak = os.getenv("BINANCE_TESTNET_API_KEY")
            sk = os.getenv("BINANCE_TESTNET_SECRET_KEY")
            if (ak is None or len(ak) == 0) or (sk is None or len(sk) == 0):
                loguru_logger.critical("Please set env for BINANCE_TESTNET_API_KEY and BINANCE_TESTNET_SECRET_KEY.")
                return
        else:
            ak = os.getenv("BINANCE_MAINNET_API_KEY")
            sk = os.getenv("BINANCE_MAINNET_SECRET_KEY")
            if (ak is None or len(ak) == 0) or (sk is None or len(sk) == 0):
                loguru_logger.critical("Please set env for BINANCE_MAINNET_API_KEY and BINANCE_MAINNET_SECRET_KEY.")
                return
        
        requests_params = {"verify": False, "timeout": 10}
        if use_proxy:
            http_proxy = os.getenv("HTTP_PROXY")
            https_proxy = os.getenv("HTTPS_PROXY")
            if (http_proxy is None or len(http_proxy) == 0) or (https_proxy is None or len(https_proxy) == 0):
                loguru_logger.critical("Please set env for HTTP_PROXY and HTTPS_PROXY.")
                return
            proxies = {
                "http": http_proxy,
                "https": https_proxy
            }
            requests_params[proxies] = proxies
        self._client = BinanceRestAPIClient(
            api_key=ak,
            api_secret=sk,
            requests_params=requests_params,
            testnet=use_testnet,
        )

        requests_params = {"timeout": 10}
        if use_proxy:
            http_proxy = os.getenv("HTTP_PROXY")
            https_proxy = os.getenv("HTTPS_PROXY")
            if (http_proxy is None or len(http_proxy) == 0) or (https_proxy is None or len(https_proxy) == 0):
                loguru_logger.critical("Please set env for HTTP_PROXY and HTTPS_PROXY.")
                return
            proxies = {
                "http": http_proxy,
                "https": https_proxy
            }
            requests_params[proxies] = proxies
        self._aclient = AsyncBinanceRestAPIClient(
            api_key=ak,
            api_secret=sk,
            requests_params=requests_params,
            testnet=use_testnet,
        )

        self._inited = True
    
    async def is_ready(self) -> bool:
        """Test connectivity to the Binance Rest API."""
        if not self._inited:
            return False

        try:
            await self._aclient.ping()
            res = await self._aclient.get_server_time()
            self._is_ready = True
        except (BinanceRequestException, BinanceAPIException) as e:
            loguru_logger.critical(f"BinanceStaggingBot is not ready, binance's exception:{e}.")
        except Exception as e:
            loguru_logger.critical(f"BinanceStaggingBot is not ready, internal exception:{e}.")
        finally:
            if self._is_ready:
                timestamp_offset = res["serverTime"] - int(time.time() * 1000)
                loguru_logger.info(f"BinanceStaggingBot is ready for operations, timestamp offset from binance server: {timestamp_offset}.")
            return self._is_ready

    async def close(self):
        if self._aclient is not None:
            await self._aclient.close_connection()
        if self._client is not None:
            self._client.close_connection()

    @timeit
    async def show_balances(self):
        """Show current balances."""
        account = None
        try:
            account = await self._aclient.get_account(recvWindow=5000)
        except (BinanceRequestException, BinanceAPIException) as e:
            loguru_logger.error(f"Failed to get balances, binance's exception:{e}.")
        except Exception as e:
            loguru_logger.error(f"Failed to get balances, internal exception:{e}.")
        finally:
            if account is not None:
                print(f"{Fore.GREEN} ======================================= BALANCES ======================================= {Style.RESET_ALL}")
                for balance in account["balances"]:
                    if balance["asset"] in ["BTC", "ETH", "USDT", "BUSD"]:
                        print(f"{Fore.CYAN}{pprint.pformat(balance, indent=1, depth=1, compact=True)}{Style.RESET_ALL}")
                print(f"{Fore.GREEN} ======================================= BALANCES ======================================= {Style.RESET_ALL}")

    @timeit
    async def show_recent_n_orders(self, sym: str, n: int = 1):
        """Get recent n orders (include active, canceled, or filled) for a specific symbol."""
        orders = None
        try:
            orders = await self._aclient.get_all_orders(
                symbol=sym,
                limit=n,
                recvWindow=5000,
            )
        except (BinanceRequestException, BinanceAPIException) as e:
            loguru_logger.error(f"Failed to get recent {n} orders, binance's exception:{e}.")
        except Exception as e:
            loguru_logger.error(f"Failed to get recent {n} orders, internal exception:{e}.")
        finally:
            if orders is not None:
                print(f"{Fore.GREEN} ======================================= RECENT N ORDERS ======================================= {Style.RESET_ALL}")
                for order in orders:
                    print(f"{Fore.CYAN}{pprint.pformat(order, indent=1, depth=1, compact=True)}{Style.RESET_ALL}")
                print(f"{Fore.GREEN} ======================================= RECENT N ORDERS ======================================= {Style.RESET_ALL}")

    @timeit
    async def trade(self, sym: str, quantity: int, when: int, side: str = "BUY", retry_cnt: int = 5) -> bool:
        """Buy some quantities of a specific coin at particular time."""
        now = time.time()
        while now < when:
            await asyncio.sleep(0.001)
            now = time.time()

        done = False
        retries = 0
        order_id = gen_n_digit_nums_and_letters(22)
        while retries < retry_cnt:
            try:
                loguru_logger.info(f"Try to trade a new order<order_id:{order_id}>...")
                if side == "BUY":
                    resp = await self._aclient.order_market_buy(
                        symbol=sym,
                        quoteOrderQty=quantity,
                        newClientOrderId=order_id,
                        recvWindow=2000,
                    )
                loguru_logger.info(f"Traded new order<order_id:{order_id}>.")
                print(f"{Fore.GREEN} ======================================= NEW ORDER ======================================= {Style.RESET_ALL}")
                print(f"{Fore.CYAN}{pprint.pformat(resp, indent=1, depth=1, compact=True)}{Style.RESET_ALL}")
                print(f"{Fore.GREEN} ======================================= NEW ORDER ======================================= {Style.RESET_ALL}")
                await db_instance().add_new_spot_market_order(order=resp)
                done = True
            except (BinanceRequestException, BinanceAPIException, BinanceOrderException) as e:
                loguru_logger.error(f"Failed to trade new order<order_id:{order_id}>, binance's exception:{e}.")
                await asyncio.sleep(0.001)
                retries += 1
            except Exception as e:
                loguru_logger.error(f"Failed to trade new order<order_id:{order_id}>, internal exception:{e}.")
                retries = retry_cnt
            finally:
                if done:
                    break
        
        return done
