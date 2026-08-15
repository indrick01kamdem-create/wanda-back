"""Détection d'opérateur mobile camerounais à partir d'un numéro."""

import re

_MTN_RE = re.compile(r"^6(([78][0-9]{7})|(5[0-4][0-9]{6}))$")
_ORANGE_RE = re.compile(r"^6((9[0-9]{7})|(5[5-9][0-9]{6}))$")


def detect_operator(phone: str) -> str | None:
    """
    Détecte l'opérateur camerounais depuis un numéro international.
    Retourne "orange", "mtn", ou None si non reconnu.

    MTN    : 67x, 68x, 650-654
    Orange : 69x, 655-659
    """
    normalized = phone.replace(" ", "").replace("-", "")
    if normalized.startswith("+237"):
        local = normalized[4:]
    elif normalized.startswith("237"):
        local = normalized[3:]
    else:
        local = normalized

    if _MTN_RE.match(local):
        return "mtn"
    if _ORANGE_RE.match(local):
        return "orange"
    return None
