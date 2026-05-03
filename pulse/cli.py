from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .runtime import PulseRuntime


def run_source(source: str, *, filename: str = "<memory>") -> None:
    rt = PulseRuntime()
    rt.run(source, filename=filename)


def run_file(path: str | Path) -> None:
    p = Path(path)
    source = p.read_text(encoding="utf-8")
    run_source(source, filename=str(p))


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] != "run":
        argv = ["run", *argv]

    parser = argparse.ArgumentParser(prog="pulse", description="Pulse (.pulse) interpreter")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Run a .pulse file")
    run_p.add_argument("file", help="Path to .pulse file")

    ns = parser.parse_args(argv)

    from .errors import PulseError
    try:
        run_file(ns.file)
    except PulseError as e:
        print(f"\n❌ Pulse Error:\n  -> {e}")
        return 1
    return 0

