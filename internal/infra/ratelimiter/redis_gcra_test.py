# -*- coding: utf-8 -*-
import asyncio

import pytest
import pytest_asyncio
import redis
import redis.asyncio as aio_redis

from internal.infra.ratelimiter.redis_gcra import Limit, RateLimiter, Result


class RateLimiterFixture:

    def __init__(self):
        pass

    def setup(self):
        self.redis_conn = redis.Redis(
            host="localhost",
            port=6379,
            db=0,
            password="sOmE_sEcUrE_pAsS",
        )
        self.limiter = RateLimiter.get_instance(
            redis_conn=self.redis_conn, async_mode=False, key_prefix="unittest_rate:"
        )

    def teardown(self):
        self.redis_conn.close()


class AIORateLimiterFixture:

    def __init__(self):
        pass

    async def setup(self):
        self.aio_redis_conn = aio_redis.Redis(
            host="localhost",
            port=6379,
            db=0,
            password="sOmE_sEcUrE_pAsS",
        )
        self.aio_limiter = RateLimiter.get_instance(
            redis_conn=self.aio_redis_conn, async_mode=True, key_prefix="unittest_rate:"
        )
        await asyncio.sleep(0)

    async def teardown(self):
        await self.aio_redis_conn.aclose()


@pytest.fixture
def my_fixture():
    fixture = RateLimiterFixture()
    fixture.setup()
    yield fixture
    fixture.teardown()


@pytest_asyncio.fixture
async def my_aio_fixture():
    fixture = AIORateLimiterFixture()
    await fixture.setup()
    yield fixture
    await fixture.teardown()


def test_allow(my_fixture):
    limit = Limit(rate=10, burst=10, period_in_sec=60)
    key = "test_allow"
    result, error = my_fixture.limiter.allow(key, limit)
    assert error is None
    assert isinstance(result, Result)
    assert result.allowed == 1
    assert result.remaining == 9


def test_allow_over_limit(my_fixture):
    limit = Limit(rate=1, burst=1, period_in_sec=60)
    key = "test_allow_over_limit"
    # First request should be allowed
    result, error = my_fixture.limiter.allow(key, limit)
    assert error is None
    assert isinstance(result, Result)
    print(result)
    assert result.allowed == 1
    assert result.remaining == 0
    assert result.retry_after_in_sec == -1.0

    # Second request should be denied
    result, error = my_fixture.limiter.allow(key, limit)
    assert error is None
    assert isinstance(result, Result)
    assert result.allowed == 0
    assert result.remaining == 0
    assert result.retry_after_in_sec > 0


def test_allow_n(my_fixture):
    limit = Limit(rate=10, burst=10, period_in_sec=60)
    key = "test_allow_n"
    result, error = my_fixture.limiter.allow_n(key, limit, 5)
    assert error is None
    assert isinstance(result, Result)
    assert result.allowed == 5
    assert result.remaining == 5
    assert result.retry_after_in_sec == -1.0


def test_allow_n_over_limit(my_fixture):
    limit = Limit(rate=10, burst=10, period_in_sec=60)
    key = "test_allow_n_over_limit"
    # First request should be allowed
    result, error = my_fixture.limiter.allow_n(key, limit, 8)
    assert error is None
    assert isinstance(result, Result)
    assert result.allowed == 8
    assert result.remaining == 2
    assert result.retry_after_in_sec == -1.0

    # Second request should be denied
    result, error = my_fixture.limiter.allow_n(key, limit, 5)
    assert error is None
    assert isinstance(result, Result)
    assert result.allowed == 0
    assert result.remaining == 0
    assert result.retry_after_in_sec > 0


def test_allow_at_most(my_fixture):
    limit = Limit(rate=10, burst=10, period_in_sec=60)
    key = "test_allow_at_most"
    result, error = my_fixture.limiter.allow_at_most(key, limit, 5)
    assert error is None
    assert isinstance(result, Result)
    assert result.allowed == 5
    assert result.remaining == 5
    assert result.retry_after_in_sec == -1.0


def test_allow_at_most_over_limit(my_fixture):
    limit = Limit(rate=10, burst=10, period_in_sec=60)
    key = "test_allow_at_most_over_limit"
    # First request should be allowed
    result, error = my_fixture.limiter.allow_at_most(key, limit, 8)
    assert error is None
    assert isinstance(result, Result)
    assert result.allowed == 8
    assert result.remaining == 2
    assert result.retry_after_in_sec == -1.0

    # Second request should be denied
    result, error = my_fixture.limiter.allow_at_most(key, limit, 5)
    assert error is None
    assert isinstance(result, Result)
    assert result.allowed == 2
    assert result.remaining == 0
    assert result.retry_after_in_sec == -1.0


def test_reset(my_fixture):
    key = "test_allow"
    assert my_fixture.limiter.reset(key) is True
    key = "test_allow_over_limit"
    assert my_fixture.limiter.reset(key) is True
    key = "test_allow_n"
    assert my_fixture.limiter.reset(key) is True
    key = "test_allow_n_over_limit"
    assert my_fixture.limiter.reset(key) is True
    key = "test_allow_at_most"
    assert my_fixture.limiter.reset(key) is True
    key = "test_allow_at_most_over_limit"
    assert my_fixture.limiter.reset(key) is True
