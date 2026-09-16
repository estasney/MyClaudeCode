from chromadb.api.types import Where, WhereDocument
from sqlalchemy import (
    ColumnElement,
    CompoundSelect,
    Integer,
    Select,
    Text,
    column,
    func,
    literal,
    literal_column,
    select,
    table,
    union_all,
)

from claude_memory import orm
from claude_memory.queries.filtering import where_condition, where_document_condition

type KeywordRow = tuple[int, str, str, orm.Json | None, float]

documents_fts = table("documents_fts", column("rowid", Integer))
fts_match_target = literal_column("documents_fts", type_=Text)


def collection_id_select(name: str) -> Select[tuple[int]]:
    return select(orm.Collection.id).where(orm.Collection.name == name)


def keyword_search_select(
    collection_id: int,
    expressions: list[tuple[int, str]],
    limit: int,
    where: Where | None = None,
    where_document: WhereDocument | None = None,
) -> CompoundSelect[KeywordRow]:
    """One statement over every phrase: a UNION ALL of per-phrase ranked subqueries tagged by phrase index."""
    score = func.bm25(fts_match_target).label("score")
    filters: list[ColumnElement[bool]] = [orm.Document.collection_id == collection_id]
    if where is not None:
        filters.append(where_condition(where))
    if where_document is not None:
        filters.append(where_document_condition(where_document))
    members: list[Select[KeywordRow]] = []
    for index, expression in expressions:
        ranked = (
            select(
                literal(index).label("phrase_index"),
                orm.Document.chroma_id,
                orm.Document.document,
                orm.Document.meta,
                score,
            )
            .select_from(orm.Document)
            .join(documents_fts, documents_fts.c.rowid == orm.Document.id)
            .where(fts_match_target.op("MATCH")(expression), *filters)
            .order_by(score)
            .limit(limit)
            .subquery()
        )
        members.append(select(ranked))
    return union_all(*members).order_by("phrase_index", "score")
