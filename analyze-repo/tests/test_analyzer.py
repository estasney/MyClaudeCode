import asyncio
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from analyze_repo.analyzer import RepoAnalyzer
from analyze_repo.models import SymbolScope
from analyze_repo.orm import Language
from analyze_repo.semantic.summarize import SummariesFailedError
from tests.fakes import FailingOnceEmbedder, ScriptedSummarizer, WordHashEmbedder


@pytest.mark.parametrize(
    ("working_tree", "summarizer"),
    [
        (
            {
                "lib.py": dedent("""\
                    def first() -> int:
                        return 1


                    def second() -> int:
                        return 2


                    def third() -> int:
                        return 3
                    """),
            },
            ScriptedSummarizer(failing=frozenset(), blocking=frozenset({"third"})),
        ),
    ],
    indirect=["working_tree"],
    ids=["third summary never answers"],
)
@pytest.mark.asyncio
async def test_summarize_repository_keeps_summaries_saved_before_an_interruption(
    analyzer: RepoAnalyzer, summarizer: ScriptedSummarizer, working_tree: Path
) -> None:
    """Arrange: three functions and a summarizer that never answers for the third.
    Act: summarize the snapshot and cancel the run once the third is requested.
    Assert: the first two summaries survive the cancelled run."""
    indexed = await analyzer.index_repository(
        working_tree, {Language.python: Path(sys.executable)}
    )
    snapshot_id = indexed.snapshot.snapshot_id
    run = asyncio.create_task(analyzer.summarize_repository(snapshot_id))
    await summarizer.blocked.wait()
    run.cancel()
    with pytest.raises(asyncio.CancelledError):
        await run
    found = await analyzer.search_symbols(snapshot_id, "", SymbolScope.module_and_class)
    summaries = {symbol.qualified_name: symbol.summary for symbol in found}
    expected = {
        "first": "describes first",
        "second": "describes second",
        "third": None,
    }
    assert summaries == expected, (
        f"summaries finished before the cancel should be saved, got {summaries}"
    )


@pytest.mark.parametrize(
    ("working_tree", "summarizer"),
    [
        (
            {
                "lib.py": dedent("""\
                    def first() -> int:
                        return 1


                    def second() -> int:
                        return 2


                    def third() -> int:
                        return 3
                    """),
            },
            ScriptedSummarizer(failing=frozenset({"second"}), blocking=frozenset()),
        ),
    ],
    indirect=["working_tree"],
    ids=["second summary fails"],
)
@pytest.mark.asyncio
async def test_summarize_repository_saves_the_others_and_retries_only_a_failure(
    analyzer: RepoAnalyzer, summarizer: ScriptedSummarizer, working_tree: Path
) -> None:
    """Arrange: three functions and a summarizer that fails on the second.
    Act: summarize the snapshot twice.
    Assert: both runs fail and the second run requests only the failed summary
    while the first run saved the other two."""
    indexed = await analyzer.index_repository(
        working_tree, {Language.python: Path(sys.executable)}
    )
    snapshot_id = indexed.snapshot.snapshot_id
    with pytest.raises(SummariesFailedError):
        await analyzer.summarize_repository(snapshot_id)
    with pytest.raises(SummariesFailedError):
        await analyzer.summarize_repository(snapshot_id)
    assert summarizer.requested == ["first", "second", "third", "second"], (
        f"the rerun should request only the failed summary, got {summarizer.requested}"
    )
    found = await analyzer.search_symbols(snapshot_id, "", SymbolScope.module_and_class)
    summaries = {symbol.qualified_name: symbol.summary for symbol in found}
    expected = {
        "first": "describes first",
        "second": None,
        "third": "describes third",
    }
    assert summaries == expected, (
        f"summaries other than the failed one should be saved, got {summaries}"
    )


@pytest.mark.parametrize(
    ("working_tree", "embedder"),
    [
        (
            {
                "lib.py": dedent("""\
                    def first() -> int:
                        return 1


                    def second() -> int:
                        return 2


                    def third() -> int:
                        return 3
                    """),
            },
            FailingOnceEmbedder(failing_call=2),
        ),
    ],
    indirect=["working_tree"],
    ids=["second batch fails"],
)
@pytest.mark.asyncio
async def test_index_repository_resumes_from_the_batches_saved_before_a_failure(
    analyzer: RepoAnalyzer, embedder: FailingOnceEmbedder, working_tree: Path
) -> None:
    """Arrange: three functions embedded one text per batch by an embedder that
    fails on its second batch.
    Act: index the tree and index it again after the failure.
    Assert: each text is embedded once across both runs."""
    overrides = {Language.python: Path(sys.executable)}
    with pytest.raises(RuntimeError, match="scripted failure"):
        await analyzer.index_repository(working_tree, overrides)
    await analyzer.index_repository(working_tree, overrides)
    assert len(embedder.embedded) == len(set(embedder.embedded)) == 3, (
        f"each of the three texts should be embedded once, got {embedder.embedded}"
    )


@pytest.mark.parametrize(
    "working_tree",
    [
        {
            "lib.py": dedent("""\
                def first() -> int:
                    return 1
                """),
        },
    ],
    indirect=True,
    ids=["one function"],
)
@pytest.mark.asyncio
async def test_summarize_repository_embeds_the_documents_that_gained_a_summary(
    analyzer: RepoAnalyzer, embedder: WordHashEmbedder, working_tree: Path
) -> None:
    """Arrange: an indexed function without a summary.
    Act: summarize the snapshot.
    Assert: the function's document is embedded again with its summary."""
    indexed = await analyzer.index_repository(
        working_tree, {Language.python: Path(sys.executable)}
    )
    embedded_before = len(embedder.embedded)
    await analyzer.summarize_repository(indexed.snapshot.snapshot_id)
    texts = embedder.embedded[embedded_before:]
    assert len(texts) == 1 and "describes first" in texts[0], (
        f"only the summarized document should be embedded again, got {texts}"
    )
