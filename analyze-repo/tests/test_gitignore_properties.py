import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from analyze_repo.pipeline import list_working_tree_files

NAME_ALPHABET = "abcAB01.-_ "


@dataclass(frozen=True)
class WorkingTreeCase:
    """Generated files and the .gitignore contents written into each directory."""

    files: tuple[str, ...]
    ignore_files: Mapping[str, str]

    def describe(self) -> str:
        ignore_text = "\n".join(
            f"--- {directory or '.'}/.gitignore ---\n{contents!r}"
            for directory, contents in sorted(self.ignore_files.items())
        )
        return f"{ignore_text}\nfiles: {list(self.files)}"


def is_safe_name(name: str) -> bool:
    return name not in {"", ".", "..", ".git", ".gitignore"}


names = st.one_of(
    st.sampled_from(
        ["a", "b", "ab", "ba", "aa", "A", "build", "sub", ".hidden", "a.log", "x y"]
    ),
    st.sampled_from(["trail ", " lead", "-", "_x", "b.log", "a b"]),
    st.text(alphabet=NAME_ALPHABET, min_size=1, max_size=4),
).filter(is_safe_name)


@st.composite
def file_layouts(draw: st.DrawFn) -> tuple[tuple[str, ...], ...]:
    """Relative file paths as component tuples; no file is also a directory."""
    candidates = draw(
        st.lists(st.lists(names, min_size=1, max_size=4).map(tuple), max_size=12)
    )
    unique = set(candidates)
    return tuple(
        sorted(
            path
            for path in unique
            if not any(other[: len(path)] == path and other != path for other in unique)
        )
    )


pattern_atoms = st.one_of(
    names.map(lambda name: name.strip() or "a"),
    st.sampled_from(["a", "b", "build", "sub", ".hidden", "log", ".", " ", "-"]),
    st.sampled_from(["*", "**", "***", "?", "*.log", "a*", "*b", "?b", "**a"]),
    st.sampled_from(
        ["[ab]", "[!a]", "[^a]", "[a-c]", "[]a]", "[!]a]", "[.-b]", "[a-]", "[z-a]"]
    ),
    st.sampled_from(["[[:alpha:]]", "[[:digit:]x]", "[[:bogus:]]", "[a", "[/]"]),
    st.sampled_from(list("*?[!# \\/abAB.")).map(lambda char: "\\" + char),
)


@st.composite
def ignore_lines(draw: st.DrawFn) -> str:
    """One .gitignore line built to reach the corners of the pattern syntax."""
    kind = draw(st.sampled_from(["pattern", "pattern", "pattern", "comment", "raw"]))
    if kind == "comment":
        return draw(st.sampled_from(["", "#", "# a", "#a", "   "]))
    if kind == "raw":
        return draw(st.text(alphabet="ab*?[]!#/\\ .", max_size=6))
    segments = draw(
        st.lists(
            st.lists(pattern_atoms, min_size=1, max_size=3).map("".join),
            min_size=1,
            max_size=3,
        )
    )
    prefix = draw(st.sampled_from(["", "", "/", "!", "!/", "\\!", "\\#", "#", "//"]))
    suffix = draw(
        st.sampled_from(["", "", "/", " ", "  ", "\\ ", "\\", "\\\\ ", "/ ", "//"])
    )
    return prefix + "/".join(segments) + suffix


@st.composite
def ignore_contents(draw: st.DrawFn) -> str:
    lines = draw(st.lists(ignore_lines(), min_size=1, max_size=6))
    separator = draw(st.sampled_from(["\n", "\n", "\r\n"]))
    ending = draw(st.sampled_from(["", separator]))
    return separator.join(lines) + ending


@st.composite
def working_tree_cases(draw: st.DrawFn) -> WorkingTreeCase:
    layout = draw(file_layouts())
    directories = sorted(
        {"/".join(path[:depth]) for path in layout for depth in range(len(path))}
    )
    chosen = draw(
        st.lists(
            st.sampled_from(directories or [""]), min_size=1, max_size=4, unique=True
        )
    )
    ignore_files = {directory: draw(ignore_contents()) for directory in chosen}
    ignore_paths = [
        f"{directory}/.gitignore" if directory else ".gitignore"
        for directory in ignore_files
    ]
    files = tuple(sorted({*("/".join(path) for path in layout), *ignore_paths}))
    return WorkingTreeCase(files=files, ignore_files=ignore_files)


def write_case(root: Path, case: WorkingTreeCase) -> None:
    for relative in case.files:
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text("", encoding="utf-8")
    for directory, contents in case.ignore_files.items():
        (root / directory / ".gitignore").write_bytes(contents.encode("utf-8"))


def isolated_git_environment(home: Path) -> dict[str, str]:
    """Keeps the user's and the system's git configuration out of the oracle."""
    return {
        **os.environ,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home),
    }


def git_ignored_paths(root: Path, paths: Sequence[str]) -> set[str]:
    """The paths git reports ignored, with parent directories and nothing tracked."""
    environment = isolated_git_environment(root.parent)
    subprocess.run(["git", "init", "--quiet"], cwd=root, env=environment, check=True)
    completed = subprocess.run(
        ["git", "check-ignore", "--no-index", "-z", "--stdin"],
        cwd=root,
        env=environment,
        input="\0".join(paths).encode("utf-8"),
        capture_output=True,
        check=False,
    )
    if completed.returncode not in {0, 1}:
        raise RuntimeError(completed.stderr.decode("utf-8", errors="replace"))
    return {path for path in completed.stdout.decode("utf-8").split("\0") if path}


@settings(max_examples=300, deadline=None)
@given(case=working_tree_cases())
def test_list_working_tree_files_matches_git(
    tmp_path_factory: pytest.TempPathFactory, case: WorkingTreeCase
) -> None:
    """Arrange: a fresh git repository holding generated files and .gitignore files.
    Act: list the working tree and ask git which of the files it ignores.
    Assert: the listing is every generated file that git does not ignore."""
    root = tmp_path_factory.mktemp("case") / "tree"
    root.mkdir()
    write_case(root, case)
    ignored = git_ignored_paths(root, case.files)
    expected = sorted(path for path in case.files if path not in ignored)

    found = sorted(
        path.relative_to(root).as_posix() for path in list_working_tree_files(root)
    )

    assert found == expected, (
        f"{case.describe()}\nexpected (git): {expected}\nfound: {found}"
    )
