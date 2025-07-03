from __future__ import annotations

import argparse
import sys
from itertools import chain
from typing import TYPE_CHECKING

from dependence._utilities import (
    check_output,
    iter_configuration_files,
    iter_parse_delimited_values,
)
from dependence.freeze import get_frozen_requirements
from dependence.update import update

if TYPE_CHECKING:
    from collections.abc import Iterable


def upgrade(
    requirements: Iterable[str],
    *,
    ignore_update: Iterable[str] = (),
    all_extra_name: str = "",
    include_pointers: tuple[str, ...] = (),
    exclude_pointers: tuple[str, ...] = (),
    exclude: Iterable[str] = (),
    exclude_recursive: Iterable[str] = (),
    depth: int | None = None,
) -> None:
    """
    This function obtains a list of dependencies for the specified
    `requirements` using `dependence.update.get_frozen_requirements()`,
    upgrades all of these dependencies in the current environment,
    then updates version specifiers for all requirements/dependencies
    in any or the `requirements` which are project config files
    to align with the newly installed package versions (using
    `dependence.update.update()`).

    Parameters:
        requirements: One or more requirement specifiers (for example:
            "requirement-name[extra-a,extra-b]" or ".[extra-a, extra-b]) and/or
            paths to a setup.py, setup.cfg, pyproject.toml, tox.ini or
            requirements.txt file.
        ignore_update: One or more project names to ignore (leave as-is)
            when updating a dependency's requirement specifier in the
            provided pyproject.toml/setup.cfg/requirements.txt/tox.ini
            file(s). Note that this does not prevent the package from being
            upgraded—for that you need to pass the package name in
            `exclude` or `exclude_recursive`.
        all_extra_name: If provided, an extra which consolidates
            the requirements for all other extras will be added/updated to
            pyproject.toml or setup.cfg (this argument is ignored for
            requirements.txt and tox.ini files).
        include_pointers: A tuple of JSON pointers indicating elements to
            include (defaults to all elements). This applies only to TOML
            files (including pyproject.toml), and is ignored for all other
            file types.
        exclude_pointers: A tuple of JSON pointers indicating elements to
            exclude (defaults to no exclusions). This applies only to TOML
            files (including pyproject.toml), and is ignored for all other
            file types.
        exclude: One or more distributions to exclude when upgrading packages.
        exclude_recursive: One or more distributions to exclude when
            upgrading packages. Recursive dependency discovery is also
            halted for these distributions, unlike those passed to `exclude`.
        depth: The maximum recursion depth to traverse when discovering
            dependencies. If `None` (the default), all dependencies are
            discovered.
    """
    frozen_requirements: tuple[str, ...] = get_frozen_requirements(
        requirements,
        exclude=exclude,
        exclude_recursive=exclude_recursive,
        no_version="*",
        depth=depth,
        include_pointers=include_pointers,
        exclude_pointers=exclude_pointers,
    )
    command: tuple[str, ...] = (
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        *frozen_requirements,
    )
    check_output(command)
    configuration_files: tuple[str, ...] = tuple(
        chain(
            *map(iter_configuration_files, requirements)  # type: ignore
        )
    )
    if configuration_files:
        update(
            configuration_files,
            ignore=ignore_update,
            all_extra_name=all_extra_name,
            include_pointers=include_pointers,
            exclude_pointers=exclude_pointers,
        )


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="dependence upgrade",
        description=(
            "Upgrade all dependencies for specified packages/projects, "
            "then upgrade version specifiers in the project files "
            "to align with newly installed versions of each distribution."
        ),
    )
    parser.add_argument(
        "-iu",
        "--ignore-update",
        default=[],
        type=str,
        action="append",
        help=(
            "A comma-separated list of distributions to ignore (leave "
            "any requirements pertaining to the package as-is) when "
            "updating project files"
        ),
    )
    parser.add_argument(
        "-aen",
        "--all-extra-name",
        default="",
        type=str,
        help=(
            "If provided, an extra which consolidates the requirements "
            "for all other extras will be added/updated to pyproject.toml "
            "or setup.cfg (this argument is ignored for "
            "requirements.txt files and other TOML files)"
        ),
    )
    parser.add_argument(
        "--include-pointer",
        default=[],
        type=str,
        action="append",
        help=(
            "One or more JSON pointers of elements to *include* "
            "(applies to TOML files only)"
        ),
    )
    parser.add_argument(
        "--exclude-pointer",
        default=[],
        type=str,
        action="append",
        help=(
            "One or more JSON pointers of elements to *exclude* "
            "(applies to TOML files only)"
        ),
    )
    parser.add_argument(
        "-e",
        "--exclude",
        default=[],
        type=str,
        action="append",
        help=(
            "A distribution (or comma-separated list of distributions) to "
            "exclude when performing upgrades"
        ),
    )
    parser.add_argument(
        "-er",
        "--exclude-recursive",
        default=[],
        type=str,
        action="append",
        help=(
            "A distribution (or comma-separated list of distributions) to "
            "exclude when performing upgrades. Unlike -e / --exclude, "
            "this argument also precludes recursive requirement discovery "
            "for the specified packages, thereby excluding all of the "
            "excluded package's requirements which are not required by "
            "another (non-excluded) distribution from the upgrade."
        ),
    )
    parser.add_argument(
        "-d",
        "--depth",
        default=None,
        type=int,
        help="Depth of recursive requirement discovery",
    )
    parser.add_argument(
        "requirement",
        nargs="+",
        type=str,
        help=(
            "One or more requirement specifiers (for example: "
            '"requirement-name", "requirement-name[extra-a,extra-b]", '
            '".[extra-a, extra-b]" or '
            '"../other-editable-package-directory[extra-a, extra-b]) '
            "and/or paths to a setup.py, setup.cfg, pyproject.toml, "
            "tox.ini or requirements.txt file"
        ),
    )
    namespace: argparse.Namespace = parser.parse_args()
    upgrade(
        requirements=namespace.requirement,
        exclude=tuple(iter_parse_delimited_values(namespace.exclude)),
        exclude_recursive=tuple(
            iter_parse_delimited_values(namespace.exclude_recursive)
        ),
        ignore_update=tuple(
            iter_parse_delimited_values(namespace.ignore_update)
        ),
        all_extra_name=namespace.all_extra_name,
        include_pointers=tuple(namespace.include_pointer),
        exclude_pointers=tuple(namespace.exclude_pointer),
    )


if __name__ == "__main__":
    main()
