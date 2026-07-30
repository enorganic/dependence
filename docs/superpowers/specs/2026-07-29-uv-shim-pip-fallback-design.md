# `uv` Shim Fallback to `pip` — Design Spec

**Date:** 2026-07-29
**Status:** Draft

## Purpose

Let `dependence` complete its `uv`-based package inventory and editable
reinstall when the `uv` command discovered on `PATH` cannot actually run,
falling back to the target interpreter's own `pip`, instead of raising
`CalledProcessError` and aborting the caller.

## Diagnosis

A downstream consumer, called from a Databricks Asset Bundle's
`databricks bundle summary` in GitHub Actions, fails with:

```text
subprocess.CalledProcessError: Command
('/home/runner/.safe-chain/shims/uv', 'pip', 'list', '--python',
'.../.venv/bin/python3', '--format=json')' returned non-zero exit status 127.
```

Traced to `dependence.freeze.get_frozen_requirements` →
`_utilities.iter_distinct` → `_iter_toml_requirement_strings` →
`iter_find_requirements_lists` → `iter_find_qualified_lists` →
`_is_installed_requirement_string` → `is_installed` →
`get_installed_distributions` → `refresh_editable_distributions` →
`map_editable_project_locations` → `map_pip_list` → `_iter_pip_list`
(`src/dependence/_utilities.py:560`), which builds its command from
`shutil.which("uv")` (`:561`).

The caller's CI environment installs
[Aikido Safe Chain](https://github.com/AikidoSec/safe-chain), a supply-chain
security tool that replaces `uv` on `PATH` with a wrapper script
(`~/.safe-chain/shims/uv`). That wrapper does not run `uv` itself — it strips
its own directory from `PATH` and execs `safe-chain uv "$@"`, which locates
and runs whichever *real* `uv` remains on the now-shim-free `PATH`:

```sh
# ~/.safe-chain/shims/uv (relevant excerpt)
PATH=$(remove_shim_from_path) exec safe-chain uv "$@"
```

In the failing step, no real `uv` is on `PATH` (the step runs outside the
build tool's environment that installed one), so `safe-chain uv pip list …`
has nothing to delegate to and exits 127. `shutil.which("uv")` still finds
the shim file itself — `dependence` has no way to distinguish "a working
`uv`" from "a wrapper that will fail" without attempting to run it.

The same failure mode reaches a second call, `_install_requirement_string`
(`:1144`), whose own `shutil.which("uv")` (`:1155`) selects the same
non-functional shim for the editable-reinstall command
(`refresh_editable_distributions`, `:606`, calls this once per editable
project after `map_pip_list`/`map_editable_project_locations` succeeds).

This is not unique to Safe Chain — any environment where `uv` resolves on
`PATH` to something that cannot run (a broken wrapper, a stale shim, a
permission error) hits the same failure today.

## Current State

Both call sites pick a command shape once, based only on whether
`shutil.which("uv")` returns a path, and never reconsider that choice:

- `_iter_pip_list` (`_utilities.py:560-586`): builds a `uv pip list …` command
  when `uv` is found, else `sys.executable -m pip list …`. Calls
  `check_output(command)` once; a `CalledProcessError` propagates unchanged.
- `_install_requirement_string` (`_utilities.py:1144-1237`): builds a
  `uv pip install …` or `pip install …` command the same way, then
  `check_output(command, shell=shell)`. On failure it already has a *retry*
  path — but only for the editable case, and only via `--force-reinstall`
  using the **same** tool that just failed (`:1233-1237`). A tool that cannot
  run at all (exit 127) fails identically on retry.

Neither function ever falls back from `uv` to `pip` after `uv` has been
selected — the choice at the top of the function is final.

## Design

### Shared fallback semantics

When a `uv`-based command fails (any nonzero exit, matching the existing
`check_output`/`CalledProcessError` contract — the failure is not narrowed to
exit code 127 specifically, since a wrapper can fail in more than one way),
retry once with the equivalent `sys.executable -m pip` command for the same
operation. If `uv` was not selected in the first place (not found on `PATH`),
behavior is unchanged — there is nothing to fall back from.

This is strictly additive: environments where the discovered `uv` already
works see no behavior change, since the fallback command never executes.

### `_iter_pip_list`

Compute both the `uv`-based and `pip`-based `list` commands whenever `uv` is
found. Attempt the `uv` command; on `CalledProcessError`, attempt the `pip`
command and use its output instead. A plain `pip list --format=json` result
includes the same fields this function consumes today, including
`editable_project_location` — confirmed by inspection of installed CPython
`pip` output — so no downstream field-mapping changes are needed.

### `_install_requirement_string`

Compute both the `uv`-based and `pip`-based `install` commands whenever `uv`
is found. Attempt the `uv` command; on `CalledProcessError`, attempt the
`pip` command before falling through to the function's existing
error-message construction and (for editable installs) `--force-reinstall`
retry. If the `pip` fallback succeeds, return normally — no error is raised
and no message is printed. If the `pip` fallback also fails, the existing
downstream logic proceeds using the `pip` command and its error, since `uv`
has already proven unusable.

### Scope boundary

This changes only how `dependence` locates a *working* package manager for
its own read (`pip list`) and local editable-install operations — no
resolution, no third-party version selection, no network behavior beyond
what the caller's chosen tool (`uv` or `pip`) already performs for a
`--no-deps` local/editable install. `dependence` does not attempt to detect
or work around specific wrapper tools (Safe Chain or otherwise) by name; it
only reacts to the command it chose failing to run.

## Validation

| Scenario | Expected result |
| --- | --- |
| `uv` on `PATH` runs successfully | Behavior unchanged; `pip` fallback command never executes. |
| No `uv` on `PATH` | Behavior unchanged; `pip` command used directly, as today. |
| `uv` on `PATH` is a non-functional wrapper (e.g. exits 127) | `pip list`/`pip install` fallback runs and succeeds; the caller sees no exception. |
| `uv` on `PATH` fails and the `pip` fallback also fails (list) | The original failure mode is preserved: `CalledProcessError` propagates. |
| `uv` on `PATH` fails and the `pip` fallback also fails (editable install) | Existing error-message and `--force-reinstall` retry behavior applies, now describing the `pip` attempt. |
| Editable project's `editable_project_location` metadata | Present and equivalent whether discovered via `uv pip list` or `pip list`. |

Reproduce the failing wrapper without mocking `dependence`'s own interfaces:
place a real, on-`PATH` executable (a short script that exits 127) ahead of
any working `uv`, so `shutil.which("uv")` resolves to it. This exercises the
real subprocess path exactly as a Safe Chain-wrapped CI runner does.

## Acceptance Criteria

- `_iter_pip_list` (and therefore `map_pip_list`, `get_frozen_requirements`,
  and every downstream consumer such as
  `refresh_editable_distributions`/`get_installed_distributions`) succeeds
  when `uv` is present on `PATH` but cannot run, provided the interpreter's
  own `pip` can.
- `_install_requirement_string`'s editable-reinstall path succeeds under the
  same condition.
- No change in behavior when `uv` already works, or when `uv` is absent.
- No change to which package manager governs dependency *resolution* for
  full installs elsewhere in `dependence` or its callers — this only affects
  the two call sites identified above.

## Out of Scope

- Detecting or special-casing Safe Chain (or any other specific wrapper) by
  name.
- Changing `dependence`'s public API or CLI (`freeze`, `update`, `upgrade`).
- Retrying more than once per call, or adding configurable retry policy.
- Any change in in dependent libraries/applications
