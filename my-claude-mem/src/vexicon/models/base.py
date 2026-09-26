import time
from dataclasses import dataclass
from typing import Annotated

from pydantic import Field, GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema, core_schema


@dataclass(frozen=True)
class ForbiddenKeys:
    keys: frozenset[str]

    def reject_forbidden(self, value: dict[str, object]) -> dict[str, object]:
        found = self.keys & value.keys()
        if found:
            raise ValueError(f"Forbidden keys: {', '.join(sorted(found))}")
        return value

    def __get_pydantic_core_schema__(
        self, source_type: object, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            self.reject_forbidden, handler(source_type)
        )

    def __get_pydantic_json_schema__(
        self, schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        json_schema = handler(schema)
        json_schema["propertyNames"] = {"not": {"enum": sorted(self.keys)}}
        return json_schema


SpaceName = Annotated[
    str,
    Field(
        min_length=3,
        max_length=63,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]*[a-zA-Z0-9]$",
        description="Space name.",
    ),
]

Readme = Annotated[
    str,
    Field(description="What the space holds and the conventions its entries follow."),
]


def current_epoch_second() -> int:
    return int(time.time())
