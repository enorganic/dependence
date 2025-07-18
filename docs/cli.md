# Command Line Interface

```console
$ dependence -h
Usage:
  dependence <command> [options]

Commands:
  update                      Update requirement versions in the specified
                              files to align with currently installed versions
                              of each distribution
  freeze                      Print dependencies inferred from an installed
                              distribution or project, in a similar format
                              to the output of `pip freeze`.
  upgrade                     Upgrade all dependencies and align project
                              requirement specifiers to match.
```

## dependence update

This command will update version specifiers for
all package requirements in your setup.cfg, pyproject.toml, tox.ini,
or requirements.txt files to match currently installed versions of each
distribution (matching the existing granularity, and only for *inclusive*
specifiers—so where the comparator is "~=", "==", ">=", or "<=", but not where
the comparator is ">", "<", or "!=").

```console
$ dependence update -h
usage: dependence update [-h] [-i IGNORE] [-aen ALL_EXTRA_NAME]
                         [--include-pointer INCLUDE_POINTER]
                         [--exclude-pointer EXCLUDE_POINTER]
                         path [path ...]

Update requirement versions in the specified files to align with currently
installed versions of each distribution.

positional arguments:
  path                  One or more local paths to a *.toml, setup.cfg,
                        and/or requirements.txt file

optional arguments:
  -h, --help            show this help message and exit
  -i IGNORE, --ignore IGNORE
                        A comma-separated list of distributions to ignore
                        (leave any requirements pertaining to the package
                        as-is)
  -aen ALL_EXTRA_NAME, --all-extra-name ALL_EXTRA_NAME
                        If provided, an extra which consolidates the
                        requirements for all other extras will be
                        added/updated to pyproject.toml or setup.cfg (this
                        argument is ignored for requirements.txt files and
                        other TOML files)
  --include-pointer INCLUDE_POINTER
                        One or more JSON pointers of elements to *include*
                        (applies to TOML files only)
  --exclude-pointer EXCLUDE_POINTER
                        One or more JSON pointers of elements to *exclude*
                        (applies to TOML files only)
```

Example:

```bash
dependence update -aen all setup.cfg pyproject.toml tox.ini
```

## dependence freeze

```console
$ dependence freeze -h
usage: dependence freeze [-h] [-e EXCLUDE] [-er EXCLUDE_RECURSIVE]
                         [-nv NO_VERSION] [-do] [--reverse] [-d DEPTH]
                         [--include-pointer INCLUDE_POINTER]
                         [--exclude-pointer EXCLUDE_POINTER]
                         requirement [requirement ...]

This command prints dependencies inferred from an installed distribution
or project, in a similar format to the output of `pip freeze`, except that
all generated requirements are specified in the format "distribution-
name==0.0.0" (including for editable installations). Using this command
instead of `pip freeze` to generate requirement files ensures that you
don't bloat your requirements files with superfluous distributions.

positional arguments:
  requirement           One or more requirement specifiers (for example:
                        "requirement-name", "requirement-
                        name[extra-a,extra-b]", ".[extra-a, extra-b]" or
                        "../other-editable-package-directory[extra-a,
                        extra-b]) and/or paths to a setup.py, setup.cfg,
                        pyproject.toml, tox.ini or requirements.txt file

optional arguments:
  -h, --help            show this help message and exit
  -e EXCLUDE, --exclude EXCLUDE
                        A distribution (or comma-separated list of
                        distributions) to exclude from the output
  -er EXCLUDE_RECURSIVE, --exclude-recursive EXCLUDE_RECURSIVE
                        A distribution (or comma-separated list of
                        distributions) to exclude from the output. Unlike
                        -e / --exclude, this argument also precludes
                        recursive requirement discovery for the specified
                        packages, thereby excluding all of the excluded
                        package's requirements which are not required by
                        another (non-excluded) distribution.
  -nv NO_VERSION, --no-version NO_VERSION
                        Don't include versions (only output distribution
                        names) for packages matching this/these glob
                        pattern(s) (note: the value must be single-quoted
                        if it contains wildcards)
  -do, --dependency-order
                        Sort requirements so that dependents precede
                        dependencies
  --reverse             Print requirements in reverse order
  -d DEPTH, --depth DEPTH
                        Depth of recursive requirement discovery
  --include-pointer INCLUDE_POINTER
                        One or more JSON pointers of elements to *include*
                        (applies to TOML files only)
  --exclude-pointer EXCLUDE_POINTER
                        One or more JSON pointers of elements to *exclude*
                        (applies to TOML files only)
```

## dependence upgrade

```console
$ dependence upgrade -h
usage: dependence upgrade [-h] [-iu IGNORE_UPDATE] [-aen ALL_EXTRA_NAME]
                          [--include-pointer INCLUDE_POINTER]
                          [--exclude-pointer EXCLUDE_POINTER] [-e EXCLUDE]
                          [-er EXCLUDE_RECURSIVE] [-d DEPTH]
                          requirement [requirement ...]

Upgrade all dependencies for specified packages/projects, then upgrade
version specifiers in the project files to align with newly installed
versions of each distribution.

positional arguments:
  requirement           One or more requirement specifiers (for example:
                        "requirement-name", "requirement-
                        name[extra-a,extra-b]", ".[extra-a, extra-b]" or
                        "../other-editable-package-directory[extra-a,
                        extra-b]) and/or paths to a setup.py, setup.cfg,
                        pyproject.toml, tox.ini or requirements.txt file

optional arguments:
  -h, --help            show this help message and exit
  -iu IGNORE_UPDATE, --ignore-update IGNORE_UPDATE
                        A comma-separated list of distributions to ignore
                        (leave any requirements pertaining to the package
                        as-is) when updating project files
  -aen ALL_EXTRA_NAME, --all-extra-name ALL_EXTRA_NAME
                        If provided, an extra which consolidates the
                        requirements for all other extras will be
                        added/updated to pyproject.toml or setup.cfg (this
                        argument is ignored for requirements.txt files and
                        other TOML files)
  --include-pointer INCLUDE_POINTER
                        One or more JSON pointers of elements to *include*
                        (applies to TOML files only)
  --exclude-pointer EXCLUDE_POINTER
                        One or more JSON pointers of elements to *exclude*
                        (applies to TOML files only)
  -e EXCLUDE, --exclude EXCLUDE
                        A distribution (or comma-separated list of
                        distributions) to exclude when performing upgrades
  -er EXCLUDE_RECURSIVE, --exclude-recursive EXCLUDE_RECURSIVE
                        A distribution (or comma-separated list of
                        distributions) to exclude when performing upgrades.
                        Unlike -e / --exclude, this argument also precludes
                        recursive requirement discovery for the specified
                        packages, thereby excluding all of the excluded
                        package's requirements which are not required by
                        another (non-excluded) distribution from the
                        upgrade.
  -d DEPTH, --depth DEPTH
                        Depth of recursive requirement discovery
```

