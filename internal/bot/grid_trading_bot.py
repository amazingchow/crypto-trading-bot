# -*- coding: utf-8 -*-
import asyncio
import decimal
import os
import shelve
import time
from typing import Any, Dict, NoReturn, Optional, Tuple

import tabulate
from binance.client import AsyncClient as AsyncBinanceRestAPIClient
from binance.exceptions import BinanceAPIException, BinanceRequestException
from binance.streams import BinanceSocketManager
from colorama import Fore, Style
from loguru import logger as loguru_logger

from internal.classes.singleton import Singleton
from internal.db import instance as db_instance
from internal.utils.helper import gen_n_digit_nums_and_letters, timeit


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
        self._trade_data_q = asyncio.Queue()

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

    @property
    def base_asset(self) -> int:
        """
        标的资产代币
        """
        return self._base_asset

    @base_asset.setter
    def base_asset(self, x: str):
        self._base_asset = x

    @property
    def quote_asset(self) -> int:
        """
        报价资产代币
        """
        return self._quote_asset

    @quote_asset.setter
    def quote_asset(self, x: str):
        self._quote_asset = x

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
                    if balance["asset"] in [self._base_asset, self._quote_asset]:
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

    async def show_symbol_information(self, sym: str):
        """Show information of coin symbol, like BTCUSDT.

        LOT_SIZE - The Lot Size filter defines the limits on the quantity for both Limit and Market orders for a symbol.
        NOTIONAL - The Notional filter defines the value calculated in the quote asset for a symbol.
        """
        info = None
        try:
            info = await self._aclient.get_symbol_info(symbol=sym)
        except (BinanceRequestException, BinanceAPIException) as e:
            loguru_logger.error(f"Failed to get information of symbol:{sym}, binance's exception:{e}.")
        except Exception as e:
            loguru_logger.error(f"Failed to get information of symbol:{sym}, internal exception:{e}.")
        finally:
            if info is not None:
                print(f"{Fore.GREEN} ======================================= SYMBOL INFORMATION ======================================= {Style.RESET_ALL}")
                table = [["Symbol", "BaseAsset", "BaseAssetPrecision", "QuoteAsset", "QuotePrecision"]]
                table.append([
                    info["symbol"],
                    info["baseAsset"],
                    info["baseAssetPrecision"],
                    info["quoteAsset"],
                    info["quotePrecision"],
                ])
                table_output = tabulate.tabulate(table, headers="firstrow", tablefmt="mixed_grid", showindex="always")
                print(f"{Fore.CYAN}{table_output}{Style.RESET_ALL}")
                print(f"{Fore.GREEN} ======================================= SYMBOL INFORMATION ======================================= {Style.RESET_ALL}")
                print(f"{Fore.GREEN} ======================================= SYMBOL EXTRA INFORMATION ======================================= {Style.RESET_ALL}")
                extra = {}
                for filter in info["filters"]:
                    if filter["filterType"] == "LOT_SIZE":
                        extra["LOT_SIZE.MinQty"] = filter["minQty"]
                        extra["LOT_SIZE.MaxQty"] = filter["maxQty"]
                    elif filter["filterType"] == "NOTIONAL":
                        extra["NOTIONAL.MinNotional"] = filter["minNotional"]
                        extra["NOTIONAL.MaxNotional"] = filter["maxNotional"]
                    elif filter["filterType"] == "MAX_NUM_ORDERS":
                        extra["MAX_NUM_ORDERS"] = filter["maxNumOrders"]
                    elif filter["filterType"] == "MAX_NUM_ALGO_ORDERS":
                        extra["MAX_NUM_ALGO_ORDERS"] = filter["maxNumAlgoOrders"]
                table = [["LOT_SIZE.MinQty", "LOT_SIZE.MaxQty", "NOTIONAL.MinNotional", "NOTIONAL.MaxNotional", "MAX_NUM_ORDERS", "MAX_NUM_ALGO_ORDERS"]]
                table.append([
                    extra.get("LOT_SIZE.MinQty", ""),
                    extra.get("LOT_SIZE.MaxQty", ""),
                    extra.get("NOTIONAL.MinNotional", ""),
                    extra.get("NOTIONAL.MaxNotional", ""),
                    extra.get("MAX_NUM_ORDERS", ""),
                    extra.get("MAX_NUM_ALGO_ORDERS", ""),
                ])
                table_output = tabulate.tabulate(table, headers="firstrow", tablefmt="mixed_grid", showindex="always")
                print(f"{Fore.CYAN}{table_output}{Style.RESET_ALL}")
                print(f"{Fore.GREEN} ======================================= SYMBOL EXTRA INFORMATION ======================================= {Style.RESET_ALL}")

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
                orders = sorted(orders, key=lambda x: x["time"], reverse=True)
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

    async def _feed_klines(self, sym: str, interval: str = AsyncBinanceRestAPIClient.KLINE_INTERVAL_1MINUTE) -> NoReturn:
        sock_client = self._sock_mgr.kline_socket(symbol=sym, interval=interval)
        await sock_client.connect()
        loguru_logger.debug(f"Ready to receive k-lines<symbol:{sym}, interval:{interval}>...")
        while 1:
            try:
                msg = await sock_client.recv()
                if msg is not None and msg["k"] is not None:
                    print(f"{Fore.GREEN} ======================================= {interval} KLINE FOR {sym} ======================================= {Style.RESET_ALL}")
                    table = [["St", "Ed", "Open", "Close", "High", "Low", "Volume", "Quote Volume"]]
                    table.append([msg["k"]["t"], msg["k"]["T"], msg["k"]["o"], msg["k"]["c"], msg["k"]["h"], msg["k"]["l"], msg["k"]["v"], msg["k"]["q"]])
                    table_output = tabulate.tabulate(table, headers="firstrow", tablefmt="mixed_grid")
                    print(f"{Fore.CYAN}{table_output}{Style.RESET_ALL}")
                    print(f"{Fore.GREEN} ======================================= {interval} KLINE FOR {sym} ======================================= {Style.RESET_ALL}")
            except Exception as e:
                loguru_logger.error(f"Failed to receive k-lines<symbol:{sym}, interval:{interval}> anymore, binance's exception:{e}.")
                break

    async def _feed_trade_data(self, sym: str) -> NoReturn:
        sock_client = self._sock_mgr.trade_socket(symbol=sym)
        await sock_client.connect()
        loguru_logger.debug(f"Ready to receive trade data<symbol:{sym}>...")
        while 1:
            try:
                msg = await sock_client.recv()
                if msg is not None:
                    print(f"{Fore.GREEN} ======================================= TRADE DATA FOR {sym} ======================================= {Style.RESET_ALL}")
                    table = [["Trade ID", "Price", "Quantity", "Buyer Order Id", "Seller Order Id", "Trade Time"]]
                    table.append([msg["t"], msg["p"], msg["q"], msg["b"], msg["a"], msg["T"]])
                    table_output = tabulate.tabulate(table, headers="firstrow", tablefmt="mixed_grid")
                    print(f"{Fore.CYAN}{table_output}{Style.RESET_ALL}")
                    print(f"{Fore.GREEN} ======================================= TRADE DATA FOR {sym} ======================================= {Style.RESET_ALL}")
                    self._trade_data_q.put_nowait(msg)
            except Exception as e:
                loguru_logger.error(f"Failed to receive trade data<symbol:{sym}> anymore, binance's exception:{e}.")
                break

    async def _buy_base_asset(self, sym: str, quote_qty: float, price: str) -> Tuple[str, str, bool]:
        done = False
        client_order_id = gen_n_digit_nums_and_letters(22)
        binance_order_id = ""
        try:
            resp = await self._aclient.create_order(
                symbol=sym,
                side="BUY",
                type="LIMIT",
                quantity=decimal.Decimal(f"{quote_qty / price:.5f}"),
                price=price,
                timeInForce="GTC",
                newClientOrderId=client_order_id,
                recvWindow=2000,
            )
            done = True
            if resp is not None:
                binance_order_id = resp["orderId"]
                print(f"resp == {resp}")
                await db_instance().add_new_spot_limit_order(order=resp)
        except BinanceRequestException as e:
            loguru_logger.error(f"Failed to create spot-limit-order for symbol:{sym}, err:{e}.")
        except BinanceAPIException as e:
            loguru_logger.error(f"Failed to create spot-limit-order for symbol:{sym}, err:{e}.")
        finally:
            if done:
                loguru_logger.debug(f"Created spot-limit-order<order_id:{client_order_id}> for symbol:{sym}.")
            return (client_order_id, binance_order_id, done)

    async def _sell_base_asset(self, sym: str, base_qty: float, price: str) -> Tuple[str, str, bool]:
        done = False
        client_order_id = gen_n_digit_nums_and_letters(22)
        binance_order_id = ""
        try:
            resp = await self._aclient.create_order(
                symbol=sym,
                side="SELL",
                type="LIMIT",
                quantity=decimal.Decimal(f"{base_qty:.5f}"),
                price=price,
                timeInForce="GTC",
                newClientOrderId=client_order_id,
                recvWindow=2000,
            )
            done = True
            if resp is not None:
                binance_order_id = resp["orderId"]
                print(f"resp == {resp}")
                await db_instance().add_new_spot_limit_order(order=resp)
        except BinanceRequestException as e:
            loguru_logger.error(f"Failed to create spot-limit-order for symbol:{sym}, err:{e}.")
        except BinanceAPIException as e:
            loguru_logger.error(f"Failed to create spot-limit-order for symbol:{sym}, err:{e}.")
        finally:
            if done:
                loguru_logger.debug(f"Created spot-limit-order<order_id:{client_order_id}> for symbol:{sym}.")
            return (client_order_id, binance_order_id, done)

    # async def _do_grid_trading(self, sym: str):
    #     for trading_price in target_price_list:
    #         side = "BUY"
    #         if trading_price < latest_price:
    #             side = "BUY"
    #         elif trading_price > latest_price:
    #             side = "SELL"
    #         try:
    #             res = await self._api_aync_client.create_order(
    #                 symbol=sym,
    #                 side=side,
    #                 type="LIMIT",
    #                 quoteOrderQty=decimal.Decimal("{:.3f}".format(single_trading_capacity)),
    #                 price=decimal.Decimal("{:.3f}".format(trading_price)),
    #                 newOrderRespType="RESULT",
    #                 newClientOrderId=self._new_client_order_id(),
    #                 recvWindow=2000,
    #             )
    #             loguru_logger.debug("Created order, res:{}", res)
    #         except BinanceRequestException as e:
    #             loguru_logger.error("Failed to create order for symbol:{}, err:{}.".format(sym, e))
    #         except BinanceAPIException as e:
    #             loguru_logger.error("Failed to create order for symbol:{}, err:{}.".format(sym, e))

    @timeit
    async def trade(self, sym: str, when: int):
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

        self._step_price = (self._upper_range_price - self._lower_range_price) // self._grids
        self._single_trading_capacity = self._total_investment // self._grids
        self._target_price_list = [self._lower_range_price + i * self._step_price for i in range(self._grids)]
        print(f"{Fore.GREEN} ======================================= GRID TRADING INITIAL SETTINGS ======================================= {Style.RESET_ALL}")
        print(f"{Fore.CYAN} base_asset              : {self._base_asset} {Style.RESET_ALL}")
        print(f"{Fore.CYAN} quote_asset             : {self._quote_asset} {Style.RESET_ALL}")
        print(f"{Fore.CYAN} lower_range_price       : {self._lower_range_price} {Style.RESET_ALL}")
        print(f"{Fore.CYAN} upper_range_price       : {self._upper_range_price} {Style.RESET_ALL}")
        print(f"{Fore.CYAN} grids                   : {self._grids} {Style.RESET_ALL}")
        print(f"{Fore.CYAN} total_investment        : {self._total_investment} {Style.RESET_ALL}")
        print(f"{Fore.CYAN} step_price              : {self._step_price} {Style.RESET_ALL}")
        print(f"{Fore.CYAN} single_trading_capacity : {self._single_trading_capacity} {Style.RESET_ALL}")
        print(f"{Fore.CYAN} target_price_list       : {self._target_price_list[:3]} ... {self._target_price_list[-3:]} {Style.RESET_ALL}")
        print(f"{Fore.GREEN} ======================================= GRID TRADING INITIAL SETTINGS ======================================= {Style.RESET_ALL}")

        print(f"{Fore.GREEN} ======================================= GRID TRADING INITIAL TRADING ======================================= {Style.RESET_ALL}")
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
            loguru_logger.debug(f"Latest price for symbol:{sym} is ${latest_price:.1f}")
        if latest_price > self._upper_range_price:
            loguru_logger.warning(f"No need to trade, since latest price ({latest_price:.1f}) is greater than upper range price ({self._upper_range_price:.1f}).")
            return
        if latest_price < self._lower_range_price:
            loguru_logger.warning(f"No need to trade, since latest price ({latest_price:.1f}) is less than lower range price ({self._lower_range_price:.1f}).")
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
            loguru_logger.debug(f"Placed order<order_id:{order_id}>.")
        except (BinanceRequestException, BinanceAPIException) as e:
            loguru_logger.error(f"Failed to create spot-market-order for symbol:{sym}, binance's exception:{e}.")
        except Exception as e:
            loguru_logger.error(f"Failed to create spot-market-order for symbol:{sym}, internal exception:{e}.")
        finally:
            if resp is None:
                return
        
        initial_base_asset_qty = None
        while 1:
            if resp["status"] == "FILLED":
                initial_base_asset_qty = float(resp["executedQty"])
                break
            await asyncio.sleep(3)
            
            try:
                inner_resp = await self._aclient.get_order(
                    symbol=sym,
                    origClientOrderId=order_id,
                    recvWindow=5000,
                )
            except (BinanceRequestException, BinanceAPIException) as e:
                loguru_logger.error(f"Failed to check order<order_id:{order_id}>, binance's exception:{e}.")
            except Exception as e:
                loguru_logger.error(f"Failed to check order<order_id:{order_id}>, internal exception:{e}.")
            finally:
                if inner_resp is not None:
                    resp = inner_resp
        loguru_logger.debug(f"Spent {initial_usdt_spent:.1f} USDT at first, got base asset:{initial_base_asset_qty:.5f}.")

        sell_price = []
        for target_price in self._target_price_list:
            if target_price > latest_price:
                sell_price.append(target_price)
        self._single_trading_base_asset_capacity = initial_base_asset_qty / len(sell_price)
        print(f"{Fore.GREEN} ======================================= GRID TRADING INITIAL TRADING ======================================= {Style.RESET_ALL}")

        print(f"{Fore.GREEN} ======================================= GRID TRADING PLACED ALL TARGET ORDERS ======================================= {Style.RESET_ALL}")
        sell_orders = []
        buy_orders = []
        with shelve.open("grid_trading_orders.db", flag="w", writeback=True) as db:
            db["active_sell"] = []
            db["active_buy"] = []

            for target_price in self._target_price_list:
                if target_price > latest_price:
                    # SELL
                    client_order_id, binance_order_id, ok = await self._sell_base_asset(
                        sym=sym,
                        base_qty=self._single_trading_base_asset_capacity,
                        price=str(target_price),
                    )
                    if ok:
                        db["active_sell"].append(client_order_id)
                        sell_orders.append((client_order_id, binance_order_id))
                else:
                    # BUY
                    client_order_id, binance_order_id, ok = await self._buy_base_asset(
                        sym=sym,
                        quote_qty=self._single_trading_capacity,
                        price=str(target_price),
                    )
                    if ok:
                        db["active_buy"].append(client_order_id)
                        buy_orders.append((client_order_id, binance_order_id))
        print(f"{Fore.GREEN} ======================================= GRID TRADING PLACED ALL TARGET ORDERS ======================================= {Style.RESET_ALL}")

        # task_feed_klines = asyncio.create_task(self._feed_klines(sym=sym, interval=AsyncBinanceRestAPIClient.KLINE_INTERVAL_5MINUTE))
        # task_feed_trade_data = asyncio.create_task(self._feed_trade_data(sym=sym))
        # _, pending = await asyncio.wait(
        #     [
        #         task_feed_klines,
        #         task_feed_trade_data,
        #     ],
        #     return_when=asyncio.FIRST_COMPLETED,
        # )
        # for task in pending:
        #     task.cancel()
