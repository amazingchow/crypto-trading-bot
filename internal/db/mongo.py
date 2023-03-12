# -*- coding: utf-8 -*-
import asyncio
import coloredlogs
import jsonschema
import logging
import pymongo.errors as perrors

from ..singleton import Singleton
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Any
from typing import Dict
from typing import Optional

_g_logger = logging.getLogger("MongoClient")
coloredlogs.install(
    level="DEBUG",
    logger=_g_logger,
    fmt="[%(asctime)s][%(levelname)s][%(name)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


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
            "kline_store": {"type": "object"},
        },
        "required": [
            "endpoint",
            "username",
            "password",
            "auth_mechanism",
            "kline_store",
        ],
    }

    def __init__(self, client_conf: Optional[Dict[str, str]] = None, io_loop: Optional[asyncio.BaseEventLoop] = None):
        if not self._validate_config(client_conf):
            raise MongoClientSetupException("Please provide valid config file.")
        
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
                io_loop=io_loop,
            )

        self._kline_db = self._client[client_conf["kline_store"]["database"]]
        self._kline_store = self._kline_db[client_conf["kline_store"]["collection"]]
        self._kline_store.create_index("symbol", unique=False)
        self._kline_store.create_index("st_timestamp", unique=False)
        self._kline_store.create_index("ed_timestamp", unique=False)

    def _validate_config(self, conf: Optional[Dict[str, str]] = None) -> bool:
        valid = False
        try:
            jsonschema.validate(instance=conf, schema=self.DB_CONFIG_SCHEMA)
            valid = True
        except jsonschema.ValidationError as e:
            _g_logger.error("Invalid database config, err:{}".format(e))
            valid = False
        return valid

    async def is_connected(self):
        try:
            result = await self._kline_db.command("ping")
            _g_logger.debug(result)
        except perrors.ServerSelectionTimeoutError:
            raise MongoClientSetupException("Please check connectivity with mongo server.")

    async def insert_kline(self, sym: Optional[str] = None, interval: Optional[str] = "1m", kline: Optional[Dict[str, Any]] = None) -> bool:
        done = False
        try:
            await self._kline_store.insert_one(document=kline)
            done = True
            _g_logger.debug("Inseted one k-line<symbol:{}, interval:{}>".format(sym, interval))
        except perrors.NetworkTimeout:
            _g_logger.error("Timeout to inset one k-line")
        except Exception as e:
            _g_logger.error("Failed to inset one k-line, err:{}".format(e))
        finally:
            return done

    def close(self):
        self._client.close()
