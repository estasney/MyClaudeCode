import asyncio
import hashlib
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from analyze_repo import orm
from analyze_repo.gitignore import IgnoreScope, is_ignored, parse_gitignore
from analyze_repo.indexer import RepoIndex, persist_index

__all__ = [
    "IndexerRegistration",
    "LanguageIndexer",
    "WorkingTree",
    "build_indexers",
    "build_indexes",
    "describe_working_tree",
    "index_working_tree",
    "list_working_tree_files",
    "working_tree_digest",
]


class LanguageIndexer(Protocol):
    """Indexes the files of one language under a repository root."""

    @property
    def language(self) -> orm.Language: ...

    def index(self, root: Path, files: Sequence[Path]) -> RepoIndex: ...


@dataclass(frozen=True)
class IndexerRegistration:
    """Builds one language's indexer from the path of that language's toolchain."""

    language: orm.Language
    build: Callable[[Path], LanguageIndexer]


def build_indexers(
    registry: Mapping[str, IndexerRegistration],
    toolchains: Mapping[orm.Language, Path],
) -> dict[str, LanguageIndexer]:
    """One indexer per language that has a toolchain, shared by every suffix it registers."""
    by_language: dict[orm.Language, LanguageIndexer] = {}
    indexers: dict[str, LanguageIndexer] = {}
    for suffix, registration in registry.items():
        toolchain = toolchains.get(registration.language)
        if toolchain is None:
            continue
        if registration.language not in by_language:
            by_language[registration.language] = registration.build(toolchain)
        indexers[suffix] = by_language[registration.language]
    return indexers


@dataclass(frozen=True)
class WorkingTree:
    """Every file under root that no .gitignore excludes, and a digest of their contents."""

    root: Path
    files: Sequence[Path]
    digest: str


def list_working_tree_files(root: Path) -> list[Path]:
    """Every file under root, minus the .git directory and what .gitignore files exclude."""
    files: list[Path] = []
    pending: list[tuple[Path, tuple[IgnoreScope, ...]]] = [(root, ())]
    while pending:
        directory, scopes = pending.pop()
        ignore_file = directory / ".gitignore"
        if ignore_file.is_file():
            rules = parse_gitignore(ignore_file.read_text().splitlines())
            scopes = (*scopes, IgnoreScope(directory=directory, rules=rules))
        for entry in sorted(directory.iterdir(), reverse=True):
            is_directory = entry.is_dir()
            if is_directory and entry.name == ".git":
                continue
            if is_ignored(scopes, entry, is_directory=is_directory):
                continue
            if is_directory:
                pending.append((entry, scopes))
            else:
                files.append(entry)
    return files


def working_tree_digest(root: Path, files: Sequence[Path]) -> str:
    """Changes when any listed file is added, removed, renamed or edited."""
    digest = hashlib.sha256()
    for path in sorted(files):
        content = path.read_bytes()
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(str(len(content)).encode())
        digest.update(b"\0")
        digest.update(content)
    return digest.hexdigest()


def describe_working_tree(repo_root: Path) -> WorkingTree:
    root = repo_root.resolve()
    files = list_working_tree_files(root)
    return WorkingTree(root=root, files=files, digest=working_tree_digest(root, files))


def build_indexes(
    tree: WorkingTree, indexers: Mapping[str, LanguageIndexer]
) -> list[RepoIndex]:
    """Routes each file by suffix; an indexer with no files is not started. Blocking; run in a thread."""
    files_by_indexer: defaultdict[LanguageIndexer, list[Path]] = defaultdict(list)
    for path in tree.files:
        indexer = indexers.get(path.suffix)
        if indexer is not None:
            files_by_indexer[indexer].append(path)
    return [
        indexer.index(tree.root, files) for indexer, files in files_by_indexer.items()
    ]


async def get_or_create_repo(session: AsyncSession, root: Path) -> orm.Repo:
    repo = await session.scalar(select(orm.Repo).where(orm.Repo.location == str(root)))
    if repo is None:
        repo = orm.Repo(name=root.name, location=str(root))
        session.add(repo)
    return repo


async def find_snapshot(
    session: AsyncSession, repo: orm.Repo, digest: str
) -> orm.Snapshot | None:
    return await session.scalar(
        select(orm.Snapshot)
        .where(orm.Snapshot.repo == repo)
        .where(orm.Snapshot.digest == digest)
    )


async def index_working_tree(
    session: AsyncSession, repo_root: Path, indexers: Mapping[str, LanguageIndexer]
) -> orm.Snapshot:
    """Indexes the working tree once per content digest; an unchanged tree returns the stored snapshot."""
    tree = await asyncio.to_thread(describe_working_tree, repo_root)
    repo = await get_or_create_repo(session, tree.root)
    snapshot = await find_snapshot(session, repo, tree.digest)
    if snapshot is not None:
        return snapshot
    indexes = await asyncio.to_thread(build_indexes, tree, indexers)
    snapshot = orm.Snapshot(repo=repo, digest=tree.digest)
    session.add(snapshot)
    for index in indexes:
        await persist_index(session, snapshot, tree.root, index)
    return snapshot
