# -*- coding: utf-8 -*-
import os
import time

import tabulate
from binance.client import AsyncClient as AsyncBinanceRestAPIClient
from binance.exceptions import BinanceAPIException, BinanceOrderException, BinanceRequestException
from colorama import Fore, Style
from loguru import logger as loguru_logger

from internal.classes.singleton import Singleton
from internal.utils.helper import gen_n_digit_nums_and_letters, timeit


class BinanceSimpleTradingBot(metaclass=Singleton):
    """
    币安现货交易机器人
    """
    
    def __init__(self, use_proxy: bool = False, use_testnet: bool = False):
        self._inited = False
        self._is_ready = False
        self._aclient = None

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
            loguru_logger.critical(f"BinanceSimpleTradingBot is not ready, binance's exception:{e}.")
        except Exception as e:
            loguru_logger.critical(f"BinanceSimpleTradingBot is not ready, internal exception:{e}.")
        finally:
            if self._is_ready:
                timestamp_offset = res["serverTime"] - int(time.time() * 1000)
                loguru_logger.info(f"BinanceSimpleTradingBot is ready for operations, timestamp offset from binance server: {timestamp_offset}.")
            return self._is_ready

    async def close(self):
        if self._aclient is not None:
            await self._aclient.close_connection()

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
                table = [["Asset", "Free", "Locked"]]
                for balance in account["balances"]:
                    if balance["asset"] in ["BTC", "ETH", "USDT", "BUSD"]:
                        table.append([balance["asset"], balance["free"], balance["locked"]])
                table_output = tabulate.tabulate(table, headers="firstrow", tablefmt="mixed_grid", showindex="always")
                print(f"{Fore.CYAN}{table_output}{Style.RESET_ALL}")
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
                print(f"{Fore.GREEN} ======================================= RECENT N SPOT MARKET ORDERS ======================================= {Style.RESET_ALL}")
                table = [["Symbol", "ClientOrderId", "OrigQty", "Side", "Price", "Status", "Time"]]
                orders = sorted(orders, key=lambda x: x["time"], reverse=True)
                for order in orders:
                    if order["type"] != "MARKET":
                        continue
                    table.append([
                        order["symbol"],
                        order["clientOrderId"],
                        order["origQty"],
                        order["side"],
                        order["price"],
                        order["status"],
                        order["time"],
                    ])
                table_output = tabulate.tabulate(table, headers="firstrow", tablefmt="mixed_grid", showindex="always")
                print(f"{Fore.CYAN}{table_output}{Style.RESET_ALL}")
                print(f"{Fore.GREEN} ======================================= RECENT N SPOT MARKET ORDERS ======================================= {Style.RESET_ALL}")

    @timeit
    async def trade(self, sym: str, base_qty: float = 0, quote_qty: float = 0, side: str = "BUY") -> bool:
        """Buy/Sell some quantities of a specific coin."""
        done = False
        order_id = gen_n_digit_nums_and_letters(22)
        try:
            resp = None
            loguru_logger.info(f"Try to trade a new spot-market-order<order_id:{order_id}>...")
            if side == "BUY":
                resp = await self._aclient.order_market_buy(
                    symbol=sym,
                    quoteOrderQty=quote_qty,
                    newClientOrderId=order_id,
                    recvWindow=2000,
                )
            elif side == "SELL":
                resp = await self._aclient.order_market_sell(
                    symbol=sym,
                    quantity=base_qty,
                    newClientOrderId=order_id,
                    recvWindow=2000,
                )
            loguru_logger.info(f"Traded spot-market-order<order_id:{order_id}>.")
            print(f"{Fore.GREEN} ======================================= NEW SPOT MARKET ORDER ======================================= {Style.RESET_ALL}")
            table = [["Symbol", "ClientOrderId", "OrigQty", "Side", "Price", "Status", "TransactTime"]]
            table.append([
                resp["symbol"],
                resp["clientOrderId"],
                resp["origQty"],
                resp["side"],
                resp["price"],
                resp["status"],
                resp["transactTime"],
            ])
            table_output = tabulate.tabulate(table, headers="firstrow", tablefmt="mixed_grid", showindex="always")
            print(f"{Fore.CYAN}{table_output}{Style.RESET_ALL}")
            print(f"{Fore.GREEN} ======================================= NEW SPOT MARKET ORDER ======================================= {Style.RESET_ALL}")
            done = True
        except (BinanceRequestException, BinanceAPIException, BinanceOrderException) as e:
            loguru_logger.error(f"Failed to trade spot-market-order<order_id:{order_id}>, binance's exception:{e}.")
        except Exception as e:
            loguru_logger.error(f"Failed to trade spot-market-order<order_id:{order_id}>, internal exception:{e}.")
        finally:
            return done
