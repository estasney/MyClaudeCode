# /// script
# requires-python = ">=3.12"
# dependencies = ["pydantic>=2"]
# ///
"""PreToolUse hook on searches in the main session that points Claude at the locate skill once per session."""

import json
import os
import sys

from pydantic import BaseModel, DirectoryPath, Field


class SearchHookInput(BaseModel):
    """Claude Code sets agent_id only when a subagent makes the call."""

    session_id: str
    agent_id: str | None = None


class PluginEnvironment(BaseModel):
    plugin_data: DirectoryPath = Field(alias="CLAUDE_PLUGIN_DATA")


def main() -> None:
    """Parallel searches race to create the session's marker file, and only the one that creates it reminds."""
    hook_input = SearchHookInput.model_validate_json(sys.stdin.read())
    if hook_input.agent_id is not None:
        return
    reminded_sessions = PluginEnvironment.model_validate(os.environ).plugin_data / "locate-reminded-sessions"
    reminded_sessions.mkdir(exist_ok=True)
    try:
        (reminded_sessions / hook_input.session_id).touch(exist_ok=False)
    except FileExistsError:
        return
    print(
        json.dumps(
            {
                "systemMessage": "Reminded Claude to use the locate skill for searches",
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": "To find where code is defined or used, invoke the my-claude-code:locate skill instead of Grep, Glob, or grep.",
                },
            }
        )
    )


if __name__ == "__main__":
    main()
