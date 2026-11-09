# -*- coding: utf-8 -*-
"""Statistical analysis engine — port of the offline KPI system's analysis module.

Provides: Welford moments, Student-t p-values (regularized incomplete beta),
Welch / paired t-tests between year groups, Holm family-wise correction,
least-squares slope trend test with two-sided p-value and confidence interval,
plus the Persian decision texts used by the offline UI.
"""
import math
from typing import Optional


# ----------------------------------------------------------------- helpers
def moments(values):
    """Welford: returns (n, mean, sample_variance)."""
    n = 0
    mean = 0.0
    m2 = 0.0
    for v in values:
        n += 1
        d = v - mean
        mean += d / n
        m2 += d * (v - mean)
    var = m2 / (n - 1) if n > 1 else None
    return n, (mean if n else None), var


def _log_gamma(x: float) -> float:
    # Lanczos approximation (g=7, n=9)
    g = 7.0
    c = [0.99999999999980993, 676.5203681218851, -1259.1392167224028,
         771.32342877765313, -176.61502916214059, 12.507343278686905,
         -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7]
    if x < 0.5:
        return math.log(math.pi / math.sin(math.pi * x)) - _log_gamma(1.0 - x)
    x -= 1.0
    a = c[0]
    t = x + g + 0.5
    for i in range(1, 9):
        a += c[i] / (x + i)
    return 0.5 * math.log(2 * math.pi) + (x + 0.5) * math.log(t) - t + math.log(a)


