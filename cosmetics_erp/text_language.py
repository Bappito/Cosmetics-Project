"""Show an item name in one language only.

Some item names in the catalog are written in both languages, for example
"חמאת שיאה אורגנית / Shea Butter". On a Hebrew page only the Hebrew part is shown, and on an
English page only the English part. Text without that two-language pattern is returned unchanged,
so SKUs, batch numbers and notes are not affected.
"""
from __future__ import annotations

import re

_HEBREW = re.compile(r"[֐-׿]")
_LATIN = re.compile(r"[A-Za-z]")
SEPARATOR = " / "


def localize_text(text: str, lang: str) -> str:
    if SEPARATOR not in text:
        return text
    left, right = text.split(SEPARATOR, 1)
    if _HEBREW.search(left) and not _HEBREW.search(right) and _LATIN.search(right):
        he, en = left.strip(), right.strip()
    elif _LATIN.search(left) and not _LATIN.search(right) and _HEBREW.search(right):
        en, he = left.strip(), right.strip()
    else:
        return text
    return he if lang == "he" else en


def make_text_factory(lang: str):
    """A sqlite3 text_factory: every text value read from the database is shown in one language."""
    def factory(raw: bytes) -> str:
        return localize_text(raw.decode("utf-8"), lang)
    return factory
