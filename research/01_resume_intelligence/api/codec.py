"""Rebuild pipeline objects from the JSON those objects already emit.

Unknown keys are ignored. A value of the wrong shape raises
``AnalysisDecodeError`` with no stored text attached.
"""
from __future__ import annotations

import types
from dataclasses import fields, is_dataclass
from typing import Any, Union, get_args, get_origin, get_type_hints


class AnalysisDecodeError(Exception):
    """The JSON is not a pipeline analysis object."""


def from_dict(cls, data: Any):
    """Return ``cls`` filled from a ``to_dict()`` object."""
    try:
        return _from_dict(cls, data)
    except AnalysisDecodeError:
        raise
    except (TypeError, ValueError, KeyError) as exc:
        raise AnalysisDecodeError(cls.__name__) from exc


def _from_dict(cls, data: Any):
    if not isinstance(data, dict):
        raise AnalysisDecodeError(getattr(cls, "__name__", "value"))
    hints = get_type_hints(cls)
    kwargs = {}
    for item in fields(cls):
        if item.name not in data:
            continue
        kwargs[item.name] = _convert(hints.get(item.name, Any), data[item.name])
    return cls(**kwargs)


def _convert(annotation, value):
    if annotation is Any:
        return value
    origin = get_origin(annotation)
    if origin is None and isinstance(annotation, type) and is_dataclass(annotation):
        if value is None:
            return None
        return _from_dict(annotation, value)
    if origin is list:
        if value is None:
            return []
        if not isinstance(value, list):
            raise TypeError("expected a list")
        inner = get_args(annotation)[0]
        return [_convert(inner, item) for item in value]
    if origin is dict:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise TypeError("expected an object")
        return dict(value)
    if origin is type(None) or annotation is type(None):
        return None
    union_args = _union_args(annotation)
    if union_args is not None:
        if value is None:
            return None
        choices = [arg for arg in union_args if arg is not type(None)]
        if len(choices) == 1:
            return _convert(choices[0], value)
        last_error = None
        for choice in choices:
            try:
                return _convert(choice, value)
            except (TypeError, ValueError, AnalysisDecodeError) as exc:
                last_error = exc
        raise TypeError("value does not match") from last_error
    if annotation is float and isinstance(value, int) and not isinstance(value, bool):
        return float(value)
    if annotation is int and isinstance(value, float) and value.is_integer():
        return int(value)
    if annotation is bool:
        if not isinstance(value, bool):
            raise TypeError("expected a boolean")
        return value
    if annotation in (str, int, float):
        if not isinstance(value, annotation) or isinstance(value, bool):
            raise TypeError("wrong type")
        return value
    return value


def _union_args(annotation):
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        return get_args(annotation)
    return None
