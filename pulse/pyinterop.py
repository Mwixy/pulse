from __future__ import annotations

import builtins
import importlib
from types import ModuleType
from typing import Any


class _PyModuleProxy:
    def __init__(self, module: ModuleType):
        self._m = module

    def __getattr__(self, name: str) -> Any:
        return getattr(self._m, name)


class _PyRoot:
    """Root object exposed as `py` inside Pulse.

    Allows expressions like:
        py.time.time()
        py.math.sqrt(9)
        py.int(1)
    """

    def __init__(self) -> None:
        self._cache: dict[str, ModuleType] = {}

    def __getattr__(self, name: str) -> Any:
        # Prefer Python builtins if available (int, len, range, etc.)
        if hasattr(builtins, name):
            return getattr(builtins, name)

        if name in self._cache:
            return _PyModuleProxy(self._cache[name])
        try:
            mod = importlib.import_module(name)
        except Exception as e:  # noqa: BLE001
            raise AttributeError(f"cannot import Python module {name!r}") from e
        self._cache[name] = mod
        return _PyModuleProxy(mod)

