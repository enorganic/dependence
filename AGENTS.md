# AGENTS.md

## Overview

`dependence` is a CLI + library that syncs dependency specifiers in
`pyproject.toml`/`setup.cfg`/`requirements.txt`/`tox.ini` with what's
installed. Subcommands (each its own module + `main()`):
- `update` — rewrite specifiers to match installed versions.
- `freeze` — recursively resolve a *package's* deps (`name==version`), unlike env-wide `pip freeze`.
- `upgrade` — `pip install --upgrade` frozen deps, then `update`.

## Commands (run from repo root, via `hatch`)

- `make install` — first-time setup (installs hatch, creates envs).
- `make format` — `hatch fmt --formatter && hatch fmt --linter && hatch run mypy`. Run before `make test`.
- `make test` — `hatch fmt --check && hatch run mypy && hatch test -c`.
- Single test: `hatch test -c -- tests/test_utilities.py::<test_name> -v`
- `make docs` — build + serve MkDocs.
- `make upgrade` / `make requirements` — dogfoods `dependence` on its own `pyproject.toml` per hatch env.

## Architecture

- `src/` layout. `dependence.__main__:main` pops `sys.argv[1]` as the
  subcommand, dynamically imports `dependence.<command>`, calls its
  `main()`. New subcommand = new module with `main()`, no central registry.
- `freeze.py`/`update.py`/`upgrade.py` are thin; logic lives in private
  `_utilities.py` (excluded from coverage).
- Shared flow: get requirement strings from config
  (`iter_configuration_file_requirement_strings` /
  `get_required_distribution_names`) → resolve installed versions
  (`get_installed_distributions` → `map_pip_list` → `_iter_pip_list`) →
  apply subcommand transform.
- `_iter_pip_list` and `_install_requirement_string` (`_utilities.py`)
  prefer `uv pip ...` when `uv` is on `PATH`, else fall back to
  `sys.executable -m pip ...`. Preserve this fallback if touching either
  function (see `docs/superpowers/specs/2026-07-29-uv-shim-pip-fallback-design.md`).
- `update` only rewrites inclusive specifiers (`~=`, `==`, `>=`, `<=`) and
  preserves existing granularity (`~=1.2` + installed `1.5.6` → `~=1.5`);
  unversioned requirements untouched. TOML targeting uses JSON pointers
  (`--include-pointer`/`--exclude-pointer`; if both given, both must match).

## Conventions

- ruff line length 79, max complexity 10; mypy `disallow_untyped_defs` over
  `src` and `tests`; ships `py.typed`.
- Tests use real subprocesses against `tests/test_projects/test_project_{a,b,c}`
  — don't mock `dependence`'s own interfaces. Coverage `fail_under = 70`.
- Branches: `feature/...` / `bugfix/...`. Before PR: `make format`, `make test`.
- Bumping `version` in `pyproject.toml` on `main` triggers release (tag,
  GitHub release, PyPI publish, docs deploy) — don't bump incidentally.
- `docs/api/*.md` are mkdocstrings stubs; API docs come from docstrings.
