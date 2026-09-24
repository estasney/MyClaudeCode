from collections.abc import Mapping
from pathlib import Path

import pytest


def write_files(root: Path, files: Mapping[str, str]) -> None:
    for name, source in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(source, encoding="utf-8")


@pytest.fixture
def working_tree(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    """A directory holding the files of the parameter, keyed by relative path."""
    files: Mapping[str, str] = request.param
    root = tmp_path / "working_tree"
    root.mkdir()
    write_files(root, files)
    return root
