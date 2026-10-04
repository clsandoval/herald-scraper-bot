"""Compatibility entrypoint; maintained code lives in herald.board."""
import pathlib
import runpy
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
if __name__ == "__main__":
    runpy.run_module("herald.board", run_name="__main__")
else:
    from herald import board as _implementation
    sys.modules[__name__] = _implementation
