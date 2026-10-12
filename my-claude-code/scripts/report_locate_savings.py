# /// script
# requires-python = ">=3.12"
# dependencies = ["pydantic>=2"]
# ///
"""PostToolUse hook on the locate skill that shows the user what its search saved against the calling model searching in the main session, and logs the run."""

import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, assert_never

from pydantic import BaseModel, DirectoryPath, Field


class ForkedSkillResponse(BaseModel):
    agent_id: str = Field(alias="agentId")
    result: str


class SkillCall(BaseModel):
    skill: str


class SkillHookInput(BaseModel):
    """A hook's if field cannot match a Skill call by skill name, so the script picks out locate calls itself."""

    tool_input: SkillCall


class LocateHookInput(BaseModel):
    transcript_path: Path
    tool_response: ForkedSkillResponse


class PluginEnvironment(BaseModel):
    plugin_data: DirectoryPath = Field(alias="CLAUDE_PLUGIN_DATA")


class CacheCreation(BaseModel):
    ephemeral_5m_input_tokens: int
    ephemeral_1h_input_tokens: int


class Usage(BaseModel):
    input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int
    cache_creation: CacheCreation


class ContentBlock(BaseModel):
    type: str


class AssistantMessage(BaseModel):
    id: str
    model: str
    usage: Usage
    content: list[ContentBlock]


class AssistantEntry(BaseModel):
    type: Literal["assistant"]
    message: AssistantMessage


class Tokens(BaseModel):
    input: int
    cache_write: int
    cache_read: int
    output: int


class LocateRun(BaseModel):
    """Cost and savings are in dollars. The two savings bound how long the search output would have stayed in the main context."""

    at: datetime
    locate_model: str
    calling_model: str
    calling_context_tokens: int
    tool_calls: int
    tokens: Tokens
    cost: float
    savings_if_session_ends: float
    savings_at_200k: float


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


def assistant_messages(transcript: str) -> list[AssistantMessage]:
    """Claude Code writes one line per content block, each repeating its response's id and usage so far."""
    return [
        AssistantEntry.model_validate(entry).message
        for entry in map(json.loads, transcript.splitlines())
        if entry.get("type") == "assistant" and entry["message"]["model"] != "<synthetic>"
    ]


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


