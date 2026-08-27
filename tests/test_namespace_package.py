"""`icdev` must stay a PEP 420 NAMESPACE package (xcore-cut-02).

WHY THIS IS A TEST AND NOT A COMMENT. This distribution and the ICDEV[IT] parent both install
into the same `icdev` name. A regular package has ONE `__path__`, so whichever were found first
would win and the other's subpackages would silently vanish -- `icdev.core` unimportable in one
direction, `icdev.tools` in the other.

Measured before choosing this layout: with `pkgutil.extend_path` in BOTH distributions
`__path__` merges correctly, but only ONE `icdev/__init__.py` ever EXECUTES. When this one won,
the parent's `_alias_tools_namespace()` never ran -- the function that makes ~1,900
`from tools.X import ...` imports resolve inside the parent's published wheel. That is an
order-dependent, silent break of every installed deployment, which is strictly worse than the
shadowing the split exists to remove.

Shipping no `icdev/__init__.py` here makes the parent's the only one, so it runs whatever the
path order. Restoring the file -- even empty, which is what it used to be -- reintroduces the
race, and nothing else in the tree would notice. Hence a test.
"""
from __future__ import annotations

import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_icdev_has_no_init_file():
    """The whole design in one assertion."""
    init = REPO_ROOT / "icdev" / "__init__.py"
    assert not init.exists(), (
        "icdev/__init__.py is back. This distribution must ship `icdev` as a PEP 420 namespace "
        "package so the ICDEV[IT] parent's __init__ is the only one that executes; see the "
        "module docstring for what breaks otherwise."
    )


def test_icdev_core_still_has_one():
    """Only the TOP level is a namespace. `icdev.core` is a real package with a real surface."""
    assert (REPO_ROOT / "icdev" / "core" / "__init__.py").exists()


def test_icdev_resolves_as_a_namespace_at_runtime():
    """Importing proves what the file layout only implies."""
    import icdev

    # A namespace package has no __file__ (or None); a regular one always has a real path.
    assert getattr(icdev, "__file__", None) in (None,), (
        f"icdev resolved as a REGULAR package from {getattr(icdev, '__file__', None)!r} — "
        "something on sys.path is shipping an icdev/__init__.py"
    )
    assert hasattr(icdev, "__path__")


def test_the_public_surface_imports_from_the_namespace():
    """The carve-out's actual contract, exercised rather than assumed."""
    from icdev.core import sensitivity  # noqa: F401
    from icdev.core.context import assert_identity, check_identity, load_env  # noqa: F401
    from icdev.core.domain import Domain, DomainError, load_domain  # noqa: F401
    from icdev.core.paths import repo_root  # noqa: F401


def test_packaging_declares_namespace_discovery():
    """`find` without `namespaces` would discover nothing once __init__.py is gone.

    It is setuptools' default today. A default that flips silently would ship a wheel
    containing no `icdev.core` at all, and the failure would surface as an ImportError in a
    PARENT, far from this repo.
    """
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "namespaces = true" in pyproject, (
        "pyproject must state `namespaces = true` under [tool.setuptools.packages.find]"
    )
