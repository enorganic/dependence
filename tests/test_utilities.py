from __future__ import annotations

import shutil

import pytest

from dependence._utilities import check_output, is_aliased


def test_is_aliased() -> None:
    if is_aliased("ls"):
        shell_output: str = check_output(
            ("which", "ls"),
            shell=True,
        )
        message: str = f"{shell_output}\n!=\n{shutil.which('ls')}"
        raise ValueError(message)


if __name__ == "__main__":
    pytest.main([__file__, "-vv", "-s"])
