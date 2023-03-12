# -*- coding: utf-8 -*-
import ujson as json

_GlobalConfig = {}


def load_config_file(fn: str):
    global _GlobalConfig
    fr = open(fn, "r")
    _GlobalConfig = json.load(fr)
    fr.close()


def get_config() -> dict:
    return _GlobalConfig
