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


def renderable_strings(path: Path):
    """String literals that can reach the canvas.

    Excludes docstrings, which only the maintainer reads, and anything passed to
    ``print``, which is console output and is held to no such rule. Being precise
    matters: a blunter check flags ``annual_savings.py``'s console warnings, and a
    convention that cries wolf gets switched off.
    """
    tree = ast.parse(path.read_text())

    exempt = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None:
                exempt.add(id(node.body[0].value))
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "print"):
            exempt.update(id(s) for s in _string_constants(node))

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

    Use a colon, a comma, a semicolon, or a second sentence instead. En-dashes are
    untouched by this rule: they are the right character for a range.
    """
    offenders = [(line, text) for line, text in renderable_strings(script)
                 if EM_DASH in text]
    assert not offenders, "\n".join(
        f"{script.name}:{line} contains an em-dash: {text[:80]!r}"
        for line, text in offenders
    )
