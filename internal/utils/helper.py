# -*- coding: utf-8 -*-
import hashlib
import random
import sys
import time


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