def locate_run(
    agent_messages: list[AssistantMessage],
    session_messages: list[AssistantMessage],
    located_text: str,
    at: datetime,
) -> LocateRun | SavingsUnknown:
    """Compare locate against the calling model making the agent's calls itself in the main session.

    The calling model's first call is the one that invoked locate and its last call answers, as the turn after locate's
    ranges are read does, so both cancel. Locate adds a turn that emits the reads, with its output left out.
    The skill result and the code in its ranges count as four characters per token. Search output left in the main
    context is read again by every later call, and the session's own growth per call projects how many calls remain
    before the context reaches 200K tokens. Only the last line of each response holds its final usage.
    """
    responses = list({message.id: message for message in agent_messages}.values())
    if not responses:
        return SavingsUnknown(reason="the agent transcript holds no usage yet")
    if not session_messages:
        return SavingsUnknown(reason="the session transcript names no model")
    agent_model = responses[-1].model
    agent_cost = priced_at(responses, agent_model)
    if agent_cost is None:
        return SavingsUnknown(reason=f"no prices for {agent_model}")
    calling = session_messages[-1]
    usage = calling.usage
    context = usage.input_tokens + usage.cache_creation_input_tokens + usage.cache_read_input_tokens
    rates = rates_for(calling.model, context)
    if rates is None:
        return SavingsUnknown(reason=f"no prices for {calling.model}")
    first = session_messages[0].usage
    session_growth = context - first.input_tokens - first.cache_creation_input_tokens - first.cache_read_input_tokens
    session_calls = len({message.id for message in session_messages})
    if session_calls < 2 or session_growth <= 0:
        return SavingsUnknown(reason="the session has no growth per call to project from")
    write_rate = rates.input * (2 if usage.cache_creation.ephemeral_1h_input_tokens else 1.25)

    def calling_model_cost(read: int, write: int, output: int) -> float:
        return (read * rates.cache_read + write * write_rate + output * rates.output) / 1_000_000

    agent_first = responses[0].usage
    agent_start = agent_first.input_tokens + agent_first.cache_creation_input_tokens + agent_first.cache_read_input_tokens
    searching = sum(
        calling_model_cost(
            read=context + response.usage.cache_read_input_tokens - agent_start,
            write=response.usage.input_tokens + response.usage.cache_creation_input_tokens,
            output=response.usage.output_tokens if response is not responses[-1] else 0,
        )
        for response in responses[1:]
    )
    located = len(located_text) // 4
    reading = calling_model_cost(read=context, write=located, output=0) + calling_model_cost(
        read=context + located, write=0, output=0
    )
    agent_last = responses[-1].usage
    search_output = (
        agent_last.input_tokens + agent_last.cache_creation_input_tokens + agent_last.cache_read_input_tokens - agent_start
    )
    later_calls = max(0.0, (200_000 - context) / (session_growth / (session_calls - 1)))
    savings_if_session_ends = searching - agent_cost - reading
    return LocateRun(
        at=at,
        locate_model=agent_model,
        calling_model=calling.model,
        calling_context_tokens=context,
        tool_calls=sum(block.type == "tool_use" for message in agent_messages for block in message.content),
        tokens=Tokens(
            input=sum(response.usage.input_tokens for response in responses),
            cache_write=sum(response.usage.cache_creation_input_tokens for response in responses),
            cache_read=sum(response.usage.cache_read_input_tokens for response in responses),
            output=sum(response.usage.output_tokens for response in responses),
        ),
        cost=agent_cost,
        savings_if_session_ends=savings_if_session_ends,
        savings_at_200k=savings_if_session_ends
        + (search_output - located) * later_calls * rates.cache_read / 1_000_000,
    )


def main() -> None:
    """Stderr from a hook that exits 0 reaches only the debug log, so the user sees a message only on success."""
    raw_input = sys.stdin.read()
    if SkillHookInput.model_validate_json(raw_input).tool_input.skill != "my-claude-code:locate":
        return
    hook_input = LocateHookInput.model_validate_json(raw_input)
    plugin_data = PluginEnvironment.model_validate(os.environ).plugin_data
    agent_transcript_path = (
        hook_input.transcript_path.with_suffix("")
        / "subagents"
        / f"agent-{hook_input.tool_response.agent_id}.jsonl"
    )
    result = hook_input.tool_response.result
    ranges = re.finditer(r"^(.+):(\d+)-(\d+) ", result, re.MULTILINE)
    located_text = result + "".join(
        "\n".join(Path(path).read_text(encoding="utf-8").splitlines()[int(start) - 1 : int(end)])
        for path, start, end in (match.groups() for match in ranges)
    )
    match locate_run(
        assistant_messages(agent_transcript_path.read_text(encoding="utf-8")),
        assistant_messages(hook_input.transcript_path.read_text(encoding="utf-8")),
        located_text,
        datetime.now(UTC),
    ):
        case LocateRun() as run:
            with (plugin_data / "locate-runs.jsonl").open("a", encoding="utf-8") as log:
                log.write(run.model_dump_json() + "\n")
            bounds = sorted({round(run.savings_if_session_ends, 2), round(run.savings_at_200k, 2)})
            saved = " to ".join(f"${bound:.2f}" for bound in bounds)
            print(json.dumps({"systemMessage": f"Saved {saved} using locate"}))
        case SavingsUnknown(reason=reason):
            print(f"Locate savings unknown, {reason}", file=sys.stderr)
        case unexpected:
            assert_never(unexpected)


if __name__ == "__main__":
    main()
