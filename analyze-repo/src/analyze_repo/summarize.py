import asyncio
from collections.abc import Sequence
from pathlib import Path

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from analyze_repo import orm

__all__ = [
    "summarize_snapshot",
]


class SummaryFailedError(RuntimeError):
    def __init__(self, qualified_name: str, detail: str) -> None:
        super().__init__(f"summary of {qualified_name} failed: {detail}")


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


async def symbols_missing_summaries(
    session: AsyncSession, snapshot: orm.Snapshot
) -> Sequence[orm.Symbol]:
    """One symbol per body hash; equal bodies share one Summary row."""
    described = select(orm.Summary.body_hash)
    statement = (
        select(orm.Symbol)
        .join(orm.File)
        .options(selectinload(orm.Symbol.file))
        .where(orm.File.snapshot_id == snapshot.id)
        .where(orm.Symbol.kind.in_(summarizable_kinds()))
        .where(orm.Symbol.body_hash.not_in(described))
    )
    by_hash = {symbol.body_hash: symbol for symbol in await session.scalars(statement)}
    return list(by_hash.values())


async def write_summary(symbol: orm.Symbol, body: str, model: str) -> orm.Summary:
    """One prompt, one reply; `Summary.model` records what answered."""
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


async def summarize_snapshot(
    session: AsyncSession,
    snapshot: orm.Snapshot,
    repo_root: Path,
    model: str,
    concurrency: int,
) -> int:
    """Returns how many Summary rows were written."""
    gate = asyncio.Semaphore(concurrency)

    async def gated(symbol: orm.Symbol) -> orm.Summary:
        async with gate:
            return await write_summary(symbol, body_text(repo_root, symbol), model)

    symbols = await symbols_missing_summaries(session, snapshot)
    summaries = await asyncio.gather(*(gated(symbol) for symbol in symbols))
    session.add_all(summaries)
    await session.flush()
    return len(summaries)
