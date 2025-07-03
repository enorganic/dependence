# dependence

[![test](https://github.com/enorganic/dependence/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/enorganic/dependence/actions/workflows/test.yml)
[![PyPI version](https://badge.fury.io/py/dependence.svg?icon=si%3Apython)](https://badge.fury.io/py/dependence)

Dependence provides a Command Line Interface and library for performing
dependency upgrades on a python project, aligning declared dependencies with
the package versions installed in the environment in which `dependence` is
executed, and for "freezing" recursively resolved package dependencies
(like `pip freeze`, but for a package, instead of the entire environment).

- [Documentation](https://enorganic.github.io/dependence/)
- [Contributing](https://enorganic.github.io/dependence/contributing)

## Installation

You can install `dependence` with pip:

```shell
pip3 install dependence
```

## Usage

### Upgrading Dependencies

The `dependence upgrade` command, and the `dependence.upgrade.upgrade`
function, discover and upgrade project and environment dependencies in the
environment in which dependence is installed to their latest version
aligned with project and dependency requirements, then selectively update
requirement specifiers in any specified TOML files (such as pyproject.toml),
setup.cfg file, requirements.txt files, or tox.ini files. Because
pyproject.toml files may contain dependencies for more than one environment,
such as when using [hatch](https://hatch.pypa.io/) environments,
[JSON-style pointers](https://datatracker.ietf.org/doc/html/rfc6901) are used
to include or exclude specific parts of TOML files.

For example, in [this project's Makefile
](https://github.com/enorganic/dependence/blob/main/Makefile#L27), we define a
`make upgrade` target as follows:

```Makefile
SHELL := bash
PYTHON_VERSION := 3.9

upgrade:
    hatch run dependence upgrade\
     --include-pointer /tool/hatch/envs/default\
     --include-pointer /project\
     pyproject.toml && \
    hatch run docs:dependence upgrade\
     --include-pointer /tool/hatch/envs/docs\
     --include-pointer /project\
     pyproject.toml && \
    hatch run hatch-static-analysis:dependence upgrade\
     --include-pointer /tool/hatch/envs/docs\
     --include-pointer /project\
     pyproject.toml && \
    hatch run hatch-test.py$(PYTHON_VERSION):dependence upgrade\
     --include-pointer /tool/hatch/envs/hatch-test\
     --include-pointer /project\
     pyproject.toml && \
    make requirements
```

You can reference the [associated pyproject.toml file for this project
](https://github.com/enorganic/dependence/blob/main/pyproject.toml#L21)
for reference concerning the implications of `--include-pointer`, which
uses identical syntax to [JSON pointers
](https://datatracker.ietf.org/doc/html/rfc6901). The `--exclude-pointer`
parameter works identically, but in reverse. If both `--include-pointer`
and `--exclude-pointer` are used, only sections which match both conditions
will be updated.

You may refer to the [`dependence upgrade` CLI reference](./cli.md#dependence-upgrade)
and/or [`dependence.upgrade` API reference](./api/upgrade.md) for details
concerning this command/module, related options, and more complex use case
examples.

The `dependence upgrade` command, and the `dependence.upgrade.upgrade`
function, are simply a composite of the dependency listing and update
functionalities covered below, but which a `pip install --upgrade`
command executed in between—so please read further for additional details.
All parameters are directly passed, with the exception of
`--ignore-update`/`ignore_update`, which is translated to the
`--ignore`/`ignore` parameter for
`dependence update`/`dependence.update.update` (renamed in this operation
for clarity of purpose).

### Listing Dependencies

The `dependence freeze` command, and the `dependence.freeze.freeze` function,
print all requirements for one or more specified python project,
requirements.txt, pyproject.toml, setup.cfg, or tox.ini files. The output
format matches that of `pip freeze`, but only lists dependencies of indicated
packages and/or editable project locations.

You may refer to the [`dependence freeze` CLI reference](./cli.md#dependence-freeze)
and/or [`dependence.freeze` API reference](./api/freeze.md) for details
concerning this command/module, related options, and more complex use case
examples.

We'll use this project, `dependence`, as a simple example. To start with, let's
see what the currently installed dependencies for this package look like
at the time of writing:

```console
$ dependence freeze .
packaging==24.1
pip==24.3.0
setuptools==75.1.0
tomli==2.1.0
tomli_w==1.0.0
```

...now let's save this output for later comparison purposes:

```bash
dependence freeze . > requirements_before.txt
```

Now, we'll upgrade our dependencies and see what they look like after:

```console
$ pip install -q --upgrade --upgrade-strategy eager . && dependence freeze .
packaging==24.2
pip==24.3.1
setuptools==75.3.0
tomli==2.2.1
tomli_w==1.0.0
```

...next let's dump them to a file and compare them with our previous
dependencies:

```console
$ dependence freeze . > dependence_after.txt
$ diff dependence_before.txt dependence_after.txt
1,5c1,5
< packaging==24.1
< pip==24.3.0
< setuptools==75.1.0
< tomli==2.1.0
< tomli_w==1.0.0
---
> packaging==24.2
> pip==24.3.1
> setuptools==75.3.0
> tomli==2.2.1
> tomli_w==1.0.1
```

As you can see above, *all* of our dependencies have been upgraded.

### Updating Requirement Specifiers

To start with, let's take a look at our pyproject.toml file:

```toml
[project]
name = "dependence"
version = "1.0.0"
dependencies = [
    "packaging>23",
    "pip",
    "setuptools>63",
    "tomli-w~=1.0",
    "tomli~=2.1",
]
```

Now that we've upgraded our dependencies, we want to update our
pyproject.toml file to align with our upgraded dependencies. This is desirable
to ensure that `dependence` isn't installed alongside a version of one of its
dependencies preceding functionality utilized by `dependence`.

```bash
dependence update pyproject.toml
```

Afterwards, our pyproject.toml file looks like this:

```toml
[project]
name = "dependence"
version = "1.0.0"
dependencies = [
    "packaging>23",
    "pip",
    "setuptools>63",
    "tomli-w~=1.0",
    "tomli~=2.2",
]
```

Here's the diff:

```console
$ diff pyproject_before.toml pyproject_after.toml
9c9
<     "tomli~=2.1",
---
>     "tomli~=2.2",
```

As you can see, only the version specifier for tomli changed. We know that
every dependency was upgraded, so why was only the `tomli` version specifier
updated? By design. Here are the rules `dependence update` adheres to:

-   We only update requirements versions when they have *inclusive* specifiers.
    For example, `~=`, `>=`, and `<=` are inclusive, whereas `!=`, `>`, and
    `<` are *exclusive*. For this reason, nothing changed for
    "packaging" and "setuptools" in our above example.
-   We always retain the existing level of specificity. If your version
    specifier is `~=1.2`, and the new version is `1.5.6`, we're going to
    update your specifier to `~=1.5`. If your requirement has a minor version
    level of specificity, and only a patch version upgrade is performed,
    nothing will change in your project dependency specifier. This is why
    you do not see any change in our above pyproject.toml file for the
    `tomli-w` dependency—both new and old share the same minor version.
-   If your requirement is unversioned, we don't touch it, of course. This is
    why you didn't see any change for "pip".

You may refer to the [`dependence update` CLI reference](./cli.md#dependence-update)
and/or [`dependence.update` API reference](./api/update.md) for details
concerning this command/module, related options, and more complex use
cases/examples.
