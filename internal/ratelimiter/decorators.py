# -*- coding: utf-8 -*-
import asyncio
import math
import sys
import time

from functools import wraps
from internal.ratelimiter.exception import RateLimitException
from internal.utils.helper import now
from typing import Callable


class RateLimitDecorator(object):

    def __init__(self, calls: int = 15, period: int = 900, clock: Callable = now(), raise_on_limit: bool = True):
        """By default the Twitter rate limiting window is respected (15 calls every 15 minutes)."""
        self._clamped_calls = max(1, min(sys.maxsize, math.floor(calls)))
        self._period = period
        self._clock = clock
        self._raise_on_limit = raise_on_limit

        # Initialise the decorator state.
        self._last_reset = clock()
        self._num_calls = 0

        # Add coroutine safety.
        self._lock = asyncio.Lock()

    async def __call__(self, func):

        @wraps(func)
        def wrapper(*args, **kargs):
            """
            Extend the behaviour of the decorated function, forwarding function
            invocations previously called no sooner than a specified period of
            time. The decorator will raise an exception if the function cannot
            be called so the caller may implement a retry strategy such as an
            exponential backoff.
            """
            async with self._lock:
                period_remaining = self.__period_remaining()
                # If the time window has elapsed then reset it.
                if period_remaining <= 0:
                    self._num_calls = 0
                    self._last_reset = self._clock()
                # Increase the number of attempts to call the function.
                self._num_calls += 1
                # If the number of attempts to call the function exceeds the maximum then raise an exception.
                if self._num_calls > self._clamped_calls:
                    if self._raise_on_limit:
                        raise RateLimitException("too many calls", period_remaining)
                    return
            return func(*args, **kargs)
        
        return wrapper

    def __period_remaining(self) -> float:
        """Return the period remaining for the current rate limit window."""
        elapsed = self._clock() - self._last_reset
        return self._period - elapsed


def sleep_and_retry(func):

    @wraps(func)
    async def wrapper(*args, **kwargs):
        while 1:
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            except RateLimitException as exception:
                if asyncio.iscoroutinefunction(func):
                    await asyncio.sleep(exception.period_remaining)
                else:
                    time.sleep(exception.period_remaining)
    
    return wrapper
