# icdev-core

The shared core of the ICDEV domain split: the small set of modules **both** parents need,
carved out of [`icdev-ai/icdev`](https://github.com/icdev-ai/icdev) with history preserved.

Distribution name is `icdev-core`; the **import root stays `icdev.core`**, unchanged.

## What is in here, and why only this

| module | answers |
|---|---|
| `paths` | *where is the repo root?* The ONE resolver. |
| `domain` | *which parent is this checkout?* Reads `icdev_domain.yaml`. |
| `context` | *may this process touch this database?* `assert_identity` / `check_identity` / `load_env`. |
| `sensitivity` | *how sensitive is this table?* The one classification ladder. |
| `schema/tables.yaml` | the core-owned table manifest. |

The boundary was chosen from measurement, not from prose (`xcore-dec-01`). Two facts decided it:

- **`icdev/core` has zero dependency on `tools/`.** It imports stdlib, plus `yaml` and
  `dotenv` *locally inside the functions that need them* so importing the module pulls in no
  third-party code. That is what made it separable at all.
- **ICDEV[FT] already imports `icdev.core` in 32 files** and obtains it by putting the IT
  checkout on `sys.path`. Replacing that `sys.path` coupling with a real dependency is the
  whole point of this repo.

Public API, derived from what the parents actually call rather than what was declared:

```
context.assert_identity  19    paths.repo_root                        13
context.load_env          3    domain.{Domain, DomainError, load_domain}  1
context.check_identity    1    sensitivity                    (IT row_security)
```

## `icdev` is a namespace package, and that is load-bearing

This distribution ships `icdev/core/` and **no `icdev/__init__.py`**, so `icdev` is a PEP 420
namespace package.

Both this distribution and the ICDEV[IT] parent install into the same `icdev` name. A regular
package has ONE `__path__`, so whichever were found first would win and the other's subpackages
would silently vanish -- `icdev.core` unimportable in one direction, `icdev.tools` in the other.
That is exactly what was measured before the fix: with the parent installed editable, `icdev`
resolved to `C:/AI/ICDev/icdev` and installing this package beside it changed nothing at all.

`pkgutil.extend_path` in **both** distributions was tried first and rejected. It merges
`__path__` correctly, but only ONE `icdev/__init__.py` ever *executes* -- and when this one won,
the parent's `_alias_tools_namespace()` never ran: the function that makes ~1,900
`from tools.X import ...` imports resolve inside the parent's published wheel. An
order-dependent silent break of every installed deployment is worse than the shadowing it was
meant to fix.

Shipping none here makes the parent's the only `__init__.py`, so it runs whatever the path
order, and `extend_path` on the parent's side pulls `icdev/core/` in beside `icdev/tools/`.

Pinned by `tests/test_namespace_package.py` and by a CI step that inspects the built wheel --
because if setuptools' `namespaces` discovery ever defaults off, this repo publishes a wheel
with no `icdev.core` in it and nothing here notices; the ImportError surfaces in a parent.

## What is deliberately NOT in here

**`shim.py` stayed in the IT parent.** It exists solely to make `tools.X` and
`icdev.tools.X` resolve to one module object in IT's dual tree — and the FT parent has no
`tools/` directory at all. Shipping it here would put one parent's layout knowledge inside
the package both parents install.

**The "functional core"** — storage, kanban, llm, genesis — stays in the IT parent. The
carve-out cards used "core" for both that and this package; they are different by three
orders of magnitude (3,690 files against 6), and only this one is separable today.

## Why this repo is public

Every module here was **already public** in `icdev-ai/icdev`, so publishing them separately
exposes nothing new. A private core would be strictly worse: the *public* parent depends on
it, so installing it in public CI would require a deploy token — a genuinely new secret in a
public workflow, traded for hiding files that are already visible.

## Using it

```bash
pip install -e ../icdev-core     # development, from a sibling checkout
```

Releases are semver tags; the wheel is a GitHub release asset, mirrored to a local wheelhouse
for `pip install --no-index --find-links` on air-gapped installs. Pure Python, no build step.

## Acceptance — what this package can and cannot prove

The original criterion here read *"proven when ICDEV[FT] drops its `sys.path.insert` of the IT
checkout and installs this package instead."* **That is not reachable, and stating it made a
finished carve-out look permanently incomplete.** Measured on ICDEV[FT] 2026-08-27:

| ICDEV[FT] modules importing | count | supplied by |
|---|---|---|
| `icdev.core.*` | 32 | **this package** |
| `tools.*` | 72 | only the ICDEV[IT] checkout |

`tools` exists because ICDEV[IT]'s `icdev/__init__.py` binds it to `icdev.tools`. This package
ships `icdev/core/` and deliberately nothing else, so it cannot supply it and installing it
cannot remove that checkout.

**What IS achieved, and is verified:**

- ICDEV[IT] no longer ships `icdev/core` and depends on this distribution (`xcore-cut-02`).
- Both parents pin a tag, never a branch, and a parent's own gate fails if it calls a symbol the
  pinned core does not export (`coherence_checker --check core_api`).
- A change here is proven against ICDEV[IT] **before** merge by `core-compat.yml`, and against
  ICDEV[FT] daily by the matching workflow in that repository (`xcore-compat-01`).

**What is still outstanding:** ICDEV[FT]'s 72 `tools.*` imports. Removing that coupling is its
own piece of work — a second extraction, or repointing those callers — and is not a side effect
of this package existing.
