from __future__ import annotations


class PulseError(Exception):
    pass


class PulseSyntaxError(PulseError):
    def __init__(self, message: str, *, filename: str, line: int, col: int):
        super().__init__(f"{filename}:{line}:{col}: SyntaxError: {message}")


class PulseRuntimeError(PulseError):
    def __init__(self, message: str, *, filename: str, line: int):
        super().__init__(f"{filename}:{line}: RuntimeError: {message}")

