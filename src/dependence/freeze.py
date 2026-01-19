from __future__ import annotations

import argparse
import os
from fnmatch import fnmatch
from functools import partial
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, cast

from dependence._utilities import (
    get_distribution,
    get_required_distribution_names,
    get_requirement_string_distribution_name,
    iter_configuration_file_requirement_strings,
    iter_configuration_files,
    iter_distinct,
    iter_parse_delimited_values,
    normalize_name,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, MutableSet
    from importlib.metadata import Distribution

_DO_NOT_PIN_DISTRIBUTION_NAMES: MutableSet[str] = {
    "importlib-metadata",
    "importlib-resources",
}


def _iter_sort_dependents_last(requirements: Iterable[str]) -> Iterable[str]:
    """
    Sort requirements such that dependents are first and dependencies are last.
    """
    requirements = list(requirements)
    distribution_name: str
    distribution_requirement: dict[str, str] = {
        get_requirement_string_distribution_name(requirement): requirement
        for requirement in requirements
    }
    dependent_dependencies: dict[str, MutableSet[str]] = {
        distribution_name: get_required_distribution_names(requirement)
        for distribution_name, requirement in distribution_requirement.items()
    }
    while dependent_dependencies:
        dependent: str
        dependencies: MutableSet[str]
        item: tuple[str, MutableSet[str]]
        for dependent, dependencies in sorted(  # noqa: C414
            tuple(dependent_dependencies.items()),
            key=lambda item: item[0].lower(),
        ):

            def is_non_circular_requirement(
                dependency: str,
                dependent: str,
            ) -> bool:
                """
                Return `True` if the dependency is still among the unaccounted
                for requirements, and is not a circular reference
                """
                return (dependency in dependent_dependencies) and (
                    # Exclude interdependent distributions
                    # (circular references)
                    dependent not in dependent_dependencies[dependency]
                )

            if (not dependencies) or not any(
                map(
                    partial(is_non_circular_requirement, dependent=dependent),
                    dependencies,
                )
            ):
                yield distribution_requirement.pop(dependent)
                del dependent_dependencies[dependent]


def get_frozen_requirements(  # noqa: C901
    requirements: Iterable[str | Path] = (),
    *,
    exclude: Iterable[str] = (),
    exclude_recursive: Iterable[str] = (),
    keep_version_specifier: Iterable[str] = (),
    no_version: Iterable[str] = (),
    dependency_order: bool = False,
    reverse: bool = False,
    depth: int | None = None,
    include_pointers: tuple[str, ...] = (),
    exclude_pointers: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """
    Get the (frozen) requirements for one or more specified distributions or
    configuration files.

    Parameters:
        requirements: One or more requirement specifiers (for example:
            "requirement-name[extra-a,extra-b]" or ".[extra-a, extra-b]) and/or
            paths to a setup.cfg, pyproject.toml, tox.ini or requirements.txt
            file
        exclude: One or more distributions to exclude/ignore
        exclude_recursive: One or more distributions to exclude/ignore.
            Note: Excluding a distribution here excludes all requirements which
            would be identified through recursion.
        keep_version_specifier: Keep the original (non-frozen) version
            specifier for package names matching any of these patterns. This
            supercedes `no_version`, if both sets of patterns match a package
            name.
        no_version: Exclude version numbers from the output
            (only return distribution names). This is superceded by
            `keep_version_specifier`, if both sets of patterns match a package
            name.
        dependency_order: Sort requirements so that dependents
            precede dependencies
        depth: Depth of recursive requirement discovery
        include_pointers: A tuple of JSON pointers indicating elements to
            include (defaults to all elements). Only applies to TOML files.
        exclude_pointers: A tuple of JSON pointers indicating elements to
            exclude (defaults to no exclusions). Only applies to TOML files.
    """
    if isinstance(requirements, (str, Path)):
        requirements = {str(requirements)}
    else:
        requirements = set(map(str, requirements))
    if isinstance(no_version, str):
        no_version = (no_version,)
    elif not isinstance(no_version, tuple):
        no_version = tuple(no_version)
    if isinstance(keep_version_specifier, str):
        keep_version_specifier = (keep_version_specifier,)
    elif not isinstance(keep_version_specifier, tuple):
        keep_version_specifier = tuple(keep_version_specifier)
    # Separate requirement strings from requirement files
    configuration_files: dict[str, dict[str, tuple[str, ...]]] = {}
    requirement_strings: MutableSet[str] = set()
    requirement: str | Path
    for requirement in requirements:
        if TYPE_CHECKING:
            assert isinstance(requirement, str)
        requirement_configuration_files: set[str] = set(
            iter_configuration_files(requirement)
        )
        if requirement_configuration_files:
            is_directory: bool = os.path.isdir(requirement)
            for (
                requirement_configuration_file
            ) in requirement_configuration_files:
                configuration_files[requirement_configuration_file] = (
                    {"include_pointers": ("/project",)}
                    if (
                        is_directory
                        and os.path.basename(
                            requirement_configuration_file
                        ).lower()
                        == "pyproject.toml"
                    )
                    else {
                        "include_pointers": include_pointers,
                        "exclude_pointers": exclude_pointers,
                    }
                )
        else:
            if requirement.startswith("setup.py"):
                raise ValueError(requirement)
            requirement_strings.add(requirement)
    configuration_file: str
    kwargs: dict[str, tuple[str, ...]]
    frozen_requirements: Iterable[str] = iter_distinct(
        chain(
            requirement_strings,
            *(
                iter_configuration_file_requirement_strings(
                    configuration_file, **kwargs
                )
                for configuration_file, kwargs in configuration_files.items()
            ),
        )
    )
    frozen_requirements = tuple(frozen_requirements)
    if depth is not None:
        depth -= 1
    if (depth is None) or depth >= 0:
        frozen_requirements = _iter_frozen_requirements(
            frozen_requirements,
            exclude=set(
                chain(
                    # Exclude requirement strings which are *not*
                    # distribution names (such as editable package paths),
                    # as in these cases we are typically looking for this
                    # package's dependencies
                    (
                        set(
                            map(
                                get_requirement_string_distribution_name,
                                requirement_strings,
                            )
                        )
                        - set(map(normalize_name, requirement_strings))
                    ),
                    map(normalize_name, exclude),
                )
            ),
            exclude_recursive=set(map(normalize_name, exclude_recursive)),
            no_version=no_version,
            keep_version_specifier=keep_version_specifier,
            depth=depth,
        )
    if dependency_order:
        frozen_requirements = tuple(
            _iter_sort_dependents_last(frozen_requirements)
        )
        if not reverse:
            frozen_requirements = tuple(reversed(frozen_requirements))
    else:
        name: str
        frozen_requirements = tuple(
            sorted(
                frozen_requirements,
                key=lambda name: name.lower(),
                reverse=reverse,
            )
        )
    return frozen_requirements


def _iter_frozen_requirements(
    requirement_strings: Iterable[str],
    exclude: MutableSet[str],
    exclude_recursive: MutableSet[str],
    no_version: Iterable[str] = (),
    depth: int | None = None,
    keep_version_specifier: Iterable[str] = (),
) -> Iterable[str]:
    # This retains a mapping of distribution names to their original
    # requirement strings in order to return those which match
    # `keep_version_specifier` patterns with their original specifiers
    distribution_names_specifiers: dict[str, str] = {}

    def get_requirement_string(distribution_name: str) -> str | None:
        if distribution_names_specifiers and (
            distribution_name in distribution_names_specifiers
        ):
            return distribution_names_specifiers[distribution_name]
        if (distribution_name in _DO_NOT_PIN_DISTRIBUTION_NAMES) or any(
            fnmatch(distribution_name, pattern) for pattern in no_version
        ):
            return distribution_name
        distribution: Distribution
        try:
            distribution = get_distribution(distribution_name)
        except KeyError:
            # If the distribution is not installed, skip it
            return None
            # If the distribution is missing, install it
            # install_requirement(distribution_name)
            # distribution = _get_distribution(distribution_name)
        return f"{distribution.metadata['Name']}=={distribution.version}"

    def get_required_distribution_names_(
        requirement_string: str,
        depth_: int | None = None,
    ) -> MutableSet[str]:
        name: str = get_requirement_string_distribution_name(
            requirement_string
        )
        if name in exclude_recursive:
            return set()
        if keep_version_specifier and any(
            fnmatch(name, pattern) for pattern in keep_version_specifier
        ):
            existing_requirement_string: str | None = (
                distribution_names_specifiers.get(name)
            )
            requirement_string = requirement_string.rstrip()
            # Prioritize requirement strings which don't include environment
            # markers over those that do, and prefer more specific requirement
            # strings (longer ones) over less specific requirement strings
            if (
                (not existing_requirement_string)
                or (
                    (";" in existing_requirement_string)
                    == (";" in requirement_string)
                    and len(existing_requirement_string)
                    < len(requirement_string)
                )
                or (
                    ";" in existing_requirement_string
                    and ";" not in requirement_string
                )
            ):
                distribution_names_specifiers[name] = requirement_string
        distribution_names: MutableSet[str] = {name}
        if (depth_ is None) or depth_:
            distribution_names |= get_required_distribution_names(
                requirement_string,
                exclude=exclude_recursive,
                depth=None if (depth_ is None) else depth_ - 1,
            )
        return cast(
            "MutableSet[str]",
            distribution_names - exclude,
        )

    requirement_string: str
    requirements: Iterable[str] = iter_distinct(
        chain(
            *(
                get_required_distribution_names_(
                    requirement_string, None if (depth is None) else depth - 1
                )
                for requirement_string in requirement_strings
            )
        ),
    )
    return filter(None, map(get_requirement_string, requirements))


def freeze(
    requirements: Iterable[str | Path] = (),
    *,
    exclude: Iterable[str] = (),
    exclude_recursive: Iterable[str] = (),
    no_version: Iterable[str] = (),
    dependency_order: bool = False,
    reverse: bool = False,
    depth: int | None = None,
    include_pointers: tuple[str, ...] = (),
    exclude_pointers: tuple[str, ...] = (),
    keep_version_specifier: Iterable[str] = (),
) -> None:
    """
    Print the (frozen) requirements for one or more specified requirements or
    configuration files.

    Parameters:
        requirements: One or more requirement specifiers (for example:
            "requirement-name[extra-a,extra-b]" or ".[extra-a, extra-b]) and/or
            paths to a setup.py, setup.cfg, pyproject.toml, tox.ini or
            requirements.txt file
        exclude: One or more distributions to exclude.
        exclude_recursive: One or more distributions to exclude. Recursive
            dependency discovery is also halted for these distributions,
            unlike those passed to `exclude`.
        no_version: Exclude version numbers from the output
            (only print distribution names) for package names matching any of
            these patterns
        dependency_order: Sort requirements so that dependents
            precede dependencies
        depth: Depth of recursive requirement discovery
        include_pointers: If this not empty, *only* these TOML tables will
            inspected (for pyproject.toml files)
        exclude_pointers: If not empty, these TOML tables will *not* be
            inspected (for pyproject.toml files)
    """
    print(  # noqa: T201
        "\n".join(
            get_frozen_requirements(
                requirements=requirements,
                exclude=exclude,
                exclude_recursive=exclude_recursive,
                no_version=no_version,
                dependency_order=dependency_order,
                reverse=reverse,
                depth=depth,
                include_pointers=include_pointers,
                exclude_pointers=exclude_pointers,
                keep_version_specifier=keep_version_specifier,
            )
        )
    )


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="dependence freeze",
        description=(
            "This command prints dependencies inferred from an installed "
            "distribution or project, in a similar format to the "
            "output of `pip freeze`, except that all generated requirements "
            'are specified in the format "distribution-name==0.0.0" '
            "(including for editable installations). Using this command "
            "instead of `pip freeze` to generate requirement files ensures "
            "that you don't bloat your requirements files with superfluous "
            "distributions."
        ),
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
    parser.add_argument(
        "-e",
        "--exclude",
        default=[],
        type=str,
        action="append",
        help=(
            "A distribution (or comma-separated list of distributions) to "
            "exclude from the output"
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
            "exclude from the output. Unlike -e / --exclude, "
            "this argument also precludes recursive requirement discovery "
            "for the specified packages, thereby excluding all of the "
            "excluded package's requirements which are not required by "
            "another (non-excluded) distribution."
        ),
    )
    parser.add_argument(
        "-nv",
        "--no-version",
        type=str,
        default=[],
        action="append",
        help=(
            "Don't include versions (only output distribution names) "
            "for packages matching this/these glob pattern(s) (note: the "
            "value must be single-quoted if it contains wildcards)"
        ),
    )
    parser.add_argument(
        "-kvs",
        "--keep-version-specifier",
        type=str,
        default=[],
        action="append",
        help=(
            "Don't freeze versions (instead retain the most specific version "
            "specifier) for packages matching this/these glob pattern(s) "
            "(note: the value must be single-quoted if it contains wildcards)"
        ),
    )
    parser.add_argument(
        "-do",
        "--dependency-order",
        default=False,
        action="store_true",
        help="Sort requirements so that dependents precede dependencies",
    )
    parser.add_argument(
        "--reverse",
        default=False,
        action="store_true",
        help="Print requirements in reverse order",
    )
    parser.add_argument(
        "-d",
        "--depth",
        default=None,
        type=int,
        help="Depth of recursive requirement discovery",
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
    namespace: argparse.Namespace = parser.parse_args()
    freeze(
        requirements=namespace.requirement,
        exclude=tuple(iter_parse_delimited_values(namespace.exclude)),
        exclude_recursive=tuple(
            iter_parse_delimited_values(namespace.exclude_recursive)
        ),
        no_version=namespace.no_version,
        keep_version_specifier=namespace.keep_version_specifier,
        dependency_order=namespace.dependency_order,
        depth=namespace.depth,
        include_pointers=tuple(namespace.include_pointer),
        exclude_pointers=tuple(namespace.exclude_pointer),
    )


if __name__ == "__main__":
    main()