def _beta_fraction(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (Numerical Recipes)."""
    MAXIT, EPS, FPMIN = 300, 3.0e-16, 1.0e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < EPS:
            break
    return h


def t_p_value(t: float, df: float) -> float:
    """Two-sided p-value of Student's t with `df` degrees of freedom."""
    if df <= 0 or not math.isfinite(t):
        return float("nan")
    x = df / (df + t * t)
    a = df / 2.0
    b = 0.5
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    bt = math.exp(_log_gamma(a + b) - _log_gamma(a) - _log_gamma(b)
                  + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        p = bt * _beta_fraction(a, b, x) / a
    else:
        p = 1.0 - bt * _beta_fraction(b, a, 1.0 - x) / b
    return max(0.0, min(1.0, p))


def t_critical(alpha: float, df: float) -> float:
    """Two-sided critical t via bisection (mirrors offline analysisCritical)."""
    lo, hi = 0.0, 1.0
    while t_p_value(hi, df) > alpha and hi < 1e8:
        hi *= 2
    for _ in range(80):
        mid = (lo + hi) / 2
        if t_p_value(mid, df) > alpha:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def slope_test(points) -> dict:
    """OLS slope of y on x with two-sided t-test of H0: slope = 0.

    points: list of (x, y). Minimum n = 4 (application rule, not power analysis).
    """
    n = len(points)
    result = {"n": n, "df": max(n - 2, 0), "p": None, "t": None, "slope": None,
              "se": None, "ci": None, "state": "insufficient"}
    if n < 4:
        return result
    mx = sum(p[0] for p in points) / n
    my = sum(p[1] for p in points) / n
    xx = sum((p[0] - mx) ** 2 for p in points)
    xy = sum((p[0] - mx) * (p[1] - my) for p in points)
    if not (xx > 0):
        result["state"] = "degenerate"
        return result
    slope = xy / xx
    sse = sum(((p[1] - my) - slope * (p[0] - mx)) ** 2 for p in points)
    result["slope"] = slope
    se = math.sqrt(sse / (n - 2) / xx) if n > 2 else float("nan")
    scale = max(abs(p[1]) for p in points)
    if not math.isfinite(se) or se <= sys_eps() * max(1.0, scale) * 16:
        result["state"] = "degenerate"
        return result
    result["se"] = se
    result["t"] = slope / se
    result["p"] = t_p_value(result["t"], n - 2)
    if result["p"] is not None and math.isfinite(result["p"]):
        margin = t_critical(0.05, n - 2) * se
        result["ci"] = [slope - margin, slope + margin]
        result["state"] = "ok"
    else:
        result["state"] = "degenerate"
    return result


def sys_eps() -> float:
    # match JS Number.EPSILON (2.220446049250313e-16)
    return 2.220446049250313e-16


def compare_groups(a_vals, b_vals, method: str, alpha: float,
                   a_months=None, b_months=None) -> dict:
    """Welch (independent) or matched-month paired t-test between two years.

    a_vals/b_vals: lists of raw values. For 'paired', a_months/b_months give the
    month index of each value so only common months are paired (delta = B - A).
    """
    av = list(a_vals)
    bv = list(b_vals)
    diffs = []
    if method == "paired":
        bmap = {}
        for i, m in enumerate(b_months if b_months is not None else range(len(bv))):
            bmap[m] = bv[i]
        av2, bv2 = [], []
        for i, m in enumerate(a_months if a_months is not None else range(len(av))):
            if m in bmap:
                av2.append(av[i])
                bv2.append(bmap[m])
                diffs.append(bmap[m] - av[i])
        av, bv = av2, bv2
    na, ma, va = moments(av)
    nb, mb, vb = moments(bv)
    r = {"state": "insufficient", "nA": na, "nB": nb, "meanA": ma, "meanB": mb,
         "delta": (mb - ma) if (na and nb) else None,
         "p": None, "adjusted": None, "t": None, "df": None, "ci": None}
    if na < 3 or nb < 3:
        return r
    if method == "paired":
        nd, md, vd = moments(diffs)
        if nd < 3 or vd is None:
            return r
        r["delta"] = md
        se = math.sqrt(vd / nd)
        r["df"] = nd - 1
    else:
        if va is None or vb is None:
            return r
        va_n = va / na
        vb_n = vb / nb
        se = math.sqrt(va_n + vb_n)
        r["df"] = ((va_n + vb_n) ** 2) / ((va_n ** 2) / (na - 1) + (vb_n ** 2) / (nb - 1))
    scale = max(1.0, abs(ma or 0), abs(mb or 0))
    if (not math.isfinite(se)) or se <= sys_eps() * scale * 16 or not math.isfinite(r["df"]):
        r["state"] = "degenerate"
        return r
    r["t"] = r["delta"] / se
    r["p"] = t_p_value(r["t"], r["df"])
    if r["p"] is None or not math.isfinite(r["p"]):
        r["state"] = "degenerate"
        return r
    margin = t_critical(alpha, r["df"]) * se
    r["ci"] = [r["delta"] - margin, r["delta"] + margin]
    r["state"] = "ok"
    return r


def holm_adjust(rows, total: int) -> None:
    """Holm–Bonferroni step-down on rows with state == 'ok'; sets `adjusted` in place.

    Family size = total number of planned pairs (conservative, offline parity).
    """
    ok = [r for r in rows if r.get("state") == "ok" and r.get("p") is not None]
    ok.sort(key=lambda r: r["p"])
    prev = 0.0
    for i, r in enumerate(ok):
        prev = max(prev, min(1.0, r["p"] * (total - i)))
        r["adjusted"] = prev


def decision_text(row, direction: str, alpha: float) -> str:
    if row["state"] == "insufficient":
        return "داده ناکافی: حداقل ۳ مشاهده در هر سال یا ۳ جفت ماه مشترک"
    if row["state"] != "ok":
        return "واریانس کافی نیست؛ بررسی دستی لازم است"
    adj = row.get("adjusted")
    if adj is None or adj >= alpha:
        return "تفاوت معنادار نیست؛ این نتیجه برابری سال‌ها را اثبات نمی‌کند"
    sign = -1 if direction == "down" else 1
    if (row["delta"] or 0) * sign < 0:
        return "افت معنادار؛ بازنگری پیشنهاد می‌شود"
    return "بهبود معنادار؛ تناسب هدف بررسی و پایش ادامه یابد"


def trend_review(trend: dict, direction: str, target: Optional[float],
                 last_value: Optional[float], alpha: float) -> dict:
    """Offline kpiTrendReview: human title/reason for the slope test result."""
    state = trend.get("state")
    if state == "insufficient":
        trend["title"] = "داده ناکافی برای تصمیم"
        trend["reason"] = ("حداقل ۴ دوره ثبت معتبر در دامنه انتخابی لازم است؛ "
                           "داده مفقود صفر محسوب نمی‌شود.")
        return trend
    if state != "ok":
        trend["title"] = "نتیجه آماری قابل اتکا نیست"
        trend["reason"] = ("پراکندگی باقیمانده صفر یا بسیار کوچک است؛ "
                           "داده‌ها و هدف به‌صورت مدیریتی بررسی شوند.")
        return trend
    slope = trend["slope"]
    p = trend["p"]
    adverse = slope * (-1 if direction == "down" else 1) < 0
    below = (target is not None and last_value is not None and
             (last_value > target if direction == "down" else last_value < target))
    if p < alpha and adverse:
        trend["title"] = "بازنگری پیشنهاد می‌شود"
        trend["reason"] = ("روند نامطلوب معنادار است؛ علل افت، اقدامات اصلاحی و "
                           "تناسب هدف/تعریف شاخص بررسی شود.")
    elif below:
        trend["title"] = "بازنگری پیشنهاد می‌شود"
        trend["reason"] = ("آخرین عملکرد به هدف نرسیده است؛ " +
                           ("با وجود روند بهبود معنادار، " if p < alpha else "") +
                           "اقدامات و تناسب هدف بررسی شود. این پیشنهاد بر مبنای "
                           "فاصله از هدف است.")
    elif target is None:
        trend["title"] = "هدف نامعتبر؛ بررسی لازم است"
        trend["reason"] = "آزمون روند محاسبه شد، اما ارزیابی نسبت به هدف ممکن نیست."
    else:
        trend["title"] = "بازنگری لازم نیست"
        trend["reason"] = ("روند مطلوب یا معنادار نیست و آخرین عملکرد در سطح هدف است؛ "
                           "پایش عادی ادامه یابد.")
    return trend
