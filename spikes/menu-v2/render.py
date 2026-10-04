"""Compatibility entrypoint; maintained code lives in herald.render."""
import pathlib
import runpy
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
if __name__ == "__main__":
    runpy.run_module("herald.render", run_name="__main__")
else:
    from herald import render as _implementation
    sys.modules[__name__] = _implementation
