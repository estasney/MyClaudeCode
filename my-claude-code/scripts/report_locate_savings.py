# /// script
# requires-python = ">=3.12"
# dependencies = ["pydantic>=2"]
# ///
"""SubagentStop hook that shows the user what a locate search saved against the same tokens on the calling model."""

import json
import sys
from pathlib import Path
from typing import Literal, assert_never

from pydantic import BaseModel


class HookInput(BaseModel):
    transcript_path: Path
    agent_transcript_path: Path


class CacheCreation(BaseModel):
    ephemeral_5m_input_tokens: int
    ephemeral_1h_input_tokens: int


class Usage(BaseModel):
    input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int
    cache_creation: CacheCreation


class AssistantMessage(BaseModel):
    id: str
    model: str
    usage: Usage


class AssistantEntry(BaseModel):
    type: Literal["assistant"]
    message: AssistantMessage


class Savings(BaseModel):
    dollars: float


class SavingsUnknown(BaseModel):
    reason: str


class Rates(BaseModel):
    """Dollars per million tokens."""

    input: float
    cache_read: float
    output: float


def rates_for(model: str, prompt_tokens: int) -> Rates | None:
    match model:
        case "claude-haiku-5-5" if prompt_tokens > 100_000:
            return Rates(input=0.50, cache_read=0.05, output=2.50)
        case "claude-haiku-5-5":
            return Rates(input=0.10, cache_read=0.01, output=0.50)
        case "claude-sonnet-5-5":
            return Rates(input=2.00, cache_read=0.20, output=10.00)
        case "claude-opus-5-5":
            return Rates(input=4.00, cache_read=0.20, output=20.00)
        case "claude-fable-5-1":
            return Rates(input=10.00, cache_read=0.25, output=50.00)
        case _:
            return None


def cost(usage: Usage, rates: Rates) -> float:
    """Cache writes cost 1.25x input for the 5-minute TTL and 2x for the 1-hour TTL."""
    return (
        usage.input_tokens * rates.input
        + usage.cache_creation.ephemeral_5m_input_tokens * rates.input * 1.25
        + usage.cache_creation.ephemeral_1h_input_tokens * rates.input * 2
        + usage.cache_read_input_tokens * rates.cache_read
        + usage.output_tokens * rates.output
    ) / 1_000_000


def api_responses(transcript: str) -> list[AssistantMessage]:
    """Claude Code writes one line per content block, so only the last line of each response holds its final usage."""
    by_id: dict[str, AssistantMessage] = {}
    for line in transcript.splitlines():
        entry = json.loads(line)
        if entry.get("type") == "assistant" and entry["message"]["model"] != "<synthetic>":
            message = AssistantEntry.model_validate(entry).message
            by_id[message.id] = message
    return list(by_id.values())


def latest_model(transcript: str) -> str | None:
    for line in reversed(transcript.splitlines()):
        entry = json.loads(line)
        if entry.get("type") == "assistant" and entry["message"]["model"] != "<synthetic>":
            return entry["message"]["model"]
    return None


def priced_at(responses: list[AssistantMessage], model: str) -> float | None:
    """The cost of the responses' tokens at the model's rates, or None when the model has no prices."""
    total = 0.0
    for response in responses:
        usage = response.usage
        rates = rates_for(model, usage.input_tokens + usage.cache_creation_input_tokens + usage.cache_read_input_tokens)
        if rates is None:
            return None
        total += cost(usage, rates)
    return total


def savings(responses: list[AssistantMessage], caller_model: str | None) -> Savings | SavingsUnknown:
    if not responses:
        return SavingsUnknown(reason="the agent transcript holds no usage yet")
    if caller_model is None:
        return SavingsUnknown(reason="the session transcript names no model")
    agent_model = responses[-1].model
    actual = priced_at(responses, agent_model)
    if actual is None:
        return SavingsUnknown(reason=f"no prices for {agent_model}")
    at_caller = priced_at(responses, caller_model)
    if at_caller is None:
        return SavingsUnknown(reason=f"no prices for {caller_model}")
    return Savings(dollars=at_caller - actual)


def main() -> None:
    """Stderr from a hook that exits 0 reaches only the debug log, so the user sees a message only on success."""
    hook_input = HookInput.model_validate_json(sys.stdin.read())
    responses = api_responses(hook_input.agent_transcript_path.read_text())
    caller_model = latest_model(hook_input.transcript_path.read_text())
    match savings(responses, caller_model):
        case Savings(dollars=dollars):
            print(json.dumps({"systemMessage": f"Saved ${dollars:.4f} using locate"}))
        case SavingsUnknown(reason=reason):
            print(f"Locate savings unknown, {reason}", file=sys.stderr)
        case unexpected:
            assert_never(unexpected)


if __name__ == "__main__":
    main()
