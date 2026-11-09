# -*- coding: utf-8 -*-
"""Jalali (Shamsi) calendar helpers."""
import jdatetime

MONTHS_FA = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
             "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]

FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"


def to_fa_digits(s) -> str:
    s = str(s)
    return "".join(FA_DIGITS[int(c)] if c.isdigit() else c for c in s)


def month_name(m: int) -> str:
    return MONTHS_FA[m - 1] if 1 <= m <= 12 else str(m)


def today():
    d = jdatetime.date.today()
    return {"year": d.year, "month": d.month, "day": d.day}


def format_date(year: int, month: int, day: int = 1, fa_digits: bool = True) -> str:
    s = f"{year:04d}/{month:02d}/{day:02d}"
    return to_fa_digits(s) if fa_digits else s


def label(year: int, month: int) -> str:
    """e.g. 'مرداد ۱۴۰۵'"""
    return f"{month_name(month)} {to_fa_digits(year)}"


def gregorian_to_jalali(gy, gm, gd):
    d = jdatetime.date.fromgregorian(year=gy, month=gm, day=gd)
    return {"year": d.year, "month": d.month, "day": d.day}
