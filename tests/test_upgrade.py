from __future__ import annotations

import sys
from importlib.metadata import version
from os import getenv
from pathlib import Path
from shutil import copytree

import pytest
from packaging.requirements import Requirement

from dependence._utilities import check_output
from dependence.upgrade import upgrade

TEST_DIRECTORY: Path = Path(__file__).absolute().parent
TEST_PROJECT_C: Path = (
    Path(__file__).absolute().parent.joinpath("test_projects/test_project_c/")
)


def test_upgrade(
    temp_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test `dependence.upgrade.upgrade()`
    """
    dependency_requirement: str | None = getenv("DEPENDENCE_TEST_REQUIREMENT")
    dependency_name: str = (
        Requirement(dependency_requirement).name
        if dependency_requirement
        else ""
    )
    if dependency_requirement and dependency_name not in ("pip", "setuptools"):
        # Keep the selected dependency major throughout the upgrade operation.
        constraints_path: Path = temp_directory / "constraints.txt"
        constraints_path.write_text(f"{dependency_requirement}\n")
        monkeypatch.setenv("PIP_CONSTRAINT", str(constraints_path))
        monkeypatch.setenv("UV_CONSTRAINT", str(constraints_path))
    source_project: Path = TEST_DIRECTORY / "test_projects/test_project_b"
    temp_project: Path = temp_directory / "test_project_b"
    copytree(source_project, temp_project)
    pyproject_toml: str
    with (
        open(source_project / "pyproject.toml") as source_pyproject_io,
        open(temp_project / "pyproject.toml", "w") as temp_pyproject_io,
    ):
        pyproject_toml = source_pyproject_io.read().replace("~=", ">=")
        if dependency_requirement and dependency_name == "jsonpointer":
            pyproject_toml = pyproject_toml.replace(
                "jsonpointer>=2.0", f"jsonpointer=={version(dependency_name)}"
            )
        assert temp_pyproject_io.write(pyproject_toml)
    check_output(
        (sys.executable, "-m", "pip", "install", "-e", str(temp_project)),
    )
    try:
        upgrade(
            requirements=(str(temp_project),),
            exclude=("pip", "setuptools"),
            all_extra_name="all",
            echo=True,
        )
        if dependency_requirement:
            assert (
                version(dependency_name)
                in Requirement(dependency_requirement).specifier
            )
        with open(temp_project / "pyproject.toml") as temp_pyproject_io:
            assert temp_pyproject_io.read() != pyproject_toml
    finally:
        check_output(
            (
                sys.executable,
                "-m",
                "pip",
                "uninstall",
                "-y",
                "test-project-b",
            ),
        )


if __name__ == "__main__":
    pytest.main()
