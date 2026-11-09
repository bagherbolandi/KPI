# -*- coding: utf-8 -*-
"""KPI calculation engine.

Implements the achievement-percentage logic documented in the original workbook
(راهنما sheet), plus an alternative threshold-band mode. Fully configurable.
"""
from typing import Optional


def achievement(actual: Optional[float], target: float, direction: str) -> Optional[float]:
    """Return achievement ratio (0..1, capped at 1.0) or None if no data.

    direction: 'up'  -> higher is better  (🔺)
               'down'-> lower is better   (🔻)
    Mirrors the workbook formula, incl. zero and negative targets.
    """
    if actual is None:
        return None
    a = float(actual)
    t = float(target)

    if direction == "up":
        if t > 0:
            r = a / t
        elif t < 0:
            r = 1 + (a - t) / abs(t)
        else:  # t == 0
            r = 1.0 if a >= 0 else 0.0
    else:  # down (lower is better)
        if t > 0:
            r = t / a if a > 0 else 1.0
        elif t < 0:
            r = 1 + (t - a) / abs(t)
        else:  # t == 0
            r = 1.0 if a <= 0 else 0.0

    # clamp to [0, 1]
    if r < 0:
        r = 0.0
    if r > 1:
        r = 1.0
    return round(r, 4)


def status_from_achievement(ach: Optional[float], th_green: float, th_yellow: float) -> Optional[str]:
    if ach is None:
        return None
    if ach >= th_green:
        return "green"
    if ach >= th_yellow:
        return "yellow"
    return "red"


def status_band(actual: Optional[float], target: float, warning: float,
                critical: float, direction: str) -> Optional[str]:
    """Alternative: classify directly by numeric bands (target/warning/critical)."""
    if actual is None:
        return None
    a = float(actual)
    if direction == "up":
        if a >= target:
            return "green"
        if a >= warning:
            return "yellow"
        return "red"
    else:  # down
        if a <= target:
            return "green"
        if a <= warning:
            return "yellow"
        return "red"


def evaluate(kpi, actual: Optional[float], th_green: float, th_yellow: float):
    """Compute (achievement, status) for a KPI given an actual value.

    kpi must expose: .target, .warning, .critical, .direction, .calc_mode,
    .th_green (nullable override), .th_yellow (nullable override).
    """
    tg = kpi.th_green if getattr(kpi, "th_green", None) is not None else th_green
    ty = kpi.th_yellow if getattr(kpi, "th_yellow", None) is not None else th_yellow
    ach = achievement(actual, kpi.target, kpi.direction)
    if getattr(kpi, "calc_mode", "achievement") == "band":
        st = status_band(actual, kpi.target, kpi.warning, kpi.critical, kpi.direction)
    else:
        st = status_from_achievement(ach, tg, ty)
    return ach, st
