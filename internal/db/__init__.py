# -*- coding: utf-8 -*-
import asyncio
import jsonschema
import logging
import pymongo
import pymongo.errors as perrors
import time

from internal.singleton import Singleton
from loguru import logger as loguru_logger
from motor.motor_asyncio import AsyncIOMotorClient
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from typing import Any, Callable, Dict, Optional


def _create_retry_decorator(min_secs: int = 1, max_secs: int = 60, max_retries: int = 3) -> Callable[[Any], Any]:
    return retry(
        reraise=True,
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=1, min=min_secs, max=max_secs),
        retry=(
            retry_if_exception_type(perrors.NetworkTimeout)
            | retry_if_exception_type(perrors.ConnectionFailure)
            | retry_if_exception_type(perrors.ExecutionTimeout)
            | retry_if_exception_type(perrors.WTimeoutError)
        ),
        before_sleep=before_sleep_log(loguru_logger, logging.WARNING),
    )


retry_decorator = _create_retry_decorator()


class MongoClientSetupException(Exception):
    pass


class MongoClient(metaclass=Singleton):
    '''
    MongoDB自定义客户端
    '''

    DB_CONFIG_SCHEMA = {
        "type": "object",
        "properties": {
            "endpoint": {"type": "string"},
            "username": {"type": "string"},
            "password": {"type": "string"},
            "auth_mechanism": {"type": "string"},
            "database": {"type": "string"},
            "collection": {"type": "string"},
        },
        "required": [
            "endpoint",
            "username",
            "password",
            "auth_mechanism",
            "database",
            "collection",
        ],
    }

    def __init__(self, client_conf: Dict[str, Any], io_loop: Optional[asyncio.BaseEventLoop] = None):
        if not self._validate_config(client_conf):
            raise MongoClientSetupException("Please provide mongodb config file.")
        
        if io_loop is not None:
            self._client = AsyncIOMotorClient(
                "mongodb://{}/".format(client_conf["endpoint"]),
                username=client_conf["username"],
                password=client_conf["password"],
                authSource="admin",
                authMechanism=client_conf["auth_mechanism"],
                serverSelectionTimeoutMS=2000,
                socketTimeoutMS=5000,
                connectTimeoutMS=2000,
                io_loop=io_loop,
            )
        else:
            self._client = AsyncIOMotorClient(
                "mongodb://{}/".format(client_conf["endpoint"]),
                username=client_conf["username"],
                password=client_conf["password"],
                authSource="admin",
                authMechanism=client_conf["auth_mechanism"],
                serverSelectionTimeoutMS=2000,
                socketTimeoutMS=5000,
                connectTimeoutMS=2000,
            )
        self._conf = client_conf

    def _validate_config(self, conf: Optional[Dict[str, Any]] = None) -> bool:
        valid = False
        try:
            jsonschema.validate(instance=conf, schema=self.DB_CONFIG_SCHEMA)
            valid = True
        except jsonschema.ValidationError:
            loguru_logger.error(f"Invalid mongodb config:{conf}.")
        finally:
            return valid

    async def is_connected(self) -> bool:
        connected = False
        try:
            self._db = self._client[self._conf["database"]]
            res = await self._db.command("ping")
            connected = res["ok"] == 1.0
            if connected:
                try:
                    self._store = self._db[self._conf["collection"]]
                    for index in self._conf["indexes"]:
                        if index["direction"] == 1:
                            self._store.create_index(
                                index["name"], pymongo.ASCENDING, unique=index["unique"], background=True, sparse=False
                            )
                        elif index["direction"] == -1:
                            self._store.create_index(
                                index["name"], pymongo.DESCENDING, unique=index["unique"], background=True, sparse=False
                            )
                except perrors.DuplicateKeyError:
                    pass
        except perrors.ServerSelectionTimeoutError:
            loguru_logger.error("Please check connectivity with mongodb server.")
        finally:
            return connected

    @retry_decorator
    async def add_new_spot_market_order(self, order: Dict[str, Any]) -> bool:
        done = False
        try:
            query = {"clientOrderId": order["clientOrderId"]}
            update_ts = int(time.time())
            update = {"$set": {
                "clientOrderId": order["clientOrderId"],
                "orderId": order["orderId"],
                "origQty": order["origQty"],
                "price": order["price"],
                "side": order["side"],
                "status": order["status"],
                "symbol": order["symbol"],
                "timeInForce": order["timeInForce"],
                "transactTime": order["transactTime"],
                "updateTime": update_ts,
            }}
            await self._store.update_one(query, update, upsert=True)
            loguru_logger.debug(f"Added a new spot-market-order:{order['clientOrderId']}.")
            done = True
        except perrors.NetworkTimeout:
            loguru_logger.error(f"Timeout to add spot-market-order:{order['clientOrderId']}.")
        except Exception as e:
            loguru_logger.error(f"Failed to add spot-market-order:{order['clientOrderId']}, err:{e}.")
        finally:
            return done

    @retry_decorator
    async def add_new_spot_limit_order(self, order: Dict[str, Any]) -> bool:
        done = False
        try:
            query = {"clientOrderId": order["clientOrderId"]}
            update = {"$set": {
                "clientOrderId": order["clientOrderId"],
                "orderId": order["orderId"],
                "origQty": order["origQty"],
                "origQuoteOrderQty": order["origQuoteOrderQty"],
                "price": order["price"],
                "side": order["side"],
                "status": order["status"],
                "symbol": order["symbol"],
                "timeInForce": order["timeInForce"],
                "time": order["time"],
                "updateTime": order["updateTime"],
            }}
            await self._store.update_one(query, update, upsert=True)
            loguru_logger.debug(f"Added a new spot-limit-order:{order['clientOrderId']}.")
            done = True
        except perrors.NetworkTimeout:
            loguru_logger.error(f"Timeout to add spot-limit-order:{order['clientOrderId']}.")
        except Exception as e:
            loguru_logger.error(f"Failed to add spot-limit-order:{order['clientOrderId']}, err:{e}.")
        finally:
            return done

    def close(self):
        self._client.close()


_instance: MongoClient = None


def init_instance(client_conf: Dict[str, Any], io_loop: Optional[asyncio.BaseEventLoop] = None):
    global _instance
    _instance = MongoClient(client_conf, io_loop)


def instance() -> MongoClient:
    return _instance
