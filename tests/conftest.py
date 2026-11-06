"""让测试能 import worker 模块与 dr-plan-generator 顶层的 draft_runbook。

从 graph-dependency-platform 拆出时只保留 DR 编排相关的 sys.path —— 原仓库的
conftest 还会注入 rca/、chaos/code/，这里都没有。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "dr-plan-generator"))


# ── 通过数下限 ────────────────────────────────────────────────────────────────
# 全部 skip 的运行在 CI 上是绿的。CI 设 DR_MIN_PASSED，通过数低于它就判失败。
# 在 logreport 里自己数，不依赖 terminal_summary 与 sessionfinish 的先后
# （原仓库 2026-09-09 实测 sessionfinish 先跑，读到的数恒为 0）。
_MIN_PASSED = int(os.environ.get("DR_MIN_PASSED") or 0)
_passed: list[str] = []


def pytest_runtest_logreport(report):
    if report.when == "call" and report.passed:
        _passed.append(report.nodeid)


def pytest_sessionfinish(session, exitstatus):
    if _MIN_PASSED and len(_passed) < _MIN_PASSED:
        session.exitstatus = 1


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if _MIN_PASSED:
        verdict = "OK" if len(_passed) >= _MIN_PASSED else "低于下限 → 失败"
        terminalreporter.write_line(f"DR_MIN_PASSED={_MIN_PASSED}，实际通过 {len(_passed)}：{verdict}")
