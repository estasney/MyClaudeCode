"""memory: the signals a user gives, and the memories derived from them.

A signal is what I did, the user's exact words, and what the words meant.
A memory is one sentence that, had it been in context, would have changed
what I did. Signals are appended as they happen and never merged. Memories
are where repeated signals collapse into one sentence.
"""

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Annotated

import typer
from sqlalchemy.orm import Session

from claude_memory.models import Memory, Polarity, Scope, Settings, Signal
from claude_memory.orm import create_schema, open_engine
from claude_memory.queries import Store

app = typer.Typer(help=__doc__, add_completion=False)


@contextmanager
def open_store() -> Generator[Store]:
    settings = Settings()  # pyright: ignore[reportCallIssue]
    settings.db.parent.mkdir(parents=True, exist_ok=True)
    engine = open_engine(settings.db)
    create_schema(engine)
    try:
        with Session(engine, expire_on_commit=False) as session, session.begin():
            yield Store(session, settings.project)
    except LookupError as error:
        raise SystemExit(str(error)) from error


@app.command()
def signal(
    words: Annotated[str, typer.Option()],
    meaning: Annotated[str, typer.Option()],
    action: Annotated[str, typer.Option()] = "",
    polarity: Annotated[Polarity, typer.Option()] = Polarity.negative,
    at: Annotated[datetime | None, typer.Option(help="ISO 8601, default now")] = None,
) -> None:
    """Record a signal."""
    draft = Signal(
        words=words,
        meaning=meaning,
        action=action,
        polarity=polarity,
        happened_at=at.astimezone() if at else datetime.now(UTC),
    )
    with open_store() as store:
        row = store.add_signal(draft)
    print(row)


@app.command()
def new(
    signal_id: Annotated[int, typer.Option("--signal")],
    text: Annotated[str, typer.Option()],
    scope: Annotated[Scope, typer.Option()] = Scope.project,
) -> None:
    """Derive a new memory from a signal."""
    draft = Memory(text=text, scope=scope)
    with open_store() as store:
        row = store.derive_memory(draft, signal_id)
    print(row)


@app.command()
def rewrite(
    signal_id: Annotated[int, typer.Option("--signal")],
    memory_id: Annotated[int, typer.Option("--memory")],
    text: Annotated[str, typer.Option()],
    scope: Annotated[Scope | None, typer.Option()] = None,
) -> None:
    """Reword an existing memory in light of a signal."""
    with open_store() as store:
        row = store.rewrite_memory(memory_id, signal_id, text, scope)
    print(row)


@app.command()
def support(
    signal_id: Annotated[int, typer.Option("--signal")],
    memory_id: Annotated[int, typer.Option("--memory")],
) -> None:
    """Record a signal as further support for an existing memory."""
    with open_store() as store:
        row = store.support_memory(memory_id, signal_id)
    print(row)


@app.command()
def search(
    query: Annotated[str, typer.Option(help="FTS5 syntax")],
    limit: Annotated[int, typer.Option()] = 5,
) -> None:
    """Rank memories against an FTS5 query."""
    with open_store() as store:
        rows = store.search(query, limit)
    for row in rows:
        print(row)


@app.command()
def load() -> None:
    """Print every memory for the project, plus the ones that apply everywhere."""
    with open_store() as store:
        rows = store.all()
    for row in rows:
        print(row)


@app.command()
def session_start(limit: Annotated[int, typer.Option()] = 20) -> None:
    """Print the top-ranked memories for the project."""
    with open_store() as store:
        rows = store.ranked(limit)
    if not rows:
        return
    print("Memories from earlier sessions, most supported first:")
    for row in rows:
        print(f"- {row.text}")


def main() -> None:
    app()
