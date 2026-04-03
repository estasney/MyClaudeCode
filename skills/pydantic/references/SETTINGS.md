# Settings Management

`pydantic-settings` is a **separate package** (`pip install pydantic-settings`). It provides `BaseSettings` for loading configuration from environment variables, `.env` files, secrets, and other sources.

## Basic usage

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_")

    db_host: str = "localhost"
    db_port: int = 5432
    debug: bool = False
```

When `Settings()` is instantiated, Pydantic reads `APP_DB_HOST`, `APP_DB_PORT`, `APP_DEBUG` from environment variables and coerces them to the declared types.

Unlike `BaseModel`, `BaseSettings` validates default values by default.

## Source priority

Values are resolved in descending priority (first wins):

1. Arguments passed to the constructor (`Settings(debug=True)`)
2. Environment variables
3. `.env` file values
4. Secrets directory values
5. Default values in the model

Override priority order by implementing `settings_customise_sources`:

```python
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

class Settings(BaseSettings):
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (env_settings, init_settings, dotenv_settings, file_secret_settings)
```

## SettingsConfigDict

Extends `ConfigDict` with settings-specific options:

- `env_prefix` -- prefix for all env var names (default: `""`)
- `env_file` -- path to `.env` file(s); can be a tuple for multiple files
- `env_file_encoding` -- encoding for `.env` file
- `env_nested_delimiter` -- delimiter for nested model fields in env vars (e.g., `"__"`)
- `env_nested_max_split` -- limits how many times the delimiter splits (avoids ambiguity with field names containing the delimiter)
- `env_ignore_empty` -- treat empty env vars as unset
- `env_parse_none_str` -- string value to interpret as `None`
- `case_sensitive` -- whether env var lookup is case-sensitive (default: `False`)
- `secrets_dir` -- path(s) to directory containing secret files (Docker Secrets pattern)

Environment variable names are case-insensitive by default.

## Nested models

Sub-models must inherit from `BaseModel` (not `BaseSettings`). Use `env_nested_delimiter` to populate them from flat env vars:

```python
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

class Database(BaseModel):
    host: str = "localhost"
    port: int = 5432

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__")
    db: Database = Database()
```

With `DB__HOST=prod-server` and `DB__PORT=5433`, the nested model is populated correctly.

Nested env vars take precedence over a top-level JSON env var for the same field.

Gotcha: `env_nested_max_split` is important when field names themselves contain the delimiter character. Without it, `APP_LLM_API_KEY` with delimiter `_` would split into `llm.api.key` instead of `llm.api_key`. Set `env_nested_max_split=1` to limit splitting.

## .env files

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
```

Multiple env files: `env_file=(".env", ".env.local")` -- later files override earlier ones.

Can also be passed at instantiation: `Settings(_env_file=".env.test")`.

## Docker Secrets

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(secrets_dir="/run/secrets")
    database_password: str
```

Each secret is a file in the secrets directory whose filename matches the field name (or env var name with prefix). Multiple secret directories: `secrets_dir=("/var/run", "/run/secrets")`.

## Field aliases with settings

Use `validation_alias` (not `alias`) for env var name overrides. `AliasChoices` works for accepting multiple env var names:

```python
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    db_url: str = Field(validation_alias=AliasChoices("DATABASE_URL", "DB_URL"))
```

## Custom sources

Implement `PydanticBaseSettingsSource` to load from JSON files, remote config, TOML, etc. Built-in: `JsonConfigSettingsSource`, `TomlConfigSettingsSource` (requires `tomli`).

## Testing pattern

Override settings in tests by passing values to the constructor (highest priority):

```python
def test_something():
    settings = Settings(db_host="test-db", debug=True)
```
