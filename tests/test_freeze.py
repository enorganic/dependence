from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from dependence._utilities import (
    get_required_distribution_names,
    get_requirement_string_distribution_name,
)
from dependence.freeze import get_frozen_requirements

if TYPE_CHECKING:
    from collections.abc import MutableSet
    from collections.abc import Set as AbstractSet


TEST_PROJECT_A: Path = (
    Path(__file__).absolute().parent.joinpath("test_projects/test_project_a/")
)
TEST_PROJECT_B: Path = (
    Path(__file__).absolute().parent.joinpath("test_projects/test_project_b/")
)
REQUIREMENTS_A: tuple[str, ...] = (
    str(TEST_PROJECT_A.joinpath("requirements.txt")),
    str(TEST_PROJECT_A.joinpath("setup.cfg")),
    str(TEST_PROJECT_A.joinpath("pyproject.toml")),
)


def test_freeze_order() -> None:
    """
    Verify the sorting of frozen requirements
    """
    error_messages: list[str] = []
    required: MutableSet[str] = set()
    requirement: str
    frozen_requirements: tuple[str, ...] = get_frozen_requirements(
        requirements=REQUIREMENTS_A, dependency_order=True
    )
    assert frozen_requirements
    for requirement in frozen_requirements:
        name: str = get_requirement_string_distribution_name(requirement)
        required_distribution_names: AbstractSet[str] = (
            get_required_distribution_names(requirement)
        )
        shared_required_distribution_names: AbstractSet[str] = (
            required & required_distribution_names
        )
        shared_required_distribution_name: str
        for (
            shared_required_distribution_name
        ) in shared_required_distribution_names:
            if name not in get_required_distribution_names(
                shared_required_distribution_name
            ):
                error_messages.append(  # noqa: PERF401
                    "Dependency sorting is incorrect: "
                    f"{name} should come before "
                    f"{shared_required_distribution_name}"
                )
        required.add(name)
    if error_messages:
        error_messages.insert(0, "\n")
        error_messages.append(
            "\nRequirements:\n\n{}".format("\n".join(required))
        )
        raise RuntimeError("\n".join(error_messages))


def test_freeze_cli() -> None:
    pass


if __name__ == "__main__":
    pytest.main(["-vv", __file__])
