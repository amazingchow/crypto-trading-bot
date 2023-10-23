# -*- coding: utf-8 -*-
import asyncio
import decimal
import os
import tabulate
import time

from binance.client import AsyncClient as AsyncBinanceRestAPIClient
from binance.exceptions import BinanceAPIException, BinanceRequestException, BinanceOrderException
from binance.streams import BinanceSocketManager
from colorama import Fore, Style
from internal.db import instance as db_instance
from internal.singleton import Singleton
from internal.utils.helper import timeit, gen_n_digit_nums_and_letters
from loguru import logger as loguru_logger
from typing import Any, Dict, NoReturn, Optional, Tuple


class BinanceGridTradingBot(metaclass=Singleton):
    """
    币安网格交易机器人
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
        self._sock_mgr = BinanceSocketManager(client=self._aclient)
        self._kline_q = asyncio.Queue()

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
            loguru_logger.critical(f"BinanceGridTradingBot is not ready, binance's exception:{e}.")
        except Exception as e:
            loguru_logger.critical(f"BinanceGridTradingBot is not ready, internal exception:{e}.")
        finally:
            if self._is_ready:
                timestamp_offset = res["serverTime"] - int(time.time() * 1000)
                loguru_logger.info(f"BinanceGridTradingBot is ready for operations, timestamp offset from binance server: {timestamp_offset}.")
            return self._is_ready

    async def close(self):
        if self._aclient is not None:
            await self._aclient.close_connection()

    @property
    def lower_range_price(self) -> float:
        """
        区间下限价格（USDT计价）
        """
        return self._lower_range_price

    @lower_range_price.setter
    def lower_range_price(self, x: float):
        self._lower_range_price = x

    @property
    def upper_range_price(self) -> float:
        """
        区间上限价格（USDT计价）
        """
        return self._upper_range_price

    @upper_range_price.setter
    def upper_range_price(self, x: float):
        self._upper_range_price = x

    @property
    def grids(self) -> int:
        """
        网格数量（50-5000）
        """
        return self._grids

    @grids.setter
    def grids(self, x: int):
        self._grids = x

    @property
    def total_investment(self) -> int:
        """
        总投资额（USDT计价）
        """
        return self._total_investment

    @total_investment.setter
    def total_investment(self, x: int):
        self._total_investment = x

    async def show_balances(self, sym: str):
        """Show current balances."""
        account = None
        try:
            account = await self._aclient.get_account(recvWindow=5000)
        except (BinanceRequestException, BinanceAPIException) as e:
            loguru_logger.error(f"Failed to get balances, binance's exception:{e}.")
        except Exception as e:
            loguru_logger.error(f"Failed to get balances, internal exception:{e}.")
        finally:
            base_asset = sym[:-4]
            if account is not None:
                print(f"{Fore.GREEN} ======================================= BALANCES ======================================= {Style.RESET_ALL}")
                table = [["Asset", "Free", "Locked"]]
                for balance in account["balances"]:
                    if balance["asset"] in [base_asset, "USDT"]:
                        table.append([balance["asset"], balance["free"], balance["locked"]])
                table_output = tabulate.tabulate(table, headers="firstrow", tablefmt="mixed_grid", showindex="always")
                print(f"{Fore.CYAN}{table_output}{Style.RESET_ALL}")
                print(f"{Fore.GREEN} ======================================= BALANCES ======================================= {Style.RESET_ALL}")

    @timeit
    async def show_profit(self, sym: str):
        """Show total profit."""
        cnt, ok = await db_instance().count_spot_limit_orders_of_x_status(sym=sym, status="FILLED")
        if ok:
            print(f"{Fore.GREEN} ======================================= PROFIT ======================================= {Style.RESET_ALL}")
            print(f"{Fore.CYAN} Cumulative Arbitrage {cnt} Times. {Style.RESET_ALL}")
            print(f"{Fore.GREEN} ======================================= PROFIT ======================================= {Style.RESET_ALL}")

    @timeit
    async def show_recent_n_orders(self, sym: str, n: int = 1):
        """Get recent n orders (include active, canceled, or filled) for BTCUSDT."""
        orders = None
        try:
            orders = await self._aclient.get_all_orders(
                symbol=sym,
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
                table = [["Symbol", "ClientOrderId", "OrigQty", "Side", "Price", "Status", "Time"]]
                for order in orders:
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
                print(f"{Fore.GREEN} ======================================= RECENT N ORDERS ======================================= {Style.RESET_ALL}")

    @timeit
    async def latest_orderbook(self, sym: str, verbose: bool = True) -> Optional[Dict[str, Any]]:
        """Get the Order Book for the BTCUSDT market."""
        orderbook = None
        try:
            orderbook = await self._aclient.get_order_book(symbol=sym, limit=5)
        except (BinanceRequestException, BinanceAPIException) as e:
            loguru_logger.error(f"Failed to get the Order Book for the {sym} market, binance's exception:{e}.")
        except Exception as e:
            loguru_logger.error(f"Failed to get the Order Book for the {sym} market, internal exception:{e}.")
        finally:
            if orderbook is not None:
                if verbose:
                    print(f"{Fore.GREEN} ======================================= {sym} ORDER BOOK ======================================= {Style.RESET_ALL}")
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
                    print(f"{Fore.GREEN} ======================================= {sym} ORDER BOOK ======================================= {Style.RESET_ALL}")
            return orderbook

    @timeit
    async def check_order(self, sym: str, order_id: str, expected_status: str = "FILLED", verbose: bool = True) -> bool:
        """Check an order's status.

        Available status: CANCELED, EXPIRED, FILLED, NEW, PARTIALLY_FILLED, PENDING_CANCEL, REJECTED
        """
        done = False
        status = None
        try:
            resp = await self._aclient.get_order(
                symbol=sym,
                origClientOrderId=order_id,
                recvWindow=5000,
            )
            if verbose:
                print(f"{Fore.GREEN} ======================================= CHECK ORDER ======================================= {Style.RESET_ALL}")
                table = [["Symbol", "ClientOrderId", "OrigQty", "Side", "Price", "Status", "Time"]]
                table.append([
                    resp["symbol"],
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
    async def cancel_order(self, sym: str, order_id: str, verbose: bool = True) -> bool:
        """Cancel an active order."""
        done = False
        try:
            resp = await self._aclient.cancel_order(
                symbol=sym,
                origClientOrderId=order_id,
                recvWindow=5000,
            )
            if verbose:
                print(f"{Fore.GREEN} ======================================= CANCEL ORDER ======================================= {Style.RESET_ALL}")
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

    async def feed_klines(self, sym: Optional[str] = None, interval: Optional[str] = "1m") -> NoReturn:
        sock_client = self._sock_mgr.kline_socket(symbol=sym, interval=interval)
        await sock_client.connect()
        loguru_logger.debug("Ready to receive k-lines<symbol:{}, interval:{}>...".format(sym, interval))
        while 1:
            res = await sock_client.recv()
            loguru_logger.debug("Received one k-line<symbol:{}, interval:{}>.".format(sym, interval))
            loguru_logger.debug("====================================================")
            loguru_logger.debug(res)
            loguru_logger.debug("====================================================")
            self._kline_q.put_nowait({"symbol": res["s"], "st_timestamp": res["k"]["t"], "ed_timestamp": res["k"]["T"], "kline": res["k"]})

    async def persist_klines(self, sym: Optional[str] = None, interval: Optional[str] = "1m") -> NoReturn:
        loguru_logger.debug("Ready to persist k-lines<symbol:{}, interval:{}>...".format(sym, interval))
        while 1:
            kline = await self._kline_q.get()
            self._kline_q.task_done()
            loguru_logger.debug("Prepare to persist one k-line<symbol:{}, interval:{}>.".format(sym, interval))
            await self._store.insert_kline(sym=sym, interval=interval, kline=kline)

    async def swap_2_usdt(self, sym: Optional[str] = None, qty: Optional[int] = None):
        done = False
        try:
            res = await self._api_aync_client.create_order(
                symbol=sym,
                side="SELL",
                type="MARKET",
                quantity=decimal.Decimal("{:.3f}".format(qty)),
                newOrderRespType="RESULT",
                recvWindow=2000,
            )
            if res["status"] == "FILLED":
                done = True
        except BinanceRequestException as e:
            loguru_logger.error("Failed to create order for symbol:{}, err:{}.".format(sym, e))
        except BinanceAPIException as e:
            loguru_logger.error("Failed to create order for symbol:{}, err:{}.".format(sym, e))
        finally:
            return done

    @timeit
    async def trade(self, sym: str, when: int, retry_cnt: int = 1):
        """Run grid-trading for a long time."""
        usdt_free_amount, usdt_locked_amount = await self.usdt_asset()
        if usdt_free_amount is None or usdt_locked_amount is None:
            return
        usdt_free_amount = float(usdt_free_amount)
        if usdt_free_amount < self.total_investment:
            loguru_logger.warning("No need to trade, USDT is insufficient.")
            return
        if float(usdt_locked_amount) > 1:
            loguru_logger.warning("No need to trade, there are pending orders existed.")
            return

        now = time.time()
        while now < when:
            await asyncio.sleep(0.001)
            now = time.time()

        step_price = (self._upper_range_price - self._lower_range_price) // self._grids
        single_trade_capacity = self._total_investment // self._grids
        trade_price_list = [self._lower_range_price + i * step_price for i in range(self._grids)]

        latest_price = None
        try:
            resp = await self._aclient.get_symbol_ticker(
                symbol=sym,
            )
            latest_price = float(resp["price"])
        except (BinanceRequestException, BinanceAPIException) as e:
            loguru_logger.error(f"Failed to get latest price for symbol:{sym}, binance's exception:{e}.")
        except Exception as e:
            loguru_logger.error(f"Failed to get latest price for symbol:{sym}, internal exception:{e}.")
        finally:
            if latest_price is None:
                return
        
        loguru_logger.debug(f"Latest price for symbol:{sym} is {latest_price}")
        if latest_price > self._upper_range_price:
            loguru_logger.warning(f"No need to trade, since latest price ({latest_price}) is greater than upper range price ({self._upper_range_price}).")
            return
        if latest_price < self._lower_range_price:
            loguru_logger.warning(f"No need to trade, since latest price ({latest_price}) is less than lower range price ({self._lower_range_price}).")
            return

        initial_usdt_spent = (self._upper_range_price - latest_price) / (self._upper_range_price - self._lower_range_price) * self._total_investment
        loguru_logger.debug(f"Try to spend {initial_usdt_spent:.1f} USDT at first...")
        order_id = gen_n_digit_nums_and_letters(22)
        resp = None
        try:
            resp = await self._aclient.create_order(
                symbol=sym,
                side="BUY",
                type="MARKET",
                quoteOrderQty=decimal.Decimal(f"{initial_usdt_spent:.1f}"),
                newClientOrderId=order_id,
                recvWindow=2000,
            )
            loguru_logger.debug(f"Order:{resp}")
        except (BinanceRequestException, BinanceAPIException) as e:
            loguru_logger.error(f"Failed to create spot-market-order for symbol:{sym}, binance's exception:{e}.")
        except Exception as e:
            loguru_logger.error(f"Failed to create spot-market-order for symbol:{sym}, internal exception:{e}.")
        finally:
            if resp is None:
                return
        
        while 1:
            if resp["status"] == "FILLED":
                break
            await asyncio.sleep(3)
            try:
                inner_resp = await self._aclient.get_order(
                    symbol=sym,
                    origClientOrderId=order_id,
                    recvWindow=5000,
                )
                loguru_logger.debug(f"Order:{inner_resp}")
            except (BinanceRequestException, BinanceAPIException) as e:
                loguru_logger.error(f"Failed to check order<order_id:{order_id}>, binance's exception:{e}.")
            except Exception as e:
                loguru_logger.error(f"Failed to check order<order_id:{order_id}>, internal exception:{e}.")
            finally:
                if inner_resp is not None:
                    resp = inner_resp
        loguru_logger.debug(f"Spent {initial_usdt_spent:.1f} USDT at first.")
        return

        _latest_price = None
        try:
            res = await self._api_aync_client.get_symbol_ticker(
                symbol=sym,
            )
            _latest_price = float(res["price"])
        except BinanceRequestException as e:
            loguru_logger.error("Failed to get latest price for symbol:{}, err:{}.".format(sym, e))
        except BinanceAPIException as e:
            loguru_logger.error("Failed to get latest price for symbol:{}, err:{}.".format(sym, e))
        finally:
            if _latest_price is not None:
                latest_price = _latest_price
        loguru_logger.debug("Latest price for symbol:{} is {}".format(sym, latest_price))

        for trading_price in trade_price_list:
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
                    quoteOrderQty=decimal.Decimal("{:.3f}".format(single_trade_capacity)),
                    price=decimal.Decimal("{:.3f}".format(trading_price)),
                    newOrderRespType="RESULT",
                    newClientOrderId=self._new_client_order_id(),
                    recvWindow=2000,
                )
                loguru_logger.debug("Created order, res:{}", res)
            except BinanceRequestException as e:
                loguru_logger.error("Failed to create order for symbol:{}, err:{}.".format(sym, e))
            except BinanceAPIException as e:
                loguru_logger.error("Failed to create order for symbol:{}, err:{}.".format(sym, e))
