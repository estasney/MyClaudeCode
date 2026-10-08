from collections.abc import Mapping
from pathlib import Path

import pytest

from analyze_repo.analyzer import RepoAnalyzer, indexer_registry
from analyze_repo.orm.engine import run_migrations
from analyze_repo.settings import Settings
from tests.fakes import ScriptedSummarizer, WordHashEmbedder


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


@pytest.fixture
def summarizer() -> ScriptedSummarizer:
    """A test overrides this by parametrizing `summarizer` directly."""
    return ScriptedSummarizer(failing=frozenset(), blocking=frozenset())


@pytest.fixture
def embedder() -> WordHashEmbedder:
    """A test overrides this by parametrizing `embedder` directly."""
    return WordHashEmbedder()


@pytest.fixture
def analyzer(
    tmp_path: Path, embedder: WordHashEmbedder, summarizer: ScriptedSummarizer
) -> RepoAnalyzer:
    """One summary at a time so tests see summaries requested in source order and
    one text per embedding batch so a small tree spans several batches."""
    settings = Settings(
        data_dir=tmp_path / "data", summary_concurrency=1, embedding_batch_size=1
    )
    run_migrations(settings.db_path)
    return RepoAnalyzer(settings, embedder, summarizer, indexer_registry())
