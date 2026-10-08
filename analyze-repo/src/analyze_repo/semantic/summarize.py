import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from analyze_repo import orm
from analyze_repo.settings import Settings


class SummaryFailedError(RuntimeError):
    def __init__(self, qualified_name: str, detail: str) -> None:
        super().__init__(f"summary of {qualified_name} failed: {detail}")


class SummariesFailedError(ExceptionGroup[SummaryFailedError]):
    """The failures of a run whose other summaries were saved."""


class Summarizer(Protocol):
    """Describes one symbol from its body."""

    async def summarize(self, symbol: orm.Symbol, body: str) -> orm.Summary: ...


def summarizable_kinds() -> tuple[orm.SymbolKind, ...]:
    """Only bodies with logic are worth a model's description."""
    return (orm.SymbolKind.class_, orm.SymbolKind.function, orm.SymbolKind.method)


def body_text(repo_root: Path, symbol: orm.Symbol) -> str:
    """The same line slice `hash_lines` hashed at index time."""
    lines = (repo_root / symbol.file.path).read_bytes().split(b"\n")
    return b"\n".join(lines[symbol.start_line : symbol.end_line + 1]).decode("utf-8")


def summary_prompt(symbol: orm.Symbol, body: str) -> str:
    return (
        f"Describe the {symbol.kind.value} `{symbol.qualified_name}` from "
        f"`{symbol.file.path}` in at most three sentences: what it does, "
        "what it takes, and what it returns or changes. "
        "Reply with the description only.\n\n"
        f"```python\n{body}\n```"
    )


def summary_options(model: str) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        model=model,
        system_prompt="You write terse, factual descriptions of source code.",
        tools=[],
        max_turns=1,
        setting_sources=[],
    )


class ClaudeSummarizer:
    """One prompt and one reply per body. `Summary.model` records what answered."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def summarize(self, symbol: orm.Symbol, body: str) -> orm.Summary:
        model = self.settings.summary_model
        answering_model = model
        async for message in query(
            prompt=summary_prompt(symbol, body), options=summary_options(model)
        ):
            match message:
                case AssistantMessage(model=answering_model):
                    pass
                case ResultMessage(is_error=False, result=str(text)):
                    return orm.Summary(
                        body_hash=symbol.body_hash, text=text, model=answering_model
                    )
                case ResultMessage(subtype=subtype, errors=errors):
                    raise SummaryFailedError(
                        symbol.qualified_name, f"{subtype} {errors or ''}".strip()
                    )
                case _:
                    pass
        raise SummaryFailedError(symbol.qualified_name, "stream ended without a result")


async def symbols_missing_summaries(
    session: AsyncSession, snapshot: orm.Snapshot
) -> Sequence[orm.Symbol]:
    """One symbol per body hash in source order. Equal bodies share one Summary row."""
    described = select(orm.Summary.body_hash)
    statement = (
        select(orm.Symbol)
        .join(orm.File)
        .options(selectinload(orm.Symbol.file))
        .where(orm.File.snapshot_id == snapshot.id)
        .where(orm.Symbol.kind.in_(summarizable_kinds()))
        .where(orm.Symbol.body_hash.not_in(described))
        .order_by(orm.File.path, orm.Symbol.start_line)
    )
    by_hash = {symbol.body_hash: symbol for symbol in await session.scalars(statement)}
    return list(by_hash.values())


async def summarize_symbols(
    new_session: async_sessionmaker[AsyncSession],
    symbols: Sequence[orm.Symbol],
    repo_root: Path,
    summarizer: Summarizer,
    concurrency: int,
) -> list[SummaryFailedError]:
    """Commits each summary as it arrives so an interrupted run keeps what it paid for.
    A failed summary does not stop the others and is returned instead of saved."""
    gate = asyncio.Semaphore(concurrency)
    failures: list[SummaryFailedError] = []

    async def summarize_and_commit(symbol: orm.Symbol) -> None:
        async with gate:
            try:
                summary = await summarizer.summarize(
                    symbol, body_text(repo_root, symbol)
                )
            except SummaryFailedError as failure:
                failures.append(failure)
            else:
                async with new_session.begin() as session:
                    session.add(summary)

    async with asyncio.TaskGroup() as group:
        for symbol in symbols:
            group.create_task(summarize_and_commit(symbol))
    return failures


__all__ = [
    "ClaudeSummarizer",
    "SummariesFailedError",
    "Summarizer",
    "SummaryFailedError",
    "body_text",
    "summarize_symbols",
    "symbols_missing_summaries",
]
