# `uv` Shim Fallback to `pip` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `dependence`'s `uv`-based package inventory (`_iter_pip_list`)
and editable reinstall (`_install_requirement_string`) fall back to the target
interpreter's own `pip` when the `uv` command discovered on `PATH` fails to
run, instead of raising `CalledProcessError`.

**Architecture:** Both functions currently pick a command shape once — `uv
pip …` if `shutil.which("uv")` finds anything, else `sys.executable -m pip
…` — and never reconsider it. Change each to compute *both* command shapes
when `uv` is found, attempt the `uv` command first, and retry with the `pip`
command only on `CalledProcessError`. This is additive: when the discovered
`uv` already works (the common case), the fallback command never executes and
behavior is unchanged.

**Tech Stack:** Python 3.10+, `subprocess`, `pytest`/`hatch test` (real
subprocesses only — no mocking of `dependence`'s own interfaces, consistent
with the existing `tests/test_utilities.py::test_is_aliased` style).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-29-uv-shim-pip-fallback-design.md`.
- Reproduce the failure with a real, on-`PATH` executable that fails (not a
  mock/monkeypatch of `dependence`'s own functions) — this repo's existing
  tests exercise real subprocesses (`test_is_aliased`), and the bug itself is
  a real-subprocess failure mode.
- No behavior change when `uv` already works or is absent from `PATH`.
- Do not narrow the fallback trigger to a specific exit code (e.g. 127
  specifically) — react to any `CalledProcessError`, matching the existing
  `check_output` contract.
- Do not change `dependence`'s public API or CLI (`freeze`, `update`,
  `upgrade`).
- Bump `version` in `pyproject.toml` (currently `1.4.1`) as part of this
  change.
- Run all commands from the repository root (`/Users/davidbelais/Code/dependence`).

---

### Task 1: Fall back to `pip` in `_iter_pip_list`

**Files:**
- Modify: `src/dependence/_utilities.py:560-586` (`_iter_pip_list`)
- Modify: `tests/test_utilities.py`

**Interfaces:**
- Consumes: nothing new — `shutil.which("uv")`, `sys.executable`,
  `check_output` (already imported/defined in this module).
- Produces: `_iter_pip_list` keeps its existing signature and yields the same
  `(normalized_name, PackageMetadata)` pairs; `map_pip_list()` and everything
  built on it (`_iter_editable_project_locations`,
  `map_editable_project_locations`, `refresh_editable_distributions`,
  `get_installed_distributions`, `get_frozen_requirements`) are unaffected
  beyond now succeeding in the failure scenario below.

- [ ] **Step 1: Write the failing test**

  In `tests/test_utilities.py`, add a test that puts a real, on-`PATH`
  executable named `uv` ahead of any working `uv` so `shutil.which("uv")`
  resolves to it, and asserts `map_pip_list()` still succeeds (falling back
  to the real interpreter's `pip`):

  ```python
  import stat
  import sys
  from pathlib import Path

  from dependence._utilities import map_pip_list


  def test_map_pip_list_falls_back_to_pip_when_uv_cannot_run(
      tmp_path: Path, monkeypatch: pytest.MonkeyPatch
  ) -> None:
      """
      A `uv` executable that is present on `PATH` but cannot actually run
      (as happens when a security wrapper, e.g. Aikido Safe Chain's shim,
      has no real `uv` to delegate to) must not prevent package discovery --
      `dependence` should fall back to `pip`.
      """
      broken_uv: Path = tmp_path.joinpath(
          "uv.bat" if sys.platform == "win32" else "uv"
      )
      broken_uv.write_text(
          "@exit /b 127\n" if sys.platform == "win32" else "#!/bin/sh\nexit 127\n"
      )
      broken_uv.chmod(broken_uv.stat().st_mode | stat.S_IEXEC)
      monkeypatch.setenv(
          "PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}"
      )
      map_pip_list.cache_clear()
      try:
          packages = map_pip_list()
      finally:
          map_pip_list.cache_clear()
      assert packages  # the running interpreter's own site-packages
  ```

  (Add `import os` and `import pytest` to the existing import block as
  needed — `monkeypatch` is a built-in pytest fixture, not a mock of
  `dependence` itself.)

- [ ] **Step 2: Run the test to verify it fails**

  Run: `hatch test -c -- tests/test_utilities.py::test_map_pip_list_falls_back_to_pip_when_uv_cannot_run -v`

  Expected: FAIL with `subprocess.CalledProcessError` (exit 127), reproducing
  the reported bug without needing a Safe Chain-wrapped CI runner.

- [ ] **Step 3: Implement the fallback**

  In `src/dependence/_utilities.py`, replace `_iter_pip_list`:

  ```python
  def _iter_pip_list() -> Iterable[tuple[str, PackageMetadata]]:
      uv: str | None = shutil.which("uv")
      pip_command: tuple[str, ...] = (
          sys.executable,
          "-m",
          "pip",
          "list",
          "--format=json",
      )
      output: str
      if uv:
          uv_command: tuple[str, ...] = (
              uv,
              "pip",
              "list",
              "--python",
              sys.executable,
              "--format=json",
          )
          try:
              output = check_output(uv_command)
          except CalledProcessError:
              # `uv` was found on `PATH` but could not run (for example, a
              # CI security wrapper's shim with no real `uv` to delegate
              # to) -- fall back to this interpreter's own `pip`.
              output = check_output(pip_command)
      else:
          output = check_output(pip_command)
      metadata: PackageMetadata
      for metadata in json.loads(output):
          yield (
              normalize_name(metadata["name"]),
              metadata,
          )
  ```

  `CalledProcessError` is already imported in this module (used by
  `is_aliased` and `_install_requirement_string`).

- [ ] **Step 4: Run the test to verify it passes**

  Run: `hatch test -c -- tests/test_utilities.py::test_map_pip_list_falls_back_to_pip_when_uv_cannot_run -v`

  Expected: PASS.

- [ ] **Step 5: Run the full test suite for this module**

  Run: `hatch test -c -- tests/test_utilities.py tests/test_freeze.py -v`

  Expected: all pass, including existing `test_is_aliased` and the
  editable-project freeze tests in `test_freeze.py` — confirming no
  regression to the (unchanged, `uv`-works) common path.

### Task 2: Fall back to `pip` in `_install_requirement_string`

**Files:**
- Modify: `src/dependence/_utilities.py:1144-1237` (`_install_requirement_string`)
- Modify: `tests/test_utilities.py`

**Interfaces:**
- Consumes: same as Task 1.
- Produces: `_install_requirement_string` keeps its existing signature and
  side effect (installs `requirement_string` into `sys.executable`'s
  environment); on a `uv` failure it installs via `pip` instead, without
  raising, before falling through to today's error/`--force-reinstall`
  handling only if the `pip` attempt also fails.

- [ ] **Step 1: Write the failing test**

  Reuse the same broken-`uv`-on-`PATH` technique from Task 1. Install a
  small real local package editably and assert it succeeds despite the
  broken `uv`:

  ```python
  def test_install_requirement_string_falls_back_to_pip_when_uv_cannot_run(
      tmp_path: Path, monkeypatch: pytest.MonkeyPatch
  ) -> None:
      # ... same broken-`uv` PATH setup as the `_iter_pip_list` test ...
      from dependence._utilities import _install_requirement_string

      project_a = str(
          Path(__file__)
          .absolute()
          .parent.joinpath("test_projects/test_project_a")
      )
      _install_requirement_string(project_a, name="test-project-a", editable=True)
      # Assert success via `pip show`/`importlib.metadata`, then uninstall
      # to leave the test environment clean.
  ```

  Use `tests/test_projects/test_project_a` (already used by
  `tests/test_freeze.py`) rather than inventing a new fixture project.
  Uninstall the package at the end of the test (`sys.executable -m pip
  uninstall -y test-project-a`) so the test environment is left as found.

- [ ] **Step 2: Run the test to verify it fails**

  Run: `hatch test -c -- tests/test_utilities.py::test_install_requirement_string_falls_back_to_pip_when_uv_cannot_run -v`

  Expected: FAIL with `CalledProcessError` (exit 127) from the broken `uv`.

- [ ] **Step 3: Implement the fallback**

  In `_install_requirement_string`, after the existing `if uv: … else: …`
  block that builds `command`/`shell` (unchanged), replace the trailing
  `try`/`except` (currently starting at line 1208) so a `uv`-only failure
  retries via `pip` before falling into the existing message/reinstall logic:

  ```python
      try:
          check_output(command, shell=shell)
      except CalledProcessError as error:
          if uv and not shell:
              pip_command: tuple[str, ...] = (
                  sys.executable,
                  "-m",
                  "pip",
                  "install",
                  "--no-deps",
                  "--no-compile",
                  *(
                      ("-e", requirement_string)
                      if editable
                      else (requirement_string,)
                  ),
              )
              try:
                  check_output(pip_command)
              except CalledProcessError as pip_error:
                  command = pip_command
                  error = pip_error
              else:
                  return
          message: str = (
              # ... existing message-construction, unchanged, now
              # describing whichever `command`/`error` reached this point ...
          )
          ...  # existing body below is otherwise unchanged
  ```

  Keep the existing message-construction and (for `editable=True`) the
  `--force-reinstall` retry exactly as today — they now simply operate on
  `command`/`error`, which may be the `pip` fallback's command/error if `uv`
  was tried and failed.

- [ ] **Step 4: Run the test to verify it passes**

  Run: `hatch test -c -- tests/test_utilities.py::test_install_requirement_string_falls_back_to_pip_when_uv_cannot_run -v`

  Expected: PASS.

- [ ] **Step 5: Run the full suite**

  Run: `hatch test -c -v`

  Expected: all tests pass, including `tests/test_freeze.py` (which exercises
  `refresh_editable_distributions` → `_install_requirement_string` indirectly
  through editable test projects) and `tests/test_update.py`/`test_upgrade.py`
  if they touch install paths.

### Task 3: Format, lint, and release

**Files:**
- Modify: `pyproject.toml:9` (version bump)

- [ ] **Step 1: Format and lint**

  Run: `make format`

  Expected: no diffs beyond the intended changes; no lint/type errors.

- [ ] **Step 2: Bump version**

  Change `version` in `pyproject.toml` from `1.4.1` to `1.4.2` (patch — this
  is a backward-compatible bug fix, no API change).

- [ ] **Step 3: Full local verification**

  Run: `make test`

  Expected: all tests, formatting, linting, and type-checking pass.

- [ ] **Step 4: Publish**

  Once merged, release per `docs/contributing.md` (`make build`/publish
  flow already configured in the `Makefile`) so `dependence==1.4.2` is
  available on PyPI for downstream consumers.

## Verification Checklist

- [ ] `_iter_pip_list` succeeds when `uv` is on `PATH` but cannot run,
  provided this interpreter's own `pip` can list packages.
- [ ] `_install_requirement_string`'s editable-reinstall path succeeds under
  the same condition.
- [ ] Neither function's behavior changes when `uv` already works or is
  absent from `PATH` (existing test suite, especially `test_freeze.py`,
  still passes unmodified).
- [ ] No mocking of `dependence`'s own functions in the new tests — only a
  real, broken executable placed on `PATH`.
- [ ] `pyproject.toml` version bumped to `1.4.2`.
