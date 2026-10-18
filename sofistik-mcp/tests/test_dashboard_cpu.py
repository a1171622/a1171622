"""PC-wide CPU % must not read 0 when two reads come close together (psutil first-call artifact)."""
from __future__ import annotations

import pytest

from sofistik_mcp import dashboard

psutil = pytest.importorskip("psutil")


def test_pc_cpu_samples_when_no_value_yet(monkeypatch):
    calls = []

    def fake(interval=None):
        calls.append(interval)
        return 42.0 if interval else 0.0

    monkeypatch.setattr(dashboard.psutil, "cpu_percent", fake)
    mon = dashboard.Collector(lambda: {})
    assert mon.pc_cpu() == 42.0                      # right after start: a short blocking sample, not 0
    assert calls[-1] == dashboard.CPU_MIN_INTERVAL_S
    n = len(calls)
    assert mon.pc_cpu() == 42.0                      # within the interval: the kept value, no new sample
    assert len(calls) == n


def test_pc_cpu_non_blocking_after_interval(monkeypatch):
    seq = iter([0.0, 55.0])
    monkeypatch.setattr(dashboard.psutil, "cpu_percent", lambda interval=None: next(seq))
    clock = [1000.0]
    monkeypatch.setattr(dashboard.time, "time", lambda: clock[0])
    mon = dashboard.Collector(lambda: {})
    clock[0] += 5
    assert mon.pc_cpu() == 55.0                      # long enough since the last call: since-last-call value
    assert mon.resources()["cpu_percent"] == 55.0    # kept within the interval
