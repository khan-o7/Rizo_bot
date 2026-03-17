"""Input validation helpers."""
from __future__ import annotations

import re


def is_valid_price(text: str) -> bool:
    """Accept integer or float price, e.g. 15000 or 15000.50"""
    try:
        val = float(text.replace(",", ".").replace(" ", ""))
        return val > 0
    except ValueError:
        return False


def parse_price(text: str) -> float:
    return float(text.replace(",", ".").replace(" ", ""))


def is_valid_phone(phone: str) -> bool:
    """Validate Uzbek phone or international format."""
    cleaned = re.sub(r"[\s\-\(\)]", "", phone)
    return bool(re.match(r"^\+?\d{9,15}$", cleaned))


def clean_phone(phone: str) -> str:
    return re.sub(r"[\s\-\(\)]", "", phone)
