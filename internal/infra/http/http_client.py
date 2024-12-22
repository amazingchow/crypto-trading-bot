# -*- coding: utf-8 -*-
import asyncio
from typing import Any, Dict, Optional

import httpx
from loguru import logger as loguru_logger


class HttpClient:
    _instance: Optional['HttpClient'] = None
    _client: Optional[httpx.Client] = None
    _aclient: Optional[httpx.AsyncClient] = None

    @staticmethod
    def get_instance() -> 'HttpClient':
        if not HttpClient._instance:
            HttpClient._instance = HttpClient()
        return HttpClient._instance

    def __init__(self):
        self._client = httpx.Client(
            verify=False,
            timeout=httpx.Timeout(60.0, connect=5.0),
            limits=httpx.Limits(max_connections=32, max_keepalive_connections=16, keepalive_expiry=600),
        )
        self._aclient = httpx.AsyncClient(
            verify=False,
            timeout=httpx.Timeout(60.0, connect=5.0),
            limits=httpx.Limits(max_connections=32, max_keepalive_connections=16, keepalive_expiry=600),
        )

    def get_client(self) -> Optional[httpx.Client]:
        return self._client
    
    def get_aclient(self) -> Optional[httpx.AsyncClient]:
        return self._aclient

    @staticmethod
    def log_event(event_name: str, info: Dict[str, Any]) -> None:
        loguru_logger.trace(f"HTTPX >>> {event_name} state, info: {info}")

    @staticmethod
    async def alog_event(event_name: str, info: Dict[str, Any]) -> None:
        loguru_logger.trace(f"HTTPX >>> {event_name} state, info: {info}")
        await asyncio.sleep(0)

    async def close(self):
        if self._client:
            self._client.close()
            await asyncio.sleep(0)
        if self._aclient:
            await self._aclient.aclose()
