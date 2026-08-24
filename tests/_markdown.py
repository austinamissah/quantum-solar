"""Parsing helpers for pinning the numbers a write-up prints.

Shared by the table gates over `docs/results/`. Not a test module -- the leading
underscore keeps pytest from collecting it.

The subtleties here are the reason this is one module rather than a copy per test:
the documents use real typography (a minus sign that is not a hyphen, an en-dash in
ranges, an em-dash for "nothing to compare against"), thousands separators that must
not be read as two numbers, and tables nested inside blockquotes. A second copy of
this parser would drift from the first.
"""

from __future__ import annotations

import re

#: A dollar amount as the documents print it, e.g. ``**$1.93**`` or ``$2.42 (flat)``.
MONEY = re.compile(r"\$(\d+\.\d{2})\b")
NUMBER = re.compile(r"\d+(?:\.\d+)?")

#: The documents set these properly; matching a plain hyphen would silently fail.
MINUS = "−"
EN_DASH = "–"
TIMES = "×"


def flatten(text: str) -> str:
    """Whitespace-normalized text, for matching prose claims.

    A sentence that reads as one phrase in the rendered document can be split across
    a source line -- "all **56** swept points" is wrapped after "swept" -- so prose is
    matched against this and tables are matched line by line against the raw text.

    Blockquote markers are stripped first. A quoted paragraph that wraps would
    otherwise flatten to "... floor `E[TVD]` = > 0.0421 ...", with a stray marker in
    the middle of the sentence, and these documents put their corrections and
    qualifications -- the claims most worth pinning -- inside blockquotes.
    """
    stripped = " ".join(re.sub(r"^\s*(?:>\s*)+", "", line) for line in text.splitlines())
    return " ".join(stripped.split())


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip("|").split("|")]


def markdown_table(text: str, header_contains: str) -> tuple[list[str], list[list[str]]]:
    """Header cells and body rows of the first table whose header matches.

    Blockquote markers are stripped, so a table nested in a ``>`` block parses the
    same as a top-level one. Cells are returned raw, still carrying ``**bold**`` and
    parentheticals; callers pull out the part they mean. The alignment row is skipped
    and the table ends at the first line that is not a row.
    """
    lines = [re.sub(r"^\s*(?:>\s*)+", "", line) for line in text.splitlines()]
    for i, line in enumerate(lines):
        if line.startswith("|") and header_contains in line:
            rows = []
            for row in lines[i + 2 :]:
                if not row.startswith("|"):
                    break
                rows.append(_cells(row))
            return _cells(line), rows
    raise AssertionError(f"no table whose header contains {header_contains!r}")


def numbers(cell: str) -> list[float]:
    """Every number in a cell, with thousands separators removed first.

    The separator is stripped only between a digit and three following digits, so
    ``$11,500`` reads as one number while a comma-separated list (``10, 12, 16, 20``)
    still reads as four.
    """
    return [float(n) for n in NUMBER.findall(re.sub(r"(?<=\d),(?=\d{3}\b)", "", cell))]


def money(cell: str) -> str:
    """The dollar figure in a cell, as printed, without the ``$``."""
    found = MONEY.findall(cell)
    assert len(found) == 1, f"expected exactly one dollar figure in {cell!r}"
    return found[0]


def signed_money(cell: str) -> float | None:
    """A dollar amount carrying its sign, or ``None`` where an em-dash is printed.

    The documents use an em-dash for "nothing to compare against" rather than for
    zero; the two are different claims and the distinction is checked by callers.
    """
    match = re.search(r"([-+]?)\$(\d+\.\d{2})", cell.replace(MINUS, "-"))
    if match is None:
        return None
    return float(match.group(2)) * (-1 if match.group(1) == "-" else 1)


def signed_int(cell: str) -> int:
    return int(re.search(r"([-+]?\d+)", cell.replace(MINUS, "-")).group(1))


def signed_float(cell: str) -> float | None:
    """A signed decimal, or ``None`` where the document prints a dash instead."""
    match = re.search(r"([-+]?\d+(?:\.\d+)?)", cell.replace(MINUS, "-"))
    return None if match is None else float(match.group(1))


def signed_percent(cell: str) -> float | None:
    """A percentage as printed, or ``None`` where the document prints an em-dash."""
    match = re.search(r"(-?\d+(?:\.\d+)?)%", cell.replace(MINUS, "-"))
    return None if match is None else float(match.group(1))


def to_the_cent(value: float) -> str:
    return f"{value:.2f}"


def to_the_tenth(value: float) -> str:
    return f"{value:.1f}"


def rounding_interval(printed: str) -> tuple[float, float]:
    """The range of true values that would print as ``printed``.

    Used where a document states a ratio computed from unrounded quantities but
    prints the rounded ones beside it: ``0.0453 / 0.00013`` is 348 as printed and
    349 as computed, and only the second is correct. Checking the claim against the
    interval its own inputs describe is the honest test -- demanding equality with
    the naive quotient would fail on correct arithmetic.
    """
    value = float(printed)
    decimals = len(printed.split(".")[1]) if "." in printed else 0
    half = 0.5 * 10 ** (-decimals)
    return value - half, value + half
