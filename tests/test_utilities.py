from __future__ import annotations

import importlib.metadata
import os
import shutil
import stat
import subprocess
import sys
from subprocess import list2cmdline
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from dependence._utilities import WHICH, check_output, is_aliased, map_pip_list


def test_is_aliased() -> None:
    command: str = "ping"
    if is_aliased(command):
        shell_output: str = check_output(
            (WHICH, command),
            shell=True,
        ).strip()
        default_shell: str = os.getenv("SHELL") or os.getenv("COMSPEC") or "?"
        which_command: str = cast("str", shutil.which(command)).strip()
        message: str = (
            f"Output from `{list2cmdline((WHICH, command))}` in "
            f"{default_shell}:\n"
            f"{shell_output}\n!=\n{which_command}"
        )
        raise ValueError(message)


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
        "@exit /b 127\n"
        if sys.platform == "win32"
        else "#!/bin/sh\nexit 127\n"
    )
    broken_uv.chmod(broken_uv.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    map_pip_list.cache_clear()
    try:
        packages = map_pip_list()
    finally:
        map_pip_list.cache_clear()
    assert packages  # the running interpreter's own site-packages


def test_install_requirement_string_falls_back_to_pip_when_uv_cannot_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    A `uv` executable that is present on `PATH` but cannot actually run
    must not prevent installation -- `dependence` should fall back to
    `pip` when installing a requirement string.

    Note: `tests/test_projects/test_project_a` (and its siblings) pin
    `setuptools~=0.0` in `[build-system] requires`, on purpose, to test
    that "zero version" pins survive `dependence`'s update logic
    untouched (see `test_update.py::test_get_updated_pyproject_toml_a`).
    That pin resolves to a setuptools release too old to build on any
    currently supported Python, so those fixtures cannot be installed
    for real. A small installable package is built here instead.
    """
    from dependence._utilities import _install_requirement_string

    broken_uv: Path = tmp_path.joinpath(
        "uv.bat" if sys.platform == "win32" else "uv"
    )
    broken_uv.write_text(
        "@exit /b 127\n"
        if sys.platform == "win32"
        else "#!/bin/sh\nexit 127\n"
    )
    broken_uv.chmod(broken_uv.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    is_aliased.cache_clear()
    package_name: str = "pip-fallback-pkg"
    package_directory: Path = tmp_path.joinpath("pip_fallback_pkg")
    package_directory.joinpath("pip_fallback_pkg").mkdir(parents=True)
    package_directory.joinpath("pip_fallback_pkg", "__init__.py").write_text(
        ""
    )
    package_directory.joinpath("pyproject.toml").write_text(
        "[build-system]\n"
        'requires = ["setuptools>=61"]\n'
        'build-backend = "setuptools.build_meta"\n'
        "\n"
        "[project]\n"
        f'name = "{package_name}"\n'
        'version = "0.0.0"\n'
    )
    try:
        _install_requirement_string(
            str(package_directory), name=package_name, editable=True
        )
        assert importlib.metadata.distribution(package_name)
    finally:
        is_aliased.cache_clear()
        subprocess.run(
            (
                sys.executable,
                "-m",
                "pip",
                "uninstall",
                "-y",
                package_name,
            ),
            check=False,
            capture_output=True,
        )


def test_install_requirement_string_raises_pip_error_when_uv_and_pip_both_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    When `uv` is present on `PATH` but cannot actually run *and* the
    `pip` fallback also fails, the exception propagated to the caller
    must describe the `pip` failure -- not the original `uv` failure.

    A bare `raise` in the `not editable` branch of
    `_install_requirement_string` would instead re-raise the `uv`
    failure, because Python's exception-context mechanism reverts the
    "currently handled exception" to the outer `except` clause once
    the nested `try`/`except` for the `pip` fallback exits without
    itself re-raising.
    """
    from dependence._utilities import _install_requirement_string

    broken_uv: Path = tmp_path.joinpath(
        "uv.bat" if sys.platform == "win32" else "uv"
    )
    broken_uv.write_text(
        "@exit /b 127\n"
        if sys.platform == "win32"
        else "#!/bin/sh\nexit 127\n"
    )
    broken_uv.chmod(broken_uv.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    is_aliased.cache_clear()
    # A requirement string that isn't a valid package name and doesn't
    # exist as a path -- `pip` will reject it immediately (no network
    # access required), so it legitimately fails too.
    invalid_requirement: str = str(
        tmp_path.joinpath("nonexistent", "path", "to", "pkg")
    )
    try:
        with pytest.raises(subprocess.CalledProcessError) as exception_info:
            _install_requirement_string(
                invalid_requirement, name="", editable=False
            )
    finally:
        is_aliased.cache_clear()
    error: subprocess.CalledProcessError = exception_info.value
    # The propagated error must be `pip`'s, not `uv`'s. Checking
    # `error.cmd` directly (rather than searching the command line
    # for the substring "pip") discriminates the two: `uv`'s command
    # is `uv pip install ...`, which also contains "pip" as a
    # sub-argument, so a substring check would pass even if `uv`'s
    # error were propagated by mistake.
    assert error.cmd[:3] == (sys.executable, "-m", "pip")
    assert error.returncode != 127
    command_line: str = list2cmdline(error.cmd)
    assert invalid_requirement in command_line
    # The `uv` failure (return code 127) must be preserved as the
    # *implicit* exception context -- `_install_requirement_string`
    # raises the `pip` error with a bare `raise error` (not
    # `raise error from uv_error`), so `__cause__` is `None` and it is
    # Python's automatic exception chaining that sets `__context__`.
    assert error.__cause__ is None
    assert isinstance(error.__context__, subprocess.CalledProcessError)
    assert error.__context__.returncode == 127


if __name__ == "__main__":
    pytest.main([__file__, "-vv", "-s"])
