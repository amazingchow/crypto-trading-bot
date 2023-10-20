# -*- coding: utf-8 -*-
import sys

from loguru import logger as loguru_logger
from os import environ


def _env(key, type_, default=None):
    if key not in environ:
        return default

    val = environ[key]

    if type_ == str:
        return val
    elif type_ == bool:
        if val.lower() in ["1", "true", "yes", "y", "ok", "on"]:
            return True
        if val.lower() in ["0", "false", "no", "n", "nok", "off"]:
            return False
        raise ValueError(
            "Invalid environment variable '%s' (expected a boolean): '%s'" % (key, val)
        )
    elif type_ == int:
        try:
            return int(val)
        except ValueError:
            raise ValueError(
                "Invalid environment variable '%s' (expected an integer): '%s'" % (key, val)
            ) from None


def init_global_logger():
    loguru_logger.configure(extra={"ctx": ""})  # Default values
    loguru_logger.remove()
    loguru_logger.add(
        sink=sys.stderr,
        level=_env("LOGURU_LEVEL", str, "DEBUG"),
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
               "<level>{level: <8}</level> | "
               "<red>ctx={extra[ctx]}</red> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "- <level>{message}</level>",
        colorize=_env("LOGURU_COLORIZE", bool, False),
        serialize=_env("LOGURU_SERIALIZE", bool, False),
        backtrace=_env("LOGURU_BACKTRACE", bool, True),
        diagnose=_env("LOGURU_DIAGNOSE", bool, True),
        enqueue=_env("LOGURU_ENQUEUE", bool, False),
        catch=_env("LOGURU_CATCH", bool, True),
    )
