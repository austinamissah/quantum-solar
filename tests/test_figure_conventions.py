"""Conventions that every generated figure has to honour.

Figures leave this repository on their own -- pasted into a write-up, attached to
something, read by people who never see the surrounding text. So the rules about
what may appear *on the canvas* are worth enforcing rather than remembering.

Scope is deliberately narrow: only scripts that actually call ``savefig``, and only
string literals that are not docstrings. A docstring explains the figure to whoever
maintains it and never reaches the image, so it is left alone.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

EM_DASH = "—"
#: En-dash is fine and is the correct character for ranges (5-9pm, T=2-5), which
#: is why this checks for the em-dash specifically rather than "any long dash".
EN_DASH = "–"


def figure_scripts() -> list[Path]:
    """Scripts that render an image, i.e. the ones these rules apply to."""
    return sorted(p for p in SCRIPTS.glob("*.py") if "savefig" in p.read_text())


def _string_constants(node):
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            yield sub


def _joined_text(node: ast.JoinedStr) -> str:
    """An f-string as one string, with each interpolation standing in as ``{}``.

    Reconstruction matters: Python parses adjacent literals into a single
    ``JoinedStr`` whose pieces are separate nodes, so ``f"bill ${x} of ${y}"``
    holds no piece containing two dollar signs even though the drawn text does.
    Checking the pieces individually misses exactly the defects worth catching.
    """
    out = []
    for part in node.values:
        if isinstance(part, ast.Constant) and isinstance(part.value, str):
            out.append(part.value)
        else:
            out.append("{}")
    return "".join(out)


def renderable_strings(path: Path):
    """Text that can reach the canvas, reconstructed as it will be drawn.

    Excludes docstrings, which only the maintainer reads, and the arguments of
    ``print`` and ``raise SystemExit``, which are console output and error
    messages. Being precise matters: a blunter check flags ``annual_savings.py``'s
    console warnings and every REFUSING TO DRAW message, and a convention that
    cries wolf gets switched off.
    """
    tree = ast.parse(path.read_text())

    exempt = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None:
                exempt.add(id(node.body[0].value))
        # `parse_math=False` is matplotlib's own opt-out: the call has already
        # said its text is literal, so the dollar-pair rule does not apply to it.
        opted_out = (isinstance(node, ast.Call)
                     and any(kw.arg == "parse_math"
                             and isinstance(kw.value, ast.Constant)
                             and kw.value.value is False
                             for kw in node.keywords))
        console = (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id in {"print", "SystemExit"})
        if console or opted_out:
            exempt.update(id(s) for s in _string_constants(node))
            exempt.update(id(s) for s in ast.walk(node)
                          if isinstance(s, ast.JoinedStr))

    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr) and id(node) not in exempt:
            # The pieces are covered by the whole; do not also report them.
            exempt.update(id(s) for s in _string_constants(node))
            yield node.lineno, _joined_text(node)

    for node in _string_constants(tree):
        if id(node) not in exempt:
            yield node.lineno, node.value


def test_there_are_figure_scripts_to_check():
    """Guard the guard: a glob that silently matches nothing would pass forever."""
    found = figure_scripts()
    assert len(found) >= 5, f"expected the figure generators, found {found}"


@pytest.mark.parametrize("script", figure_scripts(), ids=lambda p: p.name)
def test_no_em_dash_reaches_the_canvas(script):
    """No em-dash in any text that gets drawn.

    Figures here use a colon, a comma, a semicolon, or a second sentence in its
    place. En-dashes are untouched: they are the right character for a range.
    """
    offenders = [(line, text) for line, text in renderable_strings(script)
                 if EM_DASH in text]
    assert not offenders, "\n".join(
        f"{script.name}:{line} contains an em-dash: {text[:80]!r}"
        for line, text in offenders
    )


#: A currency amount looks like ``$0.36`` or ``${cost}``: a dollar immediately
#: followed by a digit or a format field. Intentional mathtext (``$\alpha^*$``)
#: has LaTeX between its delimiters and is left alone.
CURRENCY = re.compile(r"(?<!\\)\$[\d{]")


@pytest.mark.parametrize("script", figure_scripts(), ids=lambda p: p.name)
def test_no_unescaped_currency_pair_reaches_the_canvas(script):
    r"""Two bare dollar signs in one drawn string silently become mathtext.

    Matplotlib reads everything between them as LaTeX and italicises it, so
    "bill $0.36 for the day instead of $2.29" renders as "bill 0.36 for the day
    instead of 2.29", middle in italics, currency symbols gone. This shipped once
    and reads as a typo rather than as a bug. Escape them as ``\$``.
    """
    offenders = [(line, text) for line, text in renderable_strings(script)
                 if len(CURRENCY.findall(text)) >= 2]
    assert not offenders, "\n".join(
        f"{script.name}:{line} has an unescaped currency pair: {text[:80]!r}"
        for line, text in offenders
    )
