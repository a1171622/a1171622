#!/usr/bin/env python3
"""Plain-assert test runner (pytest is not required; the test_* functions also run under pytest).

usage: python3 -I tests/run_tests.py [name-substring ...]
"""
import importlib.util
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _util  # noqa: E402


def main():
    sel = sys.argv[1:]
    n_ok = n_fail = n_skip = 0
    for fn in sorted(os.listdir(HERE)):
        if not (fn.startswith("test_") and fn.endswith(".py")):
            continue
        spec = importlib.util.spec_from_file_location(fn[:-3], os.path.join(HERE, fn))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for name in sorted(n for n in dir(mod) if n.startswith("test_")):
            full = f"{fn[:-3]}.{name}"
            if sel and not any(s in full for s in sel):
                continue
            t = time.time()
            try:
                getattr(mod, name)()
                n_ok += 1
                print(f"ok    {full} ({time.time() - t:.1f}s)")
            except _util.Skip as e:
                n_skip += 1
                print(f"skip  {full}: {e}")
            except Exception:  # noqa: BLE001
                n_fail += 1
                print(f"FAIL  {full}\n{traceback.format_exc()}")
    print(f"\n{n_ok} passed, {n_fail} failed, {n_skip} skipped")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
