# -*- coding: utf-8 -*-
import asyncio
import hashlib
import random
import sys
import time

from functools import wraps
from loguru import logger as loguru_logger


def timeit(func):

    async def process(func, *args, **kwargs):
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    @wraps(func)
    async def wrapper(*args, **kwargs):
        st = time.time()
        result = await process(func, *args, **kwargs)
        ed = time.time()
        loguru_logger.debug(f"{func.__name__} took time: {ed - st:.3f} secs")
        return result

    return wrapper


def async_wrapper(func):
    async def inner(*args, **kwargs):
        func(*args, **kwargs)
    return inner


def new_request_id() -> str:
    return hashlib.md5("{}_{}".format(time.time(), random.randint(0, 10000)).encode()).hexdigest()


ALL_DIGIT_NUMS_AND_LETTERS = [str(i) for i in range(0, 10)] + \
    [str(chr(i)) for i in range(ord('a'), ord('z') + 1)] + \
    [str(chr(i)) for i in range(ord('A'), ord('Z') + 1)]
ALL_DIGIT_NUMS_AND_LETTERS_TOTAL = len(ALL_DIGIT_NUMS_AND_LETTERS)


def gen_n_digit_nums_and_letters(n: int) -> str:
    seed = random.randrange(sys.maxsize)
    random.seed(seed)
    for i in range(len(ALL_DIGIT_NUMS_AND_LETTERS) - 1, 0, -1):
        j = random.randrange(i + 1)
        ALL_DIGIT_NUMS_AND_LETTERS[i], ALL_DIGIT_NUMS_AND_LETTERS[j] = ALL_DIGIT_NUMS_AND_LETTERS[j], ALL_DIGIT_NUMS_AND_LETTERS[i]
    nums_and_letters = [ALL_DIGIT_NUMS_AND_LETTERS[random.randrange(ALL_DIGIT_NUMS_AND_LETTERS_TOTAL)] for _ in range(n)]
    return "".join(nums_and_letters)
