# CUI // SP-CTI
"""xit-decl-01 — the ICDEV[domain] declaration and the process-identity check.

Red-first: ``icdev_domain.yaml`` and ``icdev/core`` do not exist at the merge
base, so every test here fails there.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pathlib
import pytest
import yaml

from icdev.core import context as core_context
from icdev.core import domain as core_domain
from icdev.core import paths as core_paths

REPO_ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# The checked-in declaration for ICDEV[IT]
# --------------------------------------------------------------------------- #






# --------------------------------------------------------------------------- #
# Loading rules
# --------------------------------------------------------------------------- #
def _write_domain(root: Path, **overrides) -> Path:
    data = {
        "schema_version": 1,
        "domain": {"key": "ft", "name": "ICDEV[FT]", "env_prefix": "FIN"},
        "db": {"backend": "postgresql", "databases": ["icdev_ft"]},
        "dashboard": {"port": 5200},
    }
    for k, v in overrides.items():
        data[k] = v
    p = root / core_paths.DOMAIN_FILE
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    return p


def test_key_and_env_prefix_come_from_the_file_not_the_environment(tmp_path, monkeypatch):
    p = _write_domain(tmp_path)
    monkeypatch.setenv("ICDEV_DOMAIN", "it")  # must be ignored: there is no such switch
    dom = core_domain.load_domain(p)
    assert dom.key == "ft" and dom.env_prefix == "FIN"
    # env var names default from the prefix when the file does not spell them out
    assert dom.db.name_env == "FIN_PG_DATABASE"
    assert dom.db.dsn_env == "FIN_DATABASE_URL"
    assert dom.dashboard_port == 5200


def test_missing_file_yields_builtin_default_unless_required(tmp_path, monkeypatch):
    monkeypatch.setenv(core_paths.PROJECT_ROOT_ENV, str(tmp_path))
    monkeypatch.delenv(core_domain.REQUIRE_DOMAIN_ENV, raising=False)
    dom = core_domain.load_domain()
    assert dom.source == "builtin_default" and dom.key == "it" and dom.path is None
    monkeypatch.setenv(core_domain.REQUIRE_DOMAIN_ENV, "1")
    with pytest.raises(core_domain.DomainError):
        core_domain.load_domain()


@pytest.mark.parametrize("bad", [
    {"domain": {"key": "FT", "env_prefix": "FIN"}},          # key must be lowercase
    {"domain": {"key": "ft", "env_prefix": "fin"}},          # prefix must be UPPER
    {"domain": {"key": "ft", "env_prefix": "FIN"}, "dashboard": {"port": 0}},
    {"domain": {"key": "ft", "env_prefix": "FIN"}, "schema_version": 99},
    {"domain": {"key": "ft", "env_prefix": "FIN"}, "db": {"databases": "icdev_ft"}},
])
def test_invalid_declarations_are_refused(tmp_path, bad):
    data = {"schema_version": 1, "db": {"databases": ["x"]}}
    data.update(bad)
    p = tmp_path / core_paths.DOMAIN_FILE
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(core_domain.DomainError):
        core_domain.load_domain(p)


# --------------------------------------------------------------------------- #
# Root resolution
# --------------------------------------------------------------------------- #


def test_repo_root_uses_cwd_domain_file_for_installed_code(tmp_path, monkeypatch):
    parent = tmp_path / "parent"
    parent.mkdir()
    _write_domain(parent)
    monkeypatch.chdir(parent)
    monkeypatch.delenv(core_paths.PROJECT_ROOT_ENV, raising=False)
    # Pretend the kernel lives in site-packages: the anchor walk is skipped.
    monkeypatch.setattr(core_paths, "_is_installed", lambda p: True)
    assert core_paths.repo_root(anchor=__file__) == parent.resolve()
    assert core_paths.find_domain_file() == (parent / core_paths.DOMAIN_FILE).resolve()


def test_project_root_env_wins(tmp_path, monkeypatch):
    monkeypatch.setenv(core_paths.PROJECT_ROOT_ENV, str(tmp_path))
    assert core_paths.repo_root(anchor=__file__) == tmp_path.resolve()
    assert core_paths.describe(anchor=__file__)["source"] == "env"






# --------------------------------------------------------------------------- #
# Identity
# --------------------------------------------------------------------------- #
@pytest.fixture
def it_domain():
    """A declaration checked in AS A TEST FIXTURE, not read from a parent checkout.

    These tests exercise the LIBRARY -- check_identity / assert_identity. Upstream they loaded
    ICDEV[IT]'s own icdev_domain.yaml because one happened to be lying around the repo root.
    icdev-core is a library and HAS no declaration: writing one at its root to satisfy a
    fixture would fabricate a domain for something that is not one, which is precisely what
    load_domain refuses everywhere else. So the declaration lives under tests/fixtures/ where
    it is unambiguously test data.
    """
    return core_domain.load_domain(pathlib.Path(__file__).parent / "fixtures" / "it_domain.yaml")


def test_identity_unmeasured_when_no_database_is_named(it_domain):
    rep = core_context.check_identity(domain=it_domain, environ={})
    assert rep.verdict == "unmeasured" and rep.database_observed is None
    core_context.assert_identity(domain=it_domain, environ={})  # must not raise


def test_identity_matches_declared_database_by_name_or_dsn(it_domain):
    rep = core_context.check_identity(domain=it_domain, environ={"ICDEV_PG_DATABASE": "icdev"})
    assert rep.verdict == "match" and rep.database_source == "ICDEV_PG_DATABASE"
    rep = core_context.check_identity(
        domain=it_domain, environ={"ICDEV_DATABASE_URL": "postgresql://u:p@localhost:5432/icdev"}
    )
    assert rep.verdict == "match" and rep.database_source == "ICDEV_DATABASE_URL"


def test_identity_refuses_another_parents_database(it_domain, monkeypatch):
    monkeypatch.delenv(core_context.IDENTITY_GUARD_ENV, raising=False)
    env = {"ICDEV_PG_DATABASE": "icdev_ft"}
    rep = core_context.check_identity(domain=it_domain, environ=env)
    assert rep.verdict == "mismatch" and rep.enforced is True
    with pytest.raises(core_context.IdentityMismatch):
        core_context.assert_identity(domain=it_domain, environ=env)
    # name_env wins over a DSN that happens to agree — storage.py's precedence
    env2 = {"ICDEV_PG_DATABASE": "icdev_ft", "ICDEV_DATABASE_URL": "postgresql://u:p@h/icdev"}
    assert core_context.check_identity(domain=it_domain, environ=env2).verdict == "mismatch"


def test_identity_guard_env_stands_the_refusal_down_but_still_reports(it_domain, monkeypatch):
    monkeypatch.setenv(core_context.IDENTITY_GUARD_ENV, "0")
    rep = core_context.assert_identity(domain=it_domain, environ={"ICDEV_PG_DATABASE": "icdev_ft"})
    assert rep.verdict == "mismatch" and rep.enforced is False


def test_declaration_without_databases_asserts_nothing(tmp_path):
    p = _write_domain(tmp_path, db={"backend": "postgresql"})
    dom = core_domain.load_domain(p)
    rep = core_context.check_identity(domain=dom, environ={"FIN_PG_DATABASE": "anything"})
    assert rep.verdict == "unmeasured"


def test_cli_exit_codes():
    base = [sys.executable, "-m", "icdev.core.context", "--check", "--no-env"]
    env = {k: v for k, v in os.environ.items()
           if k not in ("ICDEV_PG_DATABASE", "ICDEV_DATABASE_URL", "ICDEV_PROJECT_ROOT",
                        core_context.IDENTITY_GUARD_ENV)}
    env["PYTHONIOENCODING"] = "utf-8"
    ok = subprocess.run(base + ["--json"], cwd=REPO_ROOT, env=env, capture_output=True, text=True)
    assert ok.returncode == 0, ok.stderr
    assert '"verdict": "unmeasured"' in ok.stdout
    bad = subprocess.run(base, cwd=REPO_ROOT, env={**env, "ICDEV_PG_DATABASE": "icdev_ft"},
                         capture_output=True, text=True)
    assert bad.returncode == 1, bad.stdout + bad.stderr
    assert "MISMATCH" in bad.stdout


# --------------------------------------------------------------------------- #
# The entry points consume it (declared-but-unconsumed guard)
# --------------------------------------------------------------------------- #




