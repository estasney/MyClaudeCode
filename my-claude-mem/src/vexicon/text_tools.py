"""Tools whose validated result is sent to the client as plain text.

A ``FunctionTool`` subclass swaps the result conversion step, the same way a
FastAPI response class swaps serialization. The decorated function keeps its
signature, dependency injection, and input schema. No output schema is
declared: the result is text content only.
"""

import json
from collections.abc import Callable, Iterable
from typing import Any, get_args, get_origin

from fastmcp.tools import ToolResult
from fastmcp.tools.function_tool import FunctionTool
from pydantic import BaseModel


def row_model(return_type: object) -> type[BaseModel]:
    if get_origin(return_type) is list:
        (item,) = get_args(return_type)
        if isinstance(item, type) and issubclass(item, BaseModel):
            return item
    raise TypeError(
        f"table_tool requires a list[BaseModel] return annotation, got {return_type!r}"
    )


def check_lines(return_type: object) -> None:
    if return_type != list[str]:
        raise TypeError(
            f"lines_tool requires a list[str] return annotation, got {return_type!r}"
        )


def record_model(return_type: object) -> type[BaseModel]:
    if isinstance(return_type, type) and issubclass(return_type, BaseModel):
        return return_type
    raise TypeError(
        f"record_tool requires a BaseModel return annotation, got {return_type!r}"
    )


def render_cell(value: object) -> str:
    match value:
        case None:
            return "-"
        case dict() | list():
            return json.dumps(value, separators=(",", ":"))
        case _:
            return str(value)


def render_table(model: type[BaseModel], rows: Iterable[BaseModel]) -> str:
    """Columns padded to their widest cell, two spaces apart, like ``docker ps``."""
    columns = list(model.model_fields)
    grid = [columns]
    for row in rows:
        dumped = row.model_dump(mode="json")
        grid.append([render_cell(dumped[column]) for column in columns])
    widths = [max(len(line[index]) for line in grid) for index in range(len(columns))]
    return "\n".join(
        "  ".join(
            cell.ljust(width) for cell, width in zip(line, widths, strict=True)
        ).rstrip()
        for line in grid
    )


def indent(text: str) -> str:
    return "\n".join(f"  {line}" if line else line for line in text.splitlines())


def render_records(records: Iterable[BaseModel]) -> str:
    return "\n\n".join(render_record(record) for record in records)


def render_record(record: BaseModel) -> str:
    """One ``field: value`` line per field; nested models and multi-line text go indented under the field name."""
    lines: list[str] = []
    for field in type(record).model_fields:
        match getattr(record, field):
            case [BaseModel(), *_] as models:
                lines.append(f"{field}:")
                lines.append(indent(render_records(models)))
            case BaseModel() as model:
                lines.append(f"{field}:")
                lines.append(indent(render_record(model)))
            case str() as text if "\n" in text:
                lines.append(f"{field}:")
                lines.append(indent(text))
            case _:
                dumped = record.model_dump(mode="json", include={field})[field]
                lines.append(f"{field}: {render_cell(dumped)}")
    return "\n".join(lines)


class TextTool(FunctionTool):
    def render(self, value: Any) -> str:
        raise NotImplementedError

    def convert_result(self, raw_value: Any) -> ToolResult:
        return ToolResult(content=self.render(raw_value))


class TableTool(TextTool):
    def render(self, value: Any) -> str:
        return render_table(row_model(self.return_type), value)


class LinesTool(TextTool):
    def render(self, value: Any) -> str:
        return "\n".join(value)


class RecordTool(TextTool):
    def render(self, value: Any) -> str:
        return render_record(value)


class RecordsTool(TextTool):
    def render(self, value: Any) -> str:
        return "\n\n".join(render_record(record) for record in value)


def table_tool(fn: Callable[..., Any]) -> FunctionTool:
    """Register-ready tool whose list[BaseModel] result is sent as a text table."""
    tool = TableTool.from_function(fn, output_schema=None)
    row_model(tool.return_type)
    return tool


def lines_tool(fn: Callable[..., Any]) -> FunctionTool:
    """Register-ready tool whose list[str] result is sent one item per line."""
    tool = LinesTool.from_function(fn, output_schema=None)
    check_lines(tool.return_type)
    return tool


def record_tool(fn: Callable[..., Any]) -> FunctionTool:
    """Register-ready tool whose BaseModel result is sent as field: value lines."""
    tool = RecordTool.from_function(fn, output_schema=None)
    record_model(tool.return_type)
    return tool


def records_tool(fn: Callable[..., Any]) -> FunctionTool:
    """Register-ready tool whose list[BaseModel] result is sent as blank-line separated records."""
    tool = RecordsTool.from_function(fn, output_schema=None)
    row_model(tool.return_type)
    return tool
