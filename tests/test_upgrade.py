from __future__ import annotations

import sys
from pathlib import Path
from shutil import copytree

import pytest

from dependence._utilities import check_output
from dependence.upgrade import upgrade

TEST_DIRECTORY: Path = Path(__file__).absolute().parent
TEST_PROJECT_C: Path = (
    Path(__file__).absolute().parent.joinpath("test_projects/test_project_c/")
)


def test_upgrade(
    temp_directory: Path,
) -> None:
    """
    Test `dependence.upgrade.upgrade()`
    """
    source_project: Path = TEST_DIRECTORY / "test_projects/test_project_b"
    temp_project: Path = temp_directory / "test_project_b"
    copytree(source_project, temp_project)
    pyproject_toml: str
    with (
        open(source_project / "pyproject.toml") as source_pyproject_io,
        open(temp_project / "pyproject.toml", "w") as temp_pyproject_io,
    ):
        pyproject_toml = source_pyproject_io.read().replace("~=", ">=")
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
