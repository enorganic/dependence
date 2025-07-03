from collections.abc import Iterable
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp

import pytest


@pytest.fixture(name="temp_directory", autouse=True, scope="session")
def get_temp_directory() -> Iterable[Path]:
    """
    Create a temporary directory for testing, then cleanup after tests
    have been run.
    """
    temp_directory: Path = Path(mkdtemp()).absolute()
    yield temp_directory
    rmtree(temp_directory, ignore_errors=True)
