# -*- coding: utf-8 -*-
from dataclasses import dataclass
from typing import Optional, Tuple, Union

import redis
import redis.asyncio as aio_redis
import redis.exceptions as redis_exceptions
from loguru import logger as loguru_logger

from .redis_gcra_lua import ALLOW_AT_MOST_LUA_SCRIPT, ALLOW_N_LUA_SCRIPT


@dataclass
class Limit:
    rate: int = 0
    burst: int = 0
    period_in_sec: int = 0

    def __str__(self) -> str:
        return f"{self.rate} req/{self.period_in_sec}s (burst {self.burst})"
    
    def is_zero(self) -> bool:
        return self.rate == 0 and self.burst == 0 and self.period_in_sec == 0


def per_second(rate: int) -> Limit:
    return Limit(rate=rate, burst=rate, period_in_sec=1)


def per_minute(rate: int) -> Limit:
    return Limit(rate=rate, burst=rate, period_in_sec=60)


def per_hour(rate: int) -> Limit:
    return Limit(rate=rate, burst=rate, period_in_sec=3600)


@dataclass
class Result:
    """
    -   'allowed' is the number of events that may happen at time now.
    -   'remaining' is the maximum number of requests that could be
        permitted instantaneously for this key given the current
        state. For example, if a rate limiter allows 10 requests per
        second and has already received 6 requests for this key this
        second, 'remaining' would be 4.
    -   'retry_after_in_sec' is the time until the next request will be permitted.
        It should be -1 unless the rate limit has been exceeded.
    -   'reset_after_in_sec' is the time until the RateLimiter returns to its
        initial state for a given key. For example, if a rate limiter
        manages requests per second and received one request 200ms ago,
        Reset would return 800ms. You can also think of this as the time
        until Limit and 'remaining' will be equal.
    """
    allowed: int
    remaining: int
    retry_after_in_sec: int
    reset_after_in_sec: int

    def __str__(self) -> str:
        return f"Result(allowed={self.allowed}, remaining={self.remaining}, retry_after_in_sec={self.retry_after_in_sec}, reset_after_in_sec={self.reset_after_in_sec})"


class RateLimiter:
    _instance: Optional["RateLimiter"] = None

    @staticmethod
    def get_instance(
        *,
        redis_conn: Union[redis.Redis, aio_redis.Redis],
        async_mode: bool = True,
        key_prefix: str = "rate:"
    ) -> "RateLimiter":
        if RateLimiter._instance is None:
            RateLimiter._instance = RateLimiter(
                redis_conn=redis_conn,
                async_mode=async_mode,
                key_prefix=key_prefix
            )
        return RateLimiter._instance

    def __init__(
        self,
        *,
        redis_conn: Union[redis.Redis, aio_redis.Redis],
        async_mode: bool = True,
        key_prefix: str = "rate:"
    ):
        self._rdb: Union[redis.Redis, aio_redis.Redis] = redis_conn
        self.async_mode = async_mode
        self._redis_prefix = key_prefix

    async def aallow(
        self,
        key: str,
        limit: Limit
    ) -> Tuple[Optional[Result], Optional[redis_exceptions.RedisError]]:
        """
        allow is a shortcut for allow_n(key, limit, 1).
        """
        return await self.aallow_n(key, limit, 1)

    def allow(
        self,
        key: str,
        limit: Limit
    ) -> Tuple[Optional[Result], Optional[redis_exceptions.RedisError]]:
        """
        allow is a shortcut for allow_n(key, limit, 1).
        """
        return self.allow_n(key, limit, 1)

    async def aallow_n(
        self,
        key: str,
        limit: Limit,
        n: int
    ) -> Tuple[Optional[Result], Optional[redis_exceptions.RedisError]]:
        """
        Report whether n events may happen at time now.
        """
        result: Optional[Result] = None
        redis_error: Optional[redis_exceptions.RedisError] = None
        try:
            values = await self._rdb.execute_command(
                "EVAL",
                ALLOW_N_LUA_SCRIPT,
                1,
                self._redis_prefix + key,
                limit.burst,
                limit.rate,
                limit.period_in_sec,
                n
            )
            result = Result(
                allowed=values[0],
                remaining=values[1],
                retry_after_in_sec=float(values[2].decode("utf-8")),
                reset_after_in_sec=float(values[3].decode("utf-8"))
            )
        except redis_exceptions.RedisError as e:
            loguru_logger.error(f"RedisError: {e}")
            redis_error = e
        return (result, redis_error)

    def allow_n(
        self,
        key: str,
        limit: Limit,
        n: int
    ) -> Tuple[Optional[Result], Optional[redis_exceptions.RedisError]]:
        """
        Report whether n events may happen at time now.
        """
        result: Optional[Result] = None
        redis_error: Optional[redis_exceptions.RedisError] = None
        try:
            values = self._rdb.execute_command(
                "EVAL",
                ALLOW_N_LUA_SCRIPT,
                1,
                self._redis_prefix + key,
                limit.burst,
                limit.rate,
                limit.period_in_sec,
                n
            )
            result = Result(
                allowed=values[0],
                remaining=values[1],
                retry_after_in_sec=float(values[2].decode("utf-8")),
                reset_after_in_sec=float(values[3].decode("utf-8"))
            )
        except redis_exceptions.RedisError as e:
            loguru_logger.error(f"RedisError: {e}")
            redis_error = e
        return (result, redis_error)

    async def aallow_at_most(
        self,
        key: str,
        limit: Limit,
        n: int
    ) -> Tuple[Optional[Result], Optional[redis_exceptions.RedisError]]:
        """
        Report whether at most n events may happen at time now.
        It returns number of allowed events that is less than or equal to n.
        """
        result = None
        redis_error = None
        try:
            values = await self._rdb.execute_command(
                "EVAL",
                ALLOW_AT_MOST_LUA_SCRIPT,
                1,
                self._redis_prefix + key,
                limit.burst,
                limit.rate,
                limit.period_in_sec,
                n
            )
            result = Result(
                allowed=values[0],
                remaining=values[1],
                retry_after_in_sec=float(values[2].decode("utf-8")),
                reset_after_in_sec=float(values[3].decode("utf-8"))
            )
        except redis_exceptions.RedisError as e:
            loguru_logger.error(f"RedisError: {e}")
            redis_error = e
        return (result, redis_error)

    def allow_at_most(
        self,
        key: str,
        limit: Limit,
        n: int
    ) -> Tuple[Optional[Result], Optional[redis_exceptions.RedisError]]:
        """
        Report whether at most n events may happen at time now.
        It returns number of allowed events that is less than or equal to n.
        """
        result = None
        redis_error = None
        try:
            values = self._rdb.execute_command(
                "EVAL",
                ALLOW_AT_MOST_LUA_SCRIPT,
                1,
                self._redis_prefix + key,
                limit.burst,
                limit.rate,
                limit.period_in_sec,
                n
            )
            result = Result(
                allowed=values[0],
                remaining=values[1],
                retry_after_in_sec=float(values[2].decode("utf-8")),
                reset_after_in_sec=float(values[3].decode("utf-8"))
            )
        except redis_exceptions.RedisError as e:
            loguru_logger.error(f"RedisError: {e}")
            redis_error = e
        finally:
            return (result, redis_error)

    async def areset(self, key) -> bool:
        """
        Reset the rate limiter for the given key.
        """
        return await self._rdb.execute_command("DEL", self._redis_prefix + key) == 1

    def reset(self, key) -> bool:
        """
        Reset the rate limiter for the given key.
        """
        return self._rdb.execute_command("DEL", self._redis_prefix + key) == 1
