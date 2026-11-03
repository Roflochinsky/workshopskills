"""Deliberately broken input for the deterministic factory demonstration."""


def billed_minutes(seconds: int) -> int:
    if type(seconds) is not int or seconds < 0:
        raise ValueError("seconds must be a nonnegative integer")
    return seconds // 60
