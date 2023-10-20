# -*- coding: utf-8 -*-
import ujson as json

from typing import Any, \
    Dict

_GLOBAL_CONFIG = None


def set_config(fn: str):
    global _GLOBAL_CONFIG
    _ensure_var_is_not_initialized(_GLOBAL_CONFIG, "config")
    fr = open(fn, "r")
    _GLOBAL_CONFIG = json.load(fr)
    fr.close()


def get_config() -> Dict[str, Any]:
    _ensure_var_is_initialized(_GLOBAL_CONFIG, 'config')
    return _GLOBAL_CONFIG


def _ensure_var_is_initialized(var, name):
    """Make sure the input variable is not None."""
    assert var is not None, '{} is not initialized.'.format(name)


def _ensure_var_is_not_initialized(var, name):
    """Make sure the input variable is not None."""
    assert var is None, '{} is already initialized.'.format(name)
