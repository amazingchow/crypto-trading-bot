# -*- coding: utf-8 -*-
import asyncio
import os
import tabulate
import time

from binance.client import AsyncClient as AsyncBinanceRestAPIClient
from binance.client import Client as BinanceRestAPIClient
from binance.exceptions import BinanceAPIException, BinanceRequestException, BinanceOrderException
from colorama import Fore, Style
from internal.db import instance as db_instance
from internal.singleton import Singleton
from internal.utils.helper import timeit, gen_n_digit_nums_and_letters
from loguru import logger as loguru_logger
from typing import Any, Dict, Optional, Tuple


class BinanceStablecoinSwapBot(metaclass=Singleton):
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
            loguru_logger.critical(f"BinanceStablecoinSwapBot is not ready, binance's exception:{e}.")
        except Exception as e:
            loguru_logger.critical(f"BinanceStablecoinSwapBot is not ready, internal exception:{e}.")
        finally:
            if self._is_ready:
                timestamp_offset = res["serverTime"] - int(time.time() * 1000)
                loguru_logger.info(f"BinanceStablecoinSwapBot is ready for operations, timestamp offset from binance server: {timestamp_offset}.")
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
                table = [["Asset", "Free", "Locked"]]
                for balance in account["balances"]:
                    if balance["asset"] in ["USDT", "BUSD"]:
                        table.append([balance["asset"], balance["free"], balance["locked"]])
                table_output = tabulate.tabulate(table, headers="firstrow", tablefmt="mixed_grid", showindex="always")
                print(f"{Fore.CYAN}{table_output}{Style.RESET_ALL}")
                print(f"{Fore.GREEN} ======================================= BALANCES ======================================= {Style.RESET_ALL}")

    @timeit
    async def show_profit(self):
        """Show total profit."""
        cnt, ok = await db_instance().count_spot_limit_orders_of_x_status(status="FILLED")
        if ok:
            print(f"{Fore.GREEN} ======================================= BALANCES ======================================= {Style.RESET_ALL}")
            print(f"{Fore.CYAN} Cumulative Arbitrage {cnt} Times. {Style.RESET_ALL}")
            print(f"{Fore.GREEN} ======================================= BALANCES ======================================= {Style.RESET_ALL}")

    @timeit
    async def show_recent_n_orders(self, n: int = 1):
        """Get recent n orders (include active, canceled, or filled) for BUSDUSDT."""
        orders = None
        try:
            orders = await self._aclient.get_all_orders(
                symbol="BUSDUSDT",
                limit=n,
                recvWindow=5000,
            )
            orders = sorted(orders, key=lambda x: x["time"], reverse=True)
        except (BinanceRequestException, BinanceAPIException) as e:
            loguru_logger.error(f"Failed to get recent {n} orders, binance's exception:{e}.")
        except Exception as e:
            loguru_logger.error(f"Failed to get recent {n} orders, internal exception:{e}.")
        finally:
            if orders is not None:
                print(f"{Fore.GREEN} ======================================= RECENT N ORDERS ======================================= {Style.RESET_ALL}")
                table = [["ClientOrderId", "OrigQty", "Side", "Price", "Status", "Time"]]
                for order in orders:
                    table.append([
                        order["clientOrderId"],
                        order["origQty"],
                        order["side"],
                        order["price"],
                        order["status"],
                        order["time"],
                    ])
                table_output = tabulate.tabulate(table, headers="firstrow", tablefmt="mixed_grid", showindex="always")
                print(f"{Fore.CYAN}{table_output}{Style.RESET_ALL}")
                print(f"{Fore.GREEN} ======================================= RECENT N ORDERS ======================================= {Style.RESET_ALL}")

    @timeit
    async def usdt_asset(self, verbose: bool = True) -> Tuple[Optional[str], Optional[str]]:
        """Get USDT asset balance."""
        free_amount = None
        locked_amount = None
        asset = None
        try:
            asset = await self._aclient.get_asset_balance(asset="USDT", recvWindow=5000)
        except (BinanceRequestException, BinanceAPIException) as e:
            loguru_logger.error(f"Failed to get USDT asset balance, binance's exception:{e}.")
        except Exception as e:
            loguru_logger.error(f"Failed to get USDT asset balance, internal exception:{e}.")
        finally:
            if asset is not None:
                if verbose:
                    print(f"{Fore.GREEN} ======================================= USDT ASSET BALANCE ======================================= {Style.RESET_ALL}")
                    table = [["Asset", "Free", "Locked"], [asset["asset"], asset["free"], asset["locked"]]]
                    table_output = tabulate.tabulate(table, headers="firstrow", tablefmt="mixed_grid")
                    print(f"{Fore.CYAN}{table_output}{Style.RESET_ALL}")
                    print(f"{Fore.GREEN} ======================================= USDT ASSET BALANCE ======================================= {Style.RESET_ALL}")
                free_amount = asset["free"]
                locked_amount = asset["locked"]
            return (free_amount, locked_amount)
    
    @timeit
    async def busd_asset(self, verbose: bool = True) -> Tuple[Optional[str], Optional[str]]:
        """Get BUSD asset balance."""
        free_amount = None
        locked_amount = None
        asset = None
        try:
            asset = await self._aclient.get_asset_balance(asset="BUSD", recvWindow=5000)
        except (BinanceRequestException, BinanceAPIException) as e:
            loguru_logger.error(f"Failed to get BUSD asset balance, binance's exception:{e}.")
        except Exception as e:
            loguru_logger.error(f"Failed to get BUSD asset balance, internal exception:{e}.")
        finally:
            if asset is not None:
                if verbose:
                    print(f"{Fore.GREEN} ======================================= BUSD ASSET BALANCE ======================================= {Style.RESET_ALL}")
                    table = [["Asset", "Free", "Locked"], [asset["asset"], asset["free"], asset["locked"]]]
                    table_output = tabulate.tabulate(table, headers="firstrow", tablefmt="mixed_grid")
                    print(f"{Fore.CYAN}{table_output}{Style.RESET_ALL}")
                    print(f"{Fore.GREEN} ======================================= BUSD ASSET BALANCE ======================================= {Style.RESET_ALL}")
                free_amount = asset["free"]
                locked_amount = asset["locked"]
            return (free_amount, locked_amount)

    @timeit
    async def orderbook_of_busd_usdt(self, verbose: bool = True) -> Optional[Dict[str, Any]]:
        """Get the Order Book for the BUSDUSDT market."""
        orderbook = None
        try:
            orderbook = await self._aclient.get_order_book(symbol="BUSDUSDT", limit=5)
        except (BinanceRequestException, BinanceAPIException) as e:
            loguru_logger.error(f"Failed to get the Order Book for the BUSDUSDT market, binance's exception:{e}.")
        except Exception as e:
            loguru_logger.error(f"Failed to get the Order Book for the BUSDUSDT market, internal exception:{e}.")
        finally:
            if orderbook is not None:
                if verbose:
                    print(f"{Fore.GREEN} ======================================= BUSDUSDT ORDER BOOK ======================================= {Style.RESET_ALL}")
                    table = [["Sell", "SellQty", "Buy", "BuyQty"]]
                    i, j = 4, 0
                    while i >= 0 and j < 5:
                        table.append([
                            orderbook["asks"][i][0],
                            orderbook["asks"][i][1],
                            orderbook["bids"][j][0],
                            orderbook["bids"][j][1],
                        ])
                        i -= 1
                        j += 1
                    table_output = tabulate.tabulate(table, headers="firstrow", tablefmt="psql")
                    print(f"{Fore.CYAN}{table_output}{Style.RESET_ALL}")
                    print(f"{Fore.GREEN} ======================================= BUSDUSDT ORDER BOOK ======================================= {Style.RESET_ALL}")
            return orderbook

    @timeit
    async def cancel_order(self, order_id: str, verbose: bool = True) -> bool:
        """Cancel an active order."""
        done = False
        try:
            resp = await self._aclient.cancel_order(
                symbol="BUSDUSDT",
                origClientOrderId=order_id,
                recvWindow=5000,
            )
            if verbose:
                print(f"{Fore.GREEN} ======================================= CANCEL ORDER ======================================= {Style.RESET_ALL}")
                table = [["ClientOrderId", "OrigQty", "Side", "Price", "Status", "TransactTime"]]
                table.append([
                    resp["clientOrderId"],
                    resp["origQty"],
                    resp["side"],
                    resp["price"],
                    resp["status"],
                    resp["transactTime"],
                ])
                table_output = tabulate.tabulate(table, headers="firstrow", tablefmt="mixed_grid")
                print(f"{Fore.CYAN}{table_output}{Style.RESET_ALL}")
                print(f"{Fore.GREEN} ======================================= CANCEL ORDER ======================================= {Style.RESET_ALL}")
            done = True
        except (BinanceRequestException, BinanceAPIException) as e:
            loguru_logger.error(f"Failed to cancel order<order_id:{order_id}>, binance's exception:{e}.")
        except Exception as e:
            loguru_logger.error(f"Failed to cancel order<order_id:{order_id}>, internal exception:{e}.")
        finally:
            return done

    @timeit
    async def check_order(self, order_id: str, expected_status: str = "FILLED", verbose: bool = True) -> bool:
        """Check an order's status.

        Available status: CANCELED, EXPIRED, FILLED, NEW, PARTIALLY_FILLED, PENDING_CANCEL, REJECTED
        """
        done = False
        status = None
        try:
            self._client.get_order
            resp = await self._aclient.get_order(
                symbol="BUSDUSDT",
                origClientOrderId=order_id,
                recvWindow=5000,
            )
            if verbose:
                print(f"{Fore.GREEN} ======================================= CHECK ORDER ======================================= {Style.RESET_ALL}")
                table = [["ClientOrderId", "OrigQty", "Side", "Price", "Status", "Time"]]
                table.append([
                    resp["clientOrderId"],
                    resp["origQty"],
                    resp["side"],
                    resp["price"],
                    resp["status"],
                    resp["time"],
                ])
                table_output = tabulate.tabulate(table, headers="firstrow", tablefmt="mixed_grid")
                print(f"{Fore.CYAN}{table_output}{Style.RESET_ALL}")
                print(f"{Fore.GREEN} ======================================= CHECK ORDER ======================================= {Style.RESET_ALL}")
            status = resp["status"]
        except (BinanceRequestException, BinanceAPIException) as e:
            loguru_logger.error(f"Failed to check order<order_id:{order_id}>, binance's exception:{e}.")
        except Exception as e:
            loguru_logger.error(f"Failed to check order<order_id:{order_id}>, internal exception:{e}.")
        finally:
            if status is not None and status == expected_status:
                done = True
            return done

    @timeit
    async def swap(self, when: int, retry_cnt: int = 1):
        """Run USDT/BUSD swap for a long time."""
        usdt_free_amount, usdt_locked_amount = await self.usdt_asset()
        if usdt_free_amount is None or usdt_locked_amount is None:
            return
        busd_free_amount, busd_locked_amount = await self.busd_asset()
        if busd_free_amount is None or busd_locked_amount is None:
            return
        usdt_free_amount = float(usdt_free_amount)
        busd_free_amount = float(busd_free_amount)
        if usdt_free_amount < 1 and busd_free_amount < 1:
            loguru_logger.warning("No need to swap, USDT and BUSD is insufficient.")
            return
        if float(usdt_locked_amount) > 1 or float(busd_locked_amount) > 1:
            loguru_logger.warning("No need to swap, there are pending orders existed.")
            return

        now = time.time()
        while now < when:
            await asyncio.sleep(0.001)
            now = time.time()

        side = "BUY"
        if usdt_free_amount < busd_free_amount:
            side = "SELL"
        while 1:
            # 1. Place new order.
            order_id = gen_n_digit_nums_and_letters(22)
            retries = 0
            done = False
            resp = None

            # TODO: Be more smarter to pick buy/sell price...
            orderbook = await self.orderbook_of_busd_usdt()
            buy_price = orderbook["bids"][0][0]
            buy_price_number = float(buy_price)
            sell_price = orderbook["asks"][0][0]

            while retries < retry_cnt:
                try:
                    # BUSD is the base asset (use quantity to measure the amount),
                    # while USDT is the quote asset (use quoteOrderQty to measure the amount).
                    if side == "BUY":
                        loguru_logger.info(f"Try to place a new order<order_id:{order_id}, direction: USDT -> BUSD, amount:{usdt_free_amount}>...")
                        self._client.order_limit_buy
                        resp = await self._aclient.order_limit_buy(
                            symbol="BUSDUSDT",
                            quantity=int(usdt_free_amount / buy_price_number),
                            price=buy_price,
                            timeInForce="GTC",
                            newClientOrderId=order_id,
                            recvWindow=2000,
                        )
                        loguru_logger.info(f"Placed new order<order_id:{order_id}, direction: USDT -> BUSD, amount:{usdt_free_amount}>.")
                    else:
                        loguru_logger.info(f"Try to place a new order<order_id:{order_id}, direction: BUSD -> USDT, amount:{busd_free_amount}>...")
                        resp = await self._aclient.order_limit_sell(
                            symbol="BUSDUSDT",
                            quantity=busd_free_amount,
                            price=sell_price,
                            timeInForce="GTC",
                            newClientOrderId=order_id,
                            recvWindow=2000,
                        )
                        loguru_logger.info(f"Placed new order<order_id:{order_id}, direction: BUSD -> USDT, amount:{busd_free_amount}>.")
                    print(f"{Fore.GREEN} ======================================= NEW ORDER ======================================= {Style.RESET_ALL}")
                    table = [["ClientOrderId", "OrigQty", "Side", "Price", "Status", "TransactTime"]]
                    table.append([
                        resp["clientOrderId"],
                        resp["origQty"],
                        resp["side"],
                        resp["price"],
                        resp["status"],
                        resp["transactTime"],
                    ])
                    table_output = tabulate.tabulate(table, headers="firstrow", tablefmt="mixed_grid")
                    print(f"{Fore.CYAN}{table_output}{Style.RESET_ALL}")
                    print(f"{Fore.GREEN} ======================================= NEW ORDER ======================================= {Style.RESET_ALL}")
                    done = True
                except (BinanceRequestException, BinanceAPIException, BinanceOrderException) as e:
                    if side == "BUY":
                        loguru_logger.error(f"Failed to place new order<order_id:{order_id}, direction: USDT -> BUSD>, binance's exception:{e}.")
                    else:
                        loguru_logger.error(f"Failed to place new order<order_id:{order_id}, direction: BUSD -> USDT>, binance's exception:{e}.")
                    await asyncio.sleep(0.001)
                    retries += 1
                except Exception as e:
                    if side == "BUY":
                        loguru_logger.error(f"Failed to place new order<order_id:{order_id}, direction: USDT -> BUSD>, internal exception:{e}.")
                    else:
                        loguru_logger.error(f"Failed to place new order<order_id:{order_id}, direction: BUSD -> USDT>, internal exception:{e}.")
                    retries = retry_cnt
                finally:
                    if done:
                        break

            # 2. If failed to place new order, just quit the swap routine.
            if not done:
                break
            
            # 3. Wait for the pending order to be filled.
            while 1:
                filled = await self.check_order(order_id=order_id, verbose=False)
                if filled:
                    break
                loguru_logger.debug(f"Order<order_id:{order_id}> has not been filled, wait for 30s to check later...")
                await asyncio.sleep(30)

            resp["status"] = "FILLED"
            await db_instance().add_new_spot_limit_order(order=resp)

            # 4. Reconcile the BUSD/USDT asset.
            if side == "SELL":
                loguru_logger.debug("one-way arbitrage:BUSD ->USDT has been done, start another...")
                usdt_free_amount, _ = await self.usdt_asset()
                if usdt_free_amount is None:
                    break
                usdt_free_amount = float(usdt_free_amount)
                side = "BUY"
            else:
                loguru_logger.debug("one-way arbitrage:USDT -> BUSD has been done, start another...")
                busd_free_amount, _ = await self.busd_asset()
                if busd_free_amount is None:
                    break
                busd_free_amount = float(busd_free_amount)
                side = "SELL"
