from __future__ import annotations

import pytest

from dependence._utilities import is_aliased


def test_is_aliased() -> None:
    assert not is_aliased("ls")


if __name__ == "__main__":
    pytest.main([__file__, "-vv", "-s"])
