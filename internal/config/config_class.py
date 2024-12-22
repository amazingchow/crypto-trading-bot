# -*- coding: utf-8 -*-
from typing import Any, Dict, Optional

import jsonschema
import ujson as json

# from dotenv import dotenv_values


class GlobalConfig:

    # More complex schema can be found here: https://python-jsonschema-objects.readthedocs.io/en/latest/Introduction.html

    CONFIG_SCHEMA = {
        "title": "Global Config Schema",
        "type": "object",
        "properties": {
            "env": {
                "description": "Environment",
                "type": "string",
                "enum": ["dev", "test", "beta", "grey", "prod"]
            },
            "mongo.endpoint": {
                "description": "MongoDB Endpoint",
                "type": "string"
            },
            "mongo.username": {
                "description": "MongoDB Username",
                "type": "string"
            },
            "mongo.password": {
                "description": "MongoDB Password",
                "type": "string"
            },
            "mongo.auth_mechanism": {
                "description": "MongoDB Auth Mechanism",
                "type": "string"
            },
            "mongo.database": {
                "description": "MongoDB Database",
                "type": "string"
            },
            "mongo.collection": {
                "description": "MongoDB Collection",
                "type": "string"
            },
            "mongo.indexes": {
                "description": "MongoDB Indexes",
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "keys": {
                            "description": "Keys",
                            "type": "string"
                        },
                        "unique": {
                            "description": "Unique",
                            "type": "boolean"
                        }
                    },
                    "required": ["keys", "unique"]
                }
            },
            "redis_cache.endpoint": {
                "description": "Redis Cache Endpoint",
                "type": "string"
            },
            "redis_cache.password": {
                "description": "Redis Cache Password",
                "type": "string"
            },
            "redis_cache.db": {
                "description": "Redis Cache DB",
                "type": "integer"
            },
            "trace.endpoint": {
                "description": "Trace Endpoint",
                "type": "string"
            }
        },
        "required": [
            "env",
            "mongo.endpoint",
            "mongo.username",
            "mongo.password",
            "mongo.auth_mechanism",
            "mongo.database",
            "mongo.collection",
            "mongo.indexes",
            "redis_cache.endpoint",
            "redis_cache.password",
            "redis_cache.db",
            "trace.endpoint"
        ]
    }
    _instance = None

    @staticmethod
    def get_instance() -> 'GlobalConfig':
        if not GlobalConfig._instance:
            GlobalConfig._instance = GlobalConfig()
        return GlobalConfig._instance

    def __init__(self):
        self._config: Optional[Dict[str, Any]] = None

    def load_config(self, file_path: str) -> None:
        with open(file_path, 'r') as file:
            self._config = json.load(file)
        jsonschema.validate(instance=self._config, schema=self.CONFIG_SCHEMA)

    def get_value(self, key: str) -> Any:
        if self._config:
            return self._config.get(key)
        return None
