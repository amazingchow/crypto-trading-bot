# -*- coding: utf-8 -*-
import time
from types import SimpleNamespace

import aiohttp
from aiohttp.tracing import (
    TraceConnectionCreateEndParams,
    TraceConnectionCreateStartParams,
    TraceConnectionReuseconnParams,
    TraceRequestEndParams,
    TraceRequestStartParams,
)
from loguru import logger as loguru_logger


async def on_request_start(
    session: aiohttp.ClientSession,
    trace_config_ctx: SimpleNamespace,
    params: TraceRequestStartParams
):
    loguru_logger.trace(f"{params.method} {params.url} HTTP/1.1 >>> on on_request_start state.")
    trace_config_ctx.start = time.monotonic()


async def on_request_end(
    session: aiohttp.ClientSession,
    trace_config_ctx: SimpleNamespace,
    params: TraceRequestEndParams
):
    trace_config_ctx.end = time.monotonic()
    loguru_logger.trace(f"{params.method} {params.url} HTTP/1.1 >>> on on_request_end state, used time: {trace_config_ctx.end - trace_config_ctx.start} sec.")


async def on_connection_create_start(
    session: aiohttp.ClientSession,
    trace_config_ctx: SimpleNamespace,
    params: TraceConnectionCreateStartParams
):
    loguru_logger.trace("HTTP/1.1 >>> on on_connection_create_start state.")
    trace_config_ctx.start = time.monotonic()


async def on_connection_create_end(
    session: aiohttp.ClientSession,
    trace_config_ctx: SimpleNamespace,
    params: TraceConnectionCreateEndParams
):
    trace_config_ctx.end = time.monotonic()
    loguru_logger.trace(f"HTTP/1.1 >>> on on_connection_create_end state, used time: {trace_config_ctx.end - trace_config_ctx.start} sec.")


async def on_connection_reuseconn(
    session: aiohttp.ClientSession,
    trace_config_ctx: SimpleNamespace,
    params: TraceConnectionReuseconnParams
):
    loguru_logger.trace("HTTP/1.1 >>> on on_connection_reuseconn state.")


http_trace_config = aiohttp.TraceConfig()
http_trace_config.on_request_start.append(on_request_start)
http_trace_config.on_request_end.append(on_request_end)
http_trace_config.on_connection_create_start.append(on_connection_create_start)
http_trace_config.on_connection_create_end.append(on_connection_create_end)
http_trace_config.on_connection_reuseconn.append(on_connection_reuseconn)
