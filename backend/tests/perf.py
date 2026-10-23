"""Shared helper for timing tests.

AGENTS.md section 6 sets the performance budgets. Shared CI machines are slower and noisier than a
developer laptop, so CI sets PERF_BUDGET_FACTOR (e.g. 3) to scale every budget; locally it is 1.
"""

import os


def budget(limit: float) -> float:
    """Return ``limit`` scaled by the PERF_BUDGET_FACTOR environment variable (default 1)."""
    return limit * float(os.environ.get("PERF_BUDGET_FACTOR", "1"))
