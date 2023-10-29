# -*- coding: utf-8 -*-
'''
Function decorator for rate limiting.

This module provides a function decorator that can be used to wrap a function
such that it will raise an exception if the number of calls to that function
exceeds a maximum within a specified time window.
'''
from internal.ratelimiter.decorators import RateLimitDecorator, sleep_and_retry
from internal.ratelimiter.exception import RateLimitException

limits = RateLimitDecorator
sleep_and_retry = sleep_and_retry
RateLimitException = RateLimitException

__all__ = [
    "limits",
    "sleep_and_retry"
    "RateLimitException",
]
