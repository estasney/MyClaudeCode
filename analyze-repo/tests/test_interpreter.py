from collections.abc import Sequence
from pathlib import Path

import pytest

from analyze_repo.interpreter import (
    AmbiguousInterpreterError,
    PosixVenvLayout,
    PythonToolchainDiscovery,
)


@pytest.mark.parametrize(
    ("relative_paths", "expected"),
    [
        (
            ["repo/tools-env/pyvenv.cfg", "repo/tools-env/bin/python"],
            "tools-env/bin/python",
        ),
        (["repo/venv/bin/python"], None),
        (["repo/venv/pyvenv.cfg"], None),
        (["repo/src/pkg.py"], None),
        (["above/pyvenv.cfg", "above/bin/python", "repo/src/pkg.py"], None),
    ],
    ids=[
        "any directory name qualifies",
        "python without pyvenv.cfg is not a venv",
        "pyvenv.cfg without python is not a venv",
        "nothing to find",
        "the parent directory is not searched",
    ],
)
def test_get_toolchain_finds_the_single_venv_under_root(
    tmp_path: Path, relative_paths: Sequence[str], expected: str | None
) -> None:
    """Arrange: files laid out around a repo root.
    Act: discover the toolchain for that root.
    Assert: the interpreter of the one PEP 405 venv directly under the root or None."""
    for relative in relative_paths:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        path.chmod(0o755)
    root = tmp_path / "repo"
    root.mkdir(exist_ok=True)
    found = PythonToolchainDiscovery(PosixVenvLayout()).get_toolchain(root)
    expected_path = None if expected is None else root / expected
    assert found == expected_path, f"{root} should yield {expected_path}, got {found}"


def test_get_toolchain_rejects_several_venvs(tmp_path: Path) -> None:
    """Arrange: two venvs directly under the root.
    Act: discover the toolchain.
    Assert: the ambiguity is raised rather than resolved by a guess."""
    for venv in ("a", "b"):
        (tmp_path / venv / "bin").mkdir(parents=True)
        (tmp_path / venv / "pyvenv.cfg").write_text("", encoding="utf-8")
        (tmp_path / venv / "bin" / "python").write_text("", encoding="utf-8")
        (tmp_path / venv / "bin" / "python").chmod(0o755)
    with pytest.raises(AmbiguousInterpreterError):
        PythonToolchainDiscovery(PosixVenvLayout()).get_toolchain(tmp_path)
