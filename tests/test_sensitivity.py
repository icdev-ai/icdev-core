# CUI // SP-CTI
"""xit-decl-04 -- icdev.core.sensitivity: the ONE sensitivity seam."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from icdev.core import domain as core_domain
from icdev.core import sensitivity as sens

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def it_domain():
    return core_domain.load_domain(REPO_ROOT / "icdev_domain.yaml")


@pytest.fixture
def ft_domain(tmp_path):
    p = tmp_path / "icdev_domain.yaml"
    p.write_text(yaml.safe_dump({
        "schema_version": 1,
        "domain": {"key": "ft", "name": "ICDEV[FT]", "env_prefix": "FIN"},
        "db": {"databases": ["icdev_ft"]},
        "sensitivity": {
            "column": "classification", "default": "public",
            "order": ["public", "internal", "pii", "mnpi", "account_secret"],
            "egress_restricted": ["pii", "mnpi", "account_secret"], "levels": [],
        },
    }), encoding="utf-8")
    return core_domain.load_domain(p)






def test_ft_declares_its_own_order_and_egress(ft_domain):
    assert sens.labels(ft_domain) == ("public", "internal", "pii", "mnpi", "account_secret")
    assert sens.is_egress_restricted("MNPI", ft_domain) is True
    assert sens.is_egress_restricted("internal", ft_domain) is False
    assert sens.dominates("mnpi", "pii", ft_domain) is True
    assert sens.describe(ft_domain)["domain"] == "ft"


def test_normalise_folds_separators():
    assert sens.normalise("TOP SECRET//SCI") == "top_secret_sci"
    assert sens.normalise(" Cui ") == "cui"
    assert sens.normalise(None) == ""




