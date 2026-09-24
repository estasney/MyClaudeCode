from pathlib import Path

import pytest

from analyze_repo.pipeline import list_working_tree_files


@pytest.mark.parametrize(
    ("working_tree", "expected"),
    [
        (
            {"a.py": "x = 1\n", "notes.md": "# notes\n", "sub/b.py": "y = 2\n"},
            ["a.py", "notes.md", "sub/b.py"],
        ),
        (
            {".gitignore": "build/\n", "a.py": "x = 1\n", "build/b.py": "y = 2\n"},
            [".gitignore", "a.py"],
        ),
        (
            {
                ".gitignore": "*.log\n",
                "a.py": "x = 1\n",
                "sub/.gitignore": "!keep.log\n",
                "sub/keep.log": "",
                "sub/drop.log": "",
            },
            [".gitignore", "a.py", "sub/.gitignore", "sub/keep.log"],
        ),
        (
            {".gitignore": "/a.py\n", "a.py": "x = 1\n", "sub/a.py": "y = 2\n"},
            [".gitignore", "sub/a.py"],
        ),
        (
            {".gitignore": "build\n!build/keep.py\n", "build/keep.py": "z = 3\n"},
            [".gitignore"],
        ),
    ],
    indirect=["working_tree"],
    ids=[
        "no .gitignore lists every file",
        "root .gitignore excludes a directory",
        "nested .gitignore re-includes below its directory",
        "leading slash anchors to the .gitignore directory",
        "negation cannot re-include below an excluded directory",
    ],
)
def test_list_working_tree_files_applies_gitignore(
    working_tree: Path, expected: list[str]
) -> None:
    """Arrange: a directory with files and zero or more .gitignore files.
    Act: list the working tree.
    Assert: every file is listed except those a .gitignore excludes, as git decides it."""
    found = sorted(
        path.relative_to(working_tree).as_posix()
        for path in list_working_tree_files(working_tree)
    )
    assert found == expected, f"{working_tree} should list {expected}, got {found}"
