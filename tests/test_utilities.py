from __future__ import annotations

import shutil

import pytest

from dependence._utilities import WHICH, check_output, is_aliased


def test_is_aliased() -> None:
    command: str = "ping"
    if is_aliased(command):
        shell_output: str = check_output(
            (WHICH, command),
            shell=True,
        )
        message: str = f"{shell_output}\n!=\n{shutil.which(command)}"
        raise ValueError(message)


if __name__ == "__main__":
    pytest.main([__file__, "-vv", "-s"])
