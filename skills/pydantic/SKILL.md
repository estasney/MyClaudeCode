---
name: pydantic
description: Guide for working with Pydantic v2 models, validation, serialization, settings, TypeAdapter, custom types, and FastAPI integration. Use when defining Pydantic models, writing validators, configuring serialization or JSON schema output, working with BaseSettings or pydantic-settings, using TypeAdapter for ad-hoc validation, building custom Pydantic types, or integrating Pydantic with FastAPI. Also trigger when the user mentions model_dump, model_validate, SkipJsonSchema, field_validator, model_validator, ConfigDict, or any Pydantic v2 API surface. Covers both official patterns and project-specific preferences.
allowed-tools:
  - Read(./*)
---

# Pydantic v2

Guidance for working with Pydantic v2 models, validation, serialization, and related tooling.

## Version Awareness

Pydantic v1 and v2 are fundamentally different libraries sharing a name. V2 rewrote the core in Rust (`pydantic-core`) and changed nearly every API surface. Before writing or reviewing Pydantic code, confirm the version in use. Key signals:

- **v2**: `model_config = ConfigDict(...)`, `model_validate()`, `model_dump()`, `field_validator`, `model_validator`
- **v1** (legacy): inner `class Config`, `.dict()`, `.json()`, `@validator`, `@root_validator`

If v1 code is encountered, flag it and propose the v2 equivalent. Do not mix idioms.

## Project Preferences

**1. PEP 585/604 annotations only.** `list[str]` not `List[str]`, `str | None` not `Optional[str]`, `dict[str, int]` not `Dict[str, int]`. No imports from `typing` for container generics or unions.

**2. ConfigDict only.** Never use an inner `class Config`. Flag v1 config patterns as migration targets.

**3. Avoid bare `dict` fields in models.** A `dict[str, Any]` field undermines the typed structure of a model. Prefer a nested model or `TypedDict`. If passthrough metadata is genuinely needed, call it out explicitly with a description.

**4. Discriminated unions use StrEnum.** Always define a `StrEnum` for the discriminator field, not bare `Literal` strings. Wrap the discriminated union type in a `TypeAdapter` for the validation entry point.

```python
from enum import StrEnum
from typing import Annotated
from pydantic import BaseModel, Discriminator, Field, TypeAdapter

class PetKind(StrEnum):
    CAT = "cat"
    DOG = "dog"

class Cat(BaseModel):
    kind: PetKind = Field(description="Pet type discriminator", examples=[PetKind.CAT])
    meow_volume: int = Field(description="Volume in decibels", examples=[40])

class Dog(BaseModel):
    kind: PetKind = Field(description="Pet type discriminator", examples=[PetKind.DOG])
    bark_pitch: float = Field(description="Pitch in Hz", examples=[200.0])

Pet = Annotated[Cat | Dog, Discriminator("kind")]
PetAdapter = TypeAdapter(Pet)
```

**5. `use_enum_values=True` on base models.** Stores the enum's value (the string) rather than the enum object, simplifying serialization. Note: this setting is deprecated in v2 (v1 carryover, no 1:1 replacement yet). Monitor for a successor. Gotcha: `Optional[Enum]` fields with a default enum value require `validate_default=True` for the setting to apply to the default.

**6. Prefer `model_validate_json` for JSON input.** Skip the intermediate `json.loads()` + `model_validate()` roundtrip. `model_validate_json` parses and validates in one pass through the Rust core.

**7. Annotated type aliases over `field_validator` for reusable logic.** When validation is about the type itself (e.g., "non-empty string", "positive int"), define it as an `Annotated` alias. Reserve `field_validator` for model-specific or cross-field logic.

**8. Every field uses `Field()` with `description` and `examples`.** No bare `name: str` or `name: str = "default"`. Every field gets `Field(description=..., examples=[...])`. This makes models self-documenting and produces richer JSON Schema / OpenAPI output.

**9. Make invalid states unrepresentable.** Model each meaningful domain state as a distinct type. If a registered user always has an email, that's a different model from a user mid-registration. Downstream code should never have to check for `None` on something the domain guarantees.

```python
class NewUser(BaseModel):
    name: str = Field(description="Desired display name", examples=["Alice"])
    email: str | None = Field(default=None, description="Optional during signup", examples=["alice@example.com"])

class RegisteredUser(BaseModel):
    id: int = Field(description="System-assigned user ID", examples=[42])
    name: str = Field(description="Display name", examples=["Alice"])
    email: str = Field(description="Verified email address", examples=["alice@example.com"])
```

**10. Prefer `frozen=True` where mutation is not needed.** Immutable by default. Mutable models are the exception.

**11. `extra="forbid"` as default posture.** Reject unexpected fields rather than silently ignoring them. Catches typos and schema drift.

**12. Separate input and output models.** Distinct Create, Update, and Response models rather than one model doing double duty.

**13. Explicit alias generators for camelCase APIs.** In FastAPI contexts with camelCase frontends, use `AliasGenerator` with explicit `validation_alias` and `serialization_alias`. Do not use the bare `alias_generator=to_camel` shorthand. Always pair with `populate_by_name=True`.

```python
from pydantic import AliasGenerator, BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=AliasGenerator(
            validation_alias=to_camel,
            serialization_alias=to_camel,
        ),
        populate_by_name=True,
    )
```

Serialization: `model.model_dump()` returns snake_case keys (internal Python use). `model.model_dump(by_alias=True)` returns camelCase keys (JSON responses). Deserialization: incoming camelCase JSON is accepted via the `validation_alias`. Python attribute access stays snake_case.

## Decision Tree

**Defining a model or its fields?**
Go to [MODELS.md](references/MODELS.md). Covers BaseModel, Field, ConfigDict, RootModel, frozen models, forward references, inheritance, ClassVar, private attributes.

**Converting between SQLAlchemy and Pydantic?**
Go to [ORM.md](references/ORM.md). Covers `from_attributes` for ORM instances, `result.mappings().all()` for Row/RowMapping results, bidirectional relationship recursion prevention, lazy loading pitfalls, common base class patterns.

**Writing validation logic?**
Go to [VALIDATORS.md](references/VALIDATORS.md). Covers `field_validator`, `model_validator`, `Annotated` validator stacking (`AfterValidator`, `BeforeValidator`, `WrapValidator`), reusable validators.

**Serializing models or controlling output shape?**
Go to [SERIALIZATION.md](references/SERIALIZATION.md). Covers `model_dump`, `model_dump_json`, include/exclude, `computed_field`, `field_serializer`, `model_serializer`, `serialize_as_any`, `PlainSerializer`.

**Controlling JSON Schema output?**
Go to [JSON-SCHEMA.md](references/JSON-SCHEMA.md). Covers `model_json_schema`, `SkipJsonSchema`, `WithJsonSchema`, `GenerateJsonSchema` subclassing, validation vs serialization mode.

**Validating/serializing arbitrary types without a full model?**
Go to [TYPE-ADAPTER.md](references/TYPE-ADAPTER.md). Covers `TypeAdapter`, when to use it vs BaseModel/RootModel, performance considerations, `dump_json` returning bytes.

**Loading config from environment variables, .env files, or secrets?**
Go to [SETTINGS.md](references/SETTINGS.md). Covers `pydantic-settings` (separate package), `BaseSettings`, `SettingsConfigDict`, env prefix, nested delimiter, source priority customization.

**Building custom types with Annotated metadata or core schema hooks?**
Go to [CUSTOM-TYPES.md](references/CUSTOM-TYPES.md). Covers `Annotated` stacking, `__get_pydantic_core_schema__`, `__get_pydantic_json_schema__`, constrained types.

**Integrating with FastAPI?**
Go to [FASTAPI.md](references/FASTAPI.md). Covers response models, request body models, Depends with settings, hiding internal fields from OpenAPI, strict vs lax behavior.
